"""Left sidebar panel for terminal groups"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QPushButton, QInputDialog, QMenu, QMessageBox, QLabel,
                             QHBoxLayout, QFrame, QAction, QAbstractItemView, QToolButton)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QFontMetrics

class TerminalGroupPanel(QWidget):
    """Panel for managing terminal groups"""
    
    group_selected = pyqtSignal(str, int)  # group_name, tab_index
    group_renamed = pyqtSignal(str, str)  # old_name, new_name
    group_deleted = pyqtSignal(str)  # group_name
    group_added = pyqtSignal(str)  # group_name
    
    def __init__(self):
        super().__init__()
        self.current_group_name = "Terminal Group - 1"  # Track current group
        self.init_ui()
        
    def calculate_optimal_width(self):
        """Calculate optimal width based on content with 10px padding on each side"""
        max_width = 0
        
        # Measure "+ Add Group" button text
        button_font = QFont()
        button_font.setPointSize(12)
        button_font.setBold(True)
        button_metrics = QFontMetrics(button_font)
        button_text_width = button_metrics.horizontalAdvance("+ Add Group")
        button_width = button_text_width + 20  # 10px padding each side
        max_width = max(max_width, button_width)
        
        # Measure all group names in the list widget
        label_font = QFont()
        label_font.setPointSize(12)
        label_metrics = QFontMetrics(label_font)
        
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            if item:
                group_name = item.data(Qt.UserRole)
                if group_name:
                    text_width = label_metrics.horizontalAdvance(group_name)
                    # Add 10px padding each side + 25px for delete button + 10px spacing
                    total_width = text_width + 20 + 25 + 10
                    max_width = max(max_width, total_width)
        
        # Add container margins (2px each side = 4px total)
        max_width += 4
        
        # Set minimum of 100px, maximum of 200px for reasonable bounds
        optimal_width = max(100, min(max_width, 200))
        
        return int(optimal_width)
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)  # Minimal horizontal margins for compact view
        
        # Add group button
        add_btn = QPushButton("+ Add Group")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 4px;
                font-weight: bold;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_btn.clicked.connect(self.add_group)
        layout.addWidget(add_btn)
        
        # Groups list widget (replaces the layout-based approach)
        self.groups_list = QListWidget()
        self.groups_list.setDragDropMode(QAbstractItemView.InternalMove)  # Enable drag and drop
        self.groups_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.groups_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.groups_list.customContextMenuRequested.connect(self.show_context_menu_at_pos)
        self.groups_list.itemClicked.connect(self.on_item_clicked)
        self.groups_list.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Style the list widget to match previous appearance
        self.groups_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                outline: none;
                padding: 0px;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 2px;
            }
        """)
        
        layout.addWidget(self.groups_list)
        
        # Add default groups
        self.add_default_groups()
        
        # Calculate and set optimal width after adding default groups
        self.update_panel_width()
        
    def update_panel_width(self):
        """Update panel width based on current content"""
        optimal_width = self.calculate_optimal_width()
        self.setMinimumWidth(optimal_width)
        # Allow manual resizing by not setting a maximum width
        # Users can drag the splitter to resize the panel
        # Emit signal to parent to update splitter
        if self.parent():
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.parent().update() if hasattr(self.parent(), 'update') else None)
    
    def add_default_groups(self):
        """Add default terminal groups"""
        default_groups = ["Terminal Group - 1"]
        for group in default_groups:
            self.create_group_item(group)
            
    def create_group_item(self, name):
        """Create a group item in the list widget"""
        # Create a list item
        item = QListWidgetItem()
        item.setData(Qt.UserRole, name)  # Store group name in user data
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        
        # Add to list
        self.groups_list.addItem(item)
        
        # Create custom widget for the item
        item_widget = QWidget()
        item_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QWidget:hover {
                border: 1px solid #0d47a1;
                background-color: #353535;
            }
        """)
        
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(8, 5, 8, 5)
        item_layout.setSpacing(8)
        
        # Label for group name
        label = QLabel(name)
        label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
                background-color: transparent;
                border: none;
            }
        """)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Close button
        close_btn = QToolButton()
        close_btn.setText("×")
        close_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
                margin: 0px;
            }
            QToolButton:hover {
                color: #ff4444;
                background-color: rgba(255, 68, 68, 0.2);
                border-radius: 3px;
            }
        """)
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(lambda: self.delete_group_item(item))
        close_btn.setCursor(Qt.PointingHandCursor)
        
        item_layout.addWidget(label, 1)  # Give label stretch factor of 1
        item_layout.addWidget(close_btn, 0)  # No stretch for button
        
        # Set a proper size hint for the item
        item.setSizeHint(QSize(item_widget.sizeHint().width(), 32))
        self.groups_list.setItemWidget(item, item_widget)
        
        # Apply selection style
        self._update_item_selection_style(item)
        
        # Update panel width after adding new group
        self.update_panel_width()
        
        return item
    
    def _update_item_selection_style(self, item):
        """Update the visual style of an item based on selection state"""
        if not item:
            return
            
        item_widget = self.groups_list.itemWidget(item)
        if not item_widget:
            return
            
        is_selected = self.groups_list.currentItem() == item
        
        if is_selected:
            item_widget.setStyleSheet("""
                QWidget {
                    background-color: #0d47a1;
                    border: 1px solid #1976D2;
                    border-radius: 4px;
                }
            """)
        else:
            item_widget.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    border: 1px solid #555;
                    border-radius: 4px;
                }
                QWidget:hover {
                    border: 1px solid #0d47a1;
                    background-color: #353535;
                }
            """)
    
    def on_selection_changed(self):
        """Handle selection changes to update all item styles"""
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            self._update_item_selection_style(item)
    
    def on_item_clicked(self, item):
        """Handle item click - select the group"""
        if item:
            group_name = item.data(Qt.UserRole)
            if group_name:
                self.current_group_name = group_name
                index = self.groups_list.row(item)
                self.group_selected.emit(group_name, index)
    
    def show_context_menu_at_pos(self, position):
        """Show context menu for the item at position"""
        item = self.groups_list.itemAt(position)
        if item:
            global_pos = self.groups_list.mapToGlobal(position)
            self.show_group_context_menu_for_item(item, global_pos)
    
    def add_group(self):
        """Add a new terminal group"""
        name, ok = QInputDialog.getText(self, "Add Group", "Enter group name:")
        if ok and name:
            self.create_group_item(name)
            # Emit signal to notify that a group was added
            self.group_added.emit(name)
    
    def show_group_context_menu_for_item(self, item, position):
        """Show context menu for a group item"""
        menu = QMenu(self)
        
        # Add actions
        rename_action = QAction("Rename", self)
        delete_action = QAction("Delete", self)
        
        rename_action.triggered.connect(lambda: self.rename_group_item(item))
        delete_action.triggered.connect(lambda: self.delete_group_item(item))
        
        menu.addAction(rename_action)
        menu.addAction(delete_action)
        
        # Style the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
        """)
        
        menu.exec_(position)
    
    def delete_group_item(self, item):
        """Delete a terminal group item"""
        group_name = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Delete Group",
                                    f"Are you sure you want to delete '{group_name}'?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Find the index of the group being deleted
            deleted_index = self.groups_list.row(item)
            
            # Emit signal to notify that group is being deleted
            self.group_deleted.emit(group_name)
            
            # Remove the item from the list
            self.groups_list.takeItem(deleted_index)
            
            # Update panel width after deletion
            self.update_panel_width()
            
            # Select the next appropriate group
            remaining_count = self.groups_list.count()
            if remaining_count > 0:
                # If we deleted the last group, select the new last group
                # Otherwise, select the group at the same index (which is now the "next" group)
                next_index = min(deleted_index, remaining_count - 1)
                self.select_group_at_index(next_index)
    
    def rename_group_item(self, item):
        """Rename a terminal group item"""
        old_name = item.data(Qt.UserRole)
        new_name, ok = QInputDialog.getText(self, "Rename Group", 
                                           "Enter new name:", 
                                           text=old_name)
        if ok and new_name and new_name != old_name:
            item.setData(Qt.UserRole, new_name)
            
            # Update the label in the custom widget
            item_widget = self.groups_list.itemWidget(item)
            if item_widget:
                label = item_widget.findChild(QLabel)
                if label:
                    label.setText(new_name)
                
                # Update the item's size hint to accommodate new name length
                item_widget.updateGeometry()
                item.setSizeHint(QSize(item_widget.sizeHint().width(), 32))
            
            # Update panel width after rename (in case new name is longer)
            self.update_panel_width()
            
            # Emit signal to notify that group was renamed
            self.group_renamed.emit(old_name, new_name)
    
    def select_group_at_index(self, index):
        """Programmatically select a group by index"""
        if 0 <= index < self.groups_list.count():
            item = self.groups_list.item(index)
            if item:
                group_name = item.data(Qt.UserRole)
                self.current_group_name = group_name
                self.groups_list.setCurrentItem(item)
                self.group_selected.emit(group_name, index)
    
    def get_current_group_name(self):
        """Get the name of the currently selected group"""
        return self.current_group_name
    
    # ===== State Persistence Methods =====
    
    def get_all_groups(self):
        """Get all group names for state saving (in current display order)"""
        groups = []
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            if item:
                group_name = item.data(Qt.UserRole)
                if group_name:
                    groups.append(group_name)
        return groups
    
    def restore_groups(self, groups):
        """Restore groups from saved state"""
        # Clear existing groups
        self.groups_list.clear()
        
        # Restore groups from state
        if groups:
            for group_name in groups:
                self.create_group_item(group_name)
        else:
            # If no saved groups, add defaults
            self.add_default_groups()
        
        # Update panel width after restoring groups
        self.update_panel_width()
