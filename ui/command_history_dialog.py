"""Command History Search Dialog with fuzzy matching"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QListWidget, QListWidgetItem, QLabel, QPushButton,
                             QWidget, QSizePolicy, QShortcut, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QKeySequence
from datetime import datetime
import os


def format_timestamp(timestamp_str):
    """Format timestamp to relative time"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years}y ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months}mo ago"
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "now"
    except:
        return ""


def format_command_entry(command_data):
    """Format a command entry as text for display (no custom widgets)"""
    command = command_data['command']
    
    # Build metadata line
    meta_parts = []
    
    if 'group' in command_data:
        meta_parts.append(f"[{command_data['group']}]")
    
    if 'working_dir' in command_data and command_data['working_dir']:
        working_dir = command_data['working_dir']
        # Shorten home directory
        home = os.path.expanduser("~")
        if working_dir.startswith(home):
            working_dir = "~" + working_dir[len(home):]
        # Truncate long paths
        if len(working_dir) > 40:
            working_dir = "..." + working_dir[-37:]
        meta_parts.append(working_dir)
    
    if 'timestamp' in command_data:
        time_str = format_timestamp(command_data['timestamp'])
        if time_str:
            meta_parts.append(time_str)
    
    if 'count' in command_data and command_data['count'] > 1:
        meta_parts.append(f"×{command_data['count']}")
    
    # Format as two lines: command + metadata
    if meta_parts:
        return f"{command}\n    {' • '.join(meta_parts)}"
    else:
        return command


class CommandHistoryDialog(QDialog):
    """Dialog for searching and selecting command history"""
    
    command_selected = pyqtSignal(str)  # Emits the selected command
    
    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.selected_command = None
        
        # Search debounce timer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        # Pagination
        self.current_results = []
        self.display_limit = 50  # Show max 50 items initially (reduced for smoother scrolling)
        self.displayed_count = 0
        self.is_loading_more = False
        
        self.init_ui()
        self.load_recent_commands()
    
    def init_ui(self):
        """Initialize the dialog UI"""
        self.setWindowTitle("Command History Search")
        self.setMinimumSize(700, 500)
        
        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
                color: #e5e5e5;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #e5e5e5;
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                padding: 8px;
                font-size: 14pt;
            }
            QLineEdit:focus {
                border: 2px solid #0066cc;
            }
            QListWidget {
                background-color: #1e1e1e;
                color: #e5e5e5;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #2d2d2d;
                padding: 6px 8px;
                min-height: 40px;
            }
            QListWidget::item:selected {
                background-color: #0066cc;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
            QLabel {
                color: #e5e5e5;
            }
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #004080;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header with instruction
        header_layout = QHBoxLayout()
        header_label = QLabel("🔍 Search Command History")
        header_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e5e5e5;")
        header_layout.addWidget(header_label)
        
        # Stats
        stats = self.history_manager.get_stats()
        stats_label = QLabel(f"{stats['total_commands']} total • {stats['unique_commands']} unique")
        stats_label.setStyleSheet("color: #888888; font-size: 10pt;")
        header_layout.addStretch()
        header_layout.addWidget(stats_label)
        
        layout.addLayout(header_layout)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search commands (fuzzy matching)...")
        self.search_input.textChanged.connect(self.on_search_changed)
        layout.addWidget(self.search_input)
        
        # Hint label
        hint_label = QLabel("💡 Tip: Use Ctrl+R to open this dialog anytime. Press Enter to select, Esc to cancel.")
        hint_label.setStyleSheet("color: #666666; font-size: 9pt; font-style: italic;")
        layout.addWidget(hint_label)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.results_list.itemClicked.connect(self.on_item_clicked)
        
        # Enable uniform item sizes for much better scrolling performance
        self.results_list.setUniformItemSizes(True)
        
        # Optimize scroll performance
        self.results_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_list.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        layout.addWidget(self.results_list)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Select button
        select_btn = QPushButton("Insert Command")
        select_btn.clicked.connect(self.accept_selection)
        select_btn.setDefault(True)
        button_layout.addWidget(select_btn)
        
        # Execute button
        execute_btn = QPushButton("Execute Now")
        execute_btn.clicked.connect(self.execute_selection)
        execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        button_layout.addWidget(execute_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Focus search input
        self.search_input.setFocus()
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Enter key to select
        enter_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        enter_shortcut.activated.connect(self.accept_selection)
        
        # Ctrl+Enter to execute
        execute_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        execute_shortcut.activated.connect(self.execute_selection)
        
        # Up/Down arrows to navigate list
        up_shortcut = QShortcut(QKeySequence(Qt.Key_Up), self.search_input)
        up_shortcut.activated.connect(self.navigate_up)
        
        down_shortcut = QShortcut(QKeySequence(Qt.Key_Down), self.search_input)
        down_shortcut.activated.connect(self.navigate_down)
        
        # Escape to close
        esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc_shortcut.activated.connect(self.reject)
    
    def navigate_up(self):
        """Navigate up in results list"""
        current_row = self.results_list.currentRow()
        if current_row > 0:
            self.results_list.setCurrentRow(current_row - 1)
        elif current_row == -1 and self.results_list.count() > 0:
            self.results_list.setCurrentRow(self.results_list.count() - 1)
    
    def navigate_down(self):
        """Navigate down in results list"""
        current_row = self.results_list.currentRow()
        if current_row < self.results_list.count() - 1:
            self.results_list.setCurrentRow(current_row + 1)
        elif current_row == -1 and self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
    
    def on_search_changed(self, text):
        """Handle search text change with debouncing"""
        # Debounce search - wait 150ms after last keystroke
        self.search_timer.stop()
        self.search_timer.start(150)
    
    def perform_search(self):
        """Perform the actual search"""
        query = self.search_input.text()
        
        if not query:
            # Load recent commands with limit
            self.current_results = self.history_manager.get_recent_commands(limit=500)
        else:
            # Search with higher limit
            self.current_results = self.history_manager.search_fuzzy(query, limit=500)
        
        self.displayed_count = 0
        self.display_results()
    
    def load_recent_commands(self):
        """Load recent commands when no search query"""
        self.current_results = self.history_manager.get_recent_commands(limit=500)
        self.displayed_count = 0
        self.display_results()
    
    def on_scroll(self, value):
        """Handle scroll events to implement lazy loading"""
        if self.is_loading_more:
            return
        
        # Check if we're near the bottom
        scrollbar = self.results_list.verticalScrollBar()
        if scrollbar.maximum() > 0:
            # Load more when 80% scrolled
            if value >= scrollbar.maximum() * 0.8:
                self.load_more_results()
    
    def load_more_results(self):
        """Load more results when scrolling near bottom"""
        if self.is_loading_more:
            return
        
        remaining = len(self.current_results) - self.displayed_count
        if remaining <= 0:
            return
        
        self.is_loading_more = True
        
        # Remove "load more" indicator if it exists
        last_item = self.results_list.item(self.results_list.count() - 1)
        if last_item and not last_item.data(Qt.UserRole):
            self.results_list.takeItem(self.results_list.count() - 1)
        
        # Add next batch of items
        batch_size = 25
        start_idx = self.displayed_count
        end_idx = min(start_idx + batch_size, len(self.current_results))
        
        for i in range(start_idx, end_idx):
            result = self.current_results[i]
            text = format_command_entry(result)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, result['command'])
            font = QFont("Courier New", 10)
            item.setFont(font)
            self.results_list.addItem(item)
        
        self.displayed_count = end_idx
        
        # Add "load more" indicator if there are still more results
        if self.displayed_count < len(self.current_results):
            more_item = QListWidgetItem(f"... {len(self.current_results) - self.displayed_count} more (scroll down)")
            more_item.setFlags(Qt.NoItemFlags)
            more_item.setForeground(Qt.gray)
            self.results_list.addItem(more_item)
        
        self.is_loading_more = False
    
    def display_results(self):
        """Display initial batch of search results"""
        self.results_list.clear()
        
        if not self.current_results:
            # Show "no results" message
            item = QListWidgetItem("No commands found")
            item.setFlags(Qt.NoItemFlags)
            self.results_list.addItem(item)
            return
        
        # Only display first batch of items for performance
        display_count = min(len(self.current_results), self.display_limit)
        
        # Use simple text items instead of custom widgets for much better performance
        for i in range(display_count):
            result = self.current_results[i]
            
            # Format command text with metadata
            text = format_command_entry(result)
            
            # Create simple text item
            item = QListWidgetItem(text)
            
            # Store command data in item
            item.setData(Qt.UserRole, result['command'])
            
            # Style the item with monospace font
            font = QFont("Courier New", 10)
            item.setFont(font)
            
            self.results_list.addItem(item)
        
        self.displayed_count = display_count
        
        # Add "load more" indicator if there are more results
        if len(self.current_results) > display_count:
            more_item = QListWidgetItem(f"... {len(self.current_results) - display_count} more (scroll down)")
            more_item.setFlags(Qt.NoItemFlags)
            more_item.setForeground(Qt.gray)
            self.results_list.addItem(more_item)
        
        # Select first item
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
    
    def on_item_clicked(self, item):
        """Handle item click"""
        command = item.data(Qt.UserRole)
        if command:
            self.selected_command = command
    
    def on_item_double_clicked(self, item):
        """Handle item double click"""
        command = item.data(Qt.UserRole)
        if command:
            self.selected_command = command
            self.accept()
    
    def accept_selection(self):
        """Accept the selected command"""
        current_item = self.results_list.currentItem()
        if current_item:
            command = current_item.data(Qt.UserRole)
            if command:
                self.selected_command = command
                self.accept()
    
    def execute_selection(self):
        """Execute the selected command immediately"""
        current_item = self.results_list.currentItem()
        if current_item:
            command = current_item.data(Qt.UserRole)
            if command:
                self.selected_command = command
                self.command_selected.emit(command)
                self.accept()
    
    def get_selected_command(self):
        """Get the selected command"""
        return self.selected_command



