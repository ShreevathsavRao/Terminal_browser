"""History viewer dialog for displaying archived terminal output"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTextEdit, QComboBox, QLabel, QScrollArea, QWidget,
                             QFileDialog, QMessageBox, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from datetime import datetime
import os
from ui.minimap_widget import MinimapWidget


class HistoryViewerDialog(QDialog):
    """Dialog for viewing and managing terminal history archives"""
    
    import_requested = pyqtSignal(list)  # Emits lines to import back to terminal
    
    def __init__(self, history_data, parent=None):
        super().__init__(parent)
        self.history_data = history_data
        self.current_archive_index = 0
        self.current_content_lines = []  # Store current history lines for minimap
        
        # Debug: print what we loaded
        archives = history_data.get("archives", [])
        print(f"\n[DEBUG] HistoryViewerDialog: Loaded history with {len(archives)} archives")
        for i, archive in enumerate(archives):
            context = archive.get("command_context", "Unknown")
            line_count = archive.get("line_count", len(archive.get("lines", [])))
            print(f"[DEBUG]   Archive #{i+1}: {line_count} lines, context='{context}'")
        print()
        
        self.setWindowTitle("Terminal History Viewer")
        self.setMinimumSize(1100, 600)  # Wider to accommodate minimap
        
        self.init_ui()
        self.load_archive(0)
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        
        # Top bar with archive selector
        top_bar = QHBoxLayout()
        
        # Archive info
        self.archive_label = QLabel("Archives:")
        top_bar.addWidget(self.archive_label)
        
        # Archive selector
        self.archive_combo = QComboBox()
        self.populate_archive_combo()
        self.archive_combo.currentIndexChanged.connect(self.on_archive_changed)
        top_bar.addWidget(self.archive_combo, 1)
        
        # Filter by type
        top_bar.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Content Only", "Markers Only"])
        self.filter_combo.currentIndexChanged.connect(self.refresh_display)
        top_bar.addWidget(self.filter_combo)
        
        layout.addLayout(top_bar)
        
        # Archive metadata
        self.metadata_label = QLabel()
        self.metadata_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 8px;
                border: 1px solid #555;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.metadata_label)
        
        # Create horizontal splitter for content and minimap
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Content display (terminal-like)
        self.content_view = QTextEdit()
        self.content_view.setReadOnly(True)
        self.content_view.setFont(QFont("Menlo", 12))
        self.content_view.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e5e5e5;
                border: 1px solid #555;
            }
        """)
        content_splitter.addWidget(self.content_view)
        
        # Minimap widget
        self.minimap = MinimapWidget()
        self.minimap.setMinimumWidth(20)
        self.minimap.setMaximumWidth(20)
        content_splitter.addWidget(self.minimap)
        
        # Set splitter sizes - content takes most space, minimap is fixed width
        content_splitter.setStretchFactor(0, 1)  # Content expands
        content_splitter.setStretchFactor(1, 0)  # Minimap stays fixed
        content_splitter.setCollapsible(0, False)  # Content cannot be collapsed
        content_splitter.setCollapsible(1, False)  # Minimap cannot be collapsed
        
        layout.addWidget(content_splitter, 1)
        
        # Connect content view scrolling to minimap viewport updates
        self.content_view.verticalScrollBar().valueChanged.connect(self._update_minimap_viewport)
        
        # Connect minimap clicks to content view scrolling
        self.minimap.viewport_dragged.connect(self._on_minimap_scrolled)
        self.minimap.position_clicked.connect(self._on_minimap_clicked)
        
        # Bottom buttons
        button_bar = QHBoxLayout()
        
        self.import_btn = QPushButton("Import to Terminal")
        self.import_btn.setToolTip("Add this archived content back to the terminal")
        self.import_btn.clicked.connect(self.import_archive)
        button_bar.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("Export as Text")
        self.export_btn.setToolTip("Save as plain text file")
        self.export_btn.clicked.connect(self.export_as_text)
        button_bar.addWidget(self.export_btn)
        
        button_bar.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_bar.addWidget(self.close_btn)
        
        layout.addLayout(button_bar)
        
        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #5c5c5c;
            }
            QComboBox {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #e0e0e0;
                margin-right: 5px;
            }
        """)
    
    def populate_archive_combo(self):
        """Populate the archive dropdown with all archives"""
        self.archive_combo.clear()
        
        archives = self.history_data.get("archives", [])
        
        # Handle new continuous append format (multiple archives in array)
        if archives:
            # Add "All Archives" option first
            total_lines = sum(archive.get("line_count", len(archive.get("lines", []))) for archive in archives)
            self.archive_combo.addItem(f"All Archives ({len(archives)} archives, {total_lines} lines)")
            
            # Add individual archives
            for i, archive in enumerate(archives):
                timestamp = archive.get("timestamp", "Unknown")
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = timestamp
                
                line_count = archive.get("line_count", len(archive.get("lines", [])))
                context = archive.get("command_context", "Unknown")
                row_range = archive.get("row_range", "")
                
                # Shorten context if too long
                if len(context) > 30:
                    context = context[:27] + "..."
                
                label = f"Archive #{i+1} - {time_str} ({line_count} lines) - {context}"
                self.archive_combo.addItem(label)
            return
        
        # Handle legacy format: single lines array (backward compatibility)
        if "lines" in self.history_data:
            timestamp = self.history_data.get("created_at", "Unknown")
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = timestamp
            
            total_lines = self.history_data.get("total_lines", len(self.history_data.get("lines", [])))
            command = self.history_data.get("command_context", "clear")
            label = f"Terminal History - {time_str} ({total_lines} lines) - {command}"
            self.archive_combo.addItem(label)
            return
    
    def on_archive_changed(self, index):
        """Handle archive selection change"""
        if index >= 0:
            self.load_archive(index)
    
    def load_archive(self, index):
        """Load and display an archive or all archives"""
        archives = self.history_data.get("archives", [])
        
        # Handle new continuous append format (multiple archives)
        if archives:
            # Index 0 = "All Archives" option, 1+ = individual archives
            if index == 0:
                # Display ALL archives combined
                self.current_archive_index = -1  # -1 means "all"
                
                total_lines = sum(archive.get("line_count", len(archive.get("lines", []))) for archive in archives)
                first_timestamp = archives[0].get("timestamp", "Unknown") if archives else "Unknown"
                last_timestamp = archives[-1].get("timestamp", "Unknown") if archives else "Unknown"
                
                try:
                    dt_first = datetime.fromisoformat(first_timestamp)
                    dt_last = datetime.fromisoformat(last_timestamp)
                    time_range = f"{dt_first.strftime('%Y-%m-%d %H:%M:%S')} to {dt_last.strftime('%H:%M:%S')}"
                except:
                    time_range = f"{first_timestamp} to {last_timestamp}"
                
                metadata_text = (
                    f"<b>All Archives:</b> {len(archives)} archives | "
                    f"<b>Total Lines:</b> {total_lines} | "
                    f"<b>Time Range:</b> {time_range}"
                )
                self.metadata_label.setText(metadata_text)
            else:
                # Display individual archive (index-1 because index 0 is "All Archives")
                archive_index = index - 1
                if archive_index < 0 or archive_index >= len(archives):
                    return
                
                self.current_archive_index = archive_index
                archive = archives[archive_index]
                
                timestamp = archive.get("timestamp", "Unknown")
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = timestamp
                
                line_count = archive.get("line_count", len(archive.get("lines", [])))
                context = archive.get("command_context", "Unknown")
                row_range = archive.get("row_range", "Unknown")
                
                metadata_text = (
                    f"<b>Archive #{archive_index + 1}:</b> {time_str} | "
                    f"<b>Lines:</b> {line_count} | "
                    f"<b>Context:</b> {context} | "
                    f"<b>Range:</b> {row_range}"
                )
                self.metadata_label.setText(metadata_text)
            
            # Display content
            self.refresh_display()
            return
        
        # Handle legacy format: single lines array (backward compatibility)
        if "lines" in self.history_data:
            self.current_archive_index = 0
            
            timestamp = self.history_data.get("created_at", "Unknown")
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = timestamp
            
            command = self.history_data.get("command_context", "clear")
            line_count = len(self.history_data.get("lines", []))
            total_lines = self.history_data.get("total_lines", line_count)
            
            metadata_text = (
                f"<b>Timestamp:</b> {time_str} | "
                f"<b>Lines:</b> {total_lines} | "
                f"<b>Command:</b> {command}"
            )
            self.metadata_label.setText(metadata_text)
            
            self.refresh_display()
            return
    
    def refresh_display(self):
        """Refresh the content display based on current filter"""
        archives = self.history_data.get("archives", [])
        
        # Determine which lines to display
        lines = []
        
        # Handle new continuous append format (multiple archives)
        if archives:
            if self.current_archive_index == -1:
                # Display ALL archives combined with separators
                for i, archive in enumerate(archives):
                    # Add separator before each archive (including first)
                    separator_line = {
                        "type": "archive_separator",
                        "archive_number": i + 1,
                        "timestamp": archive.get("timestamp", "Unknown"),
                        "context": archive.get("command_context", "Unknown"),
                        "line_count": archive.get("line_count", len(archive.get("lines", [])))
                    }
                    lines.append(separator_line)
                    
                    archive_lines = archive.get("lines", [])
                    lines.extend(archive_lines)
            else:
                # Display single archive
                if self.current_archive_index >= 0 and self.current_archive_index < len(archives):
                    archive = archives[self.current_archive_index]
                    lines = archive.get("lines", [])
        else:
            # Handle legacy format: single lines array
            lines = self.history_data.get("lines", [])
        
        # Get filter
        filter_type = self.filter_combo.currentText()
        
        # Clear content
        self.content_view.clear()
        cursor = self.content_view.textCursor()
        
        # Store content lines for minimap (plain text)
        self.current_content_lines = []
        
        # Render lines with line numbers
        line_counter = 1
        for line_data in lines:
            line_type = line_data.get("type", "content")
            
            # Apply filter
            if filter_type == "Content Only" and line_type == "streaming_marker":
                continue
            elif filter_type == "Markers Only" and line_type != "streaming_marker":
                continue
            
            if line_type == "archive_separator":
                # Render archive separator
                self._render_archive_separator(cursor, line_data)
                # Add separator to minimap
                self.current_content_lines.append("")
                self.current_content_lines.append("─" * 60)
                self.current_content_lines.append("")
            elif line_type == "streaming_marker":
                self._render_streaming_marker(cursor, line_data)
                # Add marker content to minimap lines
                marker_content = line_data.get("content", "")
                for marker_line in marker_content.split('\n'):
                    self.current_content_lines.append(marker_line)
            else:
                content = line_data.get("content", "")
                self._render_content_line(cursor, line_data, line_counter)
                # Add content to minimap lines
                self.current_content_lines.append(content)
                line_counter += 1
        
        # Update minimap with content
        self.minimap.set_content(self.current_content_lines)
        self._update_minimap_viewport()
    
    def _render_archive_separator(self, cursor, separator_data):
        """Render a visual separator between archives with timestamp"""
        archive_number = separator_data.get("archive_number", 0)
        timestamp = separator_data.get("timestamp", "Unknown")
        context = separator_data.get("context", "Unknown")
        line_count = separator_data.get("line_count", 0)
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            time_str = timestamp
        
        # Create separator line
        separator_line = "─" * 80
        
        # Create header text
        header_text = f"📋 Archive #{archive_number} • {time_str} • {line_count} lines • {context}"
        
        # Render separator with styling
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(100, 200, 255))  # Bright blue
        fmt.setBackground(QColor(30, 40, 50))
        fmt.setFontWeight(QFont.Bold)
        
        # Insert blank line
        cursor.insertText("\n")
        
        # Insert top separator
        cursor.insertText(separator_line + "\n", fmt)
        
        # Insert header
        cursor.insertText(header_text + "\n", fmt)
        
        # Insert bottom separator
        cursor.insertText(separator_line + "\n", fmt)
        
        # Insert blank line
        cursor.insertText("\n")
        
        # Move cursor
        self.content_view.setTextCursor(cursor)
    
    def _render_streaming_marker(self, cursor, marker_data):
        """Render a streaming marker with special styling"""
        marker_type = marker_data.get("marker_type", "unknown")
        content = marker_data.get("content", "")
        
        # Choose color based on marker type
        if marker_type == "stopped":
            color = QColor(255, 200, 100)  # Yellow/orange for pause
            bg_color = QColor(80, 60, 20)
        else:  # resumed
            color = QColor(100, 255, 100)  # Green for resume
            bg_color = QColor(20, 60, 20)
        
        # Create format
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        fmt.setBackground(bg_color)
        fmt.setFontWeight(QFont.Bold)
        
        # Insert marker
        cursor.insertText(content, fmt)
        cursor.insertText("\n")
        
        # Move cursor
        self.content_view.setTextCursor(cursor)
    
    def _render_content_line(self, cursor, line_data, line_number):
        """Render a regular content line with colors and line number"""
        content = line_data.get("content", "")
        colors = line_data.get("colors", {})
        
        # Get color for this line based on content (using minimap's logic)
        line_color = self.minimap.get_line_color(content)
        
        # Render line number with minimap's keyword color
        line_num_fmt = QTextCharFormat()
        line_num_fmt.setForeground(line_color)
        cursor.insertText(f"{line_number:6d}: ", line_num_fmt)
        
        # Create format for content
        fmt = QTextCharFormat()
        
        # Set colors if available
        fg_color_name = colors.get("fg", "default")
        bg_color_name = colors.get("bg", "default")
        
        # Map color names to QColor (basic set)
        color_map = {
            "default": QColor(229, 229, 229),
            "black": QColor(0, 0, 0),
            "red": QColor(255, 100, 100),
            "green": QColor(100, 255, 100),
            "yellow": QColor(255, 255, 100),
            "blue": QColor(100, 150, 255),
            "magenta": QColor(255, 100, 255),
            "cyan": QColor(100, 255, 255),
            "white": QColor(255, 255, 255),
        }
        
        if fg_color_name in color_map:
            fmt.setForeground(color_map[fg_color_name])
        
        if bg_color_name != "default" and bg_color_name in color_map:
            fmt.setBackground(color_map[bg_color_name])
        
        # Insert text
        cursor.insertText(content + "\n", fmt)
        self.content_view.setTextCursor(cursor)
    
    def import_archive(self):
        """Import current archive back to terminal"""
        # Handle both old format (archives array) and new format (single lines array)
        archives = self.history_data.get("archives", [])
        
        # New format: single consolidated file
        if not archives and "lines" in self.history_data:
            lines = self.history_data.get("lines", [])
        else:
            # Old format: archives array
            if self.current_archive_index >= len(archives):
                return
            archive = archives[self.current_archive_index]
            lines = archive.get("lines", [])
        
        # Filter out streaming markers for import
        content_lines = [line for line in lines if line.get("type") != "streaming_marker"]
        
        if not content_lines:
            QMessageBox.information(
                self,
                "No Content",
                "This archive contains no content to import (only markers)."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Import Archive",
            f"Import {len(content_lines)} lines back to the terminal?\n\n"
            "This will add the content to the current terminal view.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.import_requested.emit(content_lines)
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully imported {len(content_lines)} lines to terminal."
            )
    
    def export_as_text(self):
        """Export current archive as plain text file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Archive as Text",
            os.path.expanduser("~/terminal_archive.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Handle both old format (archives array) and new format (single lines array)
            archives = self.history_data.get("archives", [])
            
            # New format: single consolidated file
            if not archives and "lines" in self.history_data:
                timestamp = self.history_data.get("created_at", "Unknown")
                command = self.history_data.get("command_context", "clear")
                lines = self.history_data.get("lines", [])
                total_lines = self.history_data.get("total_lines", len(lines))
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Write header
                    f.write("="*60 + "\n")
                    f.write("Terminal Browser - Archived Output\n")
                    f.write("="*60 + "\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Total Lines: {total_lines}\n")
                    f.write(f"Command: {command}\n")
                    f.write("="*60 + "\n\n")
                    
                    # Write content
                    for line in lines:
                        content = line.get("content", "")
                        f.write(content + "\n")
            else:
                # Old format: archives array
                archive = archives[self.current_archive_index]
                lines = archive.get("lines", [])
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    # Write header
                    f.write("="*60 + "\n")
                    f.write("Terminal Browser - Archived Output\n")
                    f.write("="*60 + "\n")
                    f.write(f"Timestamp: {archive.get('timestamp', 'Unknown')}\n")
                    f.write(f"Row Range: {archive.get('row_range', 'Unknown')}\n")
                    f.write(f"Command: {archive.get('command_context', 'Unknown')}\n")
                    f.write("="*60 + "\n\n")
                    
                    # Write content
                    for line in lines:
                        content = line.get("content", "")
                        f.write(content + "\n")
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Archive exported successfully to:\n{file_path}"
            )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export archive:\n{str(e)}"
            )
    
    def _update_minimap_viewport(self, value=None):
        """Update minimap viewport based on content view scroll position"""
        scrollbar = self.content_view.verticalScrollBar()
        if not scrollbar:
            return
        
        # Calculate viewport position and size
        max_val = scrollbar.maximum()
        min_val = scrollbar.minimum()
        current_val = scrollbar.value()
        page_step = scrollbar.pageStep()
        
        if max_val > min_val:
            # Calculate normalized position (0.0 to 1.0)
            total_range = max_val - min_val + page_step
            viewport_start = current_val / total_range if total_range > 0 else 0.0
            viewport_height = page_step / total_range if total_range > 0 else 1.0
            
            # Update minimap viewport
            self.minimap.set_viewport(viewport_start, viewport_height)
        else:
            # Content fits entirely in view
            self.minimap.set_viewport(0.0, 1.0)
    
    def _on_minimap_scrolled(self, normalized_position):
        """Handle minimap viewport dragging - scroll content view"""
        scrollbar = self.content_view.verticalScrollBar()
        if not scrollbar:
            return
        
        # Convert normalized position to scrollbar value
        max_val = scrollbar.maximum()
        min_val = scrollbar.minimum()
        page_step = scrollbar.pageStep()
        
        total_range = max_val - min_val + page_step
        new_value = int(normalized_position * total_range)
        
        # Block signals to prevent feedback loop
        scrollbar.blockSignals(True)
        scrollbar.setValue(new_value)
        scrollbar.blockSignals(False)
        
        # Manually update minimap viewport
        self._update_minimap_viewport()
    
    def _on_minimap_clicked(self, normalized_position):
        """Handle minimap click - jump to position"""
        # For simplicity, treat click same as drag
        self._on_minimap_scrolled(normalized_position)
