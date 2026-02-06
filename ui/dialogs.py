"""Dialog windows for user input"""

import re
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QTextEdit, QPushButton, QFormLayout, QSizePolicy,
                             QWidget, QApplication, QToolBar, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics

class AddButtonDialog(QDialog):
    """Dialog for adding/editing command buttons"""
    
    def __init__(self, parent=None, name="", command="", description=""):
        super().__init__(parent)
        self.setWindowTitle("Add Command Button" if not name else "Edit Command Button")
        self.setMinimumWidth(400)
        self.init_ui(name, command, description)
        
    def init_ui(self, name, command, description):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        # Common input field stylesheet with fixed border width
        input_style = """
            QLineEdit, QTextEdit {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #0d47a1;
            }
        """
        
        self.name_input = QLineEdit(name)
        self.name_input.setPlaceholderText("e.g., Deploy App")
        self.name_input.setStyleSheet(input_style)
        form.addRow("Button Name:", self.name_input)
        
        self.command_input = QTextEdit()
        self.command_input.setAcceptRichText(False)  # Accept only plain text to avoid formatting issues
        # Set the command text explicitly using setPlainText to preserve newlines
        self.command_input.setPlainText(command)
        self.command_input.setPlaceholderText("e.g., npm run build && npm run deploy")
        self.command_input.setMinimumHeight(80)
        # Allow the command input to expand vertically when dialog is resized
        self.command_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Disable line numbers if any extension/widget tries to add them
        # QTextEdit doesn't have built-in line numbers, but ensure clean text handling
        self.command_input.setStyleSheet(input_style)
        form.addRow("Command:", self.command_input)
        
        self.description_input = QLineEdit(description)
        self.description_input.setPlaceholderText("Optional description")
        self.description_input.setStyleSheet(input_style)
        form.addRow("Description:", self.description_input)
        
        layout.addLayout(form)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def get_data(self):
        """Get the input data"""
        # Get command text and preserve newlines - strip only trailing whitespace
        command_text = self.command_input.toPlainText()
        # Remove any line number prefixes that might have been added (e.g., "1. ", "2. ", etc.)
        # This handles cases where line numbers might be displayed in the editor
        lines = command_text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove leading line numbers like "1. ", "2. ", etc. if present
            line = re.sub(r'^\d+\.\s*', '', line)
            cleaned_lines.append(line)
        command_text = '\n'.join(cleaned_lines)
        
        return {
            'name': self.name_input.text(),
            'command': command_text.rstrip(),  # Only strip trailing whitespace, preserve newlines
            'description': self.description_input.text()
        }


class AddFileDialog(QDialog):
    """Dialog for adding file metadata"""
    
    def __init__(self, parent=None, file_path=""):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle("Add File")
        self.setMinimumWidth(400)
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # File path
        path_label = QLabel(f"File: {self.file_path}")
        layout.addWidget(path_label)
        
        # Form
        form = QFormLayout()
        
        self.alias_input = QLineEdit()
        self.alias_input.setPlaceholderText("e.g., SSH Key")
        form.addRow("Alias:", self.alias_input)
        
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Optional description")
        form.addRow("Description:", self.description_input)
        
        layout.addLayout(form)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def get_data(self):
        """Get the input data"""
        return {
            'alias': self.alias_input.text(),
            'description': self.description_input.text(),
            'path': self.file_path
        }


class TextViewerDialog(QDialog):
    """Dialog for viewing terminal text with color rendering and minimap"""
    
    def __init__(self, parent=None, lines_data=None, title="Terminal Text Viewer"):
        # Don't set parent to make this a top-level window for minimap to find it
        super().__init__(None)
        self.setWindowTitle(title)
        self.setMinimumSize(1000, 600)
        
        # Store line data with formatting
        self.lines_data = lines_data or []
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #555;
                spacing: 5px;
                padding: 5px;
            }
            QToolBar QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QToolBar QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        
        # Add buttons
        save_btn = QPushButton("💾 Save to File")
        save_btn.clicked.connect(self.save_to_file)
        toolbar.addWidget(save_btn)
        
        copy_btn = QPushButton("📋 Copy All")
        copy_btn.clicked.connect(self.copy_all)
        toolbar.addWidget(copy_btn)
        
        toolbar.addSeparator()
        
        info_label = QLabel(f"Lines: {len(self.lines_data)}")
        info_label.setStyleSheet("color: #aaa; padding: 5px;")
        toolbar.addWidget(info_label)
        
        layout.addWidget(toolbar)
        
        # Content area with minimap
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Canvas for rendering text with colors
        self.canvas = TextViewerCanvas(self.lines_data)
        content_layout.addWidget(self.canvas)
        
        # Minimap
        from ui.minimap_widget import MinimapWidget
        self.minimap = MinimapWidget()
        self.minimap.setMaximumWidth(20)
        
        # Update minimap with content
        text_lines = [line['text'] for line in self.lines_data]
        self.minimap.set_content(text_lines)
        
        # Enable color filtering for errors/warnings automatically if they exist
        self.enable_minimap_filtering()
        
        # Connect minimap signals to canvas
        self.minimap.viewport_dragged.connect(self.on_minimap_scroll)
        self.minimap.position_clicked.connect(self.on_minimap_scroll)
        self.minimap.center_line_changed.connect(self.on_minimap_jump)
        
        # Connect canvas to minimap (for updating minimap when canvas scrolls)
        self.canvas.minimap = self.minimap
        self.canvas.dialog = self  # Give canvas reference to dialog for jump functionality
        
        # Initialize minimap viewport
        self.update_minimap_viewport()
        
        content_layout.addWidget(self.minimap)
        
        layout.addLayout(content_layout)
        
        # Close button
        button_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
    
    def enable_minimap_filtering(self):
        """Enable color filtering in minimap for errors and warnings"""
        import re
        from PyQt5.QtGui import QColor
        
        # Check if content has errors or warnings
        has_errors = False
        has_warnings = False
        
        for line_data in self.lines_data:
            text = line_data['text'].lower()
            if re.search(r'\b(error|exception|failed|failure)\b', text):
                has_errors = True
            if re.search(r'\b(warning|warn)\b', text):
                has_warnings = True
            if has_errors and has_warnings:
                break
        
        # Enable filtering if we found errors or warnings
        if has_errors or has_warnings:
            filtered_colors = []
            filtered_names = {}
            
            if has_errors:
                # Add red for errors
                error_color = QColor(255, 100, 100)
                filtered_colors.append(error_color)
                filtered_names[error_color.name()] = "Errors"
            
            if has_warnings:
                # Add yellow for warnings
                warning_color = QColor(255, 220, 100)
                filtered_colors.append(warning_color)
                filtered_names[warning_color.name()] = "Warnings"
            
            # Enable filtering
            self.minimap.color_filter_enabled = True
            self.minimap.filtered_colors = filtered_colors
            self.minimap.filtered_color_names = filtered_names
            self.minimap.filtered_indices_dirty = True
            self.minimap.update()
        
    def save_to_file(self):
        """Save the text content to a file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Text", 
            "", 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line_data in self.lines_data:
                        f.write(line_data['text'] + '\n')
                QMessageBox.information(self, "Success", f"Content saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
    
    def copy_all(self):
        """Copy all text to clipboard"""
        text = '\n'.join(line['text'] for line in self.lines_data)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "All text copied to clipboard")
    
    def on_minimap_scroll(self, position):
        """Handle minimap scroll"""
        # Calculate scroll position
        max_scroll = max(0, len(self.lines_data) * self.canvas.char_height - self.canvas.height())
        scroll_y = int(position * max_scroll)
        self.canvas.scroll_offset = scroll_y
        
        # Update viewport center line based on new scroll position
        self.canvas.viewport_center_line = (self.canvas.scroll_offset + self.canvas.height() // 2) // self.canvas.char_height
        self.canvas.viewport_center_line = max(0, min(len(self.lines_data) - 1, self.canvas.viewport_center_line))
        
        self.canvas.update()
        self.update_minimap_viewport()
    
    def on_minimap_jump(self, line_number):
        """Handle jump to specific line from minimap"""
        self.scroll_to_line(line_number)
    
    def scroll_to_line(self, line_number):
        """Scroll to center a specific line number"""
        if 0 <= line_number < len(self.lines_data):
            # Center the target line in viewport
            target_scroll = (line_number * self.canvas.char_height) - (self.canvas.height() // 2) + (self.canvas.char_height // 2)
            max_scroll = max(0, len(self.lines_data) * self.canvas.char_height - self.canvas.height())
            self.canvas.scroll_offset = max(0, min(max_scroll, target_scroll))
            
            # Update viewport highlighter
            self.canvas.viewport_center_line = line_number
            
            self.canvas.update()
            self.update_minimap_viewport()
        else:
            pass
    
    def update_minimap_viewport(self):
        """Update minimap viewport to reflect current canvas scroll position"""
        if len(self.lines_data) == 0:
            return
        
        # Calculate viewport position and height
        total_content_height = len(self.lines_data) * self.canvas.char_height
        visible_height = self.canvas.height()
        
        # Normalized position (0.0 to 1.0)
        if total_content_height > 0:
            viewport_start = self.canvas.scroll_offset / total_content_height
            viewport_height = visible_height / total_content_height
        else:
            viewport_start = 0.0
            viewport_height = 1.0
        
        # Clamp values
        viewport_start = max(0.0, min(1.0, viewport_start))
        viewport_height = max(0.0, min(1.0 - viewport_start, viewport_height))
        
        # Update minimap
        self.minimap.viewport_start = viewport_start
        self.minimap.viewport_height = viewport_height
        self.minimap.update()


class TextViewerCanvas(QWidget):
    """Canvas for rendering text with ANSI colors"""
    
    def __init__(self, lines_data):
        super().__init__()
        self.lines_data = lines_data
        self.scroll_offset = 0
        self.minimap = None  # Will be set by parent dialog
        self.dialog = None  # Reference to parent dialog for jump functionality
        
        # Font setup
        self.font_size = 13
        self.font = QFont('Menlo', self.font_size)
        self.font.setStyleHint(QFont.Monospace)
        self.font.setFixedPitch(True)
        
        # Calculate character dimensions
        metrics = QFontMetrics(self.font)
        self.char_width = metrics.horizontalAdvance('M')
        self.char_height = metrics.height()
        self.char_ascent = metrics.ascent()
        
        # Line numbers
        self.show_line_numbers = True
        self.line_number_width = 6
        self.line_number_color = QColor('#808080')
        self.line_number_bg_color = QColor('#252525')
        
        # Viewport highlighter
        self.viewport_center_line = 0
        self.viewport_highlight_color = QColor('#00ff00')
        
        # Colors
        self.bg_color = QColor('#1e1e1e')
        self.fg_color = QColor('#e5e5e5')
        
        # ANSI color mapping (same as terminal)
        self.color_map = {
            'black': QColor(12, 12, 12),
            'red': QColor(205, 49, 49),
            'green': QColor(13, 188, 121),
            'brown': QColor(229, 229, 16),
            'blue': QColor(36, 114, 200),
            'magenta': QColor(188, 63, 188),
            'cyan': QColor(17, 168, 205),
            'white': QColor(229, 229, 229),
            'default': self.fg_color
        }
        
        self.bright_color_map = {
            'black': QColor(102, 102, 102),
            'red': QColor(241, 76, 76),
            'green': QColor(35, 209, 139),
            'brown': QColor(245, 245, 67),
            'blue': QColor(59, 142, 234),
            'magenta': QColor(214, 112, 214),
            'cyan': QColor(41, 184, 219),
            'white': QColor(255, 255, 255),
            'default': self.fg_color
        }
        
        self.setStyleSheet("background-color: #1e1e1e;")
        
        # Enable mouse tracking for viewport interaction
        self.setMouseTracking(True)
        
        # Set up context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def get_color(self, color_name, is_bold=False):
        """Get QColor from color name"""
        if is_bold and color_name in self.bright_color_map:
            return self.bright_color_map[color_name]
        elif color_name in self.color_map:
            return self.color_map[color_name]
        return self.color_map['default']
    
    def paintEvent(self, event):
        """Paint the text content with colors"""
        from PyQt5.QtGui import QPen
        painter = QPainter(self)
        painter.setFont(self.font)
        
        # Fill background
        painter.fillRect(self.rect(), self.bg_color)
        
        # Calculate offsets for line numbers
        line_num_offset = self.line_number_width * self.char_width if self.show_line_numbers else 0
        
        # Draw line number background
        if self.show_line_numbers:
            painter.fillRect(0, 0, line_num_offset, self.height(), self.line_number_bg_color)
        
        # Calculate visible line range
        first_visible_line = max(0, self.scroll_offset // self.char_height)
        last_visible_line = min(len(self.lines_data), 
                                (self.scroll_offset + self.height()) // self.char_height + 1)
        
        # Render each visible line
        for line_idx in range(first_visible_line, last_visible_line):
            line_data = self.lines_data[line_idx]
            y_pos = (line_idx * self.char_height) - self.scroll_offset + self.char_ascent + 10
            
            # Draw viewport highlighter if this is the center line
            if line_idx == self.viewport_center_line:
                highlight_y = (line_idx * self.char_height) - self.scroll_offset + 10
                painter.fillRect(0, highlight_y, self.width(), self.char_height, 
                               QColor(self.viewport_highlight_color.red(), 
                                      self.viewport_highlight_color.green(), 
                                      self.viewport_highlight_color.blue(), 30))
                # Draw border around highlighted line
                painter.setPen(QPen(self.viewport_highlight_color, 1))
                painter.drawRect(0, highlight_y, self.width() - 1, self.char_height - 1)
            
            # Draw line number if enabled
            if self.show_line_numbers:
                line_num_text = f"{line_idx + 1:5d}"
                painter.setPen(self.line_number_color)
                painter.drawText(5, y_pos, line_num_text)
            
            # Start text rendering after line numbers
            x_pos = line_num_offset + 10
            
            # Render each character with its color
            for char_data in line_data.get('chars', []):
                char = char_data.get('char', ' ')
                fg_color = char_data.get('fg', 'default')
                bold = char_data.get('bold', False)
                
                # Get color
                color = self.get_color(fg_color, bold)
                painter.setPen(color)
                
                # Draw character
                painter.drawText(x_pos, y_pos, char)
                x_pos += self.char_width
        
        painter.end()
    
    def wheelEvent(self, event):
        """Handle mouse wheel scrolling"""
        # Scroll by 3 lines per wheel tick
        delta = -event.angleDelta().y() // 120 * 3 * self.char_height
        max_scroll = max(0, len(self.lines_data) * self.char_height - self.height())
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset + delta))
        
        # Update viewport center line based on scroll position
        self.viewport_center_line = (self.scroll_offset + self.height() // 2) // self.char_height
        self.viewport_center_line = max(0, min(len(self.lines_data) - 1, self.viewport_center_line))
        
        self.update()
        self.update_minimap_viewport()
    
    def update_minimap_viewport(self):
        """Update minimap viewport when canvas scrolls"""
        if self.minimap and len(self.lines_data) > 0:
            # Calculate viewport position and height
            total_content_height = len(self.lines_data) * self.char_height
            visible_height = self.height()
            
            # Normalized position (0.0 to 1.0)
            if total_content_height > 0:
                viewport_start = self.scroll_offset / total_content_height
                viewport_height = visible_height / total_content_height
            else:
                viewport_start = 0.0
                viewport_height = 1.0
            
            # Clamp values
            viewport_start = max(0.0, min(1.0, viewport_start))
            viewport_height = max(0.0, min(1.0 - viewport_start, viewport_height))
            
            # Update minimap
            self.minimap.viewport_start = viewport_start
            self.minimap.viewport_height = viewport_height
            self.minimap.update()
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on line numbers"""
        if event.button() == Qt.LeftButton and self.show_line_numbers:
            line_num_offset = self.line_number_width * self.char_width
            if event.pos().x() < line_num_offset:
                # Clicked on line number area
                y = event.pos().y() + self.scroll_offset - 10
                clicked_line = y // self.char_height
                if 0 <= clicked_line < len(self.lines_data):
                    self.viewport_center_line = clicked_line
                    
                    # Scroll to center the clicked line
                    target_scroll = (clicked_line * self.char_height) - (self.height() // 2) + (self.char_height // 2)
                    max_scroll = max(0, len(self.lines_data) * self.char_height - self.height())
                    self.scroll_offset = max(0, min(max_scroll, target_scroll))
                    
                    self.update()
                    self.update_minimap_viewport()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def show_context_menu(self, position):
        """Show context menu when right-clicking on viewport highlighter"""
        from PyQt5.QtWidgets import QMenu, QAction
        
        # Check if clicking near the viewport highlighter
        y = position.y() + self.scroll_offset - 10
        clicked_line = y // self.char_height
        
        # Only show menu if clicking on or near the highlighted line
        if abs(clicked_line - self.viewport_center_line) <= 1:
            menu = QMenu(self)
            
            # Jump to line action
            jump_action = QAction(f"📍 Line {self.viewport_center_line + 1}", self)
            jump_action.setEnabled(False)  # Just informational
            menu.addAction(jump_action)
            
            menu.addSeparator()
            
            # Copy line action
            copy_line_action = QAction("📋 Copy This Line", self)
            copy_line_action.triggered.connect(self.copy_highlighted_line)
            menu.addAction(copy_line_action)
            
            # Style the menu
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2b2b2b;
                    border: 1px solid #555;
                    padding: 5px;
                }
                QMenu::item {
                    color: #e0e0e0;
                    padding: 5px 30px;
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
            
            menu.exec_(self.mapToGlobal(position))
    
    def copy_highlighted_line(self):
        """Copy the highlighted line to clipboard"""
        if 0 <= self.viewport_center_line < len(self.lines_data):
            line_text = self.lines_data[self.viewport_center_line]['text']
            QApplication.clipboard().setText(line_text)

