"""Notes Dialog with two-panel layout and rich text editing"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QListWidgetItem, QTextEdit, QPushButton,
                             QToolBar, QAction, QColorDialog, QFontComboBox, 
                             QSpinBox, QLabel, QMessageBox, QWidget, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize, QUrl
from PyQt5.QtGui import (QFont, QTextCharFormat, QColor, QTextCursor, 
                         QTextListFormat, QIcon, QMouseEvent, QDesktopServices)
import re
import subprocess
import sys
import os


class ClickableTextEdit(QTextEdit):
    """QTextEdit with clickable URLs and file paths when Cmd/Ctrl+Click"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        
        # Regex patterns for detecting URLs and file paths
        self.url_pattern = re.compile(
            r'https?://[^\s<>"]+|www\.[^\s<>"]+',
            re.IGNORECASE
        )
        self.file_path_pattern = re.compile(
            r'(?:^|\s)([/~][^\s<>"]+)|(?:^|\s)([A-Z]:\\[^\s<>"]+)',
            re.IGNORECASE
        )
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press with Cmd/Ctrl modifier to open links"""
        # Check if Cmd (macOS) or Ctrl (Windows/Linux) is pressed
        if event.modifiers() & Qt.ControlModifier or event.modifiers() & Qt.MetaModifier:
            # Get the cursor at click position
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.WordUnderCursor)
            
            # Get the word and surrounding text for better path detection
            block = cursor.block()
            block_text = block.text()
            
            # Try to detect and open URL or path
            if self.try_open_link(block_text, cursor.selectedText()):
                return  # Link opened, don't propagate event
        
        # Normal behavior
        super().mousePressEvent(event)
    
    def try_open_link(self, line_text, word):
        """Try to detect and open a URL or file path"""
        # Try to find URL in the line
        url_matches = list(self.url_pattern.finditer(line_text))
        for match in url_matches:
            url = match.group(0)
            if word in url:  # Check if clicked word is part of this URL
                return self.open_url(url)
        
        # Try to find file path in the line
        path_matches = list(self.file_path_pattern.finditer(line_text))
        for match in path_matches:
            path = match.group(1) or match.group(2)  # Unix or Windows path
            if path and word in path:  # Check if clicked word is part of this path
                return self.open_path(path.strip())
        
        # Try the word itself as a path (for paths without spaces)
        if word.startswith('/') or word.startswith('~') or (len(word) > 2 and word[1] == ':'):
            return self.open_path(word)
        
        return False
    
    def open_url(self, url):
        """Open a URL in the default browser"""
        # Add http:// if it starts with www.
        if url.startswith('www.'):
            url = 'http://' + url
        
        # Open URL
        qurl = QUrl(url)
        if qurl.isValid():
            QDesktopServices.openUrl(qurl)
            return True
        return False
    
    def open_path(self, path):
        """Open a file or folder path"""
        # Expand user home directory
        expanded_path = os.path.expanduser(path)
        
        # Check if path exists
        if not os.path.exists(expanded_path):
            return False
        
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.Popen(['open', expanded_path])
            elif sys.platform == 'win32':  # Windows
                os.startfile(expanded_path)
            else:  # Linux and other Unix-like
                subprocess.Popen(['xdg-open', expanded_path])
            return True
        except Exception as e:
            return False


class NotesDialog(QDialog):
    """Dialog for managing tab-specific notes with rich text editing"""
    
    def __init__(self, parent=None, notes_manager=None, tab_id=None, tab_name="Tab"):
        super().__init__(parent)
        self.notes_manager = notes_manager
        self.tab_id = tab_id
        self.tab_name = tab_name
        self.current_note = None
        self.is_updating = False  # Flag to prevent recursive updates
        
        self.setWindowTitle(f"Notes - {tab_name}")
        self.setMinimumSize(900, 600)
        self.resize(1000, 650)
        
        self.init_ui()
        self.load_notes()
        
        # Auto-save timer
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.auto_save_current_note)
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Create horizontal splitter for two-panel layout
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Notes list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Button bar for left panel
        button_bar = QHBoxLayout()
        self.add_note_btn = QPushButton("+ New Note")
        self.add_note_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.add_note_btn.clicked.connect(self.add_new_note)
        
        self.delete_note_btn = QPushButton("🗑 Delete")
        self.delete_note_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.delete_note_btn.clicked.connect(self.delete_current_note)
        
        button_bar.addWidget(self.add_note_btn)
        button_bar.addWidget(self.delete_note_btn)
        left_layout.addLayout(button_bar)
        
        # Notes list
        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
        """)
        self.notes_list.currentItemChanged.connect(self.on_note_selected)
        left_layout.addWidget(self.notes_list)
        
        # Right panel - Text editor
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar for formatting
        self.toolbar = self.create_toolbar()
        right_layout.addWidget(self.toolbar)
        
        # Rich text editor with clickable links
        self.text_editor = ClickableTextEdit()
        self.text_editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                font-size: 14px;
                padding: 10px;
                line-height: 1.5;
            }
        """)
        self.text_editor.textChanged.connect(self.on_text_changed)
        self.text_editor.cursorPositionChanged.connect(self.update_format_actions)
        
        # Set placeholder for first line
        self.text_editor.setPlaceholderText("Enter note title on first line (will be underlined)...")
        
        right_layout.addWidget(self.text_editor)
        
        # Line counter label
        self.line_counter = QLabel("Lines with text: 0")
        self.line_counter.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
                background-color: #f0f0f0;
                border-top: 1px solid #ccc;
            }
        """)
        self.line_counter.setAlignment(Qt.AlignRight)
        right_layout.addWidget(self.line_counter)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)  # Left panel
        splitter.setStretchFactor(1, 3)  # Right panel takes more space
        splitter.setSizes([250, 750])
        
        layout.addWidget(splitter)
        
        # Close button at bottom
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_btn)
        layout.addLayout(bottom_layout)
    
    def create_toolbar(self):
        """Create the formatting toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                spacing: 2px;
                padding: 4px;
            }
            QToolButton {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 4px 5px;
                margin: 1px;
                color: black;
                font-size: 11px;
                min-width: 22px;
                min-height: 22px;
                max-width: 35px;
            }
            QToolButton:hover {
                background-color: #e3f2fd;
                border: 1px solid #2196F3;
            }
            QToolButton:checked {
                background-color: #2196F3;
                color: white;
                border: 1px solid #1976D2;
            }
            QToolButton:pressed {
                background-color: #1976D2;
            }
            QComboBox, QSpinBox {
                background-color: white;
                border: 1px solid #ccc;
                padding: 3px;
                min-height: 20px;
                color: black;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QLabel {
                color: black;
                font-weight: bold;
                padding: 0 3px;
            }
        """)
        
        # Font family
        font_label = QLabel("Font:")
        toolbar.addWidget(font_label)
        self.font_combo = QFontComboBox()
        self.font_combo.setFixedWidth(100)
        self.font_combo.setMaxVisibleItems(10)
        self.font_combo.setStyleSheet("QFontComboBox { color: black; background: white; }")
        self.font_combo.currentFontChanged.connect(self.change_font_family)
        toolbar.addWidget(self.font_combo)
        
        # Font size
        size_label = QLabel("Size:")
        toolbar.addWidget(size_label)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(14)
        self.font_size_spin.setSuffix("pt")
        self.font_size_spin.setFixedWidth(55)
        self.font_size_spin.setStyleSheet("QSpinBox { color: black; background: white; }")
        self.font_size_spin.valueChanged.connect(self.change_font_size)
        toolbar.addWidget(self.font_size_spin)
        
        toolbar.addSeparator()
        # Bold
        self.bold_action = QAction("B", self)
        self.bold_action.setCheckable(True)
        self.bold_action.setToolTip("Bold (Ctrl+B)")
        self.bold_action.triggered.connect(self.toggle_bold)
        self.bold_action.setShortcut("Ctrl+B")
        toolbar.addAction(self.bold_action)
        
        # Italic
        self.italic_action = QAction("I", self)
        self.italic_action.setCheckable(True)
        self.italic_action.setToolTip("Italic (Ctrl+I)")
        self.italic_action.triggered.connect(self.toggle_italic)
        self.italic_action.setShortcut("Ctrl+I")
        toolbar.addAction(self.italic_action)
        
        # Underline
        self.underline_action = QAction("U", self)
        self.underline_action.setCheckable(True)
        self.underline_action.setToolTip("Underline (Ctrl+U)")
        self.underline_action.triggered.connect(self.toggle_underline)
        self.underline_action.setShortcut("Ctrl+U")
        toolbar.addAction(self.underline_action)
        
        # Strikethrough
        self.strike_action = QAction("S", self)
        self.strike_action.setCheckable(True)
        self.strike_action.setToolTip("Strikethrough")
        self.strike_action.triggered.connect(self.toggle_strikethrough)
        toolbar.addAction(self.strike_action)
        
        toolbar.addSeparator()
        
        # Text color
        color_action = QAction("A", self)
        color_action.setToolTip("Text Color")
        color_action.triggered.connect(self.change_text_color)
        toolbar.addAction(color_action)
        
        # Background color
        bg_color_action = QAction("■", self)
        bg_color_action.setToolTip("Highlight")
        bg_color_action.triggered.connect(self.change_background_color)
        toolbar.addAction(bg_color_action)
        
        toolbar.addSeparator()
        
        # Alignment
        align_left_action = QAction("←", self)
        align_left_action.setToolTip("Left")
        align_left_action.triggered.connect(lambda: self.text_editor.setAlignment(Qt.AlignLeft))
        toolbar.addAction(align_left_action)
        
        align_center_action = QAction("·", self)
        align_center_action.setToolTip("Center")
        align_center_action.triggered.connect(lambda: self.text_editor.setAlignment(Qt.AlignCenter))
        toolbar.addAction(align_center_action)
        
        align_right_action = QAction("→", self)
        align_right_action.setToolTip("Right")
        align_right_action.triggered.connect(lambda: self.text_editor.setAlignment(Qt.AlignRight))
        toolbar.addAction(align_right_action)
        
        toolbar.addSeparator()
        
        # Bullet list
        bullet_action = QAction("•", self)
        bullet_action.setToolTip("Bullets")
        bullet_action.triggered.connect(self.insert_bullet_list)
        toolbar.addAction(bullet_action)
        
        # Numbered list
        number_action = QAction("1.", self)
        number_action.setToolTip("Numbers")
        number_action.triggered.connect(self.insert_numbered_list)
        toolbar.addAction(number_action)
        
        toolbar.addSeparator()
        
        # Clear formatting
        clear_action = QAction("✗", self)
        clear_action.setToolTip("Clear Format")
        clear_action.triggered.connect(self.clear_formatting)
        toolbar.addAction(clear_action)
        
        return toolbar
    
    def toggle_bold(self):
        """Toggle bold formatting"""
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if self.bold_action.isChecked() else QFont.Normal)
        self.merge_format(fmt)
    
    def toggle_italic(self):
        """Toggle italic formatting"""
        fmt = QTextCharFormat()
        fmt.setFontItalic(self.italic_action.isChecked())
        self.merge_format(fmt)
    
    def toggle_underline(self):
        """Toggle underline formatting"""
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self.underline_action.isChecked())
        self.merge_format(fmt)
    
    def toggle_strikethrough(self):
        """Toggle strikethrough formatting"""
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(self.strike_action.isChecked())
        self.merge_format(fmt)
    
    def change_font_family(self, font):
        """Change font family"""
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        self.merge_format(fmt)
    
    def change_font_size(self, size):
        """Change font size"""
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self.merge_format(fmt)
    
    def change_text_color(self):
        """Change text color"""
        color = QColorDialog.getColor()
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.merge_format(fmt)
    
    def change_background_color(self):
        """Change background color"""
        color = QColorDialog.getColor()
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self.merge_format(fmt)
    
    def insert_bullet_list(self):
        """Insert bullet list"""
        cursor = self.text_editor.textCursor()
        cursor.beginEditBlock()
        
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.ListDisc)
        cursor.createList(list_format)
        
        cursor.endEditBlock()
    
    def insert_numbered_list(self):
        """Insert numbered list"""
        cursor = self.text_editor.textCursor()
        cursor.beginEditBlock()
        
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.ListDecimal)
        cursor.createList(list_format)
        
        cursor.endEditBlock()
    
    def clear_formatting(self):
        """Clear all formatting"""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection():
            fmt = QTextCharFormat()
            cursor.setCharFormat(fmt)
    
    def merge_format(self, fmt):
        """Merge character format with current selection"""
        cursor = self.text_editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.text_editor.mergeCurrentCharFormat(fmt)
    
    def update_format_actions(self):
        """Update toolbar buttons based on current cursor format"""
        if self.is_updating:
            return
        
        cursor = self.text_editor.textCursor()
        fmt = cursor.charFormat()
        
        self.bold_action.setChecked(fmt.fontWeight() == QFont.Bold)
        self.italic_action.setChecked(fmt.fontItalic())
        self.underline_action.setChecked(fmt.fontUnderline())
        self.strike_action.setChecked(fmt.fontStrikeOut())
        
        # Update font combo
        if fmt.font().family():
            self.font_combo.setCurrentFont(fmt.font())
        
        # Update font size
        if fmt.fontPointSize() > 0:
            self.font_size_spin.setValue(int(fmt.fontPointSize()))
    
    def load_notes(self):
        """Load all notes for the current tab"""
        if not self.notes_manager or not self.tab_id:
            return
        
        notes = self.notes_manager.get_notes_for_tab(self.tab_id)
        self.notes_list.clear()
        
        for note in notes:
            item = QListWidgetItem(note['title'])
            item.setData(Qt.UserRole, note['id'])
            self.notes_list.addItem(item)
        
        # Select first note if available
        if self.notes_list.count() > 0:
            self.notes_list.setCurrentRow(0)
    
    def add_new_note(self):
        """Add a new note"""
        if not self.notes_manager or not self.tab_id:
            return
        
        # Save current note first
        if self.current_note:
            self.save_current_note()
        
        # Create new note
        note = self.notes_manager.add_note(self.tab_id, "Untitled Note", "")
        
        # Add to list
        item = QListWidgetItem(note['title'])
        item.setData(Qt.UserRole, note['id'])
        self.notes_list.addItem(item)
        
        # Select the new note
        self.notes_list.setCurrentItem(item)
        
        # Set focus to editor and ensure first line is underlined
        self.text_editor.setFocus()
        self.ensure_first_line_underlined()
    
    def delete_current_note(self):
        """Delete the currently selected note"""
        current_item = self.notes_list.currentItem()
        if not current_item:
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Delete Note", 
            "Are you sure you want to delete this note?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            note_id = current_item.data(Qt.UserRole)
            
            # Temporarily disconnect the selection signal to prevent triggering on_note_selected
            self.notes_list.currentItemChanged.disconnect(self.on_note_selected)
            
            # Delete from manager
            self.notes_manager.delete_note(self.tab_id, note_id)
            
            # Remove from list
            row = self.notes_list.row(current_item)
            self.notes_list.takeItem(row)
            
            # Clear editor and current note
            self.text_editor.clear()
            self.current_note = None
            
            # Reconnect the signal
            self.notes_list.currentItemChanged.connect(self.on_note_selected)
            
            # If there are remaining notes, select one
            if self.notes_list.count() > 0:
                # Select the note at the same position, or the last one if we deleted the last item
                new_row = min(row, self.notes_list.count() - 1)
                self.notes_list.setCurrentRow(new_row)
                # Manually trigger selection
                current_item = self.notes_list.currentItem()
                if current_item:
                    note_id = current_item.data(Qt.UserRole)
                    note = self.notes_manager.get_note(self.tab_id, note_id)
                if note:
                    self.current_note = note
                    self.is_updating = True
                    # Update the list item text with the actual note title
                    current_item.setText(note['title'])
                    self.text_editor.setHtml(note['content'])
                    # Ensure first line is underlined after loading
                    self.ensure_first_line_underlined()
                    # Update line counter
                    self.update_line_counter()
                    self.is_updating = False
    
    def on_note_selected(self, current, previous):
        """Handle note selection change"""
        # Save previous note
        if previous and self.current_note:
            self.save_current_note()
        
        # Load selected note
        if current:
            note_id = current.data(Qt.UserRole)
            note = self.notes_manager.get_note(self.tab_id, note_id)
            
            if note:
                self.current_note = note
                self.is_updating = True
                self.text_editor.setHtml(note['content'])
                # Ensure first line is underlined after loading
                self.ensure_first_line_underlined()
                # Update line counter
                self.update_line_counter()
                self.is_updating = False
    
    def on_text_changed(self):
        """Handle text changes - schedule auto-save and update title"""
        if self.is_updating or not self.current_note:
            return
        
        # Ensure first line is always underlined
        self.ensure_first_line_underlined()
        
        # Update line counter
        self.update_line_counter()
        
        # Schedule auto-save
        self.save_timer.start(1500)  # Save after 1.5 seconds of inactivity
        
        # Extract and update title from first line
        self.update_note_title()
    
    def ensure_first_line_underlined(self):
        """Ensure the first line is always underlined"""
        if self.is_updating:
            return
        
        self.is_updating = True
        
        # Get current cursor position
        cursor = self.text_editor.textCursor()
        saved_position = cursor.position()
        saved_anchor = cursor.anchor()
        
        # Create a new cursor to modify first line
        first_line_cursor = QTextCursor(self.text_editor.document())
        first_line_cursor.movePosition(QTextCursor.Start)
        first_line_cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 0)
        first_line_cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        
        # Apply underline format to first line
        fmt = QTextCharFormat()
        fmt.setFontUnderline(True)
        fmt.setFontWeight(QFont.Bold)  # Also make it bold for emphasis
        first_line_cursor.setCharFormat(fmt)
        
        # Restore original cursor position and selection
        cursor.setPosition(saved_anchor)
        cursor.setPosition(saved_position, QTextCursor.KeepAnchor)
        self.text_editor.setTextCursor(cursor)
        
        self.is_updating = False
    
    def update_line_counter(self):
        """Update the line counter with number of lines that have content"""
        text = self.text_editor.toPlainText()
        lines = text.split('\n')
        # Count non-empty lines
        non_empty_lines = sum(1 for line in lines if line.strip())
        self.line_counter.setText(f"Lines with text: {non_empty_lines}")
    
    def update_note_title(self):
        """Extract title from first line and update the list"""
        if not self.current_note:
            return
        
        # Get plain text
        text = self.text_editor.toPlainText()
        lines = text.split('\n')
        
        # First non-empty line is the title
        title = "Untitled Note"
        for line in lines:
            if line.strip():
                title = line.strip()[:50]  # Max 50 chars
                break
        
        # Update note title
        if title != self.current_note['title']:
            self.current_note['title'] = title
            
            # Update list item
            current_item = self.notes_list.currentItem()
            if current_item:
                current_item.setText(title)
    
    def save_current_note(self):
        """Save the current note"""
        if not self.current_note or not self.notes_manager:
            return
        
        content = self.text_editor.toHtml()
        self.notes_manager.update_note(
            self.tab_id, 
            self.current_note['id'], 
            title=self.current_note['title'],
            content=content
        )
    
    def auto_save_current_note(self):
        """Auto-save triggered by timer"""
        self.save_current_note()
    
    def closeEvent(self, event):
        """Save before closing"""
        if self.current_note:
            self.save_current_note()
        
        # Force immediate save to disk
        if self.notes_manager:
            self.notes_manager.force_save()
        
        event.accept()
    
    def accept(self):
        """Override accept to ensure save"""
        if self.current_note:
            self.save_current_note()
        
        # Force immediate save to disk
        if self.notes_manager:
            self.notes_manager.force_save()
        
        super().accept()
