"""Top tab bar for terminals (browser-like)"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QTabBar, 
                             QPushButton, QHBoxLayout, QInputDialog, QMenu, QAction,
                             QDialog, QLabel, QComboBox, QLineEdit, QFormLayout, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from ui.terminal_widgets import TerminalWidget
import os

class RenameableTabBar(QTabBar):
    """Custom tab bar that allows renaming tabs with right-click and supports drag-and-drop"""
    
    def __init__(self, parent=None, terminal_tabs_widget=None):
        super().__init__(parent)
        self.terminal_tabs_widget = terminal_tabs_widget
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # Explicitly enable movable tabs
        self.setMovable(True)
        
    def mousePressEvent(self, event):
        """Handle right-click to show context menu, allow left-click drag"""
        if event.button() == Qt.RightButton:
            index = self.tabAt(event.pos())
            if index >= 0:
                # Use stored reference to TerminalTabs widget
                if self.terminal_tabs_widget and hasattr(self.terminal_tabs_widget, 'show_tab_context_menu'):
                    self.terminal_tabs_widget.show_tab_context_menu(index, event.globalPos())
                return
        # Always call super() to allow drag functionality to work
        super().mousePressEvent(event)

class NewTerminalDialog(QDialog):
    """Dialog to configure new terminal"""
    
    def __init__(self, parent=None, tab_number=1):
        super().__init__(parent)
        self.setWindowTitle("New Terminal")
        self.setMinimumWidth(350)
        self.init_ui(tab_number)
        
    def init_ui(self, tab_number):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        # Tab name
        self.name_input = QLineEdit(f"Tab {tab_number}")
        form.addRow("Tab Name:", self.name_input)
        
        # Shell type
        self.shell_combo = QComboBox()
        
        # Detect available shells
        available_shells = self.detect_shells()
        self.shell_combo.addItems(available_shells)
        
        # Set default to user's shell or zsh/bash
        default_shell = os.environ.get('SHELL', '/bin/bash')
        shell_name = os.path.basename(default_shell)
        index = self.shell_combo.findText(shell_name, Qt.MatchContains)
        if index >= 0:
            self.shell_combo.setCurrentIndex(index)
        
        form.addRow("Shell Type:", self.shell_combo)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        layout.addWidget(buttons)
    
    def detect_shells(self):
        """Detect available shells on the system"""
        shells = []
        common_shells = [
            ('/bin/bash', 'bash'),
            ('/bin/zsh', 'zsh'),
            ('/bin/sh', 'sh'),
            ('/bin/fish', 'fish'),
            ('/bin/ksh', 'ksh'),
            ('/bin/tcsh', 'tcsh'),
            ('/usr/bin/bash', 'bash'),
            ('/usr/bin/zsh', 'zsh'),
            ('/usr/local/bin/fish', 'fish'),
        ]
        
        seen = set()
        for path, name in common_shells:
            if os.path.exists(path) and name not in seen:
                shells.append(f"{name} ({path})")
                seen.add(name)
        
        # If no shells found, add defaults
        if not shells:
            shells = ['bash (/bin/bash)', 'sh (/bin/sh)']
        
        return shells
    
    def get_data(self):
        """Get the dialog data"""
        shell_text = self.shell_combo.currentText()
        # Extract path from "name (path)" format
        if '(' in shell_text and ')' in shell_text:
            shell_path = shell_text.split('(')[1].split(')')[0]
        else:
            shell_path = '/bin/bash'
        
        return {
            'name': self.name_input.text(),
            'shell': shell_path
        }

class TerminalTabs(QWidget):
    """Browser-like terminal tabs"""
    
    def __init__(self):
        super().__init__()
        self.tab_counter = 0
        self.current_group = None
        self.tabs_per_group = {}  # Store tabs per group: {group_name: [tab_data]}
        self.terminal_widgets_cache = {}  # Cache terminal widgets: {group_name: [(name, shell, widget)]}
        self.is_switching = False  # Flag to track if a group switch is in progress
        self.tabs_changed_callback = None  # Callback for when tabs structure changes
        self.init_ui()
    
    def create_close_icon(self):
        """Create a custom close icon"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw X
        painter.setPen(QColor(200, 200, 200))
        painter.drawLine(4, 4, 12, 12)
        painter.drawLine(12, 4, 4, 12)
        
        painter.end()
        return QIcon(pixmap)
        
    def init_ui(self):
        """Initialize the UI"""
        from PyQt5.QtWidgets import QSizePolicy
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create custom tab bar container
        tab_bar_container = QWidget()
        tab_bar_container.setStyleSheet("background-color: #2b2b2b;")
        tab_bar_container.setFixedHeight(32)
        tab_bar_layout = QHBoxLayout(tab_bar_container)
        tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        tab_bar_layout.setSpacing(0)
        
        # Left navigation button
        self.left_nav_btn = QPushButton("◀")
        self.left_nav_btn.setFixedWidth(35)
        self.left_nav_btn.setFixedHeight(28)
        self.left_nav_btn.setEnabled(False)
        self.left_nav_btn.clicked.connect(self.scroll_tabs_left)
        self.left_nav_btn.setMouseTracking(True)
        self.left_nav_btn.installEventFilter(self)
        self.left_nav_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: none;
                border-right: 1px solid #555;
                padding: 2px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #424242;
            }
            QPushButton:pressed:enabled {
                background-color: #555;
            }
            QPushButton:disabled {
                background-color: #1e1e1e;
                color: #666;
            }
        """)
        tab_bar_layout.addWidget(self.left_nav_btn)
        
        # Tab widget with custom styling
        self.tab_widget = QTabWidget()
        
        # Set custom tab bar FIRST before setting properties
        custom_tab_bar = RenameableTabBar(terminal_tabs_widget=self)
        self.tab_widget.setTabBar(custom_tab_bar)
        
        # Now set tab widget properties (after custom tab bar is installed)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        
        # Enable Qt's built-in scroll buttons but we'll hide them visually
        # This allows Qt to manage tab scrolling natively when currentIndex changes
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setElideMode(Qt.ElideNone)
        
        # Set icon size for close buttons
        custom_tab_bar.setIconSize(QSize(16, 16))
        
        # Make tab bar expand to fill available space
        custom_tab_bar.setExpanding(False)  # We'll control spacing ourselves
        custom_tab_bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        # Install event filter to detect tab bar resizes
        custom_tab_bar.installEventFilter(self)
        
        # Style the tabs
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #1e1e1e;
                top: -32px;
                margin-top: 0px;
                padding-top: 0px;
            }
            QTabWidget::tab-bar {
                alignment: left;
                height: 32px;
            }
            QTabBar {
                background-color: transparent;
                margin-left: 8px;
                margin-top: 0px;
                margin-bottom: 0px;
                height: 32px;
                max-height: 32px;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 6px 25px 6px 10px;
                margin-right: 2px;
                margin-left: 2px;
                margin-top: 0px;
                margin-bottom: 0px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                min-width: 80px;
                max-width: 200px;
            }
            QTabBar::tab:first {
                margin-left: 0px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 2px solid #0d47a1;
            }
            QTabBar::tab:hover {
                background-color: #424242;
            }
            QTabBar::close-button {
                subcontrol-position: right;
                subcontrol-origin: padding;
                margin: 4px 6px 4px 4px;
                image: none;
                width: 16px;
                height: 16px;
                border: none;
            }
            QTabBar::close-button:hover {
                background-color: #f44336;
                border-radius: 2px;
            }
            /* Completely hide Qt's default scroll buttons */
            QTabBar::scroller {
                width: 0px;
                height: 0px;
            }
            QTabBar QToolButton {
                background: transparent;
                border: none;
                width: 0px;
                height: 0px;
                max-width: 0px;
                max-height: 0px;
                min-width: 0px;
                min-height: 0px;
            }
            QTabBar QToolButton::right-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QTabBar QToolButton::left-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QTabBar QToolButton:disabled {
                width: 0px;
                height: 0px;
            }
        """)
        
        # Hide any Qt default scroll buttons that might appear
        # This is done by finding all QToolButton children and hiding them
        QTimer.singleShot(0, lambda: self.hide_qt_scroll_buttons())
        
        # Store reference to tab bar for later use
        self.custom_tab_bar = custom_tab_bar
        
        # Add the tab bar to layout (after left nav button, position 1)
        tab_bar_layout.addWidget(self.tab_widget.tabBar())
        
        # Add "+" button (appears right after tabs)
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedWidth(28)
        self.add_tab_btn.setFixedHeight(28)
        self.add_tab_btn.clicked.connect(lambda: self.add_tab())
        self.add_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: none;
                border-left: 1px solid #555;
                padding: 2px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #424242;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        tab_bar_layout.addWidget(self.add_tab_btn)
        
        # Add flexible space between + and ▶ (shrinks as tabs are added)
        tab_bar_layout.addStretch(1)
        
        # Right navigation button
        self.right_nav_btn = QPushButton("▶")
        self.right_nav_btn.setFixedWidth(35)
        self.right_nav_btn.setFixedHeight(28)
        self.right_nav_btn.setEnabled(False)
        self.right_nav_btn.clicked.connect(self.scroll_tabs_right)
        self.right_nav_btn.setMouseTracking(True)
        self.right_nav_btn.installEventFilter(self)
        self.right_nav_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: none;
                border-left: 1px solid #555;
                padding: 2px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #424242;
            }
            QPushButton:pressed:enabled {
                background-color: #555;
            }
            QPushButton:disabled {
                background-color: #1e1e1e;
                color: #666;
            }
        """)
        tab_bar_layout.addWidget(self.right_nav_btn)
        
        # Add the custom tab bar container to main layout
        main_layout.addWidget(tab_bar_container)
        
        # Add the tab widget's content pane (just the pane, tab bar is already positioned above)
        self.tab_widget.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.tab_widget)
        
        # Timer to update navigation buttons
        self.nav_update_timer = QTimer()
        self.nav_update_timer.setSingleShot(True)
        self.nav_update_timer.timeout.connect(self.update_navigation_buttons)
        
        # Connect tab changes to update navigation
        self.tab_widget.currentChanged.connect(lambda: self.nav_update_timer.start(100))
        self.tab_widget.tabBar().tabMoved.connect(self.on_tab_moved)
    
    def hide_qt_scroll_buttons(self):
        """Hide Qt's default scroll buttons completely"""
        from PyQt5.QtWidgets import QToolButton
        
        # Find all QToolButton children of the tab bar and hide them
        tab_bar = self.tab_widget.tabBar()
        for child in tab_bar.findChildren(QToolButton):
            child.hide()
            child.setFixedSize(0, 0)
            child.setEnabled(False)
    
    def on_tab_moved(self, from_index, to_index):
        """Handle tab reordering - sync internal data structures"""
        # Update navigation buttons
        self.nav_update_timer.start(100)
        
        # Sync the tabs_per_group and terminal_widgets_cache to match new order
        if self.current_group:
            # Get the current order from the visible tabs
            tabs_info = []
            widgets_cache = []
            
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if widget:
                    tab_text = self.tab_widget.tabText(i)
                    shell = widget.shell if hasattr(widget, 'shell') else '/bin/bash'
                    
                    # Strip shell indicator from name
                    base_name = tab_text
                    if '[' in tab_text and ']' in tab_text:
                        base_name = tab_text.rsplit('[', 1)[0].strip()
                    
                    tabs_info.append({
                        'name': base_name,
                        'shell': shell
                    })
                    widgets_cache.append((base_name, shell, widget))
            
            # Update the data structures with the new order
            self.tabs_per_group[self.current_group] = tabs_info
            self.terminal_widgets_cache[self.current_group] = widgets_cache
            
            # Notify about tab structure change
            if self.tabs_changed_callback:
                self.tabs_changed_callback()
    
    def showEvent(self, event):
        """Update navigation buttons when widget is shown"""
        super().showEvent(event)
        # Force tab bar geometry update to ensure proper spacing at startup
        if hasattr(self, 'tab_widget') and self.tab_widget.count() > 0:
            QTimer.singleShot(50, lambda: self.tab_widget.tabBar().updateGeometry())
            QTimer.singleShot(100, lambda: self.tab_widget.tabBar().update())
        # Trigger navigation button update after the widget is fully shown
        if hasattr(self, 'update_navigation_buttons'):
            QTimer.singleShot(200, self.update_navigation_buttons)
        # Hide Qt scroll buttons
        QTimer.singleShot(50, self.hide_qt_scroll_buttons)
    
    def resizeEvent(self, event):
        """Update navigation buttons when widget is resized"""
        super().resizeEvent(event)
        if hasattr(self, 'nav_update_timer'):
            self.nav_update_timer.start(150)
        # Ensure Qt scroll buttons stay hidden
        if hasattr(self, 'hide_qt_scroll_buttons'):
            QTimer.singleShot(100, self.hide_qt_scroll_buttons)
        
    def add_tab(self, name=None, shell=None, skip_save=False):
        """Add a new terminal tab"""
        if not self.current_group:
            return None  # No group selected
            
        # Handle the case where a boolean is passed from button click
        if isinstance(name, bool):
            name = None
            
        # If called from button, show dialog
        if name is None:
            self.tab_counter += 1
            dialog = NewTerminalDialog(self, self.tab_counter)
            if dialog.exec_():
                data = dialog.get_data()
                name = data['name']
                shell = data['shell']
            else:
                return None  # User cancelled
        else:
            self.tab_counter += 1
        
        if name is None:
            name = f"Tab {self.tab_counter}"
        
        # Create terminal with specified shell and preferences
        from core.preferences_manager import PreferencesManager
        prefs_manager = PreferencesManager()
        terminal = TerminalWidget(shell=shell, prefs_manager=prefs_manager)
        
        # Connect to session recorder for command capture (if available)
        # This will capture commands typed directly in the terminal
        if hasattr(self, 'command_executed_callback'):
            terminal.command_executed.connect(self.command_executed_callback)
        
        # Connect viewport scroll signal to update minimap (if available)
        if hasattr(self, 'viewport_scrolled_callback') and hasattr(terminal, 'viewport_scrolled'):
            terminal.viewport_scrolled.connect(self.viewport_scrolled_callback)
        
        # Add shell indicator to tab name
        shell_name = os.path.basename(shell) if shell else "bash"
        tab_label = f"{name} [{shell_name}]"
        
        index = self.tab_widget.addTab(terminal, tab_label)
        self.tab_widget.setCurrentIndex(index)
        
        # Set close button icon for this tab
        self.tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, self.create_close_button())
        
        # Add to cache
        if self.current_group:
            if self.current_group not in self.terminal_widgets_cache:
                self.terminal_widgets_cache[self.current_group] = []
            self.terminal_widgets_cache[self.current_group].append((name, shell, terminal))
        
        # Save to current group's tabs
        if not skip_save:
            self.save_and_notify_tab_change()
        
        # Update navigation buttons
        self.nav_update_timer.start(100)
        
        return terminal
    
    def create_close_button(self):
        """Create a custom close button for tabs"""
        close_btn = QPushButton("×")
        close_btn.setMaximumSize(16, 16)
        close_btn.setMinimumSize(16, 16)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #f44336;
                color: white;
                border-radius: 2px;
            }
        """)
        close_btn.clicked.connect(lambda: self.close_current_button_tab(close_btn))
        return close_btn
    
    def close_current_button_tab(self, button):
        """Close the tab associated with a close button"""
        # Find which tab this button belongs to
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabBar().tabButton(i, QTabBar.RightSide) == button:
                self.close_tab(i)
                break
    
    def show_tab_context_menu(self, index, position):
        """Show context menu for tab"""
        menu = QMenu(self)
        
        # Add actions
        rename_action = QAction("Rename", self)
        close_action = QAction("Close", self)
        
        rename_action.triggered.connect(lambda: self.rename_tab(index))
        close_action.triggered.connect(lambda: self.close_tab(index))
        
        menu.addAction(rename_action)
        menu.addSeparator()
        menu.addAction(close_action)
        
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
            QMenu::item:disabled {
                color: #666;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0px;
            }
        """)
        
        menu.exec_(position)
    
    def close_tab(self, index):
        """Close a tab"""
        widget = self.tab_widget.widget(index)
        
        # Notify about tab closure (for queue cleanup) before actually closing
        if widget and hasattr(self, 'tab_closing_callback'):
            self.tab_closing_callback(widget)
        
        # Check if tab has history file and prompt for cleanup
        if widget and hasattr(widget, 'history_file_path') and widget.history_file_path:
            from PyQt5.QtWidgets import QMessageBox
            file_size = widget.get_history_file_size() if hasattr(widget, 'get_history_file_size') else "Unknown"
            
            reply = QMessageBox.question(
                self,
                'Close Tab',
                f'This tab has {file_size} of archived history.\n\n'
                f'Do you want to delete the history file?',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                return  # Don't close tab
            elif reply == QMessageBox.Yes:
                # Delete history file
                if hasattr(widget, 'history_manager') and hasattr(widget, 'tab_id'):
                    widget.history_manager.delete_history_file(widget.tab_id)
        
        # Check if this is the last tab
        is_last_tab = self.tab_widget.count() == 1
        
        self.tab_widget.removeTab(index)
        
        # Remove from cache
        if self.current_group and self.current_group in self.terminal_widgets_cache:
            self.terminal_widgets_cache[self.current_group] = [
                (name, shell, w) for name, shell, w in self.terminal_widgets_cache[self.current_group]
                if w != widget
            ]
        
        widget.deleteLater()
        
        # If we just closed the last tab, create a new one with default settings
        if is_last_tab:
            self.tab_counter += 1
            default_shell = os.environ.get('SHELL', '/bin/bash')
            self.add_tab(name=f"Tab {self.tab_counter}", shell=default_shell)
        else:
            # Save updated tabs for current group
            self.save_and_notify_tab_change()
        
        # Update navigation buttons
        self.nav_update_timer.start(100)
    
    def rename_tab(self, index):
        """Rename a tab"""
        if 0 <= index < self.tab_widget.count():
            old_name = self.tab_widget.tabText(index)
            widget = self.tab_widget.widget(index)
            
            # Extract base name without shell indicator
            base_name = old_name
            if '[' in old_name and ']' in old_name:
                base_name = old_name.rsplit('[', 1)[0].strip()
            
            new_name, ok = QInputDialog.getText(self, "Rename Tab", 
                                               "Enter new name:", 
                                               text=base_name)
            if ok and new_name:
                # Re-add shell indicator
                if widget and hasattr(widget, 'shell'):
                    shell_name = os.path.basename(widget.shell)
                    tab_label = f"{new_name} [{shell_name}]"
                    self.tab_widget.setTabText(index, tab_label)
                    
                    # Update in cache
                    if self.current_group and self.current_group in self.terminal_widgets_cache:
                        for i, (name, shell, w) in enumerate(self.terminal_widgets_cache[self.current_group]):
                            if w == widget:
                                self.terminal_widgets_cache[self.current_group][i] = (new_name, shell, w)
                                break
                else:
                    self.tab_widget.setTabText(index, new_name)
                
                # Save updated tabs
                self.save_and_notify_tab_change()
    
    def set_current_tab(self, index):
        """Set the current tab by index"""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
    
    def get_current_terminal(self):
        """Get the current terminal widget"""
        return self.tab_widget.currentWidget()
    
    def get_current_tab_name(self):
        """Get the name of the current tab"""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            return self.tab_widget.tabText(current_index)
        return None
    
    def set_all_terminals_resize_enabled(self, enabled):
        """Enable or disable PTY resizing for all terminal widgets across all groups"""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"set_all_terminals_resize_enabled: Setting resize_enabled={enabled}")
        
        # Set for currently visible widgets
        count = 0
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget and hasattr(widget, 'resize_enabled'):
                widget.resize_enabled = enabled
                count += 1
        
        # Set for cached widgets
        for group_name, cached_widgets in self.terminal_widgets_cache.items():
            for name, shell, widget in cached_widgets:
                if widget and hasattr(widget, 'resize_enabled'):
                    widget.resize_enabled = enabled
                    count += 1
        
        logger.debug(f"set_all_terminals_resize_enabled: Updated {count} widgets")
    
    def is_switching_groups(self):
        """Check if a group switch is currently in progress"""
        return self.is_switching
    
    # ===== Group Management Methods =====
    
    def load_group_tabs(self, group_name):
        """Load tabs for a specific group"""
        # Mark that we're switching groups
        self.is_switching = True
        
        # Save current group's tab info and cache widgets
        if self.current_group:
            self.save_and_cache_current_group()
        
        # Update current group
        self.current_group = group_name
        
        # Block signals and updates to prevent focus changes and redraws while switching tabs
        self.tab_widget.blockSignals(True)
        self.tab_widget.setUpdatesEnabled(False)
        
        # Store widgets being removed and disable their resize/focus handlers
        widgets_being_removed = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget:
                widgets_being_removed.append(widget)
                # Temporarily disable focus for widgets being removed
                widget.setFocusPolicy(Qt.NoFocus)
                # Disable PTY resize to prevent prompt redraws
                if hasattr(widget, 'resize_enabled'):
                    widget.resize_enabled = False
        
        # Clear all current tabs from display (but don't delete widgets)
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        
        # Initialize group if not exists
        if group_name not in self.tabs_per_group:
            self.tabs_per_group[group_name] = []
            self.terminal_widgets_cache[group_name] = []
            self.add_default_tabs_for_group(group_name)
        
        # Check if we have cached widgets for this group
        if group_name in self.terminal_widgets_cache and self.terminal_widgets_cache[group_name]:
            # Restore from cache
            for tab_name, shell, terminal_widget in self.terminal_widgets_cache[group_name]:
                # Temporarily disable focus and resize for widgets being added
                terminal_widget.setFocusPolicy(Qt.NoFocus)
                if hasattr(terminal_widget, 'resize_enabled'):
                    terminal_widget.resize_enabled = False
                
                # Connect to session recorder for command capture (if not already connected)
                if hasattr(self, 'command_executed_callback'):
                    try:
                        terminal_widget.command_executed.disconnect()
                    except:
                        pass  # Wasn't connected
                    terminal_widget.command_executed.connect(self.command_executed_callback)
                
                shell_name = os.path.basename(shell) if shell else "bash"
                tab_label = f"{tab_name} [{shell_name}]"
                index = self.tab_widget.addTab(terminal_widget, tab_label)
                self.tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, self.create_close_button())
        else:
            # Create new tabs
            for tab_data in self.tabs_per_group[group_name]:
                self.add_tab(tab_data['name'], tab_data.get('shell', '/bin/bash'), skip_save=True)
        
        # Re-enable signals and updates
        self.tab_widget.blockSignals(False)
        self.tab_widget.setUpdatesEnabled(True)
        
        # Force tab bar geometry update to prevent overlap after group switch
        if self.tab_widget.count() > 0:
            QTimer.singleShot(50, lambda: self.tab_widget.tabBar().updateGeometry())
            QTimer.singleShot(100, lambda: self.tab_widget.tabBar().update())
        
        # Restore focus policy and resize handling for all widgets after a short delay
        # This prevents race conditions with Qt's event processing
        QTimer.singleShot(100, lambda: self.restore_widget_capabilities(widgets_being_removed))
        if group_name in self.terminal_widgets_cache and self.terminal_widgets_cache[group_name]:
            restored_widgets = [w for _, _, w in self.terminal_widgets_cache[group_name]]
            QTimer.singleShot(100, lambda: self.restore_widget_capabilities(restored_widgets))
        
        # Select the first tab if any tabs exist
        if self.tab_widget.count() > 0:
            self.tab_widget.setCurrentIndex(0)
        
        # Update navigation buttons after loading group
        self.nav_update_timer.start(200)
    
    def restore_widget_focus_policy(self, widgets):
        """Restore normal focus policy for widgets after group switch"""
        for widget in widgets:
            if widget:
                widget.setFocusPolicy(Qt.StrongFocus)
    
    def restore_widget_capabilities(self, widgets):
        """Restore focus policy and resize handling for widgets after group switch"""
        for widget in widgets:
            if widget:
                # Restore focus policy
                widget.setFocusPolicy(Qt.StrongFocus)
                # Re-enable PTY resize handling
                if hasattr(widget, 'resize_enabled'):
                    widget.resize_enabled = True
        
        # Mark that group switch is complete
        self.is_switching = False
    
    def add_default_tabs_for_group(self, group_name):
        """Add default tabs for a new group"""
        default_shell = os.environ.get('SHELL', '/bin/bash')
        self.tabs_per_group[group_name] = [
            {'name': 'Tab 1', 'shell': default_shell}
        ]
    
    def save_and_cache_current_group(self):
        """Save tab info and cache terminal widgets for current group"""
        if not self.current_group:
            return
        
        tabs_info = []
        widgets_cache = []
        
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget:
                tab_text = self.tab_widget.tabText(i)
                shell = widget.shell if hasattr(widget, 'shell') else '/bin/bash'
                
                # Strip shell indicator from name
                base_name = tab_text
                if '[' in tab_text and ']' in tab_text:
                    base_name = tab_text.rsplit('[', 1)[0].strip()
                
                # Save tab info
                tabs_info.append({
                    'name': base_name,
                    'shell': shell
                })
                
                # Cache the widget
                widgets_cache.append((base_name, shell, widget))
        
        self.tabs_per_group[self.current_group] = tabs_info
        self.terminal_widgets_cache[self.current_group] = widgets_cache
    
    def save_current_group_tabs(self):
        """Save current tabs to current group storage"""
        if not self.current_group:
            return
        
        tabs_info = []
        widgets_cache = []
        
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget:
                tab_text = self.tab_widget.tabText(i)
                shell = widget.shell if hasattr(widget, 'shell') else '/bin/bash'
                
                # Strip shell indicator from name (e.g., "Tab 1 [zsh]" -> "Tab 1")
                # This prevents duplication when restoring
                base_name = tab_text
                if '[' in tab_text and ']' in tab_text:
                    # Remove the last [shell] indicator
                    base_name = tab_text.rsplit('[', 1)[0].strip()
                
                tabs_info.append({
                    'name': base_name,
                    'shell': shell
                })
                
                # Also update the widget cache to keep it in sync
                widgets_cache.append((base_name, shell, widget))
        
        self.tabs_per_group[self.current_group] = tabs_info
        self.terminal_widgets_cache[self.current_group] = widgets_cache
    
    def save_and_notify_tab_change(self):
        """Save current group tabs AND notify about the change - use only when tabs are modified"""
        self.save_current_group_tabs()
        if self.tabs_changed_callback:
            self.tabs_changed_callback()
    
    def rename_group(self, old_name, new_name):
        """Handle group rename - update all internal references"""
        # Update cache key
        if old_name in self.terminal_widgets_cache:
            self.terminal_widgets_cache[new_name] = self.terminal_widgets_cache.pop(old_name)
        
        # Update tabs_per_group key
        if old_name in self.tabs_per_group:
            self.tabs_per_group[new_name] = self.tabs_per_group.pop(old_name)
        
        # Update current_group if it's the one being renamed
        if self.current_group == old_name:
            self.current_group = new_name
    
    def delete_group(self, group_name):
        """Handle group deletion - clean up all associated tabs and widgets"""
        # If this is the current group, close all visible tabs
        if self.current_group == group_name:
            # Close all tabs in the current view
            while self.tab_widget.count() > 0:
                widget = self.tab_widget.widget(0)
                self.tab_widget.removeTab(0)
                if widget:
                    widget.deleteLater()
            
            # Clear current group reference
            self.current_group = None
        
        # Clean up cached widgets for this group
        if group_name in self.terminal_widgets_cache:
            # Delete all cached terminal widgets
            for name, shell, widget in self.terminal_widgets_cache[group_name]:
                if widget and widget != self.tab_widget.currentWidget():
                    widget.deleteLater()
            del self.terminal_widgets_cache[group_name]
        
        # Clean up tabs data for this group
        if group_name in self.tabs_per_group:
            del self.tabs_per_group[group_name]
    
    # ===== State Persistence Methods =====
    
    def get_all_tabs_info(self):
        """Get all tabs organized by group for state saving"""
        # Save current group first
        self.save_current_group_tabs()
        return self.tabs_per_group.copy()
    
    def restore_tabs(self, tabs_per_group):
        """Restore all tabs from saved state"""
        self.tabs_per_group = tabs_per_group or {}
        # Tabs will be loaded when groups are selected
    
    def apply_preferences(self, prefs_manager):
        """Apply preferences to all existing terminals"""
        # Update each terminal's viewport highlight color
        for i in range(self.tab_widget.count()):
            terminal = self.tab_widget.widget(i)
            if terminal and hasattr(terminal, 'canvas'):
                if hasattr(terminal.canvas, 'refresh_viewport_highlight_color'):
                    terminal.canvas.refresh_viewport_highlight_color()
    
    # ===== Tab Navigation Methods =====
    
    def eventFilter(self, obj, event):
        """Filter events to detect tab bar resizes and button right-clicks"""
        from PyQt5.QtCore import QEvent, Qt
        
        # Safety check: ensure widgets are initialized
        if not hasattr(self, 'tab_widget') or not hasattr(self, 'left_nav_btn') or not hasattr(self, 'right_nav_btn'):
            return super().eventFilter(obj, event)
        
        # Handle tab bar resize events
        if obj == self.tab_widget.tabBar() and event.type() in [QEvent.Resize, QEvent.Show]:
            # Update navigation buttons when tab bar resizes
            if hasattr(self, 'nav_update_timer'):
                self.nav_update_timer.start(100)
        
        # Handle right-click on left navigation button
        elif obj == self.left_nav_btn and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self.show_left_nav_menu(event.pos())
                return True
        
        # Handle right-click on right navigation button
        elif obj == self.right_nav_btn and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self.show_right_nav_menu(event.pos())
                return True
        
        return super().eventFilter(obj, event)
    
    def scroll_tabs_left(self):
        """Scroll tabs to the left (show earlier tabs)"""
        tab_bar = self.tab_widget.tabBar()
        current_index = self.tab_widget.currentIndex()
        
        # Find the first visible tab
        first_visible = self.find_first_visible_tab()
        
        if first_visible > 0:
            # Move to the previous tab - Qt will auto-scroll
            target_index = first_visible - 1
            self.tab_widget.setCurrentIndex(target_index)
        elif current_index > 0:
            # If we can't detect visibility, just move one tab left
            target_index = current_index - 1
            self.tab_widget.setCurrentIndex(target_index)
        
        QTimer.singleShot(150, self.update_navigation_buttons)
    
    def scroll_tabs_right(self):
        """Scroll tabs to the right (show later tabs)"""
        tab_bar = self.tab_widget.tabBar()
        current_index = self.tab_widget.currentIndex()
        
        # Find the last visible tab
        last_visible = self.find_last_visible_tab()
        
        if last_visible < self.tab_widget.count() - 1:
            # Move to the next tab - Qt will auto-scroll
            target_index = last_visible + 1
            self.tab_widget.setCurrentIndex(target_index)
        elif current_index < self.tab_widget.count() - 1:
            # If we can't detect visibility, just move one tab right
            target_index = current_index + 1
            self.tab_widget.setCurrentIndex(target_index)
        
        QTimer.singleShot(150, self.update_navigation_buttons)
    
    def find_first_visible_tab(self):
        """Find the index of the first visible tab"""
        tab_bar = self.tab_widget.tabBar()
        # Get the visible area of the tab bar (excluding our custom buttons)
        tab_bar_x = tab_bar.x()
        
        for i in range(self.tab_widget.count()):
            tab_rect = tab_bar.tabRect(i)
            # Check if tab's left edge is visible within the tab bar's viewport
            if tab_rect.x() >= 0 and tab_rect.left() >= tab_bar_x:
                return i
        return 0
    
    def find_last_visible_tab(self):
        """Find the index of the last visible tab"""
        tab_bar = self.tab_widget.tabBar()
        # Get the visible width of the tab bar
        tab_bar_width = tab_bar.width()
        tab_bar_x = tab_bar.x()
        visible_width = tab_bar_x + tab_bar_width
        
        for i in range(self.tab_widget.count() - 1, -1, -1):
            tab_rect = tab_bar.tabRect(i)
            # Check if tab's right edge is fully visible
            if tab_rect.right() <= visible_width and tab_rect.x() >= 0:
                return i
        return self.tab_widget.count() - 1
    
    def count_hidden_tabs_left(self):
        """Count how many tabs are hidden to the left"""
        first_visible = self.find_first_visible_tab()
        return first_visible
    
    def count_hidden_tabs_right(self):
        """Count how many tabs are hidden to the right"""
        last_visible = self.find_last_visible_tab()
        return self.tab_widget.count() - 1 - last_visible
    
    def update_navigation_buttons(self):
        """Update navigation button enabled state and labels - buttons always visible"""
        # Always hide Qt's default scroll buttons
        self.hide_qt_scroll_buttons()
        
        if self.tab_widget.count() <= 1:
            # No navigation needed for 0 or 1 tabs - disable buttons
            self.left_nav_btn.setEnabled(False)
            self.left_nav_btn.setText("◀")
            self.right_nav_btn.setEnabled(False)
            self.right_nav_btn.setText("▶")
            return
        
        tab_bar = self.tab_widget.tabBar()
        
        # Force immediate update of tab bar geometry
        tab_bar.updateGeometry()
        
        # Check if any tabs are hidden by looking at their positions
        tabs_overflow = False
        first_visible_idx = -1
        last_visible_idx = -1
        
        for i in range(self.tab_widget.count()):
            tab_rect = tab_bar.tabRect(i)
            # Check if tab is visible (x position is within tab bar width)
            if tab_rect.x() >= 0 and tab_rect.right() <= tab_bar.width():
                if first_visible_idx == -1:
                    first_visible_idx = i
                last_visible_idx = i
            elif tab_rect.x() < 0 or tab_rect.right() > tab_bar.width():
                tabs_overflow = True
        
        # Enable/disable navigation buttons based on overflow
        if tabs_overflow or first_visible_idx > 0 or last_visible_idx < self.tab_widget.count() - 1:
            # Count hidden tabs
            hidden_left = self.count_hidden_tabs_left()
            hidden_right = self.count_hidden_tabs_right()
            
            # Update left button
            if hidden_left > 0:
                self.left_nav_btn.setText(f"◀{hidden_left}")  # Compact format
                self.left_nav_btn.setEnabled(True)
            else:
                self.left_nav_btn.setText("◀")
                self.left_nav_btn.setEnabled(False)
            
            # Update right button
            if hidden_right > 0:
                self.right_nav_btn.setText(f"{hidden_right}▶")  # Compact format
                self.right_nav_btn.setEnabled(True)
            else:
                self.right_nav_btn.setText("▶")
                self.right_nav_btn.setEnabled(False)
        else:
            # All tabs fit - disable navigation buttons
            self.left_nav_btn.setText("◀")
            self.left_nav_btn.setEnabled(False)
            self.right_nav_btn.setText("▶")
            self.right_nav_btn.setEnabled(False)
    
    def get_hidden_tabs_left(self):
        """Get list of (index, name) tuples for tabs hidden on the left"""
        first_visible = self.find_first_visible_tab()
        hidden_tabs = []
        
        for i in range(first_visible):
            tab_name = self.tab_widget.tabText(i)
            hidden_tabs.append((i, tab_name))
        
        return hidden_tabs
    
    def get_hidden_tabs_right(self):
        """Get list of (index, name) tuples for tabs hidden on the right"""
        last_visible = self.find_last_visible_tab()
        hidden_tabs = []
        
        for i in range(last_visible + 1, self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            hidden_tabs.append((i, tab_name))
        
        return hidden_tabs
    
    def show_left_nav_menu(self, position):
        """Show context menu with hidden tabs on the left"""
        # Only show menu if button is enabled
        if not self.left_nav_btn.isEnabled():
            return
            
        hidden_tabs = self.get_hidden_tabs_left()
        
        if not hidden_tabs:
            return
        
        menu = QMenu(self)
        
        # Add a header
        header_action = QAction("Hidden Tabs (Left)", self)
        header_action.setEnabled(False)
        menu.addAction(header_action)
        menu.addSeparator()
        
        # Add each hidden tab
        for index, tab_name in hidden_tabs:
            action = QAction(tab_name, self)
            # Use lambda with default argument to capture index correctly
            action.triggered.connect(lambda checked=False, idx=index: self.navigate_to_tab(idx))
            menu.addAction(action)
        
        # Style the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 8px 25px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
            QMenu::item:disabled {
                color: #888;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0px;
            }
        """)
        
        # Show menu at button position
        menu.exec_(self.left_nav_btn.mapToGlobal(position))
    
    def show_right_nav_menu(self, position):
        """Show context menu with hidden tabs on the right"""
        # Only show menu if button is enabled
        if not self.right_nav_btn.isEnabled():
            return
            
        hidden_tabs = self.get_hidden_tabs_right()
        
        if not hidden_tabs:
            return
        
        menu = QMenu(self)
        
        # Add a header
        header_action = QAction("Hidden Tabs (Right)", self)
        header_action.setEnabled(False)
        menu.addAction(header_action)
        menu.addSeparator()
        
        # Add each hidden tab
        for index, tab_name in hidden_tabs:
            action = QAction(tab_name, self)
            # Use lambda with default argument to capture index correctly
            action.triggered.connect(lambda checked=False, idx=index: self.navigate_to_tab(idx))
            menu.addAction(action)
        
        # Style the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 8px 25px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
            QMenu::item:disabled {
                color: #888;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0px;
            }
        """)
        
        # Show menu at button position
        menu.exec_(self.right_nav_btn.mapToGlobal(position))
    
    def navigate_to_tab(self, index):
        """Navigate to a specific tab by index"""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
            # Update navigation buttons after navigation
            self.nav_update_timer.start(100)

