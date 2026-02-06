"""Command Book Widget with built-in and custom commands"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTreeWidget, QTreeWidgetItem, QTabWidget,
                             QLineEdit, QTextEdit, QDialog, QDialogButtonBox,
                             QComboBox, QSplitter, QGroupBox, QRadioButton,
                             QButtonGroup, QMessageBox, QInputDialog, QMenu)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont
from core.command_library import CommandLibrary

class AddCustomCommandDialog(QDialog):
    """Dialog to add/edit custom commands"""
    
    def __init__(self, parent=None, folder_path="", name="", command="", description=""):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Command" if not name else "Edit Custom Command")
        self.setMinimumWidth(500)
        self.folder_path = folder_path
        self.init_ui(name, command, description)
    
    def init_ui(self, name, command, description):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Folder path
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Folder:"))
        self.folder_input = QLineEdit(self.folder_path)
        self.folder_input.setPlaceholderText("e.g., Work/AWS or Personal")
        folder_layout.addWidget(self.folder_input)
        layout.addLayout(folder_layout)
        
        # Command name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit(name)
        self.name_input.setPlaceholderText("e.g., SSH to Production Server")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Command
        layout.addWidget(QLabel("Command:"))
        self.command_input = QTextEdit()
        self.command_input.setPlainText(command)
        self.command_input.setPlaceholderText("e.g., ssh -i ~/.ssh/prod.pem user@server.com\n\nUse placeholders like [filename], [host], [port]")
        self.command_input.setMaximumHeight(100)
        layout.addWidget(self.command_input)
        
        # Description
        layout.addWidget(QLabel("Description (optional):"))
        self.description_input = QLineEdit(description)
        self.description_input.setPlaceholderText("Brief description of what this command does")
        layout.addWidget(self.description_input)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_data(self):
        """Get the dialog data"""
        return {
            'folder_path': self.folder_input.text().strip() or "Uncategorized",
            'name': self.name_input.text().strip(),
            'command': self.command_input.toPlainText().strip(),
            'description': self.description_input.text().strip()
        }


class CommandBookWidget(QWidget):
    """Widget for browsing and managing command library"""
    
    command_selected = pyqtSignal(str, str, str)  # command, name, cmd_id
    
    def __init__(self):
        super().__init__()
        self.library = CommandLibrary()
        self.current_mode = "direct"  # "direct" or "queue"
        self.init_ui()
        self.load_commands()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QLabel("📚 Command Book")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                background-color: #2b2b2b;
                color: #e0e0e0;
                border-radius: 4px;
            }
        """)
        layout.addWidget(header)
        
        # Execution mode selector
        mode_group = QGroupBox("Execution Mode")
        mode_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        mode_layout = QHBoxLayout()
        
        self.mode_button_group = QButtonGroup()
        self.direct_radio = QRadioButton("Insert to Terminal (Manual Execution)")
        self.direct_radio.setChecked(True)
        self.direct_radio.setStyleSheet("color: #e0e0e0;")
        self.direct_radio.setToolTip("Inserts command into terminal - you press Enter to execute")
        self.queue_radio = QRadioButton("Add to Queue (Auto Execution)")
        self.queue_radio.setStyleSheet("color: #e0e0e0;")
        self.queue_radio.setToolTip("Adds command to queue for automatic batch execution")
        
        self.mode_button_group.addButton(self.direct_radio)
        self.mode_button_group.addButton(self.queue_radio)
        
        self.direct_radio.toggled.connect(self.on_mode_changed)
        
        mode_layout.addWidget(self.direct_radio)
        mode_layout.addWidget(self.queue_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Tab widget for Standard and Custom commands
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #1e1e1e;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 8px 16px;
                border: 1px solid #555;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #3d3d3d;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #424242;
            }
        """)
        
        # Standard commands tab
        self.standard_tree = self.create_command_tree()
        self.tabs.addTab(self.standard_tree, "Standard Commands")
        
        # Custom commands tab
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Custom commands toolbar
        custom_toolbar = QHBoxLayout()
        add_cmd_btn = QPushButton("➕ Add Command")
        add_cmd_btn.clicked.connect(self.add_custom_command)
        add_cmd_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        custom_toolbar.addWidget(add_cmd_btn)
        
        add_folder_btn = QPushButton("📁 New Folder")
        add_folder_btn.clicked.connect(self.add_custom_folder)
        add_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        custom_toolbar.addWidget(add_folder_btn)
        custom_toolbar.addStretch()
        custom_layout.addLayout(custom_toolbar)
        
        self.custom_tree = self.create_command_tree()
        custom_layout.addWidget(self.custom_tree)
        
        self.tabs.addTab(custom_tab, "Custom Commands")
        
        # Recently used tab
        self.recent_tree = self.create_command_tree()
        self.tabs.addTab(self.recent_tree, "Recently Used")
        
        layout.addWidget(self.tabs)
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search commands...")
        self.search_input.textChanged.connect(self.filter_commands)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
        """)
        search_layout.addWidget(self.search_input)
        layout.insertLayout(1, search_layout)
        
        # Command preview
        preview_group = QGroupBox("Command Preview")
        preview_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        preview_layout = QVBoxLayout()
        
        # Command text
        cmd_label = QLabel("Command:")
        cmd_label.setStyleSheet("color: #999; font-size: 10px; font-weight: bold; padding: 2px;")
        preview_layout.addWidget(cmd_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText("Select a command to preview")
        self.preview_text.setMaximumHeight(80)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                padding: 8px;
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 3px;
                color: #4CAF50;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #777;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        # Description text
        desc_label = QLabel("Description:")
        desc_label.setStyleSheet("color: #999; font-size: 10px; font-weight: bold; padding: 2px; margin-top: 5px;")
        preview_layout.addWidget(desc_label)
        
        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setPlainText("")
        self.description_text.setMaximumHeight(60)
        self.description_text.setStyleSheet("""
            QTextEdit {
                padding: 6px;
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 3px;
                color: #e0e0e0;
                font-size: 11px;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #777;
            }
        """)
        preview_layout.addWidget(self.description_text)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
    
    def create_command_tree(self):
        """Create a tree widget for commands"""
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.show_context_menu)
        tree.itemClicked.connect(self.on_item_clicked)
        tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 4px;
                color: #e0e0e0;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 6px;
                border-bottom: 1px solid #2b2b2b;
            }
            QTreeWidget::item:hover {
                background-color: #2b2b2b;
            }
            QTreeWidget::item:selected {
                background-color: #0d47a1;
                color: white;
            }
        """)
        
        font = QFont()
        font.setPointSize(10)
        tree.setFont(font)
        
        return tree
    
    def load_commands(self):
        """Load all commands into trees"""
        self.load_standard_commands()
        self.load_custom_commands()
        self.load_recently_used()
    
    def load_standard_commands(self):
        """Load built-in commands"""
        self.standard_tree.clear()
        builtin = self.library.get_builtin_commands()
        
        for category, subcategories in builtin.items():
            category_item = QTreeWidgetItem([f"📁 {category}"])
            category_item.setData(0, Qt.UserRole, {'type': 'folder'})
            self.standard_tree.addTopLevelItem(category_item)
            
            for subcat, commands in subcategories.items():
                subcat_item = QTreeWidgetItem([f"📂 {subcat}"])
                subcat_item.setData(0, Qt.UserRole, {'type': 'folder'})
                category_item.addChild(subcat_item)
                
                for cmd in commands:
                    cmd_id = f"builtin_{category}_{subcat}_{cmd['name']}"
                    usage_count = self.library.usage_stats.get(cmd_id, 0)
                    
                    label = cmd['name']
                    if usage_count > 0:
                        label = f"⭐ {label} ({usage_count})"
                    
                    cmd_item = QTreeWidgetItem([label])
                    cmd_item.setData(0, Qt.UserRole, {
                        'type': 'command',
                        'id': cmd_id,
                        'name': cmd['name'],
                        'command': cmd['command'],
                        'description': cmd['description']
                    })
                    subcat_item.addChild(cmd_item)
    
    def load_custom_commands(self):
        """Load custom commands"""
        self.custom_tree.clear()
        custom = self.library.get_custom_commands()
        
        def add_to_tree(obj, parent):
            for key, value in obj.items():
                if isinstance(value, dict):
                    folder_item = QTreeWidgetItem([f"📁 {key}"])
                    folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': key})
                    if parent:
                        parent.addChild(folder_item)
                    else:
                        self.custom_tree.addTopLevelItem(folder_item)
                    add_to_tree(value, folder_item)
                elif isinstance(value, list):
                    folder_item = QTreeWidgetItem([f"📂 {key}"])
                    folder_item.setData(0, Qt.UserRole, {'type': 'folder', 'path': key})
                    if parent:
                        parent.addChild(folder_item)
                    else:
                        self.custom_tree.addTopLevelItem(folder_item)
                    
                    for cmd in value:
                        usage_count = self.library.usage_stats.get(cmd['id'], 0)
                        label = cmd['name']
                        if usage_count > 0:
                            label = f"⭐ {label} ({usage_count})"
                        
                        cmd_item = QTreeWidgetItem([label])
                        cmd_item.setData(0, Qt.UserRole, {
                            'type': 'command',
                            'id': cmd['id'],
                            'name': cmd['name'],
                            'command': cmd['command'],
                            'description': cmd.get('description', '')
                        })
                        folder_item.addChild(cmd_item)
        
        add_to_tree(custom, None)
    
    def load_recently_used(self):
        """Load recently used commands"""
        self.recent_tree.clear()
        recently_used = self.library.get_recently_used()
        
        for idx, cmd in enumerate(recently_used):
            label = f"{idx+1}. {cmd['name']} ({cmd['usage_count']} uses)"
            cmd_item = QTreeWidgetItem([label])
            cmd_item.setData(0, Qt.UserRole, {
                'type': 'command',
                'id': cmd['id'],
                'name': cmd['name'],
                'command': cmd['command'],
                'description': cmd['description'],
                'path': cmd.get('path', '')
            })
            self.recent_tree.addTopLevelItem(cmd_item)
            
            # Add path info as child
            if cmd.get('path'):
                path_item = QTreeWidgetItem([f"📍 {cmd['path']}"])
                path_item.setData(0, Qt.UserRole, {'type': 'info'})
                cmd_item.addChild(path_item)
    
    def on_mode_changed(self, checked):
        """Handle execution mode change"""
        if checked:
            self.current_mode = "direct"
        else:
            self.current_mode = "queue"
    
    def on_item_clicked(self, item, column):
        """Handle item click - show preview"""
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'command':
            self.preview_text.setPlainText(data['command'])
            description = data.get('description', 'No description available')
            self.description_text.setPlainText(description)
    
    def on_item_double_clicked(self, item, column):
        """Handle item double click - execute command"""
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'command':
            command = data['command']
            name = data['name']
            cmd_id = data['id']
            
            # Check if command has placeholders
            if '[' in command and ']' in command:
                # Need to replace placeholders
                command = self.replace_placeholders(command)
                if command is None:
                    return  # User cancelled
            
            # Track usage
            self.library.track_usage(cmd_id)
            
            # Emit signal with mode info
            self.command_selected.emit(command, name, self.current_mode)
            
            # Reload trees to update usage counts
            self.load_commands()
    
    def replace_placeholders(self, command):
        """Replace placeholders in command"""
        import re
        placeholders = re.findall(r'\[([^\]]+)\]', command)
        
        if not placeholders:
            return command
        
        result = command
        for placeholder in placeholders:
            value, ok = QInputDialog.getText(
                self,
                "Enter Value",
                f"Enter value for [{placeholder}]:",
                QLineEdit.Normal
            )
            if ok and value:
                result = result.replace(f"[{placeholder}]", value)
            else:
                return None  # User cancelled
        
        return result
    
    def show_context_menu(self, position):
        """Show context menu for items"""
        tree = self.sender()
        item = tree.itemAt(position)
        
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        
        menu = QMenu(self)
        
        if data.get('type') == 'command':
            execute_action = menu.addAction("Execute")
            execute_action.triggered.connect(lambda: self.on_item_double_clicked(item, 0))
            
            copy_action = menu.addAction("Copy Command")
            copy_action.triggered.connect(lambda: self.copy_command(data['command']))
            
            # Only show edit/delete for custom commands
            if tree == self.custom_tree and 'custom_' in data['id']:
                menu.addSeparator()
                edit_action = menu.addAction("Edit")
                edit_action.triggered.connect(lambda: self.edit_custom_command(data))
                
                delete_action = menu.addAction("Delete")
                delete_action.triggered.connect(lambda: self.delete_custom_command(data['id']))
        
        elif data.get('type') == 'folder' and tree == self.custom_tree:
            delete_folder_action = menu.addAction("Delete Folder")
            delete_folder_action.triggered.connect(lambda: self.delete_custom_folder(data.get('path', '')))
        
        menu.exec_(tree.viewport().mapToGlobal(position))
    
    def copy_command(self, command):
        """Copy command to clipboard"""
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(command)
        
    def add_custom_command(self):
        """Add a new custom command"""
        dialog = AddCustomCommandDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            if data['name'] and data['command']:
                self.library.add_custom_command(
                    data['folder_path'],
                    data['name'],
                    data['command'],
                    data['description']
                )
                self.load_custom_commands()
            else:
                QMessageBox.warning(self, "Invalid Input", "Name and Command are required!")
    
    def edit_custom_command(self, cmd_data):
        """Edit an existing custom command"""
        dialog = AddCustomCommandDialog(
            self,
            "",
            cmd_data['name'],
            cmd_data['command'],
            cmd_data.get('description', '')
        )
        if dialog.exec_():
            data = dialog.get_data()
            if data['name'] and data['command']:
                self.library.update_custom_command(
                    cmd_data['id'],
                    name=data['name'],
                    command=data['command'],
                    description=data['description']
                )
                self.load_custom_commands()
    
    def delete_custom_command(self, cmd_id):
        """Delete a custom command"""
        reply = QMessageBox.question(
            self,
            "Delete Command",
            "Are you sure you want to delete this command?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.library.delete_custom_command(cmd_id)
            self.load_custom_commands()
            self.load_recently_used()
    
    def add_custom_folder(self):
        """Add a new folder for custom commands"""
        folder_path, ok = QInputDialog.getText(
            self,
            "New Folder",
            "Enter folder path (e.g., Work/AWS or Personal):",
            QLineEdit.Normal
        )
        
        if ok and folder_path:
            self.library.create_custom_folder(folder_path)
            self.load_custom_commands()
    
    def delete_custom_folder(self, folder_path):
        """Delete a custom folder"""
        if not folder_path:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Folder",
            f"Are you sure you want to delete folder '{folder_path}' and all its contents?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.library.delete_custom_folder(folder_path)
            self.load_custom_commands()
    
    def filter_commands(self, search_text):
        """Filter commands based on search text"""
        search_text = search_text.lower()
        
        def filter_tree(tree):
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                self.filter_item(item, search_text)
        
        filter_tree(self.standard_tree)
        filter_tree(self.custom_tree)
        filter_tree(self.recent_tree)
    
    def filter_item(self, item, search_text):
        """Recursively filter tree items"""
        if not search_text:
            item.setHidden(False)
            for i in range(item.childCount()):
                self.filter_item(item.child(i), search_text)
            return True
        
        # Check if this item or any child matches
        data = item.data(0, Qt.UserRole)
        matches = False
        
        if data and data.get('type') == 'command':
            text = item.text(0).lower()
            command = data.get('command', '').lower()
            description = data.get('description', '').lower()
            matches = (search_text in text or 
                      search_text in command or 
                      search_text in description)
        
        # Check children
        child_matches = False
        for i in range(item.childCount()):
            if self.filter_item(item.child(i), search_text):
                child_matches = True
        
        # Show item if it or any child matches
        show = matches or child_matches
        item.setHidden(not show)
        
        if matches or child_matches:
            item.setExpanded(True)
        
        return show

