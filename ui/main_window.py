"""Main application window"""

import asyncio
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSplitter, QTabWidget, QMessageBox, QPushButton, QToolBar, QAction, QMenuBar, QMenu,
                             QLabel, QSpinBox, QFileDialog)
from PyQt5.QtCore import Qt, QSettings, QTimer
from PyQt5.QtGui import QIcon, QKeySequence
from ui.terminal_group_panel import TerminalGroupPanel
from ui.button_panel import ButtonPanel
from ui.terminal_tabs import TerminalTabs
from ui.preferences_dialog import PreferencesDialog
from ui.help_dialog import HelpDialog
from ui.command_history_dialog import CommandHistoryDialog
from ui.minimap_widget import MinimapPanel
from ui.connection_logo_widget import ConnectionLogoWidget
from ui.notes_dialog import NotesDialog
from core.state_manager import StateManager
from core.preferences_manager import PreferencesManager
from core.command_history_manager import CommandHistoryManager
from core.notes_manager import NotesManager
from core.connectivity import ConnectivityChecker
import sys
import os
from pathlib import Path

class MainWindow(QMainWindow):
    """Main application window with all components"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings()
        self.state_manager = StateManager()
        self.prefs_manager = PreferencesManager()
        self.history_manager = CommandHistoryManager()
        self.notes_manager = NotesManager()
        self.resize_enable_timer = None  # Track the timer for re-enabling resize
        
        # Set window icon
        self.set_window_icon()
        
        self.init_ui()
        # Note: async initialization will be done separately via initialize_async()
    
    async def initialize_async(self):
        """Initialize async components - call this after __init__"""
        # Load all data files concurrently (independent operations)
        await asyncio.gather(
            self.prefs_manager.load_preferences(),
            self.history_manager.load_history(),
            self._restore_geometry_settings_async(),
            self._restore_application_state_async()
        )
    
    def set_window_icon(self):
        """Set the window icon from the logo file"""
        # Get the directory where this script is located
        if getattr(sys, 'frozen', False):
            # Running as a compiled executable
            base_path = Path(sys.executable).parent
        else:
            # Running as a script
            base_path = Path(__file__).parent.parent
        
        # Try PNG first, then SVG
        logo_path = base_path / 'assets' / 'logo_tb_terminal.png'
        if not logo_path.exists():
            logo_path = base_path / 'assets' / 'logo_tb_terminal.svg'
        
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        
    def setup_menu_bar(self):
        """Setup the menu bar
        
        NOTE: Keyboard shortcuts are intentionally removed from all menu items.
        This ensures that all keyboard input goes directly to the terminal when it has focus,
        allowing terminal applications (nano, vim, bash, etc.) to function properly.
        All menu functions are still accessible by clicking the menu items.
        """
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_tab_action = QAction("New Tab", self)
        # No keyboard shortcut - use menu only
        new_tab_action.triggered.connect(self.new_tab_shortcut)
        file_menu.addAction(new_tab_action)
        
        close_tab_action = QAction("Close Tab", self)
        # No keyboard shortcut - use menu only
        close_tab_action.triggered.connect(self.close_current_tab)
        file_menu.addAction(close_tab_action)
        
        file_menu.addSeparator()
        
        save_output_action = QAction("Save Terminal Output...", self)
        # No keyboard shortcut - use menu only
        save_output_action.triggered.connect(self.save_terminal_output)
        file_menu.addAction(save_output_action)
        
        import_history_action = QAction("Import History File...", self)
        # No keyboard shortcut - use menu only
        import_history_action.triggered.connect(self.import_history_file)
        file_menu.addAction(import_history_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        # No keyboard shortcut - use menu only
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        # Command History Search
        history_search_action = QAction("Command History Search...", self)
        # No keyboard shortcut - use menu only
        history_search_action.triggered.connect(self.show_command_history_search)
        edit_menu.addAction(history_search_action)
        
        edit_menu.addSeparator()
        
        preferences_action = QAction("Preferences...", self)
        # No keyboard shortcut - use menu only
        preferences_action.triggered.connect(self.show_preferences)
        edit_menu.addAction(preferences_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        zoom_in_action = QAction("Zoom In", self)
        # No keyboard shortcut - use menu only
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        # No keyboard shortcut - use menu only
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        zoom_reset_action = QAction("Reset Zoom", self)
        # No keyboard shortcut - use menu only
        zoom_reset_action.triggered.connect(self.zoom_reset)
        view_menu.addAction(zoom_reset_action)
        
        view_menu.addSeparator()
        
        toggle_left_action = QAction("Toggle Groups Panel", self)
        toggle_left_action.triggered.connect(lambda: self.toggle_left_button.click())
        view_menu.addAction(toggle_left_action)
        
        toggle_right_action = QAction("Toggle Buttons Panel", self)
        toggle_right_action.triggered.connect(lambda: self.toggle_right_button.click())
        view_menu.addAction(toggle_right_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        help_action = QAction("Help & Documentation", self)
        # No keyboard shortcut - use menu only
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
    
    def show_preferences(self):
        """Show preferences dialog"""
        dialog = PreferencesDialog(self)
        dialog.preferences_changed.connect(self.on_preferences_changed)
        dialog.exec_()
    
    def show_help(self):
        """Show help and documentation dialog"""
        dialog = HelpDialog(self)
        dialog.exec_()
    
    def show_command_history_search(self):
        """Show command history search dialog"""
        dialog = CommandHistoryDialog(self.history_manager, self)
        
        if dialog.exec_():
            # User selected a command
            command = dialog.get_selected_command()
            if command:
                # Insert command into current terminal
                self.insert_command_to_terminal(command)
    
    def on_preferences_changed(self):
        """Handle preferences changes"""
        # Reload preferences (use sync version for UI callback)
        self.prefs_manager.load_preferences_sync()
        
        # Notify all terminals to update their settings
        if hasattr(self, 'terminal_tabs'):
            self.terminal_tabs.apply_preferences(self.prefs_manager)
        
        # Update minimap visibility based on preference
        show_minimap = self.prefs_manager.get('terminal', 'show_minimap', True)
        current_minimap_visible = self.minimap_panel.isVisible()
        if show_minimap != current_minimap_visible:
            self.toggle_minimap_panel(show_minimap)
        
        # Refresh minimap colors based on new preferences
        if hasattr(self, 'minimap_panel'):
            self.minimap_panel.refresh_colors()

        # Update connectivity checker if configured
        try:
            probe_host = self.prefs_manager.get('network', 'probe_host', '8.8.8.8')
            probe_port = int(self.prefs_manager.get('network', 'probe_port', 53))
            probe_interval = int(self.prefs_manager.get('network', 'probe_interval', 5))
            probe_timeout = int(self.prefs_manager.get('network', 'probe_timeout', 2))

            # Restart checker with new settings, preserving running state
            was_running = False
            if hasattr(self, '_connectivity_checker') and self._connectivity_checker:
                try:
                    was_running = getattr(self._connectivity_checker, '_running', False)
                    self._connectivity_checker.stop()
                except Exception:
                    pass
                self._connectivity_checker = None

            self._connectivity_checker = ConnectivityChecker(interval=probe_interval, host=(probe_host, probe_port), timeout=probe_timeout)
            if hasattr(self, 'bottom_connection_logo'):
                self._connectivity_checker.status_changed.connect(self.bottom_connection_logo.set_connected)
                self._connectivity_checker.probing.connect(self.bottom_connection_logo.set_probing)
            # Restart only if previously running
            if was_running:
                try:
                    self._connectivity_checker.start()
                except Exception:
                    pass
        except Exception:
            pass

    def _toggle_connectivity_checker(self):
        """Toggle the background connectivity checker on logo click."""
        try:
            if not hasattr(self, '_connectivity_checker') or not self._connectivity_checker:
                return

            # If running, stop it
            if getattr(self._connectivity_checker, '_running', False):
                try:
                    self._connectivity_checker.stop()
                except Exception:
                    pass
                # Update UI to show stopped state
                if hasattr(self, 'bottom_connection_logo'):
                    self.bottom_connection_logo.set_probing(False)
                    self.bottom_connection_logo.set_connected(False)
            else:
                # Start checker
                try:
                    self._connectivity_checker.start()
                except Exception:
                    pass
        except Exception:
            pass
        
        QMessageBox.information(
            self, "Preferences Saved",
            "Preferences have been saved. Some changes may require restarting terminals to take effect."
        )
    
    def setup_shortcuts(self):
        """Setup application-wide keyboard shortcuts
        
        IMPORTANT: We use Cmd/Shift+Cmd shortcuts on macOS which don't interfere
        with terminal applications (which use Ctrl keys). These are window-level
        operations that match macOS Terminal.app behavior.
        
        Terminal applications receive all Ctrl+key combinations unmodified.
        """
        is_macos = sys.platform == 'darwin'
        
        if is_macos:
            # Shift+Cmd+N: New window (future implementation)
            # For now, just create a new tab
            new_window_action = QAction("New Window", self)
            new_window_action.setShortcut("Shift+Meta+N")
            new_window_action.triggered.connect(self.new_tab_shortcut)
            self.addAction(new_window_action)
            
            # Shift+Cmd+T: New Tab (standard macOS)
            new_tab_action = QAction("New Tab", self)
            new_tab_action.setShortcut("Shift+Meta+T")
            new_tab_action.triggered.connect(self.new_tab_shortcut)
            self.addAction(new_tab_action)
            
            # Shift+Cmd+W: Close window (for now, close current tab)
            close_window_action = QAction("Close Window", self)
            close_window_action.setShortcut("Shift+Meta+W")
            close_window_action.triggered.connect(self.close_current_tab)
            self.addAction(close_window_action)
            
            # Option+Cmd+W: Close other tabs
            close_other_tabs_action = QAction("Close Other Tabs", self)
            close_other_tabs_action.setShortcut("Alt+Meta+W")
            close_other_tabs_action.triggered.connect(self.close_other_tabs)
            self.addAction(close_other_tabs_action)
    
    def new_tab_shortcut(self):
        """Create a new terminal tab"""
        if hasattr(self, 'terminal_tabs'):
            self.terminal_tabs.add_tab()
    
    def close_current_tab(self):
        """Close the currently active tab"""
        if hasattr(self, 'terminal_tabs'):
            current_index = self.terminal_tabs.currentIndex()
            if current_index >= 0:
                self.terminal_tabs.close_tab_at_index(current_index)
    
    def show_queue_status(self):
        """Show the queue status dialog"""
        from ui.queue_status_dialog import QueueStatusDialog
        
        dialog = QueueStatusDialog(
            self.button_panel,
            self.terminal_tabs,
            parent=self
        )
        # Connect jump signal to switch terminals
        dialog.jump_to_terminal.connect(self.jump_to_terminal)
        dialog.exec_()
    
    def jump_to_terminal(self, terminal_widget):
        """Jump to (switch to) a specific terminal tab
        
        Args:
            terminal_widget: The terminal widget to switch to
        """
        if hasattr(self.terminal_tabs, 'tab_widget'):
            tab_widget = self.terminal_tabs.tab_widget
            for i in range(tab_widget.count()):
                if tab_widget.widget(i) == terminal_widget:
                    tab_widget.setCurrentIndex(i)
                    return
    
    def update_queue_status_badge(self):
        """Update the queue status button badge with number of active queues"""
        if not hasattr(self, 'queue_status_button') or not hasattr(self, 'button_panel'):
            return
        
        active_queues = self.button_panel.get_all_active_queues()
        count = len(active_queues)
        
        self.queue_status_button.setText(f"📋 Queues ({count})")
        
        # Change button color based on status
        if count > 0:
            # Has active queues - brighter blue
            self.queue_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: 1px solid #1976D2;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
            """)
        else:
            # No active queues - darker gray
            self.queue_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #424242;
                    color: #b0b0b0;
                    border: 1px solid #555;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4d4d4d;
                }
                QPushButton:pressed {
                    background-color: #333;
                }
            """)
    
    def interrupt_current_process(self):
        """Interrupt the running process in the current terminal"""
        if not hasattr(self, 'terminal_tabs'):
            return
        
        # Get the current terminal widget
        current_terminal = self.terminal_tabs.get_current_terminal()
        if not current_terminal:
            return
        
        # Check if the terminal has the interrupt_process method
        if hasattr(current_terminal, 'interrupt_process'):
            current_terminal.interrupt_process()
        elif hasattr(current_terminal, 'process'):
            # Direct access to process if interrupt_process method not available
            from PyQt5.QtCore import QProcess
            if current_terminal.process and current_terminal.process.state() == QProcess.Running:
                current_terminal.process.terminate()
    
    def save_terminal_output(self):
        """Save the current terminal output to a text file with colors and line numbers"""
        if not hasattr(self, 'terminal_tabs'):
            return
        
        # Get the current terminal widget
        current_terminal = self.terminal_tabs.get_current_terminal()
        if not current_terminal:
            QMessageBox.warning(self, "No Terminal", "No active terminal to save output from.")
            return
        
        # Check if the terminal has the save_output_to_file method
        if not hasattr(current_terminal, 'save_output_to_file'):
            QMessageBox.warning(self, "Not Supported", "This terminal type does not support saving output.")
            return
        
        # Show file dialog to choose save location
        # Get current tab name from the tab_widget
        current_index = self.terminal_tabs.tab_widget.currentIndex()
        tab_name = self.terminal_tabs.tab_widget.tabText(current_index) if current_index >= 0 else "terminal"
        default_filename = f"terminal_output_{tab_name.replace(' ', '_')}.txt"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Terminal Output",
            default_filename,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not filepath:
            return  # User cancelled
        
        # Save the output
        success = current_terminal.save_output_to_file(filepath)
        
        if success:
            QMessageBox.information(self, "Success", f"Terminal output saved to:\n{filepath}")
        else:
            QMessageBox.critical(self, "Error", "Failed to save terminal output. Check console for details.")
    
    def close_other_tabs(self):
        """Close all tabs except the current one (macOS Terminal.app style)"""
        if hasattr(self, 'terminal_tabs'):
            current_index = self.terminal_tabs.currentIndex()
            if current_index >= 0:
                # Close tabs after current index first (to maintain indices)
                tab_count = self.terminal_tabs.count()
                for i in range(tab_count - 1, current_index, -1):
                    self.terminal_tabs.close_tab_at_index(i)
                # Then close tabs before current index
                for i in range(current_index - 1, -1, -1):
                    self.terminal_tabs.close_tab_at_index(i)
    
    def zoom_in(self):
        """Increase font size in current terminal"""
        if hasattr(self, 'terminal_tabs') and hasattr(self.terminal_tabs, 'tab_widget'):
            current_terminal = self.terminal_tabs.tab_widget.currentWidget()
            if current_terminal and hasattr(current_terminal, 'font_size_spin'):
                current_size = current_terminal.font_size_spin.value()
                current_terminal.font_size_spin.setValue(min(current_size + 1, 24))
    
    def zoom_out(self):
        """Decrease font size in current terminal"""
        if hasattr(self, 'terminal_tabs') and hasattr(self.terminal_tabs, 'tab_widget'):
            current_terminal = self.terminal_tabs.tab_widget.currentWidget()
            if current_terminal and hasattr(current_terminal, 'font_size_spin'):
                current_size = current_terminal.font_size_spin.value()
                current_terminal.font_size_spin.setValue(max(current_size - 1, 8))
    
    def zoom_reset(self):
        """Reset font size to default"""
        if hasattr(self, 'terminal_tabs') and hasattr(self.terminal_tabs, 'tab_widget'):
            current_terminal = self.terminal_tabs.tab_widget.currentWidget()
            if current_terminal and hasattr(current_terminal, 'font_size_spin'):
                current_terminal.font_size_spin.setValue(13)  # Default size
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Terminal Browser")
        self.setMinimumSize(1200, 700)
        
        # Setup menu bar
        self.setup_menu_bar()
        
        # Setup application shortcuts
        self.setup_shortcuts()
        
        # Create toolbar with all buttons
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        
        # Toggle button for left panel (Terminal Groups)
        self.toggle_left_button = QPushButton("◀ Groups")
        self.toggle_left_button.setCheckable(True)
        self.toggle_left_button.setChecked(True)
        self.toggle_left_button.clicked.connect(self.toggle_left_panel)
        self.toggle_left_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:checked {
                background-color: #5d5d5d;
            }
        """)
        toolbar.addWidget(self.toggle_left_button)
        
        # Add spacer to center the preferences/help and logo group
        from PyQt5.QtWidgets import QWidget as ToolbarSpacer, QSizePolicy
        left_spacer = ToolbarSpacer()
        left_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(left_spacer)

        # Create centered group: Preferences, Logo, Help
        center_widget = QWidget()
        from PyQt5.QtWidgets import QHBoxLayout
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        preferences_btn = QPushButton("⚙ Preferences")
        preferences_btn.clicked.connect(self.show_preferences)
        preferences_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        center_layout.addWidget(preferences_btn)

        # (center logo removed) keep Preferences and Help only

        help_btn = QPushButton("❓ Help")
        help_btn.clicked.connect(self.show_help)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        center_layout.addWidget(help_btn)

        toolbar.addWidget(center_widget)
        
        # Add spacer to center the preferences button
        right_spacer = ToolbarSpacer()
        right_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(right_spacer)
        
        # Toggle button for right panel (Buttons)
        self.toggle_right_button = QPushButton("Buttons ▶")
        self.toggle_right_button.setCheckable(True)
        self.toggle_right_button.setChecked(True)
        self.toggle_right_button.clicked.connect(self.toggle_right_panel)
        self.toggle_right_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:checked {
                background-color: #5d5d5d;
            }
        """)
        toolbar.addWidget(self.toggle_right_button)
        
        # Style the toolbar
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d2d;
                border: none;
                spacing: 5px;
                padding: 5px;
            }
        """)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create outer vertical layout for main content and bottom button
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Create main splitter for four panels (groups, terminals, minimap, buttons)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(0)  # No handle width for seamless appearance
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
                border: none;
            }
        """)
        
        # Left panel - Terminal Groups
        self.terminal_group_panel = TerminalGroupPanel()
        self.main_splitter.addWidget(self.terminal_group_panel)
        
        # Center panel - Terminal Tabs Area
        self.terminal_tabs = TerminalTabs()
        # Set up callback for capturing commands from terminal input
        self.terminal_tabs.command_executed_callback = self.on_terminal_command_executed
        # Set up callback for viewport scroll events to update minimap immediately
        self.terminal_tabs.viewport_scrolled_callback = self.on_terminal_viewport_scrolled
        # Set up callback for tab closing (for queue cleanup)
        self.terminal_tabs.tab_closing_callback = self.on_terminal_tab_closing
        # Set up callback for when tabs structure changes (add/remove/rename/reorder)
        self.terminal_tabs.tabs_changed_callback = self.save_application_state
        self.main_splitter.addWidget(self.terminal_tabs)
        
        # Connect terminal tab changes to minimap updates
        # TerminalTabs has a tab_widget member which is the actual QTabWidget
        if hasattr(self.terminal_tabs, 'tab_widget'):
            self.terminal_tabs.tab_widget.currentChanged.connect(self.on_terminal_tab_changed)
        
        # Minimap panel
        self.minimap_panel = MinimapPanel()
        self.minimap_panel.position_clicked.connect(self.on_minimap_clicked)
        self.minimap_panel.viewport_dragged.connect(self.on_minimap_viewport_dragged)
        self.minimap_panel.center_line_changed.connect(self.on_minimap_center_line_changed)
        self.main_splitter.addWidget(self.minimap_panel)
        
        # Right panel - Button Panel
        self.button_panel = ButtonPanel()
        self.main_splitter.addWidget(self.button_panel)
        
        # Set minimum widths for panels to ensure content visibility
        # Group panel and button panel widths are calculated dynamically based on content
        # (text width + 10px padding each side)
        self.minimap_panel.setMinimumWidth(20)  # Slim scrollbar style
        self.minimap_panel.setMaximumWidth(20)  # Fixed width, no stretching
        
        # Get the calculated optimal widths from panels
        optimal_group_width = self.terminal_group_panel.calculate_optimal_width()
        optimal_button_width = self.button_panel.calculate_optimal_width()
        
        # Set initial splitter sizes - use calculated widths for side panels
        self.main_splitter.setSizes([optimal_group_width, 600, 20, optimal_button_width])
        
        # Store original sizes for panel toggle
        self.left_panel_size = optimal_group_width
        self.minimap_panel_size = 100
        self.right_panel_size = optimal_button_width
        
        # Connect splitter resize event to terminal resize
        self.main_splitter.splitterMoved.connect(self.on_splitter_moved)
        
        # Connect signals
        self.terminal_group_panel.group_selected.connect(self.on_group_selected)
        self.terminal_group_panel.group_renamed.connect(self.on_group_renamed)
        self.terminal_group_panel.group_deleted.connect(self.on_group_deleted)
        self.terminal_group_panel.group_added.connect(self.on_group_added)
        self.button_panel.execute_command.connect(self.execute_command)
        self.button_panel.insert_command_to_terminal.connect(self.insert_command_to_terminal)
        self.button_panel.buttons_changed.connect(self.save_application_state)
        self.button_panel.queues_changed.connect(self.update_queue_status_badge)
        
        # Connect session recorder playback signals
        if hasattr(self.button_panel, 'session_recorder_widget'):
            self.button_panel.session_recorder_widget.playback_started.connect(self.on_playback_started)
            self.button_panel.session_recorder_widget.playback_stopped.connect(self.on_playback_stopped)
        
        # Store reference for state management
        self.current_group_index = 0
        
        outer_layout.addWidget(self.main_splitter, 1)
        
        # Create bottom bar with controls
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(10)
        bottom_bar.setStyleSheet("background-color: #2d2d2d; border-top: 1px solid #3e3e3e;")
        
        # Left side: Font Size control
        font_size_label = QLabel("Font Size:")
        font_size_label.setStyleSheet("color: #e0e0e0;")
        bottom_layout.addWidget(font_size_label)
        
        # Font size spinbox (will be connected to current terminal)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        font_size_pref = self.prefs_manager.get('terminal', 'font_size', 13)
        self.font_size_spin.setValue(font_size_pref)
        self.font_size_spin.setFixedWidth(60)
        self.font_size_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 3px;
                border-radius: 3px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4c4c4c;
                border: 1px solid #555;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5c5c5c;
            }
        """)
        self.font_size_spin.valueChanged.connect(self.on_global_font_size_changed)
        bottom_layout.addWidget(self.font_size_spin)
        
        # History button with file size
        self.history_button = QPushButton("📁 Check History: 0B")
        self.history_button.setToolTip("View archived terminal history")
        self.history_button.setFixedWidth(180)
        self.history_button.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #5c5c5c;
            }
        """)
        self.history_button.clicked.connect(self.open_history_viewer)
        bottom_layout.addWidget(self.history_button)
        
        # Notes button
        self.notes_button = QPushButton("📝 Notes")
        self.notes_button.setToolTip("Open notes for current tab")
        self.notes_button.setFixedWidth(120)
        self.notes_button.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #5c5c5c;
            }
        """)
        self.notes_button.clicked.connect(self.open_notes_dialog)
        bottom_layout.addWidget(self.notes_button)
        
        # Add stretch before center button
        bottom_layout.addStretch()
        
        # Center: Jump to Bottom button (initially hidden)
        self.jump_to_bottom_button = QPushButton("↓ Jump to Bottom")
        self.jump_to_bottom_button.setStyleSheet("""
            QPushButton {
                background-color: #4c4c4c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 5px 15px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5c5c5c;
            }
            QPushButton:pressed {
                background-color: #3c3c3c;
            }
        """)
        self.jump_to_bottom_button.clicked.connect(self.on_jump_to_bottom_clicked)
        self.jump_to_bottom_button.setVisible(False)  # Hidden by default
        bottom_layout.addWidget(self.jump_to_bottom_button)
        
        # Add stretch after center button
        bottom_layout.addStretch()
        # Network status indicator (to the left of Quick Actions) — replace small Wi‑Fi with globe logo
        try:
            # Use a smaller instance of the connection logo to match bottom bar scale
            # Use bundled assets (will work in both dev and packaged app)
            self.bottom_connection_logo = ConnectionLogoWidget(size=45)

            # Add queue status button
            self.queue_status_button = QPushButton("📋 Queues (0)")
            self.queue_status_button.clicked.connect(self.show_queue_status)
            self.queue_status_button.setToolTip("View status of all command queues")
            self.queue_status_button.setStyleSheet("""
                QPushButton {
                    background-color: #1976D2;
                    color: white;
                    border: 1px solid #0D47A1;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2196F3;
                }
                QPushButton:pressed {
                    background-color: #0D47A1;
                }
            """)
            bottom_layout.addWidget(self.queue_status_button)
            
            # Add interrupt button before connection logo
            self.interrupt_button = QPushButton("⏹ Interrupt")
            self.interrupt_button.clicked.connect(self.interrupt_current_process)
            self.interrupt_button.setToolTip("Interrupt running process (Ctrl+C)")
            self.interrupt_button.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    border: 1px solid #b71c1c;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #f44336;
                }
                QPushButton:pressed {
                    background-color: #c62828;
                }
            """)
            bottom_layout.addWidget(self.interrupt_button)
            
            # Default to offline until checker reports status
            self.bottom_connection_logo.set_connected(False)
            bottom_layout.addWidget(self.bottom_connection_logo)

            # Configure connectivity checker and start it automatically
            probe_host = self.prefs_manager.get('network', 'probe_host', '8.8.8.8')
            probe_port = int(self.prefs_manager.get('network', 'probe_port', 53))
            probe_interval = int(self.prefs_manager.get('network', 'probe_interval', 5))
            probe_timeout = int(self.prefs_manager.get('network', 'probe_timeout', 2))

            self._connectivity_checker = ConnectivityChecker(interval=probe_interval, host=(probe_host, probe_port), timeout=probe_timeout)
            # Connect signals
            self._connectivity_checker.status_changed.connect(self.bottom_connection_logo.set_connected)
            self._connectivity_checker.probing.connect(self.bottom_connection_logo.set_probing)

            # Start automatic periodic probing at application start
            try:
                self._connectivity_checker.start()
            except Exception:
                pass

            # Clicking the logo triggers an immediate one-shot probe (manual probe)
            try:
                self.bottom_connection_logo.clicked.connect(lambda: self._connectivity_checker.probe_now())
            except Exception:
                pass
        except Exception:
            self._connectivity_checker = None
        
        # Right side: Quick Actions button
        self.quick_action_button = QPushButton("⚡ Quick Actions")
        self.quick_action_button.clicked.connect(self.show_quick_actions)
        self.quick_action_button.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #cccccc;
                border: 1px solid #555;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        bottom_layout.addWidget(self.quick_action_button)
        
        outer_layout.addWidget(bottom_bar)

        # Center logo removed; bottom globe handles click-to-toggle
        
        main_layout.addLayout(outer_layout)
        
        # Set up minimap update timer
        self.minimap_update_timer = QTimer()
        self.minimap_update_timer.timeout.connect(self.update_minimap_content)
        self.minimap_update_timer.start(1000)  # Update every second
        
        # Set up jump to bottom button visibility timer
        self.jump_button_timer = QTimer()
        self.jump_button_timer.timeout.connect(self.update_jump_button_visibility)
        self.jump_button_timer.start(500)  # Check every 500ms
        
        # Initialize queue status badge
        self.update_queue_status_badge()
        
    def on_global_font_size_changed(self, size):
        """Handle global font size spinbox change"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'font_size_spin'):
            # Update the current terminal's font size spinbox
            current_terminal.font_size_spin.setValue(size)
    
    def open_history_viewer(self):
        """Open history viewer for current terminal"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'view_history_in_terminal'):
            current_terminal.view_history_in_terminal()
    
    def open_notes_dialog(self):
        """Open notes dialog - universal notes for all tabs"""
        # Use a fixed universal ID instead of tab-specific
        universal_id = "universal_notes"
        
        # Open notes dialog with universal notes
        dialog = NotesDialog(
            parent=self,
            notes_manager=self.notes_manager,
            tab_id=universal_id,
            tab_name="My Notes"
        )
        dialog.exec_()
    
    def update_history_button(self):
        """Update history button with current file size"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'get_history_file_size'):
            file_size = current_terminal.get_history_file_size()
            self.history_button.setText(f"📁 Check History: {file_size}")
        else:
            self.history_button.setText("📁 Check History: 0B")
    
    def import_history_file(self):
        """Import a .tbhist file into current terminal"""
        from PyQt5.QtWidgets import QFileDialog
        import os
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Terminal History",
            os.path.expanduser("~/.terminal_browser/history/"),
            "Terminal Browser History (*.tbhist);;All Files (*)"
        )
        
        if file_path:
            current_terminal = self.terminal_tabs.get_current_terminal()
            if current_terminal and hasattr(current_terminal, 'import_history_file'):
                current_terminal.import_history_file(file_path)
                # Update history button
                self.update_history_button()
    
    def on_jump_to_bottom_clicked(self):
        """Handle jump to bottom button click"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'force_scroll_to_bottom'):
            current_terminal.force_scroll_to_bottom()
    
    def update_jump_button_visibility(self):
        """Update the visibility of the jump to bottom button based on scroll position"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        
        if current_terminal and hasattr(current_terminal, 'is_at_bottom'):
            at_bottom = current_terminal.is_at_bottom()
            # Show button when NOT at bottom
            self.jump_to_bottom_button.setVisible(not at_bottom)
        else:
            # Hide if no terminal or terminal doesn't support the feature
            self.jump_to_bottom_button.setVisible(False)
        
        # Also sync the global font size spinbox with current terminal
        if current_terminal and hasattr(current_terminal, 'font_size_spin'):
            current_size = current_terminal.font_size_spin.value()
            if self.font_size_spin.value() != current_size:
                # Block signals to avoid recursive updates
                self.font_size_spin.blockSignals(True)
                self.font_size_spin.setValue(current_size)
                self.font_size_spin.blockSignals(False)
        
        # Update history button
        self.update_history_button()
        
    def on_group_selected(self, group_name, tab_index):
        """Handle terminal group selection"""
        # Cancel any pending resize enable timer from panel toggles
        if self.resize_enable_timer is not None:
            self.resize_enable_timer.stop()
            self.resize_enable_timer = None
        
        # Store current group index
        self.current_group_index = tab_index
        
        # Load tabs for this group
        self.terminal_tabs.load_group_tabs(group_name)
        
        # Load buttons for this group
        self.button_panel.load_group_buttons(group_name)
        
        # Set current terminal for queue display
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            self.button_panel.set_current_terminal(current_terminal)
        
        # Update minimap
        self.update_minimap_content()
    
    def on_terminal_tab_changed(self, index):
        """Handle terminal tab change"""
        # Update minimap when switching tabs
        self.update_minimap_content()
        
        # Update button panel to show new terminal's queue
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            self.button_panel.set_current_terminal(current_terminal)
    
    def on_terminal_tab_closing(self, terminal_widget):
        """Handle terminal tab about to be closed - cleanup its queue
        
        Args:
            terminal_widget: The terminal widget being closed
        """
        if terminal_widget:
            self.button_panel.remove_terminal_queue(terminal_widget)
    
    def safe_enable_terminal_resize(self):
        """Safely re-enable terminal resize only if not in the middle of a group switch"""
        # Check if a group switch is in progress by checking if terminals have resize disabled
        # If group switch has its own timer running, don't interfere
        if not self.terminal_tabs.is_switching_groups():
            self.terminal_tabs.set_all_terminals_resize_enabled(True)
        self.resize_enable_timer = None
    
    def on_splitter_moved(self, pos, index):
        """Handle splitter movement to resize terminal"""
        # Get current terminal
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'update_pty_size_from_widget'):
            # Trigger PTY resize with a short delay to allow splitter movement to complete
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, current_terminal.update_pty_size_from_widget)
    
    def on_group_added(self, group_name):
        """Handle terminal group addition"""
        # Save state after adding a new group
        self.save_application_state()
    
    def on_group_renamed(self, old_name, new_name):
        """Handle terminal group rename"""
        # Update terminal tabs cache and data
        self.terminal_tabs.rename_group(old_name, new_name)
        
        # Update button panel cache and data
        self.button_panel.rename_group(old_name, new_name)
        
        # Save state after renaming
        self.save_application_state()
    
    def on_group_deleted(self, group_name):
        """Handle terminal group deletion"""
        # Clean up terminal tabs and button panel for this group
        self.terminal_tabs.delete_group(group_name)
        self.button_panel.delete_group(group_name)
        
        # Save state after deletion
        self.save_application_state()
        
        # Note: The terminal_group_panel automatically selects the next group
        # and triggers on_group_selected which loads the tabs and buttons
    
    def toggle_left_panel(self):
        """Toggle visibility of the left panel (Terminal Groups)"""
        # Cancel any pending resize enable timer
        if self.resize_enable_timer is not None:
            self.resize_enable_timer.stop()
            self.resize_enable_timer = None
        
        # Disable PTY resizing to prevent prompt redraws during panel toggle
        self.terminal_tabs.set_all_terminals_resize_enabled(False)
        
        # Block updates during the resize to prevent intermediate redraws
        self.terminal_tabs.setUpdatesEnabled(False)
        
        if self.toggle_left_button.isChecked():
            # Show the panel
            self.terminal_group_panel.show()
            # Restore the panel size
            sizes = self.main_splitter.sizes()
            sizes[0] = self.left_panel_size
            self.main_splitter.setSizes(sizes)
            self.toggle_left_button.setText("◀ Groups")
        else:
            # Store current size before hiding
            sizes = self.main_splitter.sizes()
            if sizes[0] > 0:
                self.left_panel_size = sizes[0]
            # Hide the panel
            self.terminal_group_panel.hide()
            sizes[0] = 0
            self.main_splitter.setSizes(sizes)
            self.toggle_left_button.setText("▶ Groups")
        
        # Process events to ensure resize operations complete
        from PyQt5.QtCore import QTimer, QCoreApplication
        QCoreApplication.processEvents()
        
        # Re-enable updates
        self.terminal_tabs.setUpdatesEnabled(True)
        
        # Re-enable PTY resizing after panel toggle completes
        # Use longer delay to ensure all resize events have been processed
        self.resize_enable_timer = QTimer()
        self.resize_enable_timer.setSingleShot(True)
        self.resize_enable_timer.timeout.connect(lambda: self.safe_enable_terminal_resize())
        self.resize_enable_timer.start(200)
        
    def toggle_minimap_panel(self, show=None):
        """Toggle visibility of the minimap panel
        
        Args:
            show: If None, toggle. If True, show. If False, hide.
        """
        # Determine if we should show or hide
        if show is None:
            # Check current visibility
            show = not self.minimap_panel.isVisible()
        
        if show:
            # Show the panel
            self.minimap_panel.show()
            # Restore the panel size
            sizes = self.main_splitter.sizes()
            sizes[2] = self.minimap_panel_size
            self.main_splitter.setSizes(sizes)
        else:
            # Store current size before hiding
            sizes = self.main_splitter.sizes()
            if sizes[2] > 0:
                self.minimap_panel_size = sizes[2]
            # Hide the panel
            self.minimap_panel.hide()
            sizes[2] = 0
            self.main_splitter.setSizes(sizes)
    
    def on_minimap_clicked(self, position_ratio):
        """Handle minimap click - moves viewport highlighter to clicked position WITHOUT scrolling
        
        Args:
            position_ratio: The ratio (0.0-1.0) representing the clicked position in content
        """
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            # Calculate which line number corresponds to the clicked position
            if hasattr(current_terminal, 'get_all_text'):
                all_text = current_terminal.get_all_text()
                lines = all_text.split('\n')
                total_lines = len(lines)
                # Calculate the line number at the clicked position
                clicked_line = int(position_ratio * total_lines)
                clicked_line = max(0, min(clicked_line, total_lines - 1))
                # Move the viewport highlighter to the clicked line
                if hasattr(current_terminal, 'canvas') and hasattr(current_terminal.canvas, 'viewport_center_line'):
                    old_center_line = current_terminal.canvas.viewport_center_line
                    current_terminal.canvas.viewport_center_line = clicked_line
                    # Trigger canvas repaint to show new highlighter position
                    current_terminal.canvas.update()
                    # Update minimap to show the highlighter at the clicked position
                    if hasattr(self, 'minimap_panel') and self.minimap_panel:
                        self.minimap_panel.update()
                # Scroll the terminal to the clicked line as well
                self._do_scroll_to_line(current_terminal, clicked_line)
    
    def on_minimap_viewport_dragged(self, position_ratio):
        """Handle minimap viewport drag - scrolls terminal to dragged position
        
        Args:
            position_ratio: The ratio (0.0-1.0) representing where viewport should start
        """
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            # Get scrollbar
            scrollbar = None
            if hasattr(current_terminal, 'scroll_area'):
                scrollbar = current_terminal.scroll_area.verticalScrollBar()
            elif hasattr(current_terminal, 'canvas') and hasattr(current_terminal.canvas, 'verticalScrollBar'):
                scrollbar = current_terminal.canvas.verticalScrollBar()
            
            if scrollbar:
                # Calculate target scrollbar position
                total_range = scrollbar.maximum() - scrollbar.minimum() + scrollbar.pageStep()
                target_value = int(position_ratio * total_range)
                
                # Clamp to valid range
                target_value = max(scrollbar.minimum(), min(target_value, scrollbar.maximum()))
                
                # Set scrollbar value (this will trigger viewport updates automatically)
                scrollbar.setValue(target_value)
    
    def _do_scroll_to_line(self, terminal, line_number):
        """Scroll terminal to a specific line number using scrollbar value calculation
        
        Args:
            line_number: The DISPLAYED line number (including cumulative offset)
        """
        if terminal:
            # Check if terminal has its own scroll_to_line method - use it directly!
            if hasattr(terminal, 'scroll_to_line'):
                terminal.scroll_to_line(line_number)
                return
            
            pass
            
            # Get scrollbar
            scrollbar = None
            if hasattr(terminal, 'scroll_area'):
                scrollbar = terminal.scroll_area.verticalScrollBar()
            
            if not scrollbar:
                return
            
            # Get cumulative offset from canvas to convert displayed line to actual line index
            cumulative_offset = 0
            char_height = 15  # Default
            if hasattr(terminal, 'canvas'):
                if hasattr(terminal.canvas, '_cumulative_line_offset'):
                    cumulative_offset = terminal.canvas._cumulative_line_offset
                if hasattr(terminal.canvas, 'char_height'):
                    char_height = terminal.canvas.char_height
            
            # Convert displayed line number to actual line index (0-based)
            actual_line_index = line_number - cumulative_offset - 1  # -1 because line numbers are 1-based
            
            # Get total number of lines currently in memory
            all_text = terminal.get_all_text() if hasattr(terminal, 'get_all_text') else ""
            total_lines = len(all_text.split('\n')) if all_text else 0
            
            if total_lines == 0:
                return
            
            # Clamp actual line index to valid range
            actual_line_index = max(0, min(actual_line_index, total_lines - 1))
            
            
            # Get character height to calculate pixel position
            char_height = 15  # Default
            header_offset = 10  # Header offset in pixels
            if hasattr(terminal, 'canvas') and hasattr(terminal.canvas, 'char_height'):
                char_height = terminal.canvas.char_height
            
            # Calculate the pixel position of the target line
            # This is where the line is rendered in the canvas
            line_pixel_y = actual_line_index * char_height + header_offset
            
            # Calculate viewport height and scrollbar parameters
            viewport_height_pixels = scrollbar.pageStep()
            scroll_range = scrollbar.maximum() - scrollbar.minimum()
            
            # To center the line in the viewport, we want:
            # scrollbar_value = line_pixel_y - (viewport_height / 2)
            # This positions the viewport so the line appears in the center
            target_value = line_pixel_y - (viewport_height_pixels // 2)
            
            # Clamp to scrollbar range
            target_value = max(scrollbar.minimum(), min(target_value, scrollbar.maximum()))
            
            
            # Set scrollbar value
            scrollbar.setValue(target_value)
            
            # Force update the viewport
            if scrollbar.parent():
                scrollbar.parent().update()
            
            # Update the viewport center line for highlighting AND minimap viewport position
            if hasattr(terminal, 'update_viewport_range'):
                # Recalculate viewport position after scroll
                total_range = scrollbar.maximum() - scrollbar.minimum() + scrollbar.pageStep()
                actual_value = scrollbar.value()
                viewport_start = actual_value / total_range if total_range > 0 else 0
                viewport_height_ratio = scrollbar.pageStep() / total_range if total_range > 0 else 0
                terminal.update_viewport_range(viewport_start, viewport_height_ratio)
                
                # Update minimap viewport to reflect new scroll position
                if hasattr(self, 'minimap_panel') and self.minimap_panel:
                    self.minimap_panel.set_viewport(viewport_start, viewport_height_ratio)
    
    def _do_scroll(self, scrollbar, target_value, terminal):
        """Actually perform the scroll after a brief delay - positions viewport exactly where clicked"""
        if scrollbar:
            scrollbar.setValue(target_value)
            
            # Force update the viewport
            scrollbar.parent().update()
            
            # Update the viewport center line for highlighting
            # Calculate which line is at the center of the viewport
            if terminal and hasattr(terminal, 'update_viewport_range'):
                # Recalculate viewport position
                total_range = scrollbar.maximum() - scrollbar.minimum() + scrollbar.pageStep()
                if total_range > 0:
                    viewport_start = scrollbar.value() / total_range
                    viewport_height = scrollbar.pageStep() / total_range
                    # Only allow update_viewport_range to update highlighter if not blocked by user move
                    if hasattr(terminal, '_block_next_scroll_highlighter_update') and terminal._block_next_scroll_highlighter_update:
                        terminal._block_next_scroll_highlighter_update = False
                    else:
                        terminal.update_viewport_range(viewport_start, viewport_height)
                    # Update minimap viewport to reflect new scroll position
                    if hasattr(self, 'minimap_panel') and self.minimap_panel:
                        self.minimap_panel.set_viewport(viewport_start, viewport_height)
            
            # Clear the minimap update flag after a short delay
            if hasattr(terminal, '_updating_from_minimap'):
                QTimer.singleShot(100, lambda: setattr(terminal, '_updating_from_minimap', False))
    
    def on_minimap_center_line_changed(self, line_number):
        """Handle minimap center line change to update terminal highlight and scrollbar position
        
        When user interacts with the minimap (dragging viewport box or clicking), this synchronizes:
        1. The highlighted line number in the terminal
        2. The scrollbar position to center on that line
        """
        current_terminal = self.terminal_tabs.get_current_terminal()
        if not current_terminal:
            return
        
        # Prevent circular updates - if we're already updating from scrollbar, skip
        if hasattr(current_terminal, '_updating_from_scrollbar') and current_terminal._updating_from_scrollbar:
            return
        
        # Mark that we're updating from minimap to prevent circular updates
        if hasattr(current_terminal, '_updating_from_minimap'):
            current_terminal._updating_from_minimap = True
        
        # Update the canvas viewport center line for highlighting
        if hasattr(current_terminal, 'canvas') and hasattr(current_terminal.canvas, 'viewport_center_line'):
            old_center_line = current_terminal.canvas.viewport_center_line
            current_terminal.canvas.viewport_center_line = line_number
            current_terminal.canvas.update()
        
        # Scroll the terminal to center on this line
        if hasattr(current_terminal, 'scroll_to_line'):
            current_terminal.scroll_to_line(line_number)
        
        # Clear the flag after a short delay to ensure all updates complete
        if hasattr(current_terminal, '_updating_from_minimap'):
            QTimer.singleShot(50, lambda: setattr(current_terminal, '_updating_from_minimap', False))
    
    def update_minimap_content(self):
        """Update minimap with current terminal content"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            # Try to get terminal content
            content = ""
            if hasattr(current_terminal, 'get_all_text'):
                content = current_terminal.get_all_text()
            elif hasattr(current_terminal, 'toPlainText'):
                content = current_terminal.toPlainText()
            
            if content:
                self.minimap_panel.set_content(content)
            
            # Update viewport indicator
            scrollbar = None
            if hasattr(current_terminal, 'scroll_area'):
                scrollbar = current_terminal.scroll_area.verticalScrollBar()
            elif hasattr(current_terminal, 'canvas') and hasattr(current_terminal.canvas, 'verticalScrollBar'):
                scrollbar = current_terminal.canvas.verticalScrollBar()
            
            if scrollbar:
                total_range = scrollbar.maximum() - scrollbar.minimum() + scrollbar.pageStep()
                if total_range > 0:
                    viewport_start = scrollbar.value() / total_range
                    viewport_height = scrollbar.pageStep() / total_range
                    self.minimap_panel.set_viewport(viewport_start, viewport_height)
                    
                    # Update terminal's viewport range for line number highlighting
                    if hasattr(current_terminal, 'update_viewport_range'):
                        current_terminal.update_viewport_range(viewport_start, viewport_height)
    
    def on_terminal_viewport_scrolled(self, viewport_start, viewport_height):
        # If user scrolls, allow scroll-based highlighter update again
        current_terminal = self.terminal_tabs.get_current_terminal()
        if hasattr(current_terminal, '_block_scroll_highlighter_update_until_scroll') and current_terminal._block_scroll_highlighter_update_until_scroll:
            current_terminal._block_scroll_highlighter_update_until_scroll = False
        """Handle terminal viewport scroll event - update minimap immediately
        
        When user scrolls the terminal scrollbar, this synchronizes:
        1. The minimap viewport box position
        2. The viewport center line for highlighting
        
        Args:
            viewport_start: Viewport start position ratio (0.0-1.0)
            viewport_height: Viewport height ratio (0.0-1.0)
        """
        
        current_terminal = self.terminal_tabs.get_current_terminal()
        if not current_terminal:
            return
        
        # Prevent circular updates - if we're already updating from minimap, skip
        if hasattr(current_terminal, '_updating_from_minimap') and current_terminal._updating_from_minimap:
            return
        
        # Mark that we're updating from scrollbar to prevent circular updates
        if hasattr(current_terminal, '_updating_from_scrollbar'):
            current_terminal._updating_from_scrollbar = True
        
        # Update minimap viewport position
        if hasattr(self, 'minimap_panel') and self.minimap_panel:
            self.minimap_panel.set_viewport(viewport_start, viewport_height)
        
        # Update the terminal's viewport range (which calculates center line)
        # BUT skip if we're jumping to a specific line (center line already set explicitly)
        if hasattr(current_terminal, 'update_viewport_range'):
            if not (hasattr(current_terminal, '_jumping_to_line') and current_terminal._jumping_to_line):
                # Only allow update_viewport_range to update highlighter if not blocked by user move
                if hasattr(current_terminal, '_block_next_scroll_highlighter_update') and current_terminal._block_next_scroll_highlighter_update:
                    current_terminal._block_next_scroll_highlighter_update = False
                else:
                    current_terminal.update_viewport_range(viewport_start, viewport_height)
        
        # Clear the flag after a short delay to ensure paint events complete
        if hasattr(current_terminal, '_updating_from_scrollbar'):
            QTimer.singleShot(50, lambda: setattr(current_terminal, '_updating_from_scrollbar', False))
    
    def show_quick_actions(self):
        """Show quick action menu"""
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        
        # Clear terminal action
        clear_action = menu.addAction("🧹 Clear Terminal")
        clear_action.triggered.connect(self.quick_clear_terminal)
        
        # New tab action
        new_tab_action = menu.addAction("📄 New Tab")
        new_tab_action.triggered.connect(self.new_tab_shortcut)
        
        # Focus terminal action
        focus_action = menu.addAction("🎯 Focus Terminal")
        focus_action.triggered.connect(self.quick_focus_terminal)
        
        menu.addSeparator()
        
        # Copy last command
        copy_cmd_action = menu.addAction("📋 Copy Last Command")
        copy_cmd_action.triggered.connect(self.quick_copy_last_command)
        
        # Show command history
        history_action = menu.addAction("📜 Command History")
        history_action.triggered.connect(self.show_command_history_search)
        
        menu.addSeparator()
        
        # Zoom actions
        zoom_in_action = menu.addAction("🔍+ Zoom In")
        zoom_in_action.triggered.connect(self.zoom_in)
        
        zoom_out_action = menu.addAction("🔍- Zoom Out")
        zoom_out_action.triggered.connect(self.zoom_out)
        
        zoom_reset_action = menu.addAction("🔍= Reset Zoom")
        zoom_reset_action.triggered.connect(self.zoom_reset)
        
        # Show menu at button position
        menu.exec_(self.quick_action_button.mapToGlobal(self.quick_action_button.rect().topLeft()))
    
    def quick_clear_terminal(self):
        """Clear current terminal"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'clear'):
            current_terminal.clear()
    
    def quick_focus_terminal(self):
        """Focus current terminal"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            current_terminal.setFocus()
            if hasattr(current_terminal, 'canvas'):
                current_terminal.canvas.setFocus()
    
    def quick_copy_last_command(self):
        """Copy last executed command to clipboard"""
        from PyQt5.QtWidgets import QApplication
        
        # Get last command from history
        recent = self.history_manager.get_recent_commands(1)
        if recent:
            last_cmd = recent[0]['command']
            QApplication.clipboard().setText(last_cmd)
            
            # Show brief notification
            self.quick_action_button.setText(f"✓ Copied: {last_cmd[:50]}...")
            QTimer.singleShot(2000, lambda: self.quick_action_button.setText("⚡ Quick Actions: Clear Terminal | New Tab | Focus Terminal"))
        
    def toggle_right_panel(self):
        """Toggle visibility of the right panel (Button Panel)"""
        # Cancel any pending resize enable timer
        if self.resize_enable_timer is not None:
            self.resize_enable_timer.stop()
            self.resize_enable_timer = None
        
        # Disable PTY resizing to prevent prompt redraws during panel toggle
        self.terminal_tabs.set_all_terminals_resize_enabled(False)
        
        # Block updates during the resize to prevent intermediate redraws
        self.terminal_tabs.setUpdatesEnabled(False)
        
        if self.toggle_right_button.isChecked():
            # Show the panel
            self.button_panel.show()
            # Restore the panel size - also need to ensure other panels adjust
            sizes = self.main_splitter.sizes()
            # Calculate how much space to take from terminal area
            space_needed = self.right_panel_size
            if sizes[1] > space_needed:  # If terminal has enough space
                sizes[1] -= space_needed
                sizes[3] = space_needed
            else:
                sizes[3] = self.right_panel_size
            self.main_splitter.setSizes(sizes)
            self.toggle_right_button.setText("Buttons ▶")
        else:
            # Store current size before hiding
            sizes = self.main_splitter.sizes()
            if sizes[3] > 0:
                self.right_panel_size = sizes[3]
                # Give the space back to the terminal area
                sizes[1] += sizes[3]
            # Hide the panel completely
            self.button_panel.hide()
            # Set size to 0 to ensure no space is reserved
            sizes[3] = 0
            self.main_splitter.setSizes(sizes)
            self.toggle_right_button.setText("◀ Buttons")
        
        # Set minimum size to 0 when hidden to ensure complete collapse
        if not self.toggle_right_button.isChecked():
            self.button_panel.setMaximumWidth(0)
        else:
            self.button_panel.setMaximumWidth(16777215)  # Reset to default Qt maximum
        
        # Process events to ensure resize operations complete
        from PyQt5.QtCore import QTimer, QCoreApplication
        QCoreApplication.processEvents()
        
        # Re-enable updates
        self.terminal_tabs.setUpdatesEnabled(True)
        
        # Re-enable PTY resizing after panel toggle completes
        # Use longer delay to ensure all resize events have been processed
        self.resize_enable_timer = QTimer()
        self.resize_enable_timer.setSingleShot(True)
        self.resize_enable_timer.timeout.connect(lambda: self.safe_enable_terminal_resize())
        self.resize_enable_timer.start(200)
        
    def on_terminal_command_executed(self, command):
        """Handle command executed from terminal (typed directly)"""
        
        # Record command in history manager
        current_group = self.terminal_group_panel.get_current_group_name()
        current_terminal = self.terminal_tabs.get_current_terminal()
        working_dir = ""
        # Get current directory from terminal (use current_directory attribute)
        if current_terminal and hasattr(current_terminal, 'current_directory'):
            working_dir = current_terminal.current_directory
        
        self.history_manager.add_command(command, group=current_group, working_dir=working_dir)
        
        # Record command if session recorder is recording
        if hasattr(self.button_panel, 'session_recorder_widget'):
            self.button_panel.session_recorder_widget.record_command(command, working_dir)
    
    def execute_command(self, command, env_vars=None, target_terminal=None):
        """Execute a command in a specific terminal (from buttons/command book/queue)
        
        Args:
            command: The command to execute
            env_vars: Environment variables for the command
            target_terminal: The specific terminal to execute in (if None, uses current terminal)
        """
        # Use target_terminal if provided (from queue), otherwise use current terminal
        terminal = target_terminal if target_terminal else self.terminal_tabs.get_current_terminal()
        
        if terminal:
            # Record command in history manager
            current_group = self.terminal_group_panel.get_current_group_name()
            working_dir = ""
            if hasattr(terminal, 'get_working_directory'):
                working_dir = terminal.get_working_directory()
            
            self.history_manager.add_command(command, group=current_group, working_dir=working_dir)
            
            # Record command if session recorder is recording
            if hasattr(self.button_panel, 'session_recorder_widget'):
                self.button_panel.session_recorder_widget.record_command(command, working_dir)
            
            # Connect terminal's command_finished signal to its queue's on_command_complete
            # This ensures the queue waits for the actual command to finish before processing the next one
            if hasattr(terminal, 'command_finished'):
                queue = self.button_panel.get_queue_for_terminal(terminal)
                if queue:
                    # Disconnect any existing connections to avoid duplicates
                    try:
                        terminal.command_finished.disconnect(queue.on_command_complete)
                    except:
                        pass
                    # Connect to notify queue when command finishes
                    terminal.command_finished.connect(queue.on_command_complete)
            
            # Suppress directory updates for button-executed commands
            if hasattr(terminal, 'set_suppress_directory_updates'):
                terminal.set_suppress_directory_updates(True)
                # Re-enable when prompt appears (after command completes)
                if hasattr(terminal, 'prompt_ready'):
                    # Disconnect any existing connection to avoid duplicates
                    try:
                        terminal.prompt_ready.disconnect(self._re_enable_directory_updates_on_prompt)
                    except:
                        pass
                    # Connect to re-enable directory updates when prompt appears
                    # Use functools.partial to properly capture the terminal reference
                    from functools import partial
                    terminal.prompt_ready.connect(partial(self._re_enable_directory_updates_on_prompt, terminal))
            
            terminal.execute_command(command, env_vars)
            
            # Only set focus if executing in current terminal (not background execution)
            if not target_terminal or target_terminal == self.terminal_tabs.get_current_terminal():
                terminal.setFocus()
                if hasattr(terminal, 'canvas'):
                    terminal.canvas.setFocus()
        else:
            QMessageBox.warning(self, "No Terminal", 
                              "Please select a terminal first.")
    
    def _re_enable_directory_updates_on_prompt(self, terminal):
        """Re-enable directory updates when prompt appears after button command execution"""
        if terminal and hasattr(terminal, 'set_suppress_directory_updates'):
            # Only re-enable if not in playback mode
            if not hasattr(self, 'button_panel') or not hasattr(self.button_panel, 'session_recorder_widget'):
                terminal.set_suppress_directory_updates(False)
            elif not self.button_panel.session_recorder_widget.is_playing:
                terminal.set_suppress_directory_updates(False)
            # Disconnect this one-time connection
            try:
                terminal.prompt_ready.disconnect(self._re_enable_directory_updates_on_prompt)
            except:
                pass
    
    def insert_command_to_terminal(self, command):
        """Insert a command into the terminal without executing it"""
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal:
            # Ensure command is a string and preserve newlines
            if not isinstance(command, str):
                command = str(command)
            
            # Insert command into the terminal's input buffer
            if hasattr(current_terminal, 'insert_text'):
                # Use insert_text method which should handle multi-line commands
                current_terminal.insert_text(command)
            elif hasattr(current_terminal, 'command_input'):
                # For terminals with command_input widget
                current_terminal.command_input.setText(command)
                current_terminal.command_input.setFocus()
            else:
                # Fallback: try to send the text with newlines preserved
                if hasattr(current_terminal, 'send_text'):
                    current_terminal.send_text(command)
                elif hasattr(current_terminal, 'write_to_pty'):
                    # Direct PTY write to preserve all characters including newlines
                    current_terminal.write_to_pty(command)
    
    def on_playback_started(self):
        """Handle playback started - set terminal reference for prompt-based waiting"""                                                                         
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(self.button_panel, 'session_recorder_widget'):                                                                          
            self.button_panel.session_recorder_widget.set_current_terminal(current_terminal)                                                                    
            # Suppress directory updates during auto session playback
            if hasattr(current_terminal, 'set_suppress_directory_updates'):
                current_terminal.set_suppress_directory_updates(True)
            
            # Set focus to terminal so user can see the playback immediately
            current_terminal.setFocus()
            if hasattr(current_terminal, 'canvas'):
                current_terminal.canvas.setFocus()
            
    
    def on_playback_stopped(self):
        """Handle playback stopped - clear terminal reference"""
        # Re-enable directory updates after playback
        current_terminal = self.terminal_tabs.get_current_terminal()
        if current_terminal and hasattr(current_terminal, 'set_suppress_directory_updates'):
            current_terminal.set_suppress_directory_updates(False)
        if hasattr(self.button_panel, 'session_recorder_widget'):
            self.button_panel.session_recorder_widget.set_current_terminal(None)
    
    def restore_geometry_settings(self):
        """Restore window geometry from settings (sync version for compatibility)"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        splitter_state = self.settings.value("splitter_state")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)
        
        # Restore panel visibility
        left_visible = self.settings.value("left_panel_visible", True, type=bool)
        right_visible = self.settings.value("right_panel_visible", True, type=bool)
        
        self.toggle_left_button.setChecked(left_visible)
        self.toggle_right_button.setChecked(right_visible)
        
        if not left_visible:
            self.toggle_left_panel()
        if not right_visible:
            self.toggle_right_panel()
        
        # Restore minimap visibility from preferences
        minimap_visible = self.prefs_manager.get('terminal', 'show_minimap', True)
        if not minimap_visible:
            self.toggle_minimap_panel()
    
    async def _restore_geometry_settings_async(self):
        """Restore window geometry from settings asynchronously"""
        # Run synchronously but wrapped for async gather
        await asyncio.to_thread(self.restore_geometry_settings)
    
    async def save_application_state_async(self):
        """Save complete application state asynchronously"""
        state = {
            'groups': self.terminal_group_panel.get_all_groups(),
            'tabs': self.terminal_tabs.get_all_tabs_info(),
            'buttons_per_group': self.button_panel.get_all_buttons_by_group(),
            'files_per_group': self.button_panel.get_all_files_by_group(),
            'current_group': self.current_group_index
        }
        await self.state_manager.save_state(state)
    
    def save_application_state(self):
        """Save complete application state (sync version)"""
        state = {
            'groups': self.terminal_group_panel.get_all_groups(),
            'tabs': self.terminal_tabs.get_all_tabs_info(),
            'buttons_per_group': self.button_panel.get_all_buttons_by_group(),
            'files_per_group': self.button_panel.get_all_files_by_group(),
            'current_group': self.current_group_index
        }
        # Use asyncio.create_task to save asynchronously without blocking
        asyncio.create_task(self.state_manager.save_state(state))
    
    def restore_application_state(self):
        """Restore application state from previous session (sync version for compatibility)"""
        state = None
        try:
            # Attempt synchronous load (will be replaced by async version)
            import json
            import os
            if os.path.exists(self.state_manager.state_file):
                with open(self.state_manager.state_file, 'r') as f:
                    state = json.load(f)
        except Exception as e:
            pass
        if state:
            try:
                # Restore groups
                if 'groups' in state and state['groups']:
                    self.terminal_group_panel.restore_groups(state['groups'])
                
                # Restore tabs per group
                if 'tabs' in state and state['tabs']:
                    self.terminal_tabs.restore_tabs(state['tabs'])
                
                # Restore buttons per group
                if 'buttons_per_group' in state:
                    self.button_panel.restore_all_buttons(state['buttons_per_group'])
                
                # Restore files per group
                if 'files_per_group' in state:
                    self.button_panel.restore_all_files(state['files_per_group'])
                
                # Restore current group selection and load its tabs
                if 'current_group' in state:
                    self.current_group_index = state['current_group']
                    
            except Exception as e:
                pass
        # Always trigger first group selection to load tabs (for both restored and fresh state)
        # Use the select_group_at_index method which both highlights and loads the group
        if state and 'current_group' in state and state['current_group'] is not None:
            self.terminal_group_panel.select_group_at_index(state['current_group'])
        else:
            # Default to first group if no saved state
            self.terminal_group_panel.select_group_at_index(0)
    
    async def _restore_application_state_async(self):
        """Restore application state from previous session asynchronously"""
        state = await self.state_manager.load_state()
        if state:
            try:
                # Restore groups
                if 'groups' in state and state['groups']:
                    self.terminal_group_panel.restore_groups(state['groups'])
                
                # Restore tabs per group
                if 'tabs' in state and state['tabs']:
                    self.terminal_tabs.restore_tabs(state['tabs'])
                
                # Restore buttons per group
                if 'buttons_per_group' in state:
                    self.button_panel.restore_all_buttons(state['buttons_per_group'])
                
                # Restore files per group
                if 'files_per_group' in state:
                    self.button_panel.restore_all_files(state['files_per_group'])
                
                # Restore current group selection and load its tabs
                if 'current_group' in state:
                    self.current_group_index = state['current_group']
                    
            except Exception as e:
                print
        # Always trigger first group selection to load tabs (for both restored and fresh state)
        # Use the select_group_at_index method which both highlights and loads the group
        if state and 'current_group' in state and state['current_group'] is not None:
            self.terminal_group_panel.select_group_at_index(state['current_group'])
        else:
            # Default to first group if no saved state
            self.terminal_group_panel.select_group_at_index(0)
    
    def closeEvent(self, event):
        """Save settings before closing"""
        # Stop background connectivity checker if running
        try:
            if hasattr(self, '_connectivity_checker') and self._connectivity_checker:
                self._connectivity_checker.stop()
        except Exception:
            pass
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter_state", self.main_splitter.saveState())
        
        # Save panel visibility state
        self.settings.setValue("left_panel_visible", self.toggle_left_button.isChecked())
        self.settings.setValue("right_panel_visible", self.toggle_right_button.isChecked())
        
        # Save application state synchronously to ensure it completes before exit
        state = {
            'groups': self.terminal_group_panel.get_all_groups(),
            'tabs': self.terminal_tabs.get_all_tabs_info(),
            'buttons_per_group': self.button_panel.get_all_buttons_by_group(),
            'files_per_group': self.button_panel.get_all_files_by_group(),
            'current_group': self.current_group_index
        }
        
        # Use synchronous save during close to ensure completion before app exits
        try:
            import json
            from datetime import datetime
            state['last_saved'] = datetime.now().isoformat()
            with open(self.state_manager.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state on close: {e}")
        
        # Save command history synchronously
        try:
            self.history_manager.flush_save()
        except Exception as e:
            print(f"Error saving history on close: {e}")
        
        event.accept()

