"""Queue Status Dialog - Shows all active queues across all terminals"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, QWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont


class QueueStatusItemWidget(QWidget):
    """Custom widget for displaying queue status for a terminal"""
    
    jump_to_terminal = pyqtSignal(object)  # Signal emitted with terminal widget to jump to
    
    def __init__(self, terminal_widget, tab_name, queue, status, parent=None):
        super().__init__(parent)
        self.terminal_widget = terminal_widget
        self.tab_name = tab_name
        
        # Set widget background
        self.setStyleSheet("""
            QueueStatusItemWidget {
                background-color: transparent;
            }
        """)
        
        # Main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(15)
        
        # Tab name label
        name_label = QLabel(f"<b>{tab_name}</b>")
        name_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
        """)
        name_label.setFixedWidth(150)
        layout.addWidget(name_label)
        
        # Status indicator
        is_running = status['is_running']
        status_text = "Running" if is_running else "Idle"
        status_color = "#66bb6a" if is_running else "#ffa726"
        
        status_label = QLabel(f"<span style='color:{status_color};'>● {status_text}</span>")
        status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
            }
        """)
        status_label.setFixedWidth(80)
        layout.addWidget(status_label)
        
        # Progress info
        queue_size = status['queue_size']
        pending = status['pending_size']
        current_cmd = status['current_command']
        
        if current_cmd:
            progress_text = f"Running: {current_cmd.get('name', 'Unknown')} ({pending} pending)"
        elif queue_size > 0:
            progress_text = f"{queue_size} command(s) in queue"
        else:
            progress_text = "Queue empty"
        
        progress_label = QLabel(progress_text)
        progress_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
            }
        """)
        progress_label.setWordWrap(False)
        layout.addWidget(progress_label, 1)  # Stretch
        
        # Jump button
        jump_btn = QPushButton("Jump to Tab")
        jump_btn.setFixedSize(100, 28)
        jump_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        jump_btn.clicked.connect(lambda: self.jump_to_terminal.emit(self.terminal_widget))
        layout.addWidget(jump_btn)
        
        self.setLayout(layout)


class QueueStatusDialog(QDialog):
    """Dialog showing status of all active queues across terminals"""
    
    jump_to_terminal = pyqtSignal(object)  # Signal to notify main window to switch to terminal
    
    def __init__(self, button_panel, terminal_tabs, parent=None):
        super().__init__(parent)
        self.button_panel = button_panel
        self.terminal_tabs = terminal_tabs
        self.setWindowTitle("Queue Status - All Terminals")
        self.setMinimumSize(700, 400)
        self.init_ui()
        self.setup_auto_refresh()
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Active Command Queues")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #e0e0e0;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedSize(90, 30)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #424242;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_queue_list)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Info label
        self.info_label = QLabel("Loading...")
        self.info_label.setStyleSheet("""
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.info_label)
        
        # List of queues
        self.queue_list = QListWidget()
        self.queue_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                margin: 3px;
                padding: 0px;
            }
            QListWidget::item:hover {
                background-color: #2a2a2a;
                border: 1px solid #4a4a4a;
            }
            QListWidget::item:selected {
                background-color: #2d2d2d;
                border: 1px solid #2196F3;
            }
        """)
        self.queue_list.setSpacing(2)
        layout.addWidget(self.queue_list)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(80, 32)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #424242;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Initial refresh
        self.refresh_queue_list()
    
    def setup_auto_refresh(self):
        """Setup automatic refresh of queue list"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_queue_list)
        self.refresh_timer.start(500)  # Refresh every 500ms
    
    def refresh_queue_list(self):
        """Refresh the list of active queues"""
        self.queue_list.clear()
        
        # Get all active queues
        active_queues = self.button_panel.get_all_active_queues()
        
        if not active_queues:
            self.info_label.setText("No active queues. All terminals are idle.")
            return
        
        self.info_label.setText(f"Found {len(active_queues)} terminal(s) with active queues:")
        
        for terminal, queue, status in active_queues:
            # Get tab name for this terminal
            tab_name = self.get_tab_name_for_terminal(terminal)
            
            # Create custom widget for this queue
            widget = QueueStatusItemWidget(terminal, tab_name, queue, status)
            widget.jump_to_terminal.connect(self.on_jump_to_terminal)
            
            # Create list item and set the custom widget
            list_item = QListWidgetItem(self.queue_list)
            list_item.setSizeHint(QSize(self.queue_list.width() - 30, 50))
            self.queue_list.addItem(list_item)
            self.queue_list.setItemWidget(list_item, widget)
    
    def get_tab_name_for_terminal(self, terminal):
        """Get the tab name for a terminal widget
        
        Args:
            terminal: The terminal widget
            
        Returns:
            str: The tab name, or "Unknown Tab" if not found
        """
        # Search through tab widget to find this terminal
        if hasattr(self.terminal_tabs, 'tab_widget'):
            tab_widget = self.terminal_tabs.tab_widget
            for i in range(tab_widget.count()):
                if tab_widget.widget(i) == terminal:
                    tab_text = tab_widget.tabText(i)
                    # Strip shell indicator if present
                    if '[' in tab_text and ']' in tab_text:
                        tab_text = tab_text.rsplit('[', 1)[0].strip()
                    return tab_text
        return "Unknown Tab"
    
    def on_jump_to_terminal(self, terminal_widget):
        """Handle jump to terminal request
        
        Args:
            terminal_widget: The terminal to jump to
        """
        self.jump_to_terminal.emit(terminal_widget)
        # Close dialog after jumping
        self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close - stop refresh timer"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().closeEvent(event)
