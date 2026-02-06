"""Preferences dialog for application settings"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QLineEdit, QPushButton, QSpinBox,
                             QCheckBox, QComboBox, QColorDialog, QFileDialog,
                             QGroupBox, QFormLayout, QDialogButtonBox, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QKeySequence, QKeyEvent
from core.preferences_manager import PreferencesManager
from core.platform_manager import get_platform_manager
import os
import sys


class PreferencesDialog(QDialog):
    """Dialog for managing application preferences"""
    
    preferences_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prefs_manager = PreferencesManager()
        self.init_ui()
        self.load_current_preferences()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Preferences")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # Add tabs
        self.tabs.addTab(self.create_terminal_tab(), "Terminal")
        self.tabs.addTab(self.create_appearance_tab(), "Appearance")
        self.tabs.addTab(self.create_colors_tab(), "Colors")
        self.tabs.addTab(self.create_behavior_tab(), "Behavior")
        self.tabs.addTab(self.create_shortcuts_tab(), "Shortcuts")
        
        layout.addWidget(self.tabs)
        
        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults
        )
        button_box.accepted.connect(self.accept_changes)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.restore_defaults)
        
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def create_terminal_tab(self):
        """Create terminal settings tab"""
        # Create scroll area for the terminal tab
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # Create content widget
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Default directory group
        dir_group = QGroupBox("Default Directory")
        dir_layout = QHBoxLayout()
        
        self.default_dir_edit = QLineEdit()
        self.default_dir_edit.setPlaceholderText("Default starting directory for new terminals")
        dir_layout.addWidget(self.default_dir_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(browse_btn)
        
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # Font and Columns settings group
        font_group = QGroupBox("Font & Columns Settings")
        font_layout = QFormLayout()

        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems([
            "Menlo", "Monaco", "Courier New", "Consolas", 
            "Liberation Mono", "DejaVu Sans Mono", "Ubuntu Mono"
        ])
        self.font_family_combo.setEditable(True)
        font_layout.addRow("Font Family:", self.font_family_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setSuffix(" pt")
        font_layout.addRow("Font Size:", self.font_size_spin)

        self.terminal_columns_spin = QSpinBox()
        self.terminal_columns_spin.setRange(40, 2000)
        self.terminal_columns_spin.setValue(600)
        self.terminal_columns_spin.setSuffix(" columns")
        self.terminal_columns_spin.setToolTip("Set the number of columns for terminal width. Only used when auto-fit is disabled.")
        font_layout.addRow("Terminal Columns:", self.terminal_columns_spin)
        
        # Auto-fit width checkbox
        self.auto_fit_width_check = QCheckBox("Auto-fit terminal width to available space")
        self.auto_fit_width_check.setToolTip("Automatically adjust terminal width to fill the space between button and group panels")
        self.auto_fit_width_check.setChecked(True)  # Default to enabled
        self.auto_fit_width_check.stateChanged.connect(self.on_auto_fit_changed)
        font_layout.addRow("", self.auto_fit_width_check)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)
        
        # Terminal behavior group
        behavior_group = QGroupBox("Terminal Behavior")
        behavior_layout = QVBoxLayout()
        
        self.cursor_blink_check = QCheckBox("Cursor blink")
        behavior_layout.addWidget(self.cursor_blink_check)
        
        self.scroll_output_check = QCheckBox("Scroll on output")
        behavior_layout.addWidget(self.scroll_output_check)
        
        self.scroll_keystroke_check = QCheckBox("Scroll on keystroke")
        behavior_layout.addWidget(self.scroll_keystroke_check)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        # UI Features group
        ui_group = QGroupBox("UI Features")
        ui_layout = QVBoxLayout()
        
        self.show_minimap_check = QCheckBox("Show minimap")
        self.show_minimap_check.setToolTip("Display minimap for terminal content overview and navigation")
        ui_layout.addWidget(self.show_minimap_check)
        
        self.colored_line_numbers_check = QCheckBox("Color line numbers by severity")
        self.colored_line_numbers_check.setToolTip("Color-code line numbers based on content (errors=red, warnings=yellow, success=green, etc.)")
        ui_layout.addWidget(self.colored_line_numbers_check)
        
        self.minimap_show_success_failure_check = QCheckBox("Show success/info colors in minimap")
        self.minimap_show_success_failure_check.setToolTip("Show green for success and blue for info (disable to show ONLY errors, warnings, and non-200 status codes)")
        ui_layout.addWidget(self.minimap_show_success_failure_check)
        
        # Viewport highlight color
        viewport_color_layout = QHBoxLayout()
        viewport_color_label = QLabel("Viewport highlight color:")
        viewport_color_layout.addWidget(viewport_color_label)
        
        self.viewport_highlight_combo = QComboBox()
        self.viewport_highlight_combo.addItems(["Auto (Opposite of background)", "Custom..."])
        self.viewport_highlight_combo.setToolTip("Color for the arrow box highlighting the current viewport line")
        self.viewport_highlight_combo.currentIndexChanged.connect(self.on_viewport_highlight_changed)
        viewport_color_layout.addWidget(self.viewport_highlight_combo)
        
        self.viewport_highlight_color_button = QPushButton()
        self.viewport_highlight_color_button.setFixedSize(30, 25)
        self.viewport_highlight_color_button.setVisible(False)
        self.viewport_highlight_color_button.clicked.connect(self.choose_viewport_highlight_color)
        viewport_color_layout.addWidget(self.viewport_highlight_color_button)
        
        viewport_color_layout.addStretch()
        ui_layout.addLayout(viewport_color_layout)
        
        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)

        # Network probe settings
        network_group = QGroupBox("Network")
        network_layout = QFormLayout()

        self.probe_host_edit = QLineEdit()
        self.probe_host_edit.setPlaceholderText("Probe host (IP or hostname)")
        network_layout.addRow("Probe Host:", self.probe_host_edit)

        self.probe_port_spin = QSpinBox()
        self.probe_port_spin.setRange(1, 65535)
        network_layout.addRow("Probe Port:", self.probe_port_spin)

        self.probe_interval_spin = QSpinBox()
        self.probe_interval_spin.setRange(1, 3600)
        self.probe_interval_spin.setSuffix(" s")
        network_layout.addRow("Probe Interval:", self.probe_interval_spin)

        self.probe_timeout_spin = QSpinBox()
        self.probe_timeout_spin.setRange(1, 30)
        self.probe_timeout_spin.setSuffix(" s")
        network_layout.addRow("Probe Timeout:", self.probe_timeout_spin)

        network_group.setLayout(network_layout)
        layout.addWidget(network_group)
        
        # Suggestions group
        suggestions_group = QGroupBox("Suggestions")
        suggestions_layout = QVBoxLayout()
        
        self.suggestions_files_folders_check = QCheckBox("Enable file and folder suggestions")
        self.suggestions_files_folders_check.setToolTip("Show suggestions for files and folders while typing")
        suggestions_layout.addWidget(self.suggestions_files_folders_check)
        
        self.suggestions_commands_check = QCheckBox("Enable command suggestions")
        self.suggestions_commands_check.setToolTip("Show suggestions for commands while typing")
        suggestions_layout.addWidget(self.suggestions_commands_check)
        
        suggestions_group.setLayout(suggestions_layout)
        layout.addWidget(suggestions_group)
        
        # Auto-Archive group
        archive_group = QGroupBox("Automatic History Archival")
        archive_layout = QVBoxLayout()
        
        self.auto_archive_enabled_check = QCheckBox("Enable automatic history archival")
        self.auto_archive_enabled_check.setToolTip("Automatically move old lines to history file when buffer reaches threshold")
        self.auto_archive_enabled_check.stateChanged.connect(self.on_auto_archive_enabled_changed)
        archive_layout.addWidget(self.auto_archive_enabled_check)
        
        archive_settings_layout = QFormLayout()
        
        self.auto_archive_threshold_spin = QSpinBox()
        self.auto_archive_threshold_spin.setRange(500, 20000)
        self.auto_archive_threshold_spin.setSingleStep(500)
        self.auto_archive_threshold_spin.setSuffix(" lines")
        self.auto_archive_threshold_spin.setToolTip("Trigger archival when total lines reach this number")
        archive_settings_layout.addRow("Trigger at:", self.auto_archive_threshold_spin)
        
        self.auto_archive_keep_lines_spin = QSpinBox()
        self.auto_archive_keep_lines_spin.setRange(100, 10000)
        self.auto_archive_keep_lines_spin.setSingleStep(100)
        self.auto_archive_keep_lines_spin.setSuffix(" lines")
        self.auto_archive_keep_lines_spin.setToolTip("Number of recent lines to keep in buffer after archival")
        archive_settings_layout.addRow("Keep recent:", self.auto_archive_keep_lines_spin)
        
        archive_layout.addLayout(archive_settings_layout)
        
        # Info label
        archive_info = QLabel("Example: If set to archive at 2000 lines and keep 1000 lines,\nlines 0-1000 will be archived when buffer reaches 2000 lines.")
        archive_info.setStyleSheet("color: gray; font-size: 9pt; font-style: italic;")
        archive_layout.addWidget(archive_info)
        
        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)
        
        # Minimap Keywords group
        minimap_keywords_group = QGroupBox("Minimap Custom Keywords")
        minimap_keywords_layout = QVBoxLayout()
        
        # Info label
        info_label = QLabel("Add custom keywords to highlight in the minimap with specific colors (double-click color to edit)")
        info_label.setStyleSheet("color: gray; font-size: 10pt;")
        minimap_keywords_layout.addWidget(info_label)
        
        # Keywords table with scroll area
        self.minimap_keywords_table = QTableWidget()
        self.minimap_keywords_table.setColumnCount(4)
        self.minimap_keywords_table.setHorizontalHeaderLabels(["Keyword", "Color", "Priority", "Visible"])
        self.minimap_keywords_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.minimap_keywords_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.minimap_keywords_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.minimap_keywords_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.minimap_keywords_table.setColumnWidth(1, 120)
        self.minimap_keywords_table.setColumnWidth(2, 80)
        self.minimap_keywords_table.setColumnWidth(3, 80)
        self.minimap_keywords_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.minimap_keywords_table.setMinimumHeight(180)
        self.minimap_keywords_table.setMaximumHeight(250)
        self.minimap_keywords_table.verticalHeader().setVisible(False)
        self.minimap_keywords_table.cellDoubleClicked.connect(self.edit_minimap_keyword_cell)
        
        # Enable sorting - click column headers to sort
        self.minimap_keywords_table.setSortingEnabled(True)
        self.minimap_keywords_table.horizontalHeader().setSortIndicatorShown(True)
        self.minimap_keywords_table.horizontalHeader().sortIndicatorChanged.connect(self.on_keyword_sort_changed)
        
        minimap_keywords_layout.addWidget(self.minimap_keywords_table)
        
        # Buttons for keywords
        keywords_buttons_layout = QHBoxLayout()
        
        add_keyword_btn = QPushButton("Add Keyword")
        add_keyword_btn.clicked.connect(self.add_minimap_keyword)
        keywords_buttons_layout.addWidget(add_keyword_btn)
        
        remove_keyword_btn = QPushButton("Remove Selected")
        remove_keyword_btn.clicked.connect(self.remove_minimap_keyword)
        keywords_buttons_layout.addWidget(remove_keyword_btn)
        
        keywords_buttons_layout.addStretch()
        
        minimap_keywords_layout.addLayout(keywords_buttons_layout)
        
        # Priority info
        priority_info = QLabel("Priority: Lower numbers have higher priority (1=highest, show first)")
        priority_info.setStyleSheet("color: gray; font-size: 9pt; font-style: italic;")
        minimap_keywords_layout.addWidget(priority_info)
        
        minimap_keywords_group.setLayout(minimap_keywords_layout)
        layout.addWidget(minimap_keywords_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        
        # Set the widget to scroll area
        scroll_area.setWidget(widget)
        return scroll_area
    
    def create_appearance_tab(self):
        """Create appearance settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Theme selection group
        theme_group = QGroupBox("Color Theme")
        theme_layout = QVBoxLayout()
        
        theme_select_layout = QHBoxLayout()
        theme_select_layout.addWidget(QLabel("Theme:"))
        
        self.theme_combo = QComboBox()
        for theme_id, theme_name in self.prefs_manager.get_theme_names():
            self.theme_combo.addItem(theme_name, theme_id)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_select_layout.addWidget(self.theme_combo)
        theme_select_layout.addStretch()
        
        theme_layout.addLayout(theme_select_layout)
        
        info_label = QLabel("Select a predefined theme or customize colors in the Colors tab")
        info_label.setStyleSheet("color: gray; font-size: 10pt;")
        theme_layout.addWidget(info_label)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Color settings group
        color_group = QGroupBox("Main Colors")
        color_layout = QFormLayout()
        
        # Background color
        bg_layout = QHBoxLayout()
        self.bg_color_label = QLabel()
        self.bg_color_label.setFixedSize(50, 25)
        self.bg_color_label.setStyleSheet("border: 1px solid #666; border-radius: 3px;")
        bg_layout.addWidget(self.bg_color_label)
        
        self.bg_color_edit = QLineEdit()
        self.bg_color_edit.setPlaceholderText("#1e1e1e")
        bg_layout.addWidget(self.bg_color_edit)
        
        bg_pick_btn = QPushButton("Pick...")
        bg_pick_btn.clicked.connect(lambda: self.pick_color('background'))
        bg_layout.addWidget(bg_pick_btn)
        bg_layout.addStretch()
        
        color_layout.addRow("Background:", bg_layout)
        
        # Foreground color
        fg_layout = QHBoxLayout()
        self.fg_color_label = QLabel()
        self.fg_color_label.setFixedSize(50, 25)
        self.fg_color_label.setStyleSheet("border: 1px solid #666; border-radius: 3px;")
        fg_layout.addWidget(self.fg_color_label)
        
        self.fg_color_edit = QLineEdit()
        self.fg_color_edit.setPlaceholderText("#e5e5e5")
        fg_layout.addWidget(self.fg_color_edit)
        
        fg_pick_btn = QPushButton("Pick...")
        fg_pick_btn.clicked.connect(lambda: self.pick_color('foreground'))
        fg_layout.addWidget(fg_pick_btn)
        fg_layout.addStretch()
        
        color_layout.addRow("Foreground:", fg_layout)
        
        # Cursor color
        cursor_layout = QHBoxLayout()
        self.cursor_color_label = QLabel()
        self.cursor_color_label.setFixedSize(50, 25)
        self.cursor_color_label.setStyleSheet("border: 1px solid #666; border-radius: 3px;")
        cursor_layout.addWidget(self.cursor_color_label)
        
        self.cursor_color_edit = QLineEdit()
        self.cursor_color_edit.setPlaceholderText("#00ff00")
        cursor_layout.addWidget(self.cursor_color_edit)
        
        cursor_pick_btn = QPushButton("Pick...")
        cursor_pick_btn.clicked.connect(lambda: self.pick_color('cursor'))
        cursor_layout.addWidget(cursor_pick_btn)
        cursor_layout.addStretch()
        
        color_layout.addRow("Cursor:", cursor_layout)
        
        # Selection color
        selection_layout = QHBoxLayout()
        self.selection_color_label = QLabel()
        self.selection_color_label.setFixedSize(50, 25)
        self.selection_color_label.setStyleSheet("border: 1px solid #666; border-radius: 3px;")
        selection_layout.addWidget(self.selection_color_label)
        
        self.selection_color_edit = QLineEdit()
        self.selection_color_edit.setPlaceholderText("#3399ff")
        selection_layout.addWidget(self.selection_color_edit)
        
        selection_pick_btn = QPushButton("Pick...")
        selection_pick_btn.clicked.connect(lambda: self.pick_color('selection'))
        selection_layout.addWidget(selection_pick_btn)
        selection_layout.addStretch()
        
        color_layout.addRow("Selection:", selection_layout)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_colors_tab(self):
        """Create ANSI colors settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        info_label = QLabel("Customize the 16 ANSI terminal colors")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Store color widgets
        self.color_widgets = {}
        
        # Normal colors
        normal_group = QGroupBox("Normal Colors")
        normal_layout = QFormLayout()
        
        for color_name in ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']:
            color_layout = QHBoxLayout()
            
            color_label = QLabel()
            color_label.setFixedSize(50, 25)
            color_label.setStyleSheet("border: 1px solid #666; border-radius: 3px;")
            color_layout.addWidget(color_label)
            
            color_edit = QLineEdit()
            color_layout.addWidget(color_edit)
            
            pick_btn = QPushButton("Pick...")
            pick_btn.clicked.connect(lambda checked, name=color_name: self.pick_ansi_color(name))
            color_layout.addWidget(pick_btn)
            color_layout.addStretch()
            
            self.color_widgets[color_name] = (color_label, color_edit)
            normal_layout.addRow(color_name.capitalize() + ":", color_layout)
        
        normal_group.setLayout(normal_layout)
        layout.addWidget(normal_group)
        
        # Bright colors
        bright_group = QGroupBox("Bright Colors")
        bright_layout = QFormLayout()
        
        for color_name in ['bright_black', 'bright_red', 'bright_green', 'bright_yellow', 
                          'bright_blue', 'bright_magenta', 'bright_cyan', 'bright_white']:
            color_layout = QHBoxLayout()
            
            color_label = QLabel()
            color_label.setFixedSize(50, 25)
            color_label.setStyleSheet("border: 1px solid #666; border-radius: 3px;")
            color_layout.addWidget(color_label)
            
            color_edit = QLineEdit()
            color_layout.addWidget(color_edit)
            
            pick_btn = QPushButton("Pick...")
            pick_btn.clicked.connect(lambda checked, name=color_name: self.pick_ansi_color(name))
            color_layout.addWidget(pick_btn)
            color_layout.addStretch()
            
            display_name = color_name.replace('bright_', '').capitalize()
            self.color_widgets[color_name] = (color_label, color_edit)
            bright_layout.addRow("Bright " + display_name + ":", color_layout)
        
        bright_group.setLayout(bright_layout)
        layout.addWidget(bright_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_behavior_tab(self):
        """Create behavior settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Session management group
        session_group = QGroupBox("Session Management")
        session_layout = QVBoxLayout()
        
        self.save_session_check = QCheckBox("Save session on exit")
        self.save_session_check.setToolTip("Automatically save all tabs and groups when closing")
        session_layout.addWidget(self.save_session_check)
        
        self.restore_session_check = QCheckBox("Restore session on startup")
        self.restore_session_check.setToolTip("Restore tabs and groups from last session")
        session_layout.addWidget(self.restore_session_check)
        
        session_group.setLayout(session_layout)
        layout.addWidget(session_group)
        
        # Application behavior group
        app_group = QGroupBox("Application Behavior")
        app_layout = QVBoxLayout()
        
        self.confirm_close_check = QCheckBox("Confirm before closing application")
        self.confirm_close_check.setToolTip("Show confirmation dialog when closing the application")
        app_layout.addWidget(self.confirm_close_check)
        
        app_group.setLayout(app_layout)
        layout.addWidget(app_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_shortcuts_tab(self):
        """Create keyboard shortcuts customization tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        info_label = QLabel("Customize keyboard shortcuts for window management and GUI operations")
        info_label.setStyleSheet("font-style: italic; color: gray; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Default shortcuts group (read-only)
        default_group = QGroupBox("Default Shortcuts (Read-Only)")
        default_layout = QVBoxLayout()
        
        self.default_shortcuts_table = QTableWidget()
        self.default_shortcuts_table.setColumnCount(3)
        self.default_shortcuts_table.setHorizontalHeaderLabels(["Action", "Shortcut", "Description"])
        self.default_shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.default_shortcuts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.default_shortcuts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.default_shortcuts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.default_shortcuts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.default_shortcuts_table.setAlternatingRowColors(True)
        
        # Populate default shortcuts
        self.populate_default_shortcuts()
        
        default_layout.addWidget(self.default_shortcuts_table)
        default_group.setLayout(default_layout)
        layout.addWidget(default_group)
        
        # Custom shortcuts group (editable)
        custom_group = QGroupBox("Custom Shortcuts")
        custom_layout = QVBoxLayout()
        
        custom_info = QLabel("Add your own keyboard shortcuts for executing commands")
        custom_info.setStyleSheet("font-style: italic; color: gray; margin-bottom: 5px;")
        custom_layout.addWidget(custom_info)
        
        self.custom_shortcuts_table = QTableWidget()
        self.custom_shortcuts_table.setColumnCount(3)
        self.custom_shortcuts_table.setHorizontalHeaderLabels(["Shortcut", "Command", "Actions"])
        self.custom_shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.custom_shortcuts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.custom_shortcuts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.custom_shortcuts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.custom_shortcuts_table.setAlternatingRowColors(True)
        
        custom_layout.addWidget(self.custom_shortcuts_table)
        
        # Buttons for custom shortcuts
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("➕ Add Custom Shortcut")
        add_btn.clicked.connect(self.add_custom_shortcut)
        button_layout.addWidget(add_btn)
        
        button_layout.addStretch()
        
        custom_layout.addLayout(button_layout)
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # Load custom shortcuts
        self.load_custom_shortcuts()
        
        widget.setLayout(layout)
        return widget
    
    def populate_default_shortcuts(self):
        """Populate the default shortcuts table"""
        platform_mgr = get_platform_manager()
        shortcuts_dict = platform_mgr.get_all_shortcuts()
        
        # Convert to table format grouped by category
        default_shortcuts = []
        
        # Editing shortcuts
        if 'copy' in shortcuts_dict:
            default_shortcuts.append((
                "Copy (with selection)", 
                shortcuts_dict['copy']['shortcut'],
                shortcuts_dict['copy']['description']
            ))
        
        if 'paste' in shortcuts_dict:
            default_shortcuts.append((
                "Paste", 
                shortcuts_dict['paste']['shortcut'],
                shortcuts_dict['paste']['description']
            ))
        
        if 'select_all' in shortcuts_dict:
            default_shortcuts.append((
                "Select All", 
                shortcuts_dict['select_all']['shortcut'],
                shortcuts_dict['select_all']['description']
            ))
        
        if 'cut' in shortcuts_dict:
            default_shortcuts.append((
                "Cut (with selection)", 
                shortcuts_dict['cut']['shortcut'],
                shortcuts_dict['cut']['description']
            ))
        
        # Screen operations
        if 'clear_screen' in shortcuts_dict:
            default_shortcuts.append((
                "Clear Screen", 
                shortcuts_dict['clear_screen']['shortcut'],
                shortcuts_dict['clear_screen']['description']
            ))
        
        # Terminal shortcuts (same on all platforms)
        if 'beginning_of_line' in shortcuts_dict:
            default_shortcuts.append((
                "Beginning of Line", 
                shortcuts_dict['beginning_of_line']['shortcut'],
                shortcuts_dict['beginning_of_line']['description']
            ))
        
        if 'end_of_line' in shortcuts_dict:
            default_shortcuts.append((
                "End of Line", 
                shortcuts_dict['end_of_line']['shortcut'],
                shortcuts_dict['end_of_line']['description']
            ))
        
        if 'delete_word_bash' in shortcuts_dict:
            default_shortcuts.append((
                "Delete Word (bash)", 
                shortcuts_dict['delete_word_bash']['shortcut'],
                shortcuts_dict['delete_word_bash']['description']
            ))
        
        if 'kill_to_end' in shortcuts_dict:
            default_shortcuts.append((
                "Kill to End", 
                shortcuts_dict['kill_to_end']['shortcut'],
                shortcuts_dict['kill_to_end']['description']
            ))
        
        if 'kill_to_start' in shortcuts_dict:
            default_shortcuts.append((
                "Kill to Start", 
                shortcuts_dict['kill_to_start']['shortcut'],
                shortcuts_dict['kill_to_start']['description']
            ))
        
        if 'reverse_search' in shortcuts_dict:
            default_shortcuts.append((
                "Reverse Search", 
                shortcuts_dict['reverse_search']['shortcut'],
                shortcuts_dict['reverse_search']['description']
            ))
        
        if 'interrupt' in shortcuts_dict:
            default_shortcuts.append((
                "Interrupt", 
                shortcuts_dict['interrupt']['shortcut'],
                shortcuts_dict['interrupt']['description']
            ))
        
        if 'suspend' in shortcuts_dict:
            default_shortcuts.append((
                "Suspend", 
                shortcuts_dict['suspend']['shortcut'],
                shortcuts_dict['suspend']['description']
            ))
        
        # Platform-specific shortcuts
        if 'word_left' in shortcuts_dict:
            default_shortcuts.append((
                "Word Left", 
                shortcuts_dict['word_left']['shortcut'],
                shortcuts_dict['word_left']['description']
            ))
        
        if 'word_right' in shortcuts_dict:
            default_shortcuts.append((
                "Word Right", 
                shortcuts_dict['word_right']['shortcut'],
                shortcuts_dict['word_right']['description']
            ))
        
        if 'delete_word' in shortcuts_dict:
            default_shortcuts.append((
                "Delete Word", 
                shortcuts_dict['delete_word']['shortcut'],
                shortcuts_dict['delete_word']['description']
            ))
        
        # Window management
        if 'new_tab' in shortcuts_dict:
            default_shortcuts.append((
                "New Tab", 
                shortcuts_dict['new_tab']['shortcut'],
                shortcuts_dict['new_tab']['description']
            ))
        
        if 'close_tab' in shortcuts_dict:
            default_shortcuts.append((
                "Close Tab", 
                shortcuts_dict['close_tab']['shortcut'],
                shortcuts_dict['close_tab']['description']
            ))
        
        if 'close_other_tabs' in shortcuts_dict:
            default_shortcuts.append((
                "Close Other Tabs", 
                shortcuts_dict['close_other_tabs']['shortcut'],
                shortcuts_dict['close_other_tabs']['description']
            ))
        
        self.default_shortcuts_table.setRowCount(len(default_shortcuts))
        
        for row, (action, shortcut, description) in enumerate(default_shortcuts):
            action_item = QTableWidgetItem(action)
            shortcut_item = QTableWidgetItem(shortcut)
            desc_item = QTableWidgetItem(description)
            
            # Make items non-editable
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            shortcut_item.setFlags(shortcut_item.flags() & ~Qt.ItemIsEditable)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            
            self.default_shortcuts_table.setItem(row, 0, action_item)
            self.default_shortcuts_table.setItem(row, 1, shortcut_item)
            self.default_shortcuts_table.setItem(row, 2, desc_item)
        
        self.default_shortcuts_table.resizeRowsToContents()
    
    def load_custom_shortcuts(self):
        """Load custom shortcuts from preferences"""
        custom_shortcuts = self.prefs_manager.get('shortcuts', 'custom_shortcuts', {})
        
        self.custom_shortcuts_table.setRowCount(len(custom_shortcuts))
        
        for row, (shortcut, command) in enumerate(custom_shortcuts.items()):
            shortcut_item = QTableWidgetItem(shortcut)
            command_item = QTableWidgetItem(command)
            
            self.custom_shortcuts_table.setItem(row, 0, shortcut_item)
            self.custom_shortcuts_table.setItem(row, 1, command_item)
            
            # Add action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            edit_btn = QPushButton("✏️ Edit")
            edit_btn.clicked.connect(lambda checked, r=row: self.edit_custom_shortcut(r))
            edit_btn.setMaximumWidth(70)
            actions_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("🗑️ Delete")
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_custom_shortcut(r))
            delete_btn.setMaximumWidth(80)
            actions_layout.addWidget(delete_btn)
            
            self.custom_shortcuts_table.setCellWidget(row, 2, actions_widget)
        
        self.custom_shortcuts_table.resizeRowsToContents()
    
    def add_custom_shortcut(self):
        """Open dialog to add a custom shortcut"""
        dialog = ShortcutEditorDialog(self)
        if dialog.exec_():
            shortcut, command = dialog.get_shortcut_data()
            if shortcut and command:
                # Add new row
                row = self.custom_shortcuts_table.rowCount()
                self.custom_shortcuts_table.insertRow(row)
                
                shortcut_item = QTableWidgetItem(shortcut)
                command_item = QTableWidgetItem(command)
                
                self.custom_shortcuts_table.setItem(row, 0, shortcut_item)
                self.custom_shortcuts_table.setItem(row, 1, command_item)
                
                # Add action buttons
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                edit_btn = QPushButton("✏️ Edit")
                edit_btn.clicked.connect(lambda checked, r=row: self.edit_custom_shortcut(r))
                edit_btn.setMaximumWidth(70)
                actions_layout.addWidget(edit_btn)
                
                delete_btn = QPushButton("🗑️ Delete")
                delete_btn.clicked.connect(lambda checked, r=row: self.delete_custom_shortcut(r))
                delete_btn.setMaximumWidth(80)
                actions_layout.addWidget(delete_btn)
                
                self.custom_shortcuts_table.setCellWidget(row, 2, actions_widget)
                self.custom_shortcuts_table.resizeRowsToContents()
    
    def edit_custom_shortcut(self, row):
        """Edit a custom shortcut"""
        shortcut_item = self.custom_shortcuts_table.item(row, 0)
        command_item = self.custom_shortcuts_table.item(row, 1)
        
        if shortcut_item and command_item:
            dialog = ShortcutEditorDialog(self, shortcut_item.text(), command_item.text())
            if dialog.exec_():
                shortcut, command = dialog.get_shortcut_data()
                if shortcut and command:
                    shortcut_item.setText(shortcut)
                    command_item.setText(command)
    
    def delete_custom_shortcut(self, row):
        """Delete a custom shortcut"""
        reply = QMessageBox.question(
            self, "Delete Shortcut",
            "Are you sure you want to delete this custom shortcut?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.custom_shortcuts_table.removeRow(row)
            # Refresh the table to update button connections
            self.refresh_custom_shortcuts_buttons()
    
    def refresh_custom_shortcuts_buttons(self):
        """Refresh action buttons after row deletion"""
        for row in range(self.custom_shortcuts_table.rowCount()):
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            edit_btn = QPushButton("✏️ Edit")
            edit_btn.clicked.connect(lambda checked, r=row: self.edit_custom_shortcut(r))
            edit_btn.setMaximumWidth(70)
            actions_layout.addWidget(edit_btn)
            
            delete_btn = QPushButton("🗑️ Delete")
            delete_btn.clicked.connect(lambda checked, r=row: self.delete_custom_shortcut(r))
            delete_btn.setMaximumWidth(80)
            actions_layout.addWidget(delete_btn)
            
            self.custom_shortcuts_table.setCellWidget(row, 2, actions_widget)
    
    def load_current_preferences(self):
        """Load current preferences into the UI"""
        prefs = self.prefs_manager
        
        # Terminal tab
        self.default_dir_edit.setText(prefs.get('terminal', 'default_directory', os.path.expanduser('~')))
        
        font_family = prefs.get('terminal', 'font_family', 'Menlo')
        index = self.font_family_combo.findText(font_family)
        if index >= 0:
            self.font_family_combo.setCurrentIndex(index)
        else:
            self.font_family_combo.setCurrentText(font_family)
        
        self.font_size_spin.setValue(prefs.get('terminal', 'font_size', 13))
        self.terminal_columns_spin.setValue(prefs.get('terminal', 'columns', 120))
        
        # Load auto-fit width setting
        auto_fit = prefs.get('terminal', 'auto_fit_width', True)
        self.auto_fit_width_check.setChecked(auto_fit)
        # Enable/disable columns spinbox based on auto-fit state
        self.terminal_columns_spin.setEnabled(not auto_fit)
        
        self.cursor_blink_check.setChecked(prefs.get('terminal', 'cursor_blink', True))
        self.scroll_output_check.setChecked(prefs.get('terminal', 'scroll_on_output', True))
        self.scroll_keystroke_check.setChecked(prefs.get('terminal', 'scroll_on_keystroke', True))
        self.show_minimap_check.setChecked(prefs.get('terminal', 'show_minimap', True))
        self.colored_line_numbers_check.setChecked(prefs.get('terminal', 'colored_line_numbers', True))
        self.minimap_show_success_failure_check.setChecked(prefs.get('terminal', 'minimap_show_success_failure_colors', True))
        self.suggestions_files_folders_check.setChecked(prefs.get('terminal', 'suggestions_files_folders', True))
        self.suggestions_commands_check.setChecked(prefs.get('terminal', 'suggestions_commands', False))
        
        # Load auto-archive preferences
        auto_archive_enabled = prefs.get('terminal', 'auto_archive_enabled', False)
        self.auto_archive_enabled_check.setChecked(auto_archive_enabled)
        self.auto_archive_threshold_spin.setValue(prefs.get('terminal', 'auto_archive_threshold', 2000))
        self.auto_archive_keep_lines_spin.setValue(prefs.get('terminal', 'auto_archive_keep_lines', 1000))
        # Enable/disable spin boxes based on checkbox
        self.auto_archive_threshold_spin.setEnabled(auto_archive_enabled)
        self.auto_archive_keep_lines_spin.setEnabled(auto_archive_enabled)

        # Network settings
        self.probe_host_edit.setText(prefs.get('network', 'probe_host', '8.8.8.8'))
        self.probe_port_spin.setValue(prefs.get('network', 'probe_port', 53))
        self.probe_interval_spin.setValue(prefs.get('network', 'probe_interval', 5))
        self.probe_timeout_spin.setValue(prefs.get('network', 'probe_timeout', 2))
        
        # Load viewport highlight color
        viewport_color = prefs.get('terminal', 'viewport_highlight_color', 'auto')
        if viewport_color == 'auto':
            self.viewport_highlight_combo.setCurrentIndex(0)
            self.viewport_highlight_color_button.setVisible(False)
        else:
            self.viewport_highlight_combo.setCurrentIndex(1)
            self.viewport_highlight_custom_color = viewport_color
            self.viewport_highlight_color_button.setVisible(True)
            self.viewport_highlight_color_button.setStyleSheet(
                f"background-color: {viewport_color}; border: 1px solid #666; border-radius: 3px;"
            )
        
        # Load minimap custom keywords
        custom_keywords = prefs.get('terminal', 'minimap_custom_keywords', {})
        self.minimap_keywords_table.setSortingEnabled(False)  # Disable sorting while loading
        self.minimap_keywords_table.setRowCount(0)  # Clear existing rows
        for keyword, config in custom_keywords.items():
            row = self.minimap_keywords_table.rowCount()
            self.minimap_keywords_table.insertRow(row)
            
            # Keyword
            keyword_item = QTableWidgetItem(keyword)
            self.minimap_keywords_table.setItem(row, 0, keyword_item)
            
            # Color - with background and contrasting text
            color_hex = config.get('color', '#808080')
            color = QColor(color_hex)
            color_item = QTableWidgetItem(color_hex)
            color_item.setBackground(color)
            color_item.setForeground(QColor("#ffffff" if color.lightness() < 128 else "#000000"))
            self.minimap_keywords_table.setItem(row, 1, color_item)
            
            # Priority - with numeric data for sorting
            priority = config.get('priority', 5)
            priority_item = QTableWidgetItem(str(priority))
            priority_item.setData(Qt.UserRole, priority)  # Set numeric value for sorting
            self.minimap_keywords_table.setItem(row, 2, priority_item)
            
            # Visible - checkbox
            visible = config.get('visible', True)
            visible_check = QCheckBox()
            visible_check.setChecked(visible)
            visible_check.setStyleSheet("margin-left: 30%; margin-right: 30%;")
            self.minimap_keywords_table.setCellWidget(row, 3, visible_check)
        
        # Re-enable sorting after loading all keywords
        self.minimap_keywords_table.setSortingEnabled(True)
        
        # Appearance tab
        current_theme = prefs.get('appearance', 'theme', 'dark')
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
        
        self.update_color_displays()
        
        # Behavior tab
        self.save_session_check.setChecked(prefs.get('behavior', 'save_session_on_exit', True))
        self.restore_session_check.setChecked(prefs.get('behavior', 'restore_session_on_startup', True))
        self.confirm_close_check.setChecked(prefs.get('behavior', 'confirm_on_close', True))
    
    def update_color_displays(self):
        """Update all color display widgets"""
        prefs = self.prefs_manager
        
        # Main colors
        bg_color = prefs.get('appearance', 'background_color', '#1e1e1e')
        self.bg_color_edit.setText(bg_color)
        self.bg_color_label.setStyleSheet(f"background-color: {bg_color}; border: 1px solid #666; border-radius: 3px;")
        
        fg_color = prefs.get('appearance', 'foreground_color', '#e5e5e5')
        self.fg_color_edit.setText(fg_color)
        self.fg_color_label.setStyleSheet(f"background-color: {fg_color}; border: 1px solid #666; border-radius: 3px;")
        
        cursor_color = prefs.get('appearance', 'cursor_color', '#00ff00')
        self.cursor_color_edit.setText(cursor_color)
        self.cursor_color_label.setStyleSheet(f"background-color: {cursor_color}; border: 1px solid #666; border-radius: 3px;")
        
        selection_color = prefs.get('appearance', 'selection_color', '#3399ff')
        self.selection_color_edit.setText(selection_color)
        self.selection_color_label.setStyleSheet(f"background-color: {selection_color}; border: 1px solid #666; border-radius: 3px;")
        
        # ANSI colors
        colors = prefs.get_category('colors')
        for color_name, (label, edit) in self.color_widgets.items():
            color_value = colors.get(color_name, '#000000')
            edit.setText(color_value)
            label.setStyleSheet(f"background-color: {color_value}; border: 1px solid #666; border-radius: 3px;")
    
    def on_theme_changed(self, index):
        """Handle theme selection change"""
        theme_id = self.theme_combo.itemData(index)
        if theme_id:
            # Create a temporary preferences manager to apply theme
            temp_prefs = PreferencesManager()
            temp_prefs._preferences = self.prefs_manager._preferences.copy()
            temp_prefs.apply_theme(theme_id)
            
            # Update current preferences manager
            self.prefs_manager._preferences = temp_prefs._preferences.copy()
            
            # Update display
            self.update_color_displays()
    
    def browse_directory(self):
        """Browse for default directory"""
        current_dir = self.default_dir_edit.text() or os.path.expanduser('~')
        directory = QFileDialog.getExistingDirectory(
            self, "Select Default Directory", current_dir
        )
        if directory:
            self.default_dir_edit.setText(directory)
    
    def add_minimap_keyword(self):
        """Add a new minimap keyword"""
        from PyQt5.QtWidgets import QInputDialog
        
        # Get keyword
        keyword, ok1 = QInputDialog.getText(self, "Add Keyword", "Enter keyword:")
        if not ok1 or not keyword.strip():
            return
        
        keyword = keyword.strip().lower()
        
        # Get priority
        priority, ok2 = QInputDialog.getInt(self, "Set Priority", 
                                            "Enter priority (1=highest):", 
                                            value=5, min=1, max=100)
        if not ok2:
            return
        
        # Get color
        color = QColorDialog.getColor(QColor("#808080"), self, "Select Color")
        if not color.isValid():
            return
        
        # Add to table
        row = self.minimap_keywords_table.rowCount()
        self.minimap_keywords_table.insertRow(row)
        
        # Keyword
        keyword_item = QTableWidgetItem(keyword)
        self.minimap_keywords_table.setItem(row, 0, keyword_item)
        
        # Color - with background color for visibility
        color_item = QTableWidgetItem(color.name())
        color_item.setBackground(color)
        color_item.setForeground(QColor("#ffffff" if color.lightness() < 128 else "#000000"))
        self.minimap_keywords_table.setItem(row, 1, color_item)
        
        # Priority
        priority_item = QTableWidgetItem(str(priority))
        priority_item.setData(Qt.UserRole, priority)  # Set numeric value for sorting
        self.minimap_keywords_table.setItem(row, 2, priority_item)
        
        # Visible - checkbox
        visible_check = QCheckBox()
        visible_check.setChecked(True)
        visible_check.setStyleSheet("margin-left: 30%; margin-right: 30%;")
        self.minimap_keywords_table.setCellWidget(row, 3, visible_check)
    
    def remove_minimap_keyword(self):
        """Remove selected minimap keyword"""
        selected_rows = self.minimap_keywords_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a keyword to remove")
            return
        
        # Remove rows in reverse order to avoid index issues
        for index in sorted(selected_rows, reverse=True):
            self.minimap_keywords_table.removeRow(index.row())
    
    def edit_minimap_keyword_cell(self, row, column):
        """Edit a minimap keyword cell - show color picker for color column"""
        if column == 1:  # Color column
            color_item = self.minimap_keywords_table.item(row, column)
            if color_item:
                current_color = QColor(color_item.text())
                color = QColorDialog.getColor(current_color, self, "Select Keyword Color")
                if color.isValid():
                    color_item.setText(color.name())
                    color_item.setBackground(color)
                    # Set text color based on background brightness
                    color_item.setForeground(QColor("#ffffff" if color.lightness() < 128 else "#000000"))
    
    def on_auto_fit_changed(self, state):
        """Handle auto-fit checkbox state change"""
        # Enable/disable the columns spinbox based on auto-fit state
        # When auto-fit is enabled, the fixed column value is not used
        is_checked = (state == Qt.Checked)
        self.terminal_columns_spin.setEnabled(not is_checked)
    
    def on_auto_archive_enabled_changed(self, state):
        """Handle auto-archive checkbox change"""
        # Enable/disable archive settings based on checkbox
        enabled = (state == Qt.Checked)
        self.auto_archive_threshold_spin.setEnabled(enabled)
        self.auto_archive_keep_lines_spin.setEnabled(enabled)
    
    def on_keyword_sort_changed(self, column, order):
        """Handle sorting of keywords table - ensure proper numeric sorting for Priority column"""
        # Temporarily disable sorting to prevent recursion
        self.minimap_keywords_table.setSortingEnabled(False)
        
        # For Priority column (column 2), we need to ensure numeric sorting
        if column == 2:  # Priority column
            for row in range(self.minimap_keywords_table.rowCount()):
                priority_item = self.minimap_keywords_table.item(row, 2)
                if priority_item:
                    try:
                        # Set the sort role to use numeric value
                        priority_val = int(priority_item.text())
                        priority_item.setData(Qt.UserRole, priority_val)
                    except ValueError:
                        priority_item.setData(Qt.UserRole, 999)  # Default for invalid values
        
        # Re-enable sorting
        self.minimap_keywords_table.setSortingEnabled(True)
    
    def on_viewport_highlight_changed(self, index):
        """Handle viewport highlight color mode change"""
        is_custom = index == 1  # "Custom..." option
        self.viewport_highlight_color_button.setVisible(is_custom)
        
        if not is_custom:
            # Reset to auto mode
            self.viewport_highlight_custom_color = None
    
    def choose_viewport_highlight_color(self):
        """Choose custom viewport highlight color"""
        current_color = QColor("#ffffff")
        if hasattr(self, 'viewport_highlight_custom_color') and self.viewport_highlight_custom_color:
            current_color = QColor(self.viewport_highlight_custom_color)
        
        color = QColorDialog.getColor(current_color, self, "Select Viewport Highlight Color")
        if color.isValid():
            self.viewport_highlight_custom_color = color.name()
            self.viewport_highlight_color_button.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid #666; border-radius: 3px;"
            )
    
    def pick_color(self, color_type):
        """Pick a color using color dialog"""
        prefs = self.prefs_manager
        
        if color_type == 'background':
            current = prefs.get('appearance', 'background_color', '#1e1e1e')
            edit = self.bg_color_edit
            label = self.bg_color_label
        elif color_type == 'foreground':
            current = prefs.get('appearance', 'foreground_color', '#e5e5e5')
            edit = self.fg_color_edit
            label = self.fg_color_label
        elif color_type == 'cursor':
            current = prefs.get('appearance', 'cursor_color', '#00ff00')
            edit = self.cursor_color_edit
            label = self.cursor_color_label
        elif color_type == 'selection':
            current = prefs.get('appearance', 'selection_color', '#3399ff')
            edit = self.selection_color_edit
            label = self.selection_color_label
        else:
            return
        
        color = QColorDialog.getColor(QColor(current), self, f"Select {color_type.capitalize()} Color")
        if color.isValid():
            color_hex = color.name()
            edit.setText(color_hex)
            label.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #666; border-radius: 3px;")
    
    def pick_ansi_color(self, color_name):
        """Pick an ANSI color"""
        colors = self.prefs_manager.get_category('colors')
        current = colors.get(color_name, '#000000')
        
        label, edit = self.color_widgets[color_name]
        
        color = QColorDialog.getColor(QColor(current), self, f"Select {color_name.replace('_', ' ').title()}")
        if color.isValid():
            color_hex = color.name()
            edit.setText(color_hex)
            label.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #666; border-radius: 3px;")
    
    def accept_changes(self):
        """Save preferences and close dialog"""
        prefs = self.prefs_manager
        
        # Save terminal preferences
        prefs.set('terminal', 'default_directory', self.default_dir_edit.text())
        prefs.set('terminal', 'font_family', self.font_family_combo.currentText())
        prefs.set('terminal', 'font_size', self.font_size_spin.value())
        prefs.set('terminal', 'columns', self.terminal_columns_spin.value())
        prefs.set('terminal', 'auto_fit_width', self.auto_fit_width_check.isChecked())
        prefs.set('terminal', 'cursor_blink', self.cursor_blink_check.isChecked())
        prefs.set('terminal', 'scroll_on_output', self.scroll_output_check.isChecked())
        prefs.set('terminal', 'scroll_on_keystroke', self.scroll_keystroke_check.isChecked())
        prefs.set('terminal', 'show_minimap', self.show_minimap_check.isChecked())
        prefs.set('terminal', 'colored_line_numbers', self.colored_line_numbers_check.isChecked())
        prefs.set('terminal', 'minimap_show_success_failure_colors', self.minimap_show_success_failure_check.isChecked())
        prefs.set('terminal', 'suggestions_files_folders', self.suggestions_files_folders_check.isChecked())
        prefs.set('terminal', 'suggestions_commands', self.suggestions_commands_check.isChecked())
        
        # Save auto-archive preferences
        prefs.set('terminal', 'auto_archive_enabled', self.auto_archive_enabled_check.isChecked())
        prefs.set('terminal', 'auto_archive_threshold', self.auto_archive_threshold_spin.value())
        prefs.set('terminal', 'auto_archive_keep_lines', self.auto_archive_keep_lines_spin.value())

        # Save network settings
        prefs.set('network', 'probe_host', self.probe_host_edit.text().strip() or '8.8.8.8')
        prefs.set('network', 'probe_port', int(self.probe_port_spin.value()))
        prefs.set('network', 'probe_interval', int(self.probe_interval_spin.value()))
        prefs.set('network', 'probe_timeout', int(self.probe_timeout_spin.value()))
        
        # Save viewport highlight color
        if self.viewport_highlight_combo.currentIndex() == 0:
            prefs.set('terminal', 'viewport_highlight_color', 'auto')
        else:
            if hasattr(self, 'viewport_highlight_custom_color') and self.viewport_highlight_custom_color:
                prefs.set('terminal', 'viewport_highlight_color', self.viewport_highlight_custom_color)
            else:
                prefs.set('terminal', 'viewport_highlight_color', 'auto')
        
        # Save minimap custom keywords
        custom_keywords = {}
        for row in range(self.minimap_keywords_table.rowCount()):
            keyword_item = self.minimap_keywords_table.item(row, 0)
            color_item = self.minimap_keywords_table.item(row, 1)
            priority_item = self.minimap_keywords_table.item(row, 2)
            visible_widget = self.minimap_keywords_table.cellWidget(row, 3)
            
            if keyword_item and color_item and priority_item:
                keyword = keyword_item.text().strip().lower()
                color = color_item.text()
                try:
                    priority = int(priority_item.text())
                except ValueError:
                    priority = 5
                
                # Get visible state from checkbox
                visible = True
                if visible_widget and isinstance(visible_widget, QCheckBox):
                    visible = visible_widget.isChecked()
                
                custom_keywords[keyword] = {
                    'color': color,
                    'priority': priority,
                    'visible': visible
                }
        
        prefs.set('terminal', 'minimap_custom_keywords', custom_keywords)
        
        # Save appearance preferences
        prefs.set('appearance', 'background_color', self.bg_color_edit.text())
        prefs.set('appearance', 'foreground_color', self.fg_color_edit.text())
        prefs.set('appearance', 'cursor_color', self.cursor_color_edit.text())
        prefs.set('appearance', 'selection_color', self.selection_color_edit.text())
        
        # Save ANSI colors
        colors = {}
        for color_name, (label, edit) in self.color_widgets.items():
            colors[color_name] = edit.text()
        prefs.set_category('colors', colors)
        
        # Save behavior preferences
        prefs.set('behavior', 'save_session_on_exit', self.save_session_check.isChecked())
        prefs.set('behavior', 'restore_session_on_startup', self.restore_session_check.isChecked())
        prefs.set('behavior', 'confirm_on_close', self.confirm_close_check.isChecked())
        
        # Save custom shortcuts
        custom_shortcuts = {}
        for row in range(self.custom_shortcuts_table.rowCount()):
            shortcut_item = self.custom_shortcuts_table.item(row, 0)
            command_item = self.custom_shortcuts_table.item(row, 1)
            if shortcut_item and command_item:
                custom_shortcuts[shortcut_item.text()] = command_item.text()
        prefs.set('shortcuts', 'custom_shortcuts', custom_shortcuts)
        
        # Save to file (use sync version for UI interaction)
        if prefs.save_preferences_sync():
            self.preferences_changed.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save preferences")
    
    def restore_defaults(self):
        """Restore default preferences"""
        reply = QMessageBox.question(
            self, "Restore Defaults",
            "Are you sure you want to restore all preferences to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.prefs_manager.reset_to_defaults()
            self.load_current_preferences()
            QMessageBox.information(self, "Restored", "Preferences restored to defaults")


class ShortcutRecorderWidget(QLineEdit):
    """Widget for recording keyboard shortcuts"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Click here and press a key combination...")
        self.recorded_shortcut = ""
        self.is_recording = False
        
    def focusInEvent(self, event):
        """Start recording when focused"""
        super().focusInEvent(event)
        self.is_recording = True
        self.setStyleSheet("background-color: #ffffcc; border: 2px solid #4a9eff;")
        self.setText("Recording... Press keys now")
        
    def focusOutEvent(self, event):
        """Stop recording when focus lost"""
        super().focusOutEvent(event)
        self.is_recording = False
        self.setStyleSheet("")
        if not self.recorded_shortcut:
            self.setText("")
    
    def keyPressEvent(self, event: QKeyEvent):
        """Capture key press and convert to shortcut string"""
        if not self.is_recording:
            return
        
        key = event.key()
        modifiers = event.modifiers()
        
        # Ignore pure modifier keys
        if key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            return
        
        # Build shortcut string
        shortcut_parts = []
        
        if modifiers & Qt.ControlModifier:
            shortcut_parts.append("Ctrl")
        if modifiers & Qt.ShiftModifier:
            shortcut_parts.append("Shift")
        if modifiers & Qt.AltModifier:
            shortcut_parts.append("Alt")
        if modifiers & Qt.MetaModifier:
            if sys.platform == 'darwin':
                shortcut_parts.append("Cmd")
            else:
                shortcut_parts.append("Meta")
        
        # Get key name
        key_text = QKeySequence(key).toString()
        if key_text:
            shortcut_parts.append(key_text)
        
        self.recorded_shortcut = "+".join(shortcut_parts)
        self.setText(self.recorded_shortcut)
        self.setStyleSheet("")
        event.accept()
    
    def get_shortcut(self):
        """Get the recorded shortcut"""
        return self.recorded_shortcut
    
    def set_shortcut(self, shortcut):
        """Set a shortcut manually"""
        self.recorded_shortcut = shortcut
        self.setText(shortcut)


class ShortcutEditorDialog(QDialog):
    """Dialog for editing a custom shortcut"""
    
    def __init__(self, parent=None, shortcut="", command=""):
        super().__init__(parent)
        self.shortcut = shortcut
        self.command = command
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Custom Shortcut Editor")
        self.setMinimumWidth(500)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Info label
        info = QLabel("Create a custom keyboard shortcut to execute a terminal command")
        info.setStyleSheet("font-style: italic; color: gray; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # Shortcut input
        shortcut_group = QGroupBox("Keyboard Shortcut")
        shortcut_layout = QVBoxLayout()
        
        shortcut_help = QLabel("Click in the field below and press your desired key combination")
        shortcut_help.setStyleSheet("font-size: 10pt; color: gray;")
        shortcut_layout.addWidget(shortcut_help)
        
        self.shortcut_recorder = ShortcutRecorderWidget()
        if self.shortcut:
            self.shortcut_recorder.set_shortcut(self.shortcut)
        shortcut_layout.addWidget(self.shortcut_recorder)
        
        # Warning label
        warning = QLabel("⚠️ Avoid using Ctrl+key combinations as they're reserved for terminal applications")
        warning.setStyleSheet("font-size: 9pt; color: #ff6600; margin-top: 5px;")
        shortcut_layout.addWidget(warning)
        
        shortcut_group.setLayout(shortcut_layout)
        layout.addWidget(shortcut_group)
        
        # Command input
        command_group = QGroupBox("Command to Execute")
        command_layout = QVBoxLayout()
        
        command_help = QLabel("Enter the terminal command to execute when the shortcut is pressed")
        command_help.setStyleSheet("font-size: 10pt; color: gray;")
        command_layout.addWidget(command_help)
        
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("e.g., ls -la, git status, npm start")
        if self.command:
            self.command_edit.setText(self.command)
        command_layout.addWidget(self.command_edit)
        
        # Examples
        examples = QLabel("Examples: ls -la, cd ~/Documents, git pull, python script.py")
        examples.setStyleSheet("font-size: 9pt; color: gray; margin-top: 5px;")
        command_layout.addWidget(examples)
        
        command_group.setLayout(command_layout)
        layout.addWidget(command_group)
        
        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_shortcut)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def accept_shortcut(self):
        """Validate and accept the shortcut"""
        shortcut = self.shortcut_recorder.get_shortcut()
        command = self.command_edit.text().strip()
        
        if not shortcut:
            QMessageBox.warning(self, "Invalid Shortcut", "Please record a keyboard shortcut first")
            return
        
        if not command:
            QMessageBox.warning(self, "Invalid Command", "Please enter a command to execute")
            return
        
        # Warn about Ctrl+key shortcuts
        if shortcut.startswith("Ctrl+") and not shortcut.startswith("Ctrl+Shift+"):
            reply = QMessageBox.warning(
                self, "Warning",
                "Using Ctrl+key shortcuts may interfere with terminal applications like nano, vim, and bash.\n\n"
                "It's recommended to use Cmd+key (macOS), Shift+Ctrl+key, or Alt+key combinations instead.\n\n"
                "Do you want to continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        self.shortcut = shortcut
        self.command = command
        self.accept()
    
    def get_shortcut_data(self):
        """Get the shortcut and command"""
        return self.shortcut, self.command

