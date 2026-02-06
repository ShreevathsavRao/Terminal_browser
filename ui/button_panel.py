"""Right sidebar panel for buttons and command queue"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QScrollArea, QLabel, QFrame, QListWidget, 
                             QListWidgetItem, QMenu, QSplitter, QFileDialog,
                             QLineEdit, QInputDialog, QMessageBox, QDialog,
                             QDialogButtonBox, QStackedWidget, QToolButton)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QFontMetrics, QPainter, QTransform, QIcon
from ui.dialogs import AddButtonDialog, AddFileDialog
from core.command_queue import CommandQueue


class VerticalTabButton(QPushButton):
    """A button with vertical (rotated) text for tab-like appearance"""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        
    def paintEvent(self, event):
        """Custom paint to rotate text 90 degrees counter-clockwise"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        if self.isChecked():
            if "Book" in self.text():
                painter.fillRect(self.rect(), Qt.darkYellow)
            elif "Recorder" in self.text():
                painter.fillRect(self.rect(), Qt.darkGreen)
            else:
                painter.fillRect(self.rect(), self.palette().dark())
        elif self.underMouse():
            painter.fillRect(self.rect(), self.palette().midlight())
        else:
            painter.fillRect(self.rect(), self.palette().button())
        
        # Rotate and draw text
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(270)  # Rotate counter-clockwise
        
        # Set font and color
        painter.setFont(self.font())
        if self.isChecked():
            painter.setPen(Qt.white)
        else:
            painter.setPen(self.palette().buttonText().color())
        
        # Draw text centered
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        text_height = fm.height()
        painter.drawText(-text_width // 2, text_height // 4, self.text())
        
    def sizeHint(self):
        """Return size hint with swapped dimensions for vertical text"""
        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self.text())
        text_height = fm.height()
        # Swap width and height since text is rotated
        return QSize(text_height + 16, text_width + 16)


class QueueItemWidget(QWidget):
    """Custom widget for command queue items with cancel button"""
    
    cancel_clicked = pyqtSignal(int)  # Signal emitted when cancel button is clicked
    
    def __init__(self, index, name, command, status, parent=None):
        super().__init__(parent)
        self.index = index
        self.name = name
        self.command = command
        self.status = status
        
        # Set widget background
        self.setStyleSheet("""
            QueueItemWidget {
                background-color: transparent;
            }
        """)
        
        # Main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        
        # Drag handle indicator
        drag_label = QLabel("☰")
        drag_label.setStyleSheet("""
            QLabel {
                color: #888; 
                font-size: 14px;
                font-weight: bold;
            }
        """)
        drag_label.setToolTip("Drag to reorder")
        drag_label.setFixedWidth(20)
        layout.addWidget(drag_label)
        
        # Command info label
        status_color = {
            'pending': '#ffa726',
            'running': '#66bb6a',
            'completed': '#42a5f5',
            'completed (timeout)': '#7e57c2',
            'completed (forced)': '#ab47bc'
        }.get(status, '#e0e0e0')
        
        info_label = QLabel(f"<b>{index + 1}.</b> {name} <span style='color:{status_color};'>• {status}</span>")
        info_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                padding: 2px;
                font-size: 12px;
            }
        """)
        info_label.setToolTip(f"Command: {command}")
        info_label.setWordWrap(False)
        layout.addWidget(info_label, 1)  # Stretch factor of 1 to take remaining space
        
        # Cancel button (only show for pending commands)
        if status == 'pending':
            cancel_btn = QPushButton("✕")
            cancel_btn.setToolTip("Cancel this command")
            cancel_btn.setFixedSize(24, 24)
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #f44336;
                }
                QPushButton:pressed {
                    background-color: #c62828;
                }
            """)
            cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.index))
            layout.addWidget(cancel_btn)
        
        self.setLayout(layout)


class ButtonPanel(QWidget):
    """Right panel for command buttons and queue"""
    
    execute_command = pyqtSignal(str, dict, object)  # command, env_vars, terminal_widget
    insert_command_to_terminal = pyqtSignal(str)  # command (insert only, don't execute)
    buttons_changed = pyqtSignal()  # Signal when buttons are added, edited, or deleted
    queues_changed = pyqtSignal()  # Signal when any queue starts/stops (for status button update)
    
    def __init__(self):
        super().__init__()
        self.queues_per_terminal = {}  # Store queues per terminal: {terminal_widget: CommandQueue}
        self.current_terminal = None  # Track current terminal to display its queue
        self.current_group = None  # Track current group
        self.buttons_per_group = {}  # Store buttons per group: {group_name: [button_data]}
        self.files_per_group = {}  # Store files per group: {group_name: {file_name: file_path}}
        self.init_ui()
        self.setup_connections()
    
    def get_or_create_queue(self, terminal):
        """Get or create a command queue for a terminal
        
        Args:
            terminal: The terminal widget
            
        Returns:
            CommandQueue: The queue for this terminal
        """
        if terminal not in self.queues_per_terminal:
            # Create new queue for this terminal
            queue = CommandQueue(terminal_widget=terminal)
            queue.execute_command.connect(self.on_execute_command)
            queue.queue_updated.connect(self.update_queue_display)
            queue.queue_updated.connect(self.queues_changed.emit)  # Notify when queue changes
            self.queues_per_terminal[terminal] = queue
        return self.queues_per_terminal[terminal]
    
    def get_queue_for_terminal(self, terminal):
        """Get the queue for a specific terminal (returns None if doesn't exist)
        
        Args:
            terminal: The terminal widget
            
        Returns:
            CommandQueue or None: The queue for this terminal
        """
        return self.queues_per_terminal.get(terminal)
    
    def get_all_active_queues(self):
        """Get all terminals with active (running or non-empty) queues
        
        Returns:
            list: List of tuples (terminal, queue, status_dict)
        """
        active_queues = []
        for terminal, queue in self.queues_per_terminal.items():
            status = queue.get_status()
            # Include if running or has items in queue
            if status['is_running'] or status['queue_size'] > 0:
                active_queues.append((terminal, queue, status))
        return active_queues
    
    def set_current_terminal(self, terminal):
        """Set the current terminal and refresh queue display
        
        Args:
            terminal: The terminal widget to set as current
        """
        self.current_terminal = terminal
        self.update_queue_display()
        self.update_queue_button_states()  # Update button states for this terminal's queue
    
    def remove_terminal_queue(self, terminal):
        """Remove and cleanup queue for a terminal (when tab is closed)
        
        Args:
            terminal: The terminal widget being closed
        """
        if terminal in self.queues_per_terminal:
            queue = self.queues_per_terminal[terminal]
            queue.stop()
            queue.clear()
            # Disconnect signals
            try:
                queue.execute_command.disconnect()
                queue.queue_updated.disconnect()
            except:
                pass
            del self.queues_per_terminal[terminal]
            self.queues_changed.emit()  # Notify that queue status changed
    
    def update_queue_button_states(self):
        """Update queue control button states based on current terminal's queue status"""
        if not self.current_terminal:
            # No terminal selected - default to stopped state
            self.start_queue_btn.setEnabled(True)
            self.stop_queue_btn.setEnabled(False)
            self.skip_current_btn.setEnabled(False)
            return
        
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            # Queue doesn't exist yet - default to stopped state
            self.start_queue_btn.setEnabled(True)
            self.stop_queue_btn.setEnabled(False)
            self.skip_current_btn.setEnabled(False)
            return
        
        # Update buttons based on queue's running state
        if queue.is_running:
            self.start_queue_btn.setEnabled(False)
            self.stop_queue_btn.setEnabled(True)
            self.skip_current_btn.setEnabled(True)
        else:
            self.start_queue_btn.setEnabled(True)
            self.stop_queue_btn.setEnabled(False)
            self.skip_current_btn.setEnabled(False)
        
    def calculate_optimal_width(self):
        """Calculate optimal width based on content with 10px padding on each side"""
        max_content_width = 0
        
        # Create font metrics for measurements
        header_font = QFont()
        header_font.setPointSize(10)  # Reduced from 12 to match macOS
        header_font.setBold(True)
        header_metrics = QFontMetrics(header_font)
        
        button_font = QFont()
        button_font.setPointSize(9)  # Reduced from 11 to match macOS
        button_metrics = QFontMetrics(button_font)
        
        # Calculate vertical tab bar width (left sidebar)
        # For vertical tabs, width = text height (since rotated) + padding
        tab_bar_width = header_metrics.height() + 16
        
        # Measure section labels
        section_labels = ["Command Queue", "Attached Files"]
        for text in section_labels:
            text_width = header_metrics.horizontalAdvance(text)
            width = text_width + 20  # 10px padding each side
            max_content_width = max(max_content_width, width)
        
        # Measure "+ Add Button" button (full width)
        add_button_text = button_metrics.horizontalAdvance("+ Add Button")
        add_button_width = add_button_text + 20 + 16  # text + padding + button padding
        max_content_width = max(max_content_width, add_button_width)
        
        # Measure "+ Add File" button (full width)
        add_file_text = button_metrics.horizontalAdvance("+ Add File")
        add_file_width = add_file_text + 20 + 16
        max_content_width = max(max_content_width, add_file_width)
        
        # Measure each command button row in current group
        # Each row has: [Main Button (flex)] [Edit: 50px] [Delete: 60px] in HBoxLayout
        if self.current_group and self.current_group in self.buttons_per_group:
            for button_data in self.buttons_per_group[self.current_group]:
                button_text = button_data.get('name', '')
                text_width = button_metrics.horizontalAdvance(button_text)
                is_default = button_data.get('is_default', False)
                
                # Main button: text + 10px padding each side + 16px internal padding
                main_button_width = text_width + 20 + 16
                
                # Row width = main button + Edit (50px) + Delete (60px) + spacing between buttons
                if not is_default:
                    row_width = main_button_width + 50 + 60 + 10  # 10px spacing in HBoxLayout
                else:
                    row_width = main_button_width
                
                max_content_width = max(max_content_width, row_width)
        
        # Total width = tab bar + content area + margins + scrollbar
        total_width = tab_bar_width + max_content_width + 10 + 20  # 10px content margin + 20px scrollbar
        
        # Return calculated width
        return int(total_width)
        
        return int(optimal_width)
        
    def update_panel_width(self):
        """Update panel width based on current content"""
        optimal_width = self.calculate_optimal_width()
        self.setMinimumWidth(optimal_width)
        # Allow manual resizing by not setting a maximum width
        # Users can drag the splitter to resize the panel
        # Notify parent to update
        if self.parent():
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.parent().update() if hasattr(self.parent(), 'update') else None)
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)  # No horizontal margins to sit flush against minimap
        
        # Create splitter for button area and queue area
        splitter = QSplitter(Qt.Vertical)
        
        # Button Area (top)
        button_area = self.create_button_area()
        splitter.addWidget(button_area)
        
        # Queue Area (bottom)
        queue_area = self.create_queue_area()
        splitter.addWidget(queue_area)
        
        splitter.setSizes([400, 200])
        
        layout.addWidget(splitter)
        
    def create_button_area(self):
        """Create the button management area"""
        container = QWidget()
        # Use horizontal layout to put content on left, vertical tabs on right
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left side: Content area with stacked widget
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create stacked widget to switch between views
        self.button_stack = QStackedWidget()
        self.button_stack = QStackedWidget()
        
        # Page 0: Button Management
        button_mgmt_widget = QWidget()
        button_mgmt_layout = QVBoxLayout(button_mgmt_widget)
        button_mgmt_layout.setContentsMargins(0, 5, 0, 0)
        
        # Add button toolbar
        button_toolbar = QHBoxLayout()
        
        add_btn = QPushButton("+ Add Button")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        add_btn.clicked.connect(self.add_button)
        button_toolbar.addWidget(add_btn)
        
        button_mgmt_layout.addLayout(button_toolbar)
        
        # Scroll area for buttons
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #555;
                background-color: #1e1e1e;
                border-radius: 4px;
            }
        """)
        
        self.button_container = QWidget()
        self.button_layout = QVBoxLayout(self.button_container)
        self.button_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.button_container)
        button_mgmt_layout.addWidget(scroll)
        
        # Add button management page to stack
        self.button_stack.addWidget(button_mgmt_widget)
        
        # Page 1: Command Book (inline)
        from ui.command_book_widget import CommandBookWidget
        self.command_book_widget = CommandBookWidget()
        self.command_book_widget.command_selected.connect(self.handle_command_book_selection_inline)
        self.button_stack.addWidget(self.command_book_widget)
        
        # Page 2: Session Recorder (inline)
        from ui.session_recorder_widget import SessionRecorderWidget
        self.session_recorder_widget = SessionRecorderWidget()
        self.session_recorder_widget.command_executed.connect(self.handle_session_recorder_command)
        self.button_stack.addWidget(self.session_recorder_widget)
        
        # Page 3: Attached Files
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(5, 5, 5, 5)
        
        # File attachments section header
        files_header = QLabel("Attached Files")
        files_header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                color: #e0e0e0;
                background-color: #2b2b2b;
                border-radius: 3px;
            }
        """)
        files_layout.addWidget(files_header)
        
        # Add file button
        add_file_btn = QPushButton("+ Add File")
        add_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        add_file_btn.clicked.connect(self.add_file)
        files_layout.addWidget(add_file_btn)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                color: #e0e0e0;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:hover {
                background-color: #424242;
            }
        """)
        files_layout.addWidget(self.file_list)
        
        self.button_stack.addWidget(files_widget)
        
        # Add stack to main layout
        layout.addWidget(self.button_stack)
        
        # Add content area to main horizontal layout (left side)
        main_layout.addWidget(content_widget)
        
        # Right side: Vertical tab buttons
        tab_bar_widget = QWidget()
        tab_bar_widget.setStyleSheet("background-color: #1e1e1e;")
        header_layout = QVBoxLayout(tab_bar_widget)
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setAlignment(Qt.AlignTop)
        
        # Command Buttons tab with vertical text
        self.buttons_tab_btn = VerticalTabButton("Commands")
        self.buttons_tab_btn.setChecked(True)
        self.buttons_tab_btn.clicked.connect(lambda: self.switch_button_view(0))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.buttons_tab_btn.setFont(font)
        header_layout.addWidget(self.buttons_tab_btn)
        
        # Command Book toggle button with vertical text
        self.command_book_tab_btn = VerticalTabButton("📚 Book")
        self.command_book_tab_btn.clicked.connect(lambda: self.switch_button_view(1))
        self.command_book_tab_btn.setFont(font)
        header_layout.addWidget(self.command_book_tab_btn)
        
        # Session Recorder toggle button with vertical text
        self.session_recorder_tab_btn = VerticalTabButton("🎬 Record")
        self.session_recorder_tab_btn.clicked.connect(lambda: self.switch_button_view(2))
        self.session_recorder_tab_btn.setFont(font)
        header_layout.addWidget(self.session_recorder_tab_btn)
        
        # Search button with vertical text
        search_btn = VerticalTabButton("🔍 Search")
        search_btn.setToolTip("Search Commands")
        search_btn.clicked.connect(self.go_to_search)
        search_btn.setFont(font)
        header_layout.addWidget(search_btn)
        
        # Add stretch to push buttons to top
        header_layout.addStretch()
        
        # Attached Files button with vertical text (at bottom)
        self.files_tab_btn = VerticalTabButton("📎 Files")
        self.files_tab_btn.setToolTip("Attached Files")
        self.files_tab_btn.clicked.connect(lambda: self.switch_button_view(3))
        self.files_tab_btn.setFont(font)
        header_layout.addWidget(self.files_tab_btn)
        
        main_layout.addWidget(tab_bar_widget)
        
        return container
    
    def create_queue_area(self):
        """Create the command queue area"""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        # Header
        header = QLabel("Command Queue")
        header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                background-color: #2b2b2b;
                color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        layout.addWidget(header)
        
        # Queue list with context menu and drag-drop
        self.queue_list = QListWidget()
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.show_queue_context_menu)
        self.queue_list.setDragDropMode(QListWidget.InternalMove)  # Enable drag and drop
        self.queue_list.setDefaultDropAction(Qt.MoveAction)
        self.queue_list.model().rowsMoved.connect(self.on_queue_reordered)  # Handle reordering
        self.queue_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                color: #e0e0e0;
                outline: none;
            }
            QListWidget::item {
                padding: 0px;
                border-bottom: 1px solid #444;
                background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: #3d3d3d;
            }
            QListWidget::item:hover {
                background-color: #353535;
            }
        """)
        layout.addWidget(self.queue_list)
        
        # Queue control buttons
        button_layout = QHBoxLayout()
        
        self.start_queue_btn = QPushButton("▶ Start")
        self.start_queue_btn.clicked.connect(self.start_queue)
        
        self.stop_queue_btn = QPushButton("⏸ Stop")
        self.stop_queue_btn.clicked.connect(self.stop_queue)
        self.stop_queue_btn.setEnabled(False)
        
        self.skip_current_btn = QPushButton("⏭ Skip")
        self.skip_current_btn.setToolTip("Skip current running command and continue with next")
        self.skip_current_btn.clicked.connect(self.skip_current_command)
        self.skip_current_btn.setEnabled(False)
        
        kill_queue_btn = QPushButton("🗑 Clear")
        kill_queue_btn.clicked.connect(self.kill_queue)
        
        for btn in [self.start_queue_btn, self.stop_queue_btn, self.skip_current_btn, kill_queue_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #424242;
                    color: white;
                    border: none;
                    padding: 6px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #616161;
                }
                QPushButton:disabled {
                    background-color: #2b2b2b;
                    color: #666;
                }
            """)
            button_layout.addWidget(btn)
        
        layout.addLayout(button_layout)
        
        return container
    
    def create_button_widget(self, name, command, description="", is_default=False):
        """Create a button widget"""
        button_frame = QFrame()
        button_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                margin: 2px;
            }
            QFrame:hover {
                border: 1px solid #0d47a1;
            }
        """)
        
        layout = QHBoxLayout(button_frame)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Store button properties on the frame for later retrieval
        button_frame.setProperty('name', name)
        button_frame.setProperty('command', command)
        button_frame.setProperty('description', description)
        button_frame.setProperty('is_default', is_default)
        
        # Execute button
        exec_btn = QPushButton(name)
        exec_btn.setMinimumHeight(28)  # Reduced from 35 to match macOS
        exec_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
                text-align: left;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        exec_btn.clicked.connect(lambda: self.queue_command(command, name))
        layout.addWidget(exec_btn, stretch=1)
        
        # Edit button
        if not is_default:
            edit_btn = QPushButton("Edit")
            edit_btn.setMaximumWidth(50)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            edit_btn.clicked.connect(lambda checked, bf=button_frame: self.edit_button(bf))
            layout.addWidget(edit_btn)
        
        # Delete button
        if not is_default:
            delete_btn = QPushButton("Delete")
            delete_btn.setMaximumWidth(60)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            delete_btn.clicked.connect(lambda: self.delete_button(button_frame))
            layout.addWidget(delete_btn)
        
        self.button_layout.addWidget(button_frame)
    
    def add_button(self):
        """Show dialog to add a new button"""
        if not self.current_group:
            return
        
        dialog = AddButtonDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            self.create_button_widget(data['name'], data['command'], data['description'])
            
            # Save current group state to keep storage in sync with display
            self.save_current_group_state()
            
            # Update panel width after adding button
            self.update_panel_width()
            
            # Emit signal to trigger state save
            self.buttons_changed.emit()
    
    def edit_button(self, button_frame):
        """Edit an existing button"""
        # Get current values from button_frame properties
        name = button_frame.property('name')
        command = button_frame.property('command')
        description = button_frame.property('description') or ''
        
        dialog = AddButtonDialog(self, name, command, description)
        if dialog.exec_():
            data = dialog.get_data()
            
            # Update button frame properties
            button_frame.setProperty("command", data['command'])
            button_frame.setProperty("name", data['name'])
            button_frame.setProperty("description", data['description'])
            
            # Update the execute button text (first QPushButton child)
            buttons = button_frame.findChildren(QPushButton)
            if buttons:
                exec_btn = buttons[0]  # First button is the execute button
                exec_btn.setText(data['name'])
                # Update the lambda to use new command and name
                exec_btn.disconnect()
                exec_btn.clicked.connect(lambda: self.queue_command(data['command'], data['name']))
            
            # Save current group state to keep storage in sync with display
            self.save_current_group_state()
            
            # Update panel width after editing button (in case name changed)
            self.update_panel_width()
            
            # Emit signal to trigger state save
            self.buttons_changed.emit()
    
    def delete_button(self, button_frame):
        """Delete a button"""
        # Remove from display
        self.button_layout.removeWidget(button_frame)
        button_frame.deleteLater()
        
        # Save current group state to keep storage in sync with display
        # (this will rebuild the storage from the current display state)
        self.save_current_group_state()
        
        # Update panel width after deleting button
        self.update_panel_width()
        
        # Emit signal to trigger state save
        self.buttons_changed.emit()
    
    def queue_command(self, command, name):
        """Add command to current terminal's queue"""
        if not self.current_terminal:
            return
        env_vars = self.get_env_vars_from_files()
        queue = self.get_or_create_queue(self.current_terminal)
        queue.add_command(command, name, env_vars)
        self.update_queue_display()
    
    def get_env_vars_from_files(self):
        """Get environment variables from attached files"""
        env_vars = {}
        if self.current_group and self.current_group in self.files_per_group:
            for name, path in self.files_per_group[self.current_group].items():
                # For PEM files, set SSH key path
                if path.endswith('.pem'):
                    env_vars['SSH_KEY'] = path
                # Add more file type handling as needed
        return env_vars
    
    def update_queue_display(self):
        """Update the queue display with custom widgets for current terminal"""
        self.queue_list.clear()
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        for idx, item in enumerate(queue.get_queue()):
            # Create custom widget for this queue item
            widget = QueueItemWidget(
                idx, 
                item['name'], 
                item['command'], 
                item['status']
            )
            widget.cancel_clicked.connect(self.on_cancel_queue_item)
            
            # Create list item and set the custom widget
            list_item = QListWidgetItem(self.queue_list)
            list_item.setSizeHint(QSize(self.queue_list.width() - 20, 40))  # Set fixed height
            self.queue_list.addItem(list_item)
            self.queue_list.setItemWidget(list_item, widget)
    
    def on_cancel_queue_item(self, index):
        """Handle cancel button click on a queue item"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        # Adjust index if current command is running
        adjusted_index = index
        if queue.current_command:
            adjusted_index = index - 1
        
        if adjusted_index >= 0:
            queue.remove_command(adjusted_index)
    
    def on_queue_reordered(self, parent, start, end, destination, row):
        """Handle queue reordering via drag and drop"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        # Adjust indices if current command is running
        offset = 1 if queue.current_command else 0
        
        # Calculate actual indices in the queue (excluding current command)
        from_index = start - offset
        to_index = row - offset
        
        # Adjust to_index if dragging down
        if to_index > from_index:
            to_index -= 1
        
        # Update the command queue
        if from_index >= 0 and to_index >= 0:
            queue.move_command(from_index, to_index)

    
    def start_queue(self):
        """Start processing the current terminal's queue"""
        if not self.current_terminal:
            return
        queue = self.get_or_create_queue(self.current_terminal)
        queue.start()
        self.update_queue_button_states()  # Update button states
        self.queues_changed.emit()
    
    def stop_queue(self):
        """Stop processing the current terminal's queue"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        queue.stop()
        self.update_queue_button_states()  # Update button states
        self.queues_changed.emit()
    
    def skip_current_command(self):
        """Skip the current running command and continue with next"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if queue and queue.force_complete_current():
            self.update_queue_display()
    
    def kill_queue(self):
        """Clear all commands from current terminal's queue"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if queue:
            queue.clear()
            self.update_queue_display()
            self.update_queue_button_states()  # Update button states after clearing
            self.queues_changed.emit()
    
    def add_file(self):
        """Add a file attachment"""
        if not self.current_group:
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select File", 
            "", 
            "All Files (*);;PEM Files (*.pem);;Key Files (*.key)"
        )
        
        if file_path:
            file_name = file_path.split('/')[-1]
            
            # Initialize group files if needed
            if self.current_group not in self.files_per_group:
                self.files_per_group[self.current_group] = {}
            
            # Add to current group
            self.files_per_group[self.current_group][file_name] = file_path
            self.file_list.addItem(file_name)
    
    def show_file_context_menu(self, position):
        """Show context menu for files"""
        item = self.file_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        delete_action = menu.addAction("Remove")
        
        action = menu.exec_(self.file_list.mapToGlobal(position))
        
        if action == delete_action:
            file_name = item.text()
            # Remove from current group's storage
            if self.current_group and self.current_group in self.files_per_group:
                if file_name in self.files_per_group[self.current_group]:
                    del self.files_per_group[self.current_group][file_name]
            # Remove from display
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
    
    def setup_connections(self):
        """Setup signal connections"""
        # Queue connections are now set up per-terminal in get_or_create_queue()
        pass
    
    def on_execute_command(self, command, env_vars, terminal_widget):
        """Handle command execution from queue"""
        self.execute_command.emit(command, env_vars, terminal_widget)
    
    def switch_button_view(self, index):
        """Switch between button management, command book, session recorder, and files views"""
        self.button_stack.setCurrentIndex(index)
        
        # Update button states
        self.buttons_tab_btn.setChecked(index == 0)
        self.command_book_tab_btn.setChecked(index == 1)
        self.session_recorder_tab_btn.setChecked(index == 2)
        self.files_tab_btn.setChecked(index == 3)
    
    def go_to_search(self):
        """Switch to Command Book and focus search box"""
        # Switch to Command Book view
        self.switch_button_view(1)
        
        # Focus the search input in the command book widget
        if hasattr(self.command_book_widget, 'search_input'):
            self.command_book_widget.search_input.setFocus()
            self.command_book_widget.search_input.selectAll()
    
    def handle_command_book_selection_inline(self, command, name, mode):
        """Handle command selection from inline command book"""
        if mode == "direct":
            # Insert command to terminal (user will execute manually)
            self.insert_command_to_terminal.emit(command)
        else:
            # Add to current terminal's queue
            if not self.current_terminal:
                return
            env_vars = self.get_env_vars_from_files()
            queue = self.get_or_create_queue(self.current_terminal)
            queue.add_command(command, name, env_vars)
            self.update_queue_display()
    
    def handle_session_recorder_command(self, command):
        """Handle command execution from session recorder"""
        env_vars = self.get_env_vars_from_files()
        self.execute_command.emit(command, env_vars, self.current_terminal)
    
    def show_queue_context_menu(self, position):
        """Show context menu for queue items"""
        item = self.queue_list.itemAt(position)
        if not item:
            return
        
        row = self.queue_list.row(item)
        
        menu = QMenu()
        
        edit_action = menu.addAction("✏️ Edit Command")
        edit_action.triggered.connect(lambda: self.edit_queue_command(row))
        
        menu.addSeparator()
        
        move_up_action = menu.addAction("⬆️ Move Up")
        move_up_action.triggered.connect(lambda: self.move_queue_command(row, row - 1))
        move_up_action.setEnabled(row > 0)
        
        move_down_action = menu.addAction("⬇️ Move Down")
        move_down_action.triggered.connect(lambda: self.move_queue_command(row, row + 1))
        move_down_action.setEnabled(row < self.queue_list.count() - 1)
        
        menu.addSeparator()
        
        remove_action = menu.addAction("🗑️ Remove")
        remove_action.triggered.connect(lambda: self.remove_queue_command(row))
        
        menu.exec_(self.queue_list.mapToGlobal(position))
    
    def edit_queue_command(self, index):
        """Edit a command in the queue"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        queue_items = queue.get_queue()
        if 0 <= index < len(queue_items):
            item = queue_items[index]
            
            # Show edit dialog
            new_command, ok = QInputDialog.getText(
                self,
                "Edit Command",
                f"Edit command for '{item['name']}':",
                QLineEdit.Normal,
                item['command']
            )
            
            if ok and new_command:
                # Adjust index if current command is running
                adjusted_index = index
                if queue.current_command:
                    adjusted_index = index - 1
                
                if adjusted_index >= 0:
                    queue.edit_command(adjusted_index, new_command)
    
    def remove_queue_command(self, index):
        """Remove a command from the queue"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        reply = QMessageBox.question(
            self,
            "Remove Command",
            "Are you sure you want to remove this command from the queue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Adjust index if current command is running
            adjusted_index = index
            if queue.current_command:
                adjusted_index = index - 1
            
            if adjusted_index >= 0:
                queue.remove_command(adjusted_index)
    
    def move_queue_command(self, from_index, to_index):
        """Move a command in the queue"""
        if not self.current_terminal:
            return
        queue = self.get_queue_for_terminal(self.current_terminal)
        if not queue:
            return
        # Adjust indices if current command is running
        if queue.current_command:
            from_index -= 1
            to_index -= 1
        
        if from_index >= 0 and to_index >= 0:
            queue.move_command(from_index, to_index)
    
    # ===== State Persistence Methods =====
    
    def load_group_buttons(self, group_name):
        """Load buttons for a specific group"""
        self.current_group = group_name
        
        # Clear current buttons and files
        self.clear_all_buttons()
        self.file_list.clear()
        
        # Initialize group storage if needed
        if group_name not in self.buttons_per_group:
            self.buttons_per_group[group_name] = []
            self.add_default_buttons_for_group(group_name)
        
        if group_name not in self.files_per_group:
            self.files_per_group[group_name] = {}
        
        # Load buttons for this group
        for button_data in self.buttons_per_group[group_name]:
            self.create_button_widget(
                button_data['name'],
                button_data['command'],
                button_data.get('description', ''),
                button_data.get('is_default', False)
            )
        
        # Load files for this group
        for file_name, file_path in self.files_per_group[group_name].items():
            self.file_list.addItem(file_name)
        
        # Update panel width after loading buttons
        self.update_panel_width()
    
    def add_default_buttons_for_group(self, group_name):
        """Add default buttons for a new group"""
        default_buttons = [
            {"name": "Clear", "command": "clear", "description": "Clear terminal screen", "is_default": True},
            {"name": "List Files", "command": "ls -la", "description": "List all files", "is_default": True},
            {"name": "Current Dir", "command": "pwd", "description": "Print working directory", "is_default": True},
        ]
        self.buttons_per_group[group_name] = default_buttons
    
    def clear_all_buttons(self):
        """Remove all button widgets from display"""
        while self.button_layout.count():
            child = self.button_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def save_current_group_state(self):
        """Save the current displayed buttons back to storage"""
        if not self.current_group:
            return
        
        buttons = []
        for i in range(self.button_layout.count()):
            widget = self.button_layout.itemAt(i).widget()
            if widget and isinstance(widget, QFrame):
                buttons.append({
                    'name': widget.property('name'),
                    'command': widget.property('command'),
                    'description': widget.property('description') or '',
                    'is_default': widget.property('is_default') or False
                })
        
        # Update storage
        self.buttons_per_group[self.current_group] = buttons
    
    def get_all_buttons_by_group(self):
        """Get all buttons organized by group for state saving"""
        # Save current group state first
        self.save_current_group_state()
        return self.buttons_per_group.copy()
    
    def get_all_files_by_group(self):
        """Get all files organized by group for state saving"""
        return self.files_per_group.copy()
    
    def restore_all_buttons(self, buttons_per_group):
        """Restore all buttons from saved state"""
        self.buttons_per_group = buttons_per_group or {}
        # Buttons will be loaded when groups are selected
    
    def restore_all_files(self, files_per_group):
        """Restore all files from saved state"""
        self.files_per_group = files_per_group or {}
    
    def rename_group(self, old_name, new_name):
        """Handle group rename - update all internal references"""
        # Update buttons_per_group key
        if old_name in self.buttons_per_group:
            self.buttons_per_group[new_name] = self.buttons_per_group.pop(old_name)
        
        # Update files_per_group key
        if old_name in self.files_per_group:
            self.files_per_group[new_name] = self.files_per_group.pop(old_name)
        
        # Update current_group if it's the one being renamed
        if self.current_group == old_name:
            self.current_group = new_name
    
    def delete_group(self, group_name):
        """Handle group deletion - clean up all associated buttons and files"""
        # If this is the current group, clear the display
        if self.current_group == group_name:
            self.clear_all_buttons()
            self.file_list.clear()
            self.current_group = None
        
        # Clean up buttons data for this group
        if group_name in self.buttons_per_group:
            del self.buttons_per_group[group_name]
        
        # Clean up files data for this group
        if group_name in self.files_per_group:
            del self.files_per_group[group_name]

