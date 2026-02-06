"""Full-featured terminal widget using pyte for proper interactive command support"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QSpinBox, QPushButton, QApplication, QMenu, QAction, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QEvent, QPointF
from PyQt5.QtGui import QFont, QColor, QPainter, QPalette, QKeyEvent, QFontMetrics, QMouseEvent, QPen, QPolygonF
import os
import sys
import pty
import select
import termios
import struct
import fcntl
import signal
import re
import time
import subprocess
import platform
import pyte
import uuid
from datetime import datetime
from core.preferences_manager import PreferencesManager
from core.platform_manager import get_platform_manager
from ui.suggestion_widget import SuggestionWidget, SuggestionManager
from ui.terminal_search_widget import TerminalSearchWidget
import socket

# Toggle UI debug logging in hot paths (set to True only when debugging)
UI_DEBUG = False


class PTYReader(QThread):
    """Thread to read from PTY master"""
    
    output_received = pyqtSignal(bytes)
    
    def __init__(self, master_fd):
        super().__init__()
        self.master_fd = master_fd
        self.running = True
        
    def run(self):
        """Read from PTY and emit output"""
        while self.running:
            try:
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        try:
                            self.output_received.emit(data)
                        except RuntimeError:
                            # Widget deleted, stop thread
                            break
                    else:
                        break
            except OSError:
                break
    
    def stop(self):
        """Stop the reader thread"""
        self.running = False


class TerminalCanvas(QWidget):
    """Canvas widget for rendering terminal content"""
    
    # Bottom padding: always show 3 empty lines below the last content
    BOTTOM_PADDING_LINES = 3
    
    def __init__(self, parent=None):
        # Initialize all attributes used in event handlers and paintEvent early with defaults
        self._initialized = False
        
        # Load preferences early
        prefs_manager = PreferencesManager()
        
        # Basic attributes
        self.screen = None
        self.parent_terminal = parent
        
        # Font and sizing
        self.font_size = prefs_manager.get('terminal', 'font_size', 13)
        font_family = prefs_manager.get('terminal', 'font_family', 'Menlo')
        self.font = QFont(font_family, self.font_size)
        self.font.setStyleHint(QFont.Monospace)
        self.font.setFixedPitch(True)
        self.char_width = 10
        self.char_height = 18
        self.char_ascent = 14
        self.user_columns = prefs_manager.get('terminal', 'columns', 600)
        
        # Colors
        bg_color = prefs_manager.get('appearance', 'background_color', '#1e1e1e')
        self.bg_color = QColor(bg_color)
        self.fg_color = QColor(prefs_manager.get('appearance', 'foreground_color', '#e5e5e5'))
        self.cursor_color_pref = QColor(prefs_manager.get('appearance', 'cursor_color', '#00ff00'))
        self.selection_color_pref = QColor(prefs_manager.get('appearance', 'selection_color', '#3399ff'))
        
        # Line numbers
        self.show_line_numbers = True
        self.show_column_numbers = True
        self.line_number_width = 6
        self.column_number_height = 1
        self.line_number_color = QColor('#808080')
        self.line_number_bg_color = QColor('#252525')
        self.column_number_color = QColor('#808080')
        self.column_number_bg_color = QColor('#252525')
        self.colored_line_numbers = prefs_manager.get('terminal', 'colored_line_numbers', True)
        
        # Cursor
        cursor_blink = prefs_manager.get('terminal', 'cursor_blink', True)
        self.cursor_visible = True
        self.cursor_blink_enabled = cursor_blink
        
        # Selection
        self.selection_start = None
        self.selection_end = None
        self.selection_anchor = None
        self.is_selecting = False
        
        # Mouse tracking
        self.last_click_time = 0
        self.last_click_pos = None
        self.click_count = 0
        self.triple_click_timeout_ms = 400
        self.hover_range = None
        self.is_selecting_by_line_number = False
        self.line_number_selection_anchor = None  # Track anchor line for shift-click selection
        self.viewport_center_line = -1
        self._last_mouse_pos = None  # Track last mouse position for modifier key changes
        self._pending_hover_range = None  # Pending hover range for debouncing
        self._hover_update_timer = QTimer()  # Timer for debouncing hover updates
        self._hover_update_timer.timeout.connect(self._apply_hover_update)
        self._hover_update_timer.setSingleShot(True)
        
        # Search
        self.search_matches = []
        self.current_search_match = -1
        
        # Content tracking
        self._selection_content_hash = None
        self._selection_start_line_content = None
        self._total_lines_count = 0
        self._cumulative_line_offset = 0
        self.max_content_width = 0
        
        # Color maps
        colors_prefs = prefs_manager.get_category('colors')
        self.color_map = {
            'black': QColor(colors_prefs.get('black', '#000000')),
            'red': QColor(colors_prefs.get('red', '#cd3131')),
            'green': QColor(colors_prefs.get('green', '#0dbc79')),
            'brown': QColor(colors_prefs.get('yellow', '#e5e510')),
            'yellow': QColor(colors_prefs.get('yellow', '#e5e510')),
            'blue': QColor(colors_prefs.get('blue', '#2472c8')),
            'magenta': QColor(colors_prefs.get('magenta', '#bc3fbc')),
            'cyan': QColor(colors_prefs.get('cyan', '#11a8cd')),
            'white': QColor(colors_prefs.get('white', '#e5e5e5')),
            'default': QColor(colors_prefs.get('white', '#e5e5e5')),
        }
        self.bright_color_map = {
            'black': QColor(colors_prefs.get('bright_black', '#666666')),
            'red': QColor(colors_prefs.get('bright_red', '#f14c4c')),
            'green': QColor(colors_prefs.get('bright_green', '#23d18b')),
            'brown': QColor(colors_prefs.get('bright_yellow', '#f5f543')),
            'yellow': QColor(colors_prefs.get('bright_yellow', '#f5f543')),
            'blue': QColor(colors_prefs.get('bright_blue', '#3b8eea')),
            'magenta': QColor(colors_prefs.get('bright_magenta', '#d670d6')),
            'cyan': QColor(colors_prefs.get('bright_cyan', '#29b8db')),
            'white': QColor(colors_prefs.get('bright_white', '#ffffff')),
            'default': QColor(255, 255, 255),
        }
        
        # Viewport highlight
        viewport_highlight_color = prefs_manager.get('terminal', 'viewport_highlight_color', 'auto')
        if viewport_highlight_color == 'auto':
            self.viewport_highlight_color = self.get_opposite_color(self.bg_color)
        else:
            self.viewport_highlight_color = QColor(viewport_highlight_color)

        super().__init__(parent)
        
        # Enable mouse tracking to receive mouseMoveEvent without buttons pressed
        self.setMouseTracking(True)
        
        # Set up context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Calculate character dimensions
        self.update_char_size()
        
        self._initialized = True  # Mark as fully initialized

    def get_user_columns(self):
        """Return user-set columns if set, else None for auto."""
        return self.user_columns if self.user_columns and self.user_columns > 0 else None
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts for copy/paste/select all
        
        IMPORTANT: We intentionally DO NOT use QShortcut for any operations.
        All keyboard shortcuts are handled in keyPressEvent of the parent terminal widget.
        
        This ensures that:
        1. ALL keys go through keyPressEvent first
        2. We can decide contextually whether to handle as GUI shortcut or terminal input
        3. Terminal applications (nano, vim, emacs, etc.) receive all keys they need
        4. Only Enter and Esc have special GUI behavior, everything else goes to terminal
        
        The following shortcuts are handled in handle_key_press():
        - Platform-specific copy/paste/select (Cmd+C/V/A on macOS, Ctrl+C/V on Windows/Linux)
        - Ctrl+Shift+C/V/A as alternative shortcuts on all platforms
        - All other keys are passed directly to the terminal application
        """
        # No shortcuts are set up here - all handling is done in keyPressEvent
        # This prevents QShortcut from intercepting keys before they reach the terminal
        self.shortcuts = []
    
    def handle_copy(self):
        """Handle copy shortcut"""
        if self.selection_start and self.selection_end:
            selected_text = self.get_selected_text()
            if selected_text:
                QApplication.clipboard().setText(selected_text)
    
    def handle_paste(self):
        """Handle paste shortcut"""
        clipboard_text = QApplication.clipboard().text()
        if clipboard_text and self.parent_terminal:
            self.parent_terminal.write_to_pty(clipboard_text)
    
    def handle_select_all(self):
        """Handle select all shortcut"""
        self.select_all()
    
    def event(self, event):
        """Override event to intercept Tab key and modifier key changes"""
        if event.type() == QEvent.KeyPress:
            key_event = QKeyEvent(event)
            
            # Intercept Tab and Shift+Tab to prevent focus navigation
            if key_event.key() == Qt.Key_Tab or key_event.key() == Qt.Key_Backtab:
                # Call keyPressEvent directly and mark event as accepted
                self.keyPressEvent(key_event)
                event.accept()
                return True
            
            # Check for Ctrl/Cmd key press - update hover if mouse is over widget
            if key_event.key() in (Qt.Key_Control, Qt.Key_Meta) and self._last_mouse_pos:
                self._update_hover_at_position(self._last_mouse_pos)
        
        elif event.type() == QEvent.KeyRelease:
            key_event = QKeyEvent(event)
            
            # Check for Ctrl/Cmd key release - clear hover
            if key_event.key() in (Qt.Key_Control, Qt.Key_Meta):
                if self.hover_range:
                    self.hover_range = None
                    self.update()
                event.accept()
                return True
        
        # For all other events, use default processing
        return super().event(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events and delegate to parent terminal"""
        try:
            if self.parent_terminal and hasattr(self.parent_terminal, 'handle_key_press'):
                self.parent_terminal.handle_key_press(event)
                event.accept()
            else:
                super().keyPressEvent(event)
        except RuntimeError:
            # Widget has been deleted, ignore the event
            pass
    
    def update_char_size(self):
        """Update character width and height based on font"""
        metrics = QFontMetrics(self.font)
        self.char_width = metrics.horizontalAdvance('M')
        self.char_height = metrics.height()
        self.char_ascent = metrics.ascent()
    
    def get_opposite_color(self, color):
        """Calculate the opposite (inverted) color
        
        Args:
            color: QColor object
            
        Returns:
            QColor: Inverted color
        """
        return QColor(255 - color.red(), 255 - color.green(), 255 - color.blue())
    
    def draw_arrow_box(self, painter, x, y, width, height, color):
        """Draw an arrow-style box (like an envelope shape)
        
        Args:
            painter: QPainter object
            x, y: Top-left corner position
            width, height: Dimensions of the box
            color: QColor for the border
        """
        from PyQt5.QtGui import QPolygonF
        from PyQt5.QtCore import QPointF
        
        arrow_depth = min(8, height // 3)  # Arrow indentation depth
        
        # Create polygon points for arrow box shape
        points = [
            QPointF(x, y),                              # Top-left
            QPointF(x + arrow_depth, y + height/2),     # Left arrow point
            QPointF(x, y + height),                     # Bottom-left
            QPointF(x + width, y + height),             # Bottom-right
            QPointF(x + width - arrow_depth, y + height/2),  # Right arrow point
            QPointF(x + width, y),                      # Top-right
            QPointF(x, y)                               # Close the path
        ]
        
        polygon = QPolygonF(points)
        
        # Draw the arrow box
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(polygon)
    
    def toggle_cursor_blink(self):
        """Toggle cursor visibility for blinking effect"""
        if self.cursor_blink_enabled:
            self.cursor_visible = not self.cursor_visible
            self.update()
    
    def set_font_size(self, size):
        """Set font size"""
        self.font_size = size
        self.font.setPointSize(size)
        self.update_char_size()
        self.update()
    
    def calculate_max_content_width(self):
        """Calculate the maximum width of actual content across all lines"""
        if not self.screen:
            return self.screen.columns if self.screen else 80
        
        max_width = self.screen.columns
        
        # Check history lines
        if hasattr(self.screen, 'history') and hasattr(self.screen.history, 'top'):
            for line in self.screen.history.top:
                # Find the rightmost non-space character
                rightmost = 0
                for col in range(len(line)):
                    if col in line:
                        char_data = self.get_char_data(line[col])
                        if char_data and char_data != ' ':
                            rightmost = col + 1
                max_width = max(max_width, rightmost)
        
        # Check current screen buffer
        for row_idx in range(self.screen.lines):
            line = self.screen.buffer[row_idx]
            rightmost = 0
            for col in range(len(line)):
                if col in line:
                    char_data = self.get_char_data(line[col])
                    if char_data and char_data != ' ':
                        rightmost = col + 1
            max_width = max(max_width, rightmost)
        
        return max_width
    
    def sizeHint(self):
        """Suggest size for the widget - returns actual content size"""
        if self.screen:
            # Use actual content width instead of just screen columns
            content_width = self.calculate_max_content_width()
            width = self.char_width * content_width + 20
            # Add bottom padding: 3 empty lines always visible below content
            height = self.char_height * (self.screen.lines + self.BOTTOM_PADDING_LINES) + 20
            
            # Add space for line numbers if enabled (column numbers are in fixed header)
            if self.show_line_numbers:
                width += self.line_number_width * self.char_width
            
            return QSize(width, height)
        return QSize(800, 600)
    
    def minimumSizeHint(self):
        """Minimum size for the widget"""
        return QSize(400, 300)
    
    def refresh_viewport_highlight_color(self):
        """Reload viewport highlight color from preferences"""
        prefs_manager = PreferencesManager()
        viewport_highlight_color = prefs_manager.get('terminal', 'viewport_highlight_color', 'auto')
        if viewport_highlight_color == 'auto':
            # Calculate opposite color of background
            self.viewport_highlight_color = self.get_opposite_color(self.bg_color)
        else:
            self.viewport_highlight_color = QColor(viewport_highlight_color)
        self.update()
    
    def resizeCanvas(self):
        """Resize canvas to fit all content including history"""
        if self.screen:
            # Use actual content width instead of just screen columns
            content_width = self.calculate_max_content_width()
            width = self.char_width * content_width + 20
            
            # Calculate total lines (history + visible)
            total_lines = self.screen.lines
            if hasattr(self.screen, 'history'):
                total_lines += len(self.screen.history.top)
            
            # Add bottom padding: 3 empty lines always visible below content
            height = self.char_height * (total_lines + self.BOTTOM_PADDING_LINES) + 20
            
            # Add space for line numbers if enabled (column numbers are in fixed header)
            if self.show_line_numbers:
                width += self.line_number_width * self.char_width
            
            # Ensure canvas is at least as large as the viewport to capture all clicks
            # But allow it to grow wider for horizontal scrolling
            if self.parent_terminal and hasattr(self.parent_terminal, 'scroll_area'):
                viewport_width = self.parent_terminal.scroll_area.viewport().width()
                viewport_height = self.parent_terminal.scroll_area.viewport().height()
                # Ensure minimum width is viewport width, but allow wider for content
                width = max(width, viewport_width)
                height = max(height, viewport_height)
            
            self.resize(width, height)
            self.updateGeometry()
    
    def get_char_data(self, char):
        """Extract character data - handles both string and object types for pyte compatibility"""
        if isinstance(char, str):
            return char
        elif hasattr(char, 'data'):
            return char.data
        else:
            return ' '
    
    def get_color(self, color_name, is_bold=False):
        """Get QColor from color name"""
        if is_bold and color_name in self.bright_color_map:
            return self.bright_color_map[color_name]
        elif color_name in self.color_map:
            return self.color_map[color_name]
        return self.color_map['default']
    
    def get_line_severity_color(self, line):
        """Get color for line number based on content severity
        
        Returns tuple of (text_color, bg_color) based on line content.
        KEYWORDS have HIGHEST PRIORITY, then HTTP status codes.
        This matches the minimap coloring logic exactly.
        
        Priority order:
        1. Keywords (error, failed, warning, etc.) - HIGHEST
        2. HTTP Status codes (5xx, 4xx, 3xx, 2xx)
        3. Default colors
        """
        # Extract text content from line (line is a dict of Char objects)
        line_text = ''.join(line[col].data if col in line else ' ' for col in range(self.screen.columns))
        line_lower = line_text.lower()
        
        # Keyword-based detection - HIGHEST PRIORITY
        # Critical Errors - Bright Red
        if any(keyword in line_lower for keyword in ['error', 'exception', 'crash', 'fatal', 'critical']):
            return QColor(255, 100, 100), QColor(80, 30, 30)
        
        # Failures - Orange
        if any(keyword in line_lower for keyword in ['fail', 'failed', 'failure', 'denied']):
            return QColor(255, 160, 60), QColor(70, 45, 15)
        
        # Warnings - Yellow
        if any(keyword in line_lower for keyword in ['warn', 'warning', 'caution']):
            return QColor(255, 220, 100), QColor(80, 70, 20)
        
        # HTTP Status codes - SECOND PRIORITY (after keywords)
        # Use regex patterns to match status codes in proper context
        # Patterns: "Status: XXX", "HTTP/1.X XXX", or standalone " XXX " with spaces
        
        # Server Errors (5xx) - Bright Red
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])5[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(255, 80, 80), QColor(70, 25, 25)
        
        # Client Errors (4xx) - Orange
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])4[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(255, 180, 80), QColor(80, 50, 20)
        
        # Redirects (3xx) - Cyan
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])3[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(0, 200, 200), QColor(0, 50, 50)
        
        # Success (2xx) - Green
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])2[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(100, 255, 100), QColor(20, 60, 20)
        
        # Success keywords - Green
        if any(keyword in line_lower for keyword in ['success', 'passed', 'complete']):
            return QColor(80, 240, 80), QColor(15, 55, 15)
        
        # Info - Blue
        if any(keyword in line_lower for keyword in ['info', 'get ', 'post ', 'put ', 'patch ', 'delete ']):
            return QColor(120, 180, 255), QColor(20, 40, 70)
        
        # Debug - Purple
        if any(keyword in line_lower for keyword in ['debug', 'trace', 'verbose']):
            return QColor(180, 140, 255), QColor(40, 30, 70)
        
        # Default - Gray
        return QColor('#808080'), QColor('#252525')
    
    def paintEvent(self, event):
        """Paint the terminal content including history"""
        if not self._initialized:
            return  # Don't paint until fully initialized
        
        if not self.screen:
            return
        
        painter = QPainter(self)
        painter.setFont(self.font)

        # Cache color objects and font metrics for performance
        cached_colors = {}
        def get_cached_color(color, bold=False):
            key = (color, bold)
            if key not in cached_colors:
                cached_colors[key] = self.get_color(color, bold)
            return cached_colors[key]

        font_metrics = painter.fontMetrics()
        bold_font = QFont(self.font)
        bold_font.setBold(True)
        bold_font_metrics = QFontMetrics(bold_font)

        # Draw background using preference color
        painter.fillRect(self.rect(), self.bg_color)

        # Calculate offsets for line numbers (column numbers are now in fixed header)
        line_num_offset = self.line_number_width * self.char_width if self.show_line_numbers else 0
        
        # PERFORMANCE OPTIMIZATION: Only render lines that are visible in the viewport
        # Calculate which lines are visible based on scroll position
        visible_start_line = 0
        visible_end_line = 0
        
        if self.parent_terminal and hasattr(self.parent_terminal, 'scroll_area'):
            # Get the vertical scroll position in pixels
            scroll_value = self.parent_terminal.scroll_area.verticalScrollBar().value()
            viewport_height = self.parent_terminal.scroll_area.viewport().height()
            
            # Calculate which lines are visible (with a small buffer above/below for smooth scrolling)
            buffer_lines = 1  # Render minimal extra lines for smoother scrolling with large buffers
            visible_start_line = max(0, (scroll_value // self.char_height) - buffer_lines)
            visible_end_line = min(
                ((scroll_value + viewport_height) // self.char_height) + buffer_lines,
                len(self.screen.history.top) + self.screen.lines if hasattr(self.screen, 'history') else self.screen.lines
            )
        else:
            # Fallback: render all lines if we can't determine viewport
            visible_start_line = 0
            visible_end_line = len(self.screen.history.top) + self.screen.lines if hasattr(self.screen, 'history') else self.screen.lines
        
        # Get all lines including history
        # NOTE: We need to use screen.buffer (not screen.display) to get color information
        # screen.display returns plain strings, screen.buffer returns Char objects with attributes
        all_lines = []
        if hasattr(self.screen, 'history'):
            # Get history lines (oldest first) - these are already dictionaries with Char objects
            all_lines.extend(list(self.screen.history.top))
        # Add current screen buffer - use buffer instead of display to get Char objects
        for row_idx in range(self.screen.lines):
            all_lines.append(self.screen.buffer[row_idx])
        
        # Track cumulative line offset - increment when old lines are removed from history
        current_total_lines = len(all_lines)
        if self._total_lines_count > 0 and current_total_lines < self._total_lines_count:
            # Check if this is a screen clear (dramatic drop in line count)
            # If line count drops by more than 50%, reset offset instead of incrementing
            if current_total_lines < self._total_lines_count * 0.5:
                # Screen was cleared - reset line numbering to start from 1
                self._cumulative_line_offset = 0
                self._total_lines_count = current_total_lines
            else:
                # Normal history trimming - increment the offset
                lines_removed = self._total_lines_count - current_total_lines
                self._cumulative_line_offset += lines_removed
                self._total_lines_count = current_total_lines
        else:
            self._total_lines_count = current_total_lines
        
        # Draw only the visible lines (PERFORMANCE CRITICAL)
        for y in range(visible_start_line, min(visible_end_line, len(all_lines))):
            line = all_lines[y]
            y_offset = y * self.char_height + 10

            # Draw line number if enabled and this is a fresh (not wrapped) line
            if self.show_line_numbers:
                is_fresh_line = not getattr(line, 'is_wrapped', False)
                if is_fresh_line:
                    if self.colored_line_numbers:
                        line_num_fg_color, line_num_bg_color = self.get_line_severity_color(line)
                    else:
                        line_num_fg_color = self.line_number_color
                        line_num_bg_color = self.line_number_bg_color
                    painter.fillRect(0, y_offset, line_num_offset, self.char_height, line_num_bg_color)
                    if y == self.viewport_center_line:
                        self.draw_arrow_box(painter, 1, y_offset, line_num_offset - 2, self.char_height - 1, self.viewport_highlight_color)
                    painter.setPen(line_num_fg_color)
                    line_text = str(y + 1 + self._cumulative_line_offset)
                    text_width = font_metrics.horizontalAdvance(line_text)
                    px = line_num_offset - text_width - 5
                    painter.drawText(px, y_offset + self.char_ascent, line_text)

            # --- 2. Draw each character with proper width (emoji/wide char fix) ---
            x_pos = 0
            while x_pos < self.screen.columns:
                char = line.get(x_pos)
                if not char or char.data == ' ':
                    x_pos += 1
                    continue
                fg_color = char.fg
                bg_color = char.bg
                bold = char.bold
                reverse = char.reverse
                px = line_num_offset + x_pos * self.char_width + 10
                py = y_offset
                # Determine character width (emoji/wide char support)
                text = char.data
                # Use font metrics to get width, fallback to char_width
                if hasattr(font_metrics, 'horizontalAdvance'):
                    char_pixel_width = font_metrics.horizontalAdvance(text)
                else:
                    char_pixel_width = self.char_width
                # Some emojis/wide chars may take 2 columns
                col_width = 2 if char_pixel_width > self.char_width * 1.5 else 1
                # Draw background
                if bg_color != 'default' or reverse:
                    bg_qcolor = get_cached_color(fg_color if reverse else bg_color, bold)
                    painter.fillRect(px, py, self.char_width * col_width, self.char_height, bg_qcolor)
                # Draw character
                if text:
                    if reverse:
                        fg_qcolor = get_cached_color(bg_color if bg_color != 'default' else 'white', bold)
                    else:
                        fg_qcolor = get_cached_color(fg_color, bold)
                    painter.setPen(fg_qcolor)
                    if bold and not reverse:
                        painter.setFont(bold_font)
                        painter.drawText(px, py + self.char_ascent, text)
                        painter.setFont(self.font)
                    else:
                        painter.drawText(px, py + self.char_ascent, text)
                x_pos += col_width
        
        # Draw selection highlight
        if self.selection_start and self.selection_end:
            self.draw_selection(painter)
        
        # Draw search highlights
        if self.search_matches:
            self.draw_search_highlights(painter, line_num_offset)
        
        # Draw hover underline for clickable files/folders
        if self.hover_range:
            self.draw_hover_underline(painter, line_num_offset)
        
        # Draw cursor (only when visible for blinking effect)
        if self.cursor_visible:
            cursor = self.screen.cursor
            cx = line_num_offset + cursor.x * self.char_width + 10
            
            # Calculate cursor Y position
            # cursor.y is relative to the visible screen (0-indexed, 0 to rows-1)
            # all_lines = history + screen.display (visible lines)
            # So cursor is at: history_length + cursor.y
            history_offset = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
            cy = (history_offset + cursor.y) * self.char_height + 10
            
            # Draw cursor as a filled rectangle using preference color
            cursor_color = self.cursor_color_pref
            cursor_color.setAlpha(128)
            painter.fillRect(cx, cy, self.char_width, self.char_height, cursor_color)
    
    def draw_hover_underline(self, painter, line_num_offset):
        """Draw underline for hovered clickable file/folder"""
        if not self.hover_range:
            return
        
        start_row, start_col, end_row, end_col = self.hover_range
        
        # Use a color that stands out (slightly brighter than foreground)
        underline_color = self.fg_color
        underline_color.setAlpha(200)
        painter.setPen(underline_color)
        
        if start_row == end_row:
            # Single line underline
            x = line_num_offset + start_col * self.char_width + 10
            y = (start_row + 1) * self.char_height + 8  # Position just below text
            width = (end_col - start_col) * self.char_width
            # Draw line (2px thick)
            painter.drawLine(x, y, x + width, y)
            painter.drawLine(x, y + 1, x + width, y + 1)
        else:
            # Multi-line underline
            # First line
            x = line_num_offset + start_col * self.char_width + 10
            y = (start_row + 1) * self.char_height + 8
            width = (self.screen.columns - start_col) * self.char_width
            painter.drawLine(x, y, x + width, y)
            painter.drawLine(x, y + 1, x + width, y + 1)
            
            # Middle lines
            for row in range(start_row + 1, end_row):
                x = line_num_offset + 10
                y = (row + 1) * self.char_height + 8
                width = self.screen.columns * self.char_width
                painter.drawLine(x, y, x + width, y)
                painter.drawLine(x, y + 1, x + width, y + 1)
            
            # Last line
            x = line_num_offset + 10
            y = (end_row + 1) * self.char_height + 8
            width = end_col * self.char_width
            painter.drawLine(x, y, x + width, y)
            painter.drawLine(x, y + 1, x + width, y + 1)
    
    def draw_selection(self, painter):
        """Draw text selection highlight"""
        if not self.selection_start or not self.selection_end:
            return
        
        start_row, start_col = self.selection_start
        end_row, end_col = self.selection_end
        
        # Ensure start is before end
        if (start_row > end_row) or (start_row == end_row and start_col > end_col):
            start_row, start_col, end_row, end_col = end_row, end_col, start_row, start_col
        
        # Calculate offsets
        line_num_offset = 0
        if self.show_line_numbers:
            line_num_offset = self.line_number_width * self.char_width
        
        # Draw selection highlight using preference color
        selection_color = self.selection_color_pref
        selection_color.setAlpha(100)
        
        if start_row == end_row:
            # Single line selection
            x = line_num_offset + start_col * self.char_width + 10
            y = start_row * self.char_height + 10
            width = (end_col - start_col) * self.char_width
            painter.fillRect(x, y, width, self.char_height, selection_color)
        else:
            # Multi-line selection
            # First line
            x = line_num_offset + start_col * self.char_width + 10
            y = start_row * self.char_height + 10
            width = (self.screen.columns - start_col) * self.char_width
            painter.fillRect(x, y, width, self.char_height, selection_color)
            
            # Middle lines
            for row in range(start_row + 1, end_row):
                x = line_num_offset + 10
                y = row * self.char_height + 10
                width = self.screen.columns * self.char_width
                painter.fillRect(x, y, width, self.char_height, selection_color)
            
            # Last line
            x = line_num_offset + 10
            y = end_row * self.char_height + 10
            width = end_col * self.char_width
            painter.fillRect(x, y, width, self.char_height, selection_color)
    
    def draw_search_highlights(self, painter, line_num_offset):
        """Draw search match highlights"""
        if not self.search_matches:
            return
        
        # Color for all matches (yellow with transparency)
        match_color = QColor('#ffff00')
        match_color.setAlpha(100)
        
        # Color for current match (orange, more prominent)
        current_match_color = QColor('#ff8800')
        current_match_color.setAlpha(150)
        
        for idx, (row, col, length) in enumerate(self.search_matches):
            # Choose color based on whether this is the current match
            color = current_match_color if idx == self.current_search_match else match_color
            
            # Draw highlight
            x = line_num_offset + col * self.char_width + 10
            y = row * self.char_height + 10
            width = length * self.char_width
            painter.fillRect(x, y, width, self.char_height, color)
    
    def get_char_at_pos(self, pos):
        """Get character row/col from pixel position"""
        if not self.screen:
            return None
        
        # Calculate offsets
        line_num_offset = 0
        if self.show_line_numbers:
            line_num_offset = self.line_number_width * self.char_width
        
        x = pos.x() - line_num_offset - 10
        y = pos.y() - 10
        
        if x < 0 or y < 0:
            return None
        
        col = x // self.char_width
        row = y // self.char_height
        
        # Calculate total lines including history
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        if col >= self.screen.columns or row >= total_lines:
            return None
        
        return (row, col)
    
    def get_row_from_line_number_click(self, pos):
        """Get row number from a click in the line number area, or None if not in line number area"""
        if not self.screen or not self.show_line_numbers:
            return None
        
        # Calculate line number area width
        line_num_offset = self.line_number_width * self.char_width
        
        # Check if click is within line number area
        if pos.x() < 0 or pos.x() >= line_num_offset:
            return None
        
        # Calculate row from y position
        y = pos.y() - 10
        if y < 0:
            return None
        
        row = y // self.char_height
        
        # Calculate total lines including history
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        if row >= total_lines:
            return None
        
        return row
    
    def get_line_at_row(self, row):
        """Get line at a given row index (including history)"""
        if not self.screen:
            return None
        
        # Get all lines including history
        # Use buffer instead of display to get Char objects with color info
        all_lines = []
        if hasattr(self.screen, 'history'):
            all_lines.extend(list(self.screen.history.top))
        # Add current screen buffer (not display)
        for row_idx in range(self.screen.lines):
            all_lines.append(self.screen.buffer[row_idx])
        
        if row < 0 or row >= len(all_lines):
            return None
        
        return all_lines[row]
    
    def get_selected_text(self):
        """Get the currently selected text"""
        if not self.selection_start or not self.selection_end or not self.screen:
            return ""
        
        start_row, start_col = self.selection_start
        end_row, end_col = self.selection_end
        
        # Ensure start is before end
        if (start_row > end_row) or (start_row == end_row and start_col > end_col):
            start_row, start_col, end_row, end_col = end_row, end_col, start_row, start_col
        
        selected_lines = []
        
        if start_row == end_row:
            # Single line selection
            line_text = ""
            line = self.get_line_at_row(start_row)
            if line:
                for col in range(start_col, end_col):
                    # line is a dictionary, check if col exists as key
                    if col in line:
                        char = line[col]
                        line_text += self.get_char_data(char)
            selected_lines.append(line_text)
        else:
            # Multi-line selection
            # First line
            line_text = ""
            line = self.get_line_at_row(start_row)
            if line:
                for col in range(start_col, self.screen.columns):
                    # line is a dictionary, check if col exists as key
                    if col in line:
                        char = line[col]
                        line_text += self.get_char_data(char)
            selected_lines.append(line_text.rstrip())
            
            # Middle lines
            for row in range(start_row + 1, end_row):
                line_text = ""
                line = self.get_line_at_row(row)
                if line:
                    for col in range(self.screen.columns):
                        # line is a dictionary, check if col exists as key
                        if col in line:
                            char = line[col]
                            line_text += self.get_char_data(char)
                selected_lines.append(line_text.rstrip())
            
            # Last line
            line_text = ""
            line = self.get_line_at_row(end_row)
            if line:
                for col in range(end_col):
                    # line is a dictionary, check if col exists as key
                    if col in line:
                        char = line[col]
                        line_text += self.get_char_data(char)
            selected_lines.append(line_text.rstrip())
        
        return "\n".join(selected_lines)
    
    def extract_lines_with_formatting(self, start_row=None, end_row=None):
        """Extract lines with color and formatting information for viewer
        
        Args:
            start_row: Starting row index (None = from beginning)
            end_row: Ending row index (None = to end)
            
        Returns:
            List of dictionaries with format:
            {
                'text': 'plain text line',
                'chars': [
                    {'char': 'A', 'fg': 'red', 'bold': True},
                    {'char': 'B', 'fg': 'default', 'bold': False},
                    ...
                ]
            }
        """
        if not self.screen:
            return []
        
        # Calculate total lines
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        # Set defaults
        if start_row is None:
            start_row = 0
        if end_row is None:
            end_row = total_lines - 1
        
        # Clamp to valid range
        start_row = max(0, min(start_row, total_lines - 1))
        end_row = max(0, min(end_row, total_lines - 1))
        
        # Ensure start is before end
        if start_row > end_row:
            start_row, end_row = end_row, start_row
        
        lines_data = []
        
        for row in range(start_row, end_row + 1):
            line = self.get_line_at_row(row)
            if not line:
                # Empty line
                lines_data.append({
                    'text': '',
                    'chars': []
                })
                continue
            
            line_text = ""
            char_data_list = []
            
            # Extract each character with its formatting
            for col in range(self.screen.columns):
                if col in line:
                    char_obj = line[col]
                    char = self.get_char_data(char_obj)
                    
                    # Extract color and style info
                    fg_color = 'default'
                    bold = False
                    
                    if hasattr(char_obj, 'fg'):
                        fg_color = char_obj.fg
                    if hasattr(char_obj, 'bold'):
                        bold = char_obj.bold
                    
                    line_text += char
                    char_data_list.append({
                        'char': char,
                        'fg': fg_color,
                        'bold': bold
                    })
                else:
                    line_text += ' '
                    char_data_list.append({
                        'char': ' ',
                        'fg': 'default',
                        'bold': False
                    })
            
            lines_data.append({
                'text': line_text.rstrip(),
                'chars': char_data_list
            })
        
        return lines_data
    
    def extract_selected_lines_with_formatting(self):
        """Extract currently selected lines with formatting"""
        if not self.selection_start or not self.selection_end:
            return []
        
        start_row, start_col = self.selection_start
        end_row, end_col = self.selection_end
        
        # Ensure start is before end
        if (start_row > end_row) or (start_row == end_row and start_col > end_col):
            start_row, start_col, end_row, end_col = end_row, end_col, start_row, start_col
        
        # Extract full lines in the selection range
        return self.extract_lines_with_formatting(start_row, end_row)
    
    def select_all(self):
        """Select all text in the terminal including history"""
        if not self.screen:
            return
        
        # Calculate total lines including history
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        # Find the last row with actual content (scan backwards from end)
        last_content_row = total_lines - 1
        for row in range(total_lines - 1, -1, -1):
            line = self.get_line_at_row(row)
            if line:
                # Check if line has any non-space content
                has_content = False
                for col in line.keys():
                    char = line[col]
                    char_data = self.get_char_data(char)
                    if char_data and char_data.strip():  # Non-empty, non-space character
                        has_content = True
                        break
                if has_content:
                    last_content_row = row
                    break
            # If we reach row 0 without finding content, select at least first row
            if row == 0:
                last_content_row = 0
                break
        
        # Find the last column with content on the last content row
        last_content_col = 0
        line = self.get_line_at_row(last_content_row)
        if line:
            # Get maximum column index with content
            for col in sorted(line.keys(), reverse=True):
                char = line[col]
                char_data = self.get_char_data(char)
                if char_data and char_data.strip():  # Non-empty, non-space character
                    last_content_col = col + 1  # +1 to include this character in selection
                    break
            # If no non-space content found, use first column
            if last_content_col == 0 and line.keys():
                last_content_col = max(line.keys()) + 1
        else:
            # If no line data, default to column 0
            last_content_col = 0
        
        self.selection_anchor = (0, 0)
        self.selection_start = (0, 0)
        self.selection_end = (last_content_row, last_content_col)
        
        # Capture selection content for tracking
        self._capture_selection_content()
        self._total_lines_count = total_lines
        
        self.update()
    
    def clear_selection(self):
        """Clear the current selection"""
        self.selection_start = None
        self.selection_end = None
        self.selection_anchor = None
        self.line_number_selection_anchor = None  # Reset line number anchor
        self._selection_content_hash = None
        self._selection_start_line_content = None
        self.update()
    
    def _capture_selection_content(self):
        """Capture the content at the current selection for tracking when content scrolls"""
        if not self.selection_start or not self.screen:
            self._selection_content_hash = None
            self._selection_start_line_content = None
            return
        
        start_row, start_col = self.selection_start
        line = self.get_line_at_row(start_row)
        
        if line:
            # Get the full line text as our identifier
            line_text = ""
            max_col = max(line.keys()) if line else 0
            for c in range(max_col + 1):
                if c in line:
                    char = line[c]
                    line_text += self.get_char_data(char)
                else:
                    line_text += " "
            
            self._selection_start_line_content = line_text.rstrip()
            # Use hash for quick comparison
            self._selection_content_hash = hash(self._selection_start_line_content)
            
    
    def _update_selection_after_scroll(self):
        """Update selection coordinates when content scrolls (new lines added)
        
        This is called after new content is added to the terminal. If the selection
        was pointing to specific content, we find where that content has moved to
        and update the selection coordinates.
        """
        if not self.selection_start or not self._selection_start_line_content or not self.screen:
            return
        
        start_row, start_col = self.selection_start
        end_row, end_col = self.selection_end if self.selection_end else (start_row, start_col)
        
        # Get all lines including history
        all_lines = []
        if hasattr(self.screen, 'history'):
            all_lines.extend(list(self.screen.history.top))
        for row_idx in range(self.screen.lines):
            all_lines.append(self.screen.buffer[row_idx])
        
        # First check if the content at the current position still matches
        # (it might not have moved at all)
        if start_row < len(all_lines):
            current_line = all_lines[start_row]
            if current_line:
                current_line_text = ""
                max_col = max(current_line.keys()) if current_line else 0
                for c in range(max_col + 1):
                    if c in current_line:
                        char = current_line[c]
                        current_line_text += self.get_char_data(char)
                    else:
                        current_line_text += " "
                current_line_text = current_line_text.rstrip()
                
                # If content matches, no need to update
                if current_line_text == self._selection_start_line_content:
                    return
        
        # Content has moved - search for it
        # Search broadly around the original position
        search_start = max(0, start_row - 20)  # Look above in case content shifted
        search_end = min(len(all_lines), start_row + 100)  # Look below - content likely moved down
        
        for new_row in range(search_start, search_end):
            if new_row >= len(all_lines):
                break
            
            line = all_lines[new_row]
            if not line:
                continue
            
            # Get line text
            line_text = ""
            max_col = max(line.keys()) if line else 0
            for c in range(max_col + 1):
                if c in line:
                    char = line[c]
                    line_text += self.get_char_data(char)
                else:
                    line_text += " "
            
            line_text = line_text.rstrip()
            
            # Check if this matches our selected content
            if line_text == self._selection_start_line_content:
                # Found it! Update selection coordinates
                row_offset = new_row - start_row
                
                if row_offset != 0:  # Only update if there was actual movement
                    # Update all selection coordinates by the same offset
                    self.selection_start = (start_row + row_offset, start_col)
                    if self.selection_end:
                        self.selection_end = (end_row + row_offset, end_col)
                    if self.selection_anchor:
                        anchor_row, anchor_col = self.selection_anchor
                        self.selection_anchor = (anchor_row + row_offset, anchor_col)
                    
                    # Debug output
                
                # Re-capture content at new position
                self._capture_selection_content()
                return
        
        # If we couldn't find the content, it might have scrolled off
        # Don't clear selection - it's still valid, just the content might be out of search range
    
    def select_word_at_pos(self, pos):
        """Select the word at the given position (row, col)"""
        if not self.screen:
            return
        
        row, col = pos
        line = self.get_line_at_row(row)
        if not line:
            return
        
        # Get the full line text
        line_text = ""
        max_col = max(line.keys()) if line else 0
        for c in range(max_col + 1):
            if c in line:
                char = line[c]
                line_text += self.get_char_data(char)
            else:
                line_text += " "
        
        if col >= len(line_text):
            return
        
        # Characters that indicate word boundaries
        word_boundary_chars = " \t\n\r|&;<>(){}[]`$#@!%^*+=?,\"'"
        
        # Find word start (go backwards)
        word_start = col
        while word_start > 0:
            char = line_text[word_start - 1]
            if char in word_boundary_chars:
                break
            word_start -= 1
        
        # Find word end (go forwards)
        word_end = col
        while word_end < len(line_text):
            char = line_text[word_end]
            if char in word_boundary_chars:
                break
            word_end += 1
        
        # Set selection
        self.selection_anchor = (row, word_start)
        self.selection_start = (row, word_start)
        self.selection_end = (row, word_end)
        
        # Capture selection content for tracking
        self._capture_selection_content()
        if self.screen:
            self._total_lines_count = self.screen.lines
            if hasattr(self.screen, 'history'):
                self._total_lines_count += len(self.screen.history.top)
        
        self.update()
    
    def select_line_at_pos(self, pos):
        """Select the entire line at the given position (row, col)"""
        if not self.screen:
            return
        
        row, col = pos
        
        # Select entire line (from column 0 to end of line)
        # Get the line to find its actual length
        line = self.get_line_at_row(row)
        if not line:
            # If line doesn't exist, select from 0 to screen width
            line_end = self.screen.columns
        else:
            # Find the last column with content
            max_col = max(line.keys()) if line else 0
            line_end = max_col + 1
        
        # Set selection for entire line
        self.selection_anchor = (row, 0)
        self.selection_start = (row, 0)
        self.selection_end = (row, line_end)
        
        # Capture selection content for tracking
        self._capture_selection_content()
        if self.screen:
            self._total_lines_count = self.screen.lines
            if hasattr(self.screen, 'history'):
                self._total_lines_count += len(self.screen.history.top)
        
        self.update()
    
    def get_text_at_pos(self, pos):
        """Get text/word at the given position (row, col), handling filenames with spaces"""
        if not self.screen:
            return None
        
        row, col = pos
        line = self.get_line_at_row(row)
        if not line:
            return None
        
        # Extract the word/path at this position
        # First, get the full line text
        line_text = ""
        max_col = max(line.keys()) if line else 0
        for c in range(max_col + 1):
            if c in line:
                char = line[c]
                line_text += self.get_char_data(char)
            else:
                line_text += " "
        
        if col >= len(line_text):
            return None
        
        # Characters that indicate end of a filename/path in terminal output
        # These are typically shell operators or separators
        stop_chars = "|&;<>(){}[]`$#@!%^*+=?,\"'"
        
        # Strategy 1: Extract text but stop at 2+ consecutive spaces (column boundaries)
        # Go backwards from click position
        start_with_spaces = col
        prev_was_space = False
        while start_with_spaces > 0:
            char = line_text[start_with_spaces - 1]
            if char in stop_chars or char == '\n' or char == '\r':
                break
            
            # Stop if we hit 2+ consecutive spaces (column boundary)
            if char == ' ':
                if prev_was_space:
                    # Found 2 consecutive spaces, stop here
                    break
                prev_was_space = True
            else:
                prev_was_space = False
            
            # Allow alphanumeric, single spaces, dots, slashes, dashes, underscores, colons, parentheses
            if char.isalnum() or char in " ./\\_-:~()":
                start_with_spaces -= 1
            else:
                break
        
        # Skip any trailing spaces at the start
        while start_with_spaces < col and line_text[start_with_spaces] == ' ':
            start_with_spaces += 1
        
        # Go forwards from click position
        end_with_spaces = col + 1  # Start after current character
        prev_was_space = (line_text[col] == ' ') if col < len(line_text) else False
        while end_with_spaces < len(line_text):
            char = line_text[end_with_spaces]
            if char in stop_chars or char == '\n' or char == '\r':
                break
            
            # Stop if we hit 2+ consecutive spaces (column boundary)
            if char == ' ':
                if prev_was_space:
                    # Found 2 consecutive spaces, stop here
                    break
                prev_was_space = True
            else:
                prev_was_space = False
            
            # Allow alphanumeric, single spaces, dots, slashes, dashes, underscores, colons, parentheses
            if char.isalnum() or char in " ./\\_-:~()":
                end_with_spaces += 1
            else:
                break
        
        # Trim trailing spaces
        while end_with_spaces > start_with_spaces and line_text[end_with_spaces - 1] == ' ':
            end_with_spaces -= 1
        
        # Strategy: Try the full range first (with spaces), then try shorter candidates
        # This handles filenames with spaces by checking if the full extracted text is a valid path
        best_path = None
        best_length = 0
        
        # First, try the full extracted range (with spaces allowed)
        full_text = line_text[start_with_spaces:end_with_spaces].strip()
        if full_text:
            resolved = self.resolve_path(full_text)
            if resolved:
                return full_text
        
        # Try progressively shorter versions from the right (in case of trailing characters)
        for end in range(end_with_spaces, start_with_spaces, -1):
            candidate = line_text[start_with_spaces:end].strip()
            if not candidate:
                continue
            
            resolved = self.resolve_path(candidate)
            if resolved:
                if len(candidate) > best_length:
                    best_path = candidate
                    best_length = len(candidate)
        
        if best_path:
            return best_path
        
        # Fallback: Extract without spaces (simple word)
        start_no_spaces = col
        while start_no_spaces > 0:
            char = line_text[start_no_spaces - 1]
            if char in " \t\n\r" + stop_chars:
                break
            if char.isalnum() or char in "./\\_-:~":
                start_no_spaces -= 1
            else:
                break
        
        end_no_spaces = col
        while end_no_spaces < len(line_text):
            char = line_text[end_no_spaces]
            if char in " \t\n\r" + stop_chars:
                break
            if char.isalnum() or char in "./\\_-:~":
                end_no_spaces += 1
            else:
                break
        
        word_no_spaces = line_text[start_no_spaces:end_no_spaces].strip()
        if word_no_spaces:
            return word_no_spaces
        
        return None
    
    def open_with_default_app(self, path):
        """Open file/folder with default application using platform-specific commands"""
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                result = subprocess.run(["open", path], check=False, capture_output=True, text=True)
                if result.returncode != 0 and UI_DEBUG:
                    print(f"[OPEN] Error opening {path}: {result.stderr}")
                elif UI_DEBUG:
                    print(f"[OPEN] Successfully opened: {path}")
            elif system == "Linux":
                result = subprocess.run(["xdg-open", path], check=False, capture_output=True, text=True)
                if result.returncode != 0 and UI_DEBUG:
                    print(f"[OPEN] Error opening {path}: {result.stderr}")
            elif system == "Windows":
                result = subprocess.run(["start", path], shell=True, check=False, capture_output=True, text=True)
                if result.returncode != 0 and UI_DEBUG:
                    print(f"[OPEN] Error opening {path}: {result.stderr}")
            else:
                if UI_DEBUG:
                    print(f"[OPEN] Unsupported platform: {system}")
        except Exception as e:
            if UI_DEBUG:
                print(f"[OPEN] Exception opening {path}: {e}")
    
    def resolve_path(self, text):
        """Try to resolve text as a file/folder path"""
        if not text:
            return None
        
        # Strip any trailing slashes or whitespace
        text = text.strip().rstrip('/')
        
        # Skip text that's clearly not a path
        # Don't try to resolve if it contains typical non-path patterns
        non_path_indicators = [
            ': ',  # Likely error messages like "Note: ..."
            'Exception',
            'Error',
            'warning',
            'Traceback',
            'at line',
        ]
        text_lower = text.lower()
        if any(indicator.lower() in text_lower for indicator in non_path_indicators):
            return None
        
        # Skip if text is too long (paths are rarely > 500 chars)
        if len(text) > 500:
            return None
        
        # Get current directory from parent terminal
        current_dir = None
        if self.parent_terminal and hasattr(self.parent_terminal, 'current_directory'):
            current_dir = self.parent_terminal.current_directory
        
        if not current_dir:
            current_dir = os.path.expanduser("~")
        
        if UI_DEBUG:
            print(f"[RESOLVE] Trying to resolve '{text}' from current_dir: {current_dir}")
        
        # Try different path resolutions
        candidates = []
        
        # 1. If text is an absolute path, try it directly
        if os.path.isabs(text):
            candidates.append(text)
        
        # 2. Try as relative path from current directory
        candidates.append(os.path.join(current_dir, text))
        
        # 3. Try in parent directory of current directory
        parent_dir = os.path.dirname(current_dir)
        if parent_dir:
            candidates.append(os.path.join(parent_dir, text))
        
        # 4. Try in home directory
        home_dir = os.path.expanduser("~")
        candidates.append(os.path.join(home_dir, text))
        
        # 5. Try with expanded home directory prefix
        if text.startswith("~"):
            candidates.append(os.path.expanduser(text))
        
        # 6. Try just the text as-is if it's already a valid path
        candidates.append(text)
        
        # Return the first valid candidate
        for candidate in candidates:
            if os.path.exists(candidate):
                resolved = os.path.abspath(candidate)
                if UI_DEBUG:
                    print(f"[RESOLVE] Found valid path: {resolved}")
                return resolved
        
        if UI_DEBUG:
            print(f"[RESOLVE] No valid path found. Tried: {candidates[:3]}...")
        return None
    
    def cd_to_directory(self, directory_path):
        """Navigate to a directory by executing cd command"""
        if not os.path.isdir(directory_path):
            if UI_DEBUG:
                print(f"[CD] Not a directory: {directory_path}")
            return
        
        # Send cd command to the terminal
        cd_command = f"cd {self.shell_quote(directory_path)}\n"
        
        if UI_DEBUG:
            print(f"[CD] Executing: {cd_command.strip()}")
        
        try:
            # Write the cd command to the terminal
            if self.parent_terminal and hasattr(self.parent_terminal, 'master_fd'):
                os.write(self.parent_terminal.master_fd, cd_command.encode())
                
                # Update the current directory tracker
                if hasattr(self.parent_terminal, 'current_directory'):
                    self.parent_terminal.current_directory = directory_path
            else:
                if UI_DEBUG:
                    print(f"[CD] Could not access terminal master_fd")
        except Exception as e:
            if UI_DEBUG:
                print(f"[CD] Exception: {e}")
    
    def shell_quote(self, path):
        """Quote a path for safe use in shell commands"""
        # Replace single quotes with '\'' and wrap in single quotes
        return "'" + path.replace("'", "'\\''") + "'"
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click to select word"""
        if event.button() == Qt.LeftButton:
            char_pos = self.get_char_at_pos(event.pos())
            if char_pos:
                self.select_word_at_pos(char_pos)
                # Track this as a potential start of triple click
                current_time = time.time() * 1000  # Convert to milliseconds
                self.last_click_time = current_time
                self.last_click_pos = event.pos()
                self.click_count = 2  # We just had a double click
                event.accept()
                return
        
        super().mouseDoubleClickEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for text selection, Ctrl+Click to open files, and triple-click to select line"""
        if event.button() == Qt.LeftButton:
            # Clear hover when clicking
            if self.hover_range:
                self.hover_range = None
                self.update()
            
            # Check if click is on line number area
            clicked_row = self.get_row_from_line_number_click(event.pos())
            if clicked_row is not None:
                # Check if Shift is held
                modifiers = event.modifiers()
                is_shift_held = (modifiers & Qt.ShiftModifier)
                
                if is_shift_held and self.line_number_selection_anchor is not None:
                    # Shift-click on line number: extend selection from anchor to clicked line
                    anchor_row = self.line_number_selection_anchor
                    
                    # Determine selection direction
                    if clicked_row >= anchor_row:
                        # Selecting downwards
                        self.selection_start = (anchor_row, 0)
                        self.selection_end = (clicked_row, self.screen.columns if self.screen else 0)
                    else:
                        # Selecting upwards
                        self.selection_start = (clicked_row, 0)
                        self.selection_end = (anchor_row, self.screen.columns if self.screen else 0)
                    
                    self.is_selecting_by_line_number = True
                    self.is_selecting = True
                    
                    # Update viewport center line
                    self.viewport_center_line = clicked_row
                    
                    # Capture selection content for tracking
                    self._capture_selection_content()
                    if self.screen:
                        self._total_lines_count = self.screen.lines
                        if hasattr(self.screen, 'history'):
                            self._total_lines_count += len(self.screen.history.top)
                    
                    self.update()
                    event.accept()
                    return
                else:
                    # Normal click on line number (no shift or no anchor)
                    # Set the anchor for future shift-clicks
                    self.line_number_selection_anchor = clicked_row
                    
                    # Update viewport highlighter to that line
                    old_center_line = self.viewport_center_line
                    self.viewport_center_line = clicked_row
                    # Set persistent block for scroll-based highlighter update
                    if self.parent_terminal:
                        self.parent_terminal._block_scroll_highlighter_update_until_scroll = True
                    else:
                        self._block_scroll_highlighter_update_until_scroll = True
                    
                    # Notify the minimap to update the highlighter position
                    if self.parent_terminal:
                        # Emit signal to update minimap (if connected via main_window)
                        from ui.main_window import MainWindow
                        from PyQt5.QtWidgets import QApplication
                        for widget in QApplication.topLevelWidgets():
                            if isinstance(widget, MainWindow):
                                if hasattr(widget, 'minimap_panel'):
                                    widget.minimap_panel.update()
                                break
                    
                    # Select entire line
                    self.is_selecting_by_line_number = True
                    self.select_line_at_pos((clicked_row, 0))
                    self.is_selecting = True
                    
                    # Update the canvas to show the new highlighter position
                    self.update()
                    event.accept()
                    return
            
            # Check for triple click (must be close in time and position to previous double click)
            current_time = time.time() * 1000  # Convert to milliseconds
            time_since_last = current_time - self.last_click_time
            is_triple_click = False
            
            if (self.click_count == 2 and 
                time_since_last < self.triple_click_timeout_ms and
                self.last_click_pos is not None):
                # Check if click position is close to last click position
                pos_diff = (event.pos() - self.last_click_pos).manhattanLength()
                if pos_diff < 10:  # Within 10 pixels
                    is_triple_click = True
                    self.click_count = 0  # Reset counter
                    self.last_click_time = 0
                    self.last_click_pos = None
            
            # Reset click tracking if too much time has passed
            if time_since_last >= self.triple_click_timeout_ms:
                self.click_count = 0
                self.last_click_time = 0
                self.last_click_pos = None
            
            # Handle triple click - select entire line
            if is_triple_click:
                char_pos = self.get_char_at_pos(event.pos())
                if char_pos:
                    self.select_line_at_pos(char_pos)
                    event.accept()
                    return
            
            # Check modifiers
            modifiers = event.modifiers()
            is_ctrl_click = (modifiers & Qt.ControlModifier) or (modifiers & Qt.MetaModifier)
            is_shift_click = (modifiers & Qt.ShiftModifier)
            
            # Handle Shift+Cmd+Click to navigate to folder (cd command)
            if is_ctrl_click and is_shift_click:
                char_pos = self.get_char_at_pos(event.pos())
                if char_pos:
                    # Get text at clicked position
                    text = self.get_text_at_pos(char_pos)
                    if UI_DEBUG:
                        print(f"[SHIFT+CMD+CLICK] Extracted text: {text!r}")
                    if text:
                        # Try to resolve as file/folder path
                        resolved_path = self.resolve_path(text)
                        if UI_DEBUG:
                            print(f"[SHIFT+CMD+CLICK] Resolved path: {resolved_path!r}")
                        if resolved_path and os.path.isdir(resolved_path):
                            # It's a directory - execute cd command
                            if UI_DEBUG:
                                print(f"[SHIFT+CMD+CLICK] Navigating to: {resolved_path}")
                            self.cd_to_directory(resolved_path)
                            event.accept()
                            return
                        else:
                            if UI_DEBUG:
                                if resolved_path:
                                    print(f"[SHIFT+CMD+CLICK] Path is not a directory: {resolved_path}")
                                else:
                                    print(f"[SHIFT+CMD+CLICK] Could not resolve path for: {text!r}")
                    else:
                        if UI_DEBUG:
                            print(f"[SHIFT+CMD+CLICK] No text extracted at position {char_pos}")
                else:
                    if UI_DEBUG:
                        print(f"[SHIFT+CMD+CLICK] Could not get character position")
            
            # Handle Ctrl+Click to open files/folders (don't interfere with selection)
            elif is_ctrl_click and not is_shift_click:
                # Handle Ctrl+Click to open files/folders
                char_pos = self.get_char_at_pos(event.pos())
                if char_pos:
                    # Get text at clicked position
                    text = self.get_text_at_pos(char_pos)
                    if UI_DEBUG:
                        print(f"[CMD+CLICK] Extracted text: {text!r}")
                    if text:
                        # Try to resolve as file/folder path
                        resolved_path = self.resolve_path(text)
                        if UI_DEBUG:
                            print(f"[CMD+CLICK] Resolved path: {resolved_path!r}")
                        if resolved_path:
                            # Open with default application
                            if UI_DEBUG:
                                print(f"[CMD+CLICK] Opening: {resolved_path}")
                            self.open_with_default_app(resolved_path)
                            event.accept()
                            return
                        else:
                            if UI_DEBUG:
                                print(f"[CMD+CLICK] Could not resolve path for: {text!r}")
                    else:
                        if UI_DEBUG:
                            print(f"[CMD+CLICK] No text extracted at position {char_pos}")
                else:
                    if UI_DEBUG:
                        print(f"[CMD+CLICK] Could not get character position")
            
            # Get character position at click
            char_pos = self.get_char_at_pos(event.pos())
            if not char_pos:
                super().mousePressEvent(event)
                return
            
            # Handle Shift+Click to extend selection
            if is_shift_click:
                # Determine the anchor point (where selection should start from)
                anchor = None
                if self.selection_anchor is not None:
                    # Use stored anchor if available
                    anchor = self.selection_anchor
                elif self.selection_start is not None:
                    # Fall back to current selection_start
                    anchor = self.selection_start
                else:
                    # No existing selection - start new selection from click position
                    anchor = char_pos
                
                # Extend selection from anchor to click position
                self.selection_anchor = anchor
                self.selection_start = anchor
                self.selection_end = char_pos
                self.is_selecting = True
                self.update()
            else:
                # Normal click - start new selection (unless we just had a double click)
                # Note: If this becomes a double-click, mouseDoubleClickEvent will replace
                # the selection with word selection immediately
                if self.click_count != 2:
                    self.selection_anchor = char_pos  # Set anchor point
                    self.selection_start = char_pos
                    self.selection_end = char_pos
                    self.is_selecting = True
                    self.update()
                
                # Track single click for potential double/triple click detection
                # Reset counter if too much time has passed since last click
                if time_since_last >= self.triple_click_timeout_ms:
                    self.click_count = 0
                    self.last_click_time = 0
                    self.last_click_pos = None
                
                # Track this click for potential double/triple click detection
                if self.click_count == 0:
                    self.last_click_time = current_time
                    self.last_click_pos = event.pos()
                    self.click_count = 1
                # If click_count == 1 and time is short, this might become a double-click
                # Don't update tracking here - let mouseDoubleClickEvent handle it
        
        super().mousePressEvent(event)
    
    def get_text_range_at_pos(self, pos):
        """Get the text range (start_col, end_col) at the given position, handling filenames with spaces"""
        if not self.screen:
            return None
        
        char_pos = self.get_char_at_pos(pos)
        if not char_pos:
            return None
        
        row, col = char_pos
        line = self.get_line_at_row(row)
        if not line:
            return None
        
        # Extract the word/path at this position
        line_text = ""
        max_col = max(line.keys()) if line else 0
        for c in range(max_col + 1):
            if c in line:
                char = line[c]
                line_text += self.get_char_data(char)
            else:
                line_text += " "
        
        if col >= len(line_text):
            return None
        
        # Characters that indicate end of a filename/path in terminal output
        stop_chars = "|&;<>(){}[]`$#@!%^*+=?,\"'"
        
        # Use improved column-boundary-aware extraction
        # Go backwards from click position
        start_with_spaces = col
        prev_was_space = False
        while start_with_spaces > 0:
            char = line_text[start_with_spaces - 1]
            if char in stop_chars or char == '\n' or char == '\r':
                break
            
            # Stop if we hit 2+ consecutive spaces (column boundary)
            if char == ' ':
                if prev_was_space:
                    break
                prev_was_space = True
            else:
                prev_was_space = False
            
            if char.isalnum() or char in " ./\\_-:~()":
                start_with_spaces -= 1
            else:
                break
        
        # Skip any trailing spaces at the start
        while start_with_spaces < col and line_text[start_with_spaces] == ' ':
            start_with_spaces += 1
        
        # Go forwards from click position
        end_with_spaces = col + 1
        prev_was_space = (line_text[col] == ' ') if col < len(line_text) else False
        while end_with_spaces < len(line_text):
            char = line_text[end_with_spaces]
            if char in stop_chars or char == '\n' or char == '\r':
                break
            
            if char == ' ':
                if prev_was_space:
                    break
                prev_was_space = True
            else:
                prev_was_space = False
            
            if char.isalnum() or char in " ./\\_-:~()":
                end_with_spaces += 1
            else:
                break
        
        # Trim trailing spaces
        while end_with_spaces > start_with_spaces and line_text[end_with_spaces - 1] == ' ':
            end_with_spaces -= 1
        
        # Extract text and check if it's a valid path
        if start_with_spaces >= end_with_spaces:
            return None
        
        candidate = line_text[start_with_spaces:end_with_spaces]
        resolved_path = self.resolve_path(candidate)
        if resolved_path:
            return (row, start_with_spaces, row, end_with_spaces)
        
        return None
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for text selection and hover detection"""
        # Track mouse position for modifier key changes
        self._last_mouse_pos = event.pos()
        
        if self.is_selecting and event.buttons() & Qt.LeftButton:
            # Check if we're selecting by line numbers
            if self.is_selecting_by_line_number:
                # Try to get row from line number area
                row = self.get_row_from_line_number_click(event.pos())
                if row is not None:
                    # Still in line number area - extend line selection from anchor
                    if self.line_number_selection_anchor is not None:
                        anchor_row = self.line_number_selection_anchor
                        # Determine which row comes first
                        if row >= anchor_row:
                            # Selecting downwards
                            self.selection_start = (anchor_row, 0)
                            self.selection_end = (row, self.screen.columns if self.screen else 0)
                        else:
                            # Selecting upwards
                            self.selection_start = (row, 0)
                            self.selection_end = (anchor_row, self.screen.columns if self.screen else 0)
                        self.update()
                else:
                    # Moved outside line number area - still treat as line selection
                    # but get the row from the current position
                    char_pos = self.get_char_at_pos(event.pos())
                    if char_pos:
                        row = char_pos[0]
                        if self.line_number_selection_anchor is not None:
                            anchor_row = self.line_number_selection_anchor
                            if row >= anchor_row:
                                self.selection_start = (anchor_row, 0)
                                self.selection_end = (row, self.screen.columns if self.screen else 0)
                            else:
                                self.selection_start = (row, 0)
                                self.selection_end = (anchor_row, self.screen.columns if self.screen else 0)
                            self.update()
            else:
                # Normal character-based text selection during drag
                char_pos = self.get_char_at_pos(event.pos())
                if char_pos:
                    self.selection_end = char_pos
                    # Clear hover during selection
                    if self.hover_range:
                        self.hover_range = None
                    self.update()
        else:
            # Handle hover for clickable files/folders - only show underline when Ctrl/Cmd is held
            modifiers = event.modifiers()
            is_ctrl_held = (modifiers & Qt.ControlModifier) or (modifiers & Qt.MetaModifier)
            
            if is_ctrl_held:
                # Show underline when Ctrl/Cmd is held
                hover_range = self.get_text_range_at_pos(event.pos())
                if hover_range != self.hover_range:
                    self._pending_hover_range = hover_range
                    # Debounce hover updates (50ms delay)
                    if not self._hover_update_timer.isActive():
                        self._hover_update_timer.start(50)
            else:
                # Clear underline when Ctrl/Cmd is not held
                if self.hover_range:
                    self.hover_range = None
                    self.update()
        
        super().mouseMoveEvent(event)
    
    def _update_hover_at_position(self, pos):
        """Update hover underline at the given position"""
        from PyQt5.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        is_ctrl_held = (modifiers & Qt.ControlModifier) or (modifiers & Qt.MetaModifier)
        
        if is_ctrl_held:
            hover_range = self.get_text_range_at_pos(pos)
            if hover_range != self.hover_range:
                self.hover_range = hover_range
                self.update()
        else:
            if self.hover_range:
                self.hover_range = None
                self.update()
    
    def _apply_hover_update(self):
        """Apply pending hover update (debounced)"""
        if self._pending_hover_range != self.hover_range:
            self.hover_range = self._pending_hover_range
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release for text selection"""
        if event.button() == Qt.LeftButton:
            self.is_selecting = False
            self.is_selecting_by_line_number = False  # Reset line number selection flag
            
            # Capture the selected content for tracking when content scrolls
            if self.selection_start and self.selection_end:
                self._capture_selection_content()
                # Update total lines count
                if self.screen:
                    self._total_lines_count = self.screen.lines
                    if hasattr(self.screen, 'history'):
                        self._total_lines_count += len(self.screen.history.top)
            
            # Copy selected text to clipboard automatically on macOS (optional)
            # Commenting this out for now - user can use Cmd+C
            # if self.selection_start and self.selection_end:
            #     selected_text = self.get_selected_text()
            #     if selected_text:
            #         QApplication.clipboard().setText(selected_text)
        super().mouseReleaseEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave event - clear hover underline"""
        if self.hover_range:
            self.hover_range = None
            self.update()
        super().leaveEvent(event)
    
    def wheelEvent(self, event):
        """Handle wheel events - send arrow keys in alternate screen mode, otherwise scroll normally"""
        # Get parent terminal widget to check alternate screen mode
        parent = self.parent()
        while parent and not isinstance(parent, PyteTerminalWidget):
            parent = parent.parent()
        
        # In alternate screen mode (nano/vim), send arrow keys to the application
        if parent and hasattr(parent, 'was_in_alternate_mode') and parent.was_in_alternate_mode:
            # Calculate scroll amount (typically 3 lines per wheel notch)
            delta = event.angleDelta().y()
            if delta != 0:
                # Positive delta = scroll up, negative = scroll down
                lines_to_scroll = abs(delta) // 120  # 120 units per notch
                if lines_to_scroll < 1:
                    lines_to_scroll = 1
                
                # Send arrow key sequences to nano/vim
                if delta > 0:
                    # Scroll up - send Up arrow keys
                    arrow_key = '\x1b[A'  # Up arrow escape sequence
                else:
                    # Scroll down - send Down arrow keys
                    arrow_key = '\x1b[B'  # Down arrow escape sequence
                
                # Send multiple arrow keys for faster scrolling
                for _ in range(lines_to_scroll):
                    parent.write_to_pty(arrow_key)
                
                event.accept()
                return
        
        # Normal mode - let scroll area handle scrolling through history
        event.ignore()
    
    def show_context_menu(self, position):
        """Show right-click context menu
        
        NOTE: No keyboard shortcuts are set on these menu items to prevent
        them from interfering with terminal applications. Users can still
        use keyboard shortcuts (handled in keyPressEvent) or click menu items.
        """
        # Check if clicking on line number area - but now show highlighter menu for viewport
        if self.show_line_numbers:
            line_num_offset = self.line_number_width * self.char_width
            
            # Check if click is on line number area
            if position.x() < line_num_offset:
                # Get the row at click position
                row = self.get_row_from_line_number_click(position)
                
                # Check if this is near the viewport center line (highlighter)
                if row is not None and self.viewport_center_line >= 0 and abs(row - self.viewport_center_line) <= 1:
                    # Show export menu for viewport highlighter
                    self.show_viewport_export_menu(position, row)
                    return
        
        # Regular context menu
        menu = QMenu(self)
        
        # Copy action
        copy_action = QAction("Copy", self)
        # No shortcut - handled in keyPressEvent instead
        copy_action.triggered.connect(self.copy_selection)
        copy_action.setEnabled(self.selection_start is not None and self.selection_end is not None)
        
        # Paste action
        paste_action = QAction("Paste", self)
        # No shortcut - handled in keyPressEvent instead
        paste_action.triggered.connect(self.paste_from_clipboard)
        
        # Select All action
        select_all_action = QAction("Select All", self)
        # No shortcut - handled in keyPressEvent instead
        select_all_action.triggered.connect(self.select_all)
        
        menu.addAction(copy_action)
        menu.addAction(paste_action)
        menu.addSeparator()
        menu.addAction(select_all_action)
        
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
    
    def show_viewport_export_menu(self, position, row):
        """Show export menu for viewport highlighter (replaces line number and archive menus)"""
        menu = QMenu(self)
        
        # Info header
        info_action = QAction(f"📍 Line {row + 1} (Viewport)", self)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        
        menu.addSeparator()
        
        # Check if there's a selection
        has_selection = self.selection_start is not None and self.selection_end is not None
        
        # Export selected lines action
        export_selected_action = QAction("📄 Export Selected Lines to Viewer", self)
        export_selected_action.setToolTip("Open selected lines in a new viewer with color rendering and minimap")
        export_selected_action.triggered.connect(self.export_selected_lines_to_viewer)
        export_selected_action.setEnabled(has_selection)
        menu.addAction(export_selected_action)
        
        # Export all lines action
        export_all_action = QAction("📋 Export All Lines to Viewer", self)
        export_all_action.setToolTip("Open all terminal content in a new viewer")
        export_all_action.triggered.connect(self.export_all_lines_to_viewer)
        menu.addAction(export_all_action)
        
        menu.addSeparator()
        
        # Archive action (original functionality)
        archive_action = QAction(f"📦 Clear Lines Above & Archive", self)
        archive_action.setToolTip("Archive lines above this row to history file")
        archive_action.triggered.connect(lambda: self.parent_terminal.clear_lines_above_and_archive(row))
        menu.addAction(archive_action)
        
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
    
    def export_selected_lines_to_viewer(self):
        """Export selected lines to a new text viewer dialog"""
        if not self.selection_start or not self.selection_end:
            return
        
        # Extract lines with formatting
        lines_data = self.extract_selected_lines_with_formatting()
        
        if not lines_data:
            return
        
        # Get selection range for title
        start_row, _ = self.selection_start
        end_row, _ = self.selection_end
        if start_row > end_row:
            start_row, end_row = end_row, start_row
        
        # Import and show dialog
        from ui.dialogs import TextViewerDialog
        dialog = TextViewerDialog(
            self, 
            lines_data, 
            f"Terminal Lines {start_row + 1}-{end_row + 1}"
        )
        dialog.exec_()
    
    def export_all_lines_to_viewer(self):
        """Export all terminal lines to a new text viewer dialog"""
        # Extract all lines with formatting
        lines_data = self.extract_lines_with_formatting()
        
        if not lines_data:
            return
        
        # Import and show dialog
        from ui.dialogs import TextViewerDialog
        dialog = TextViewerDialog(
            self, 
            lines_data, 
            "All Terminal Lines"
        )
        dialog.exec_()
    
    def copy_selection(self):
        """Copy selected text to clipboard"""
        selected_text = self.get_selected_text()
        if selected_text:
            QApplication.clipboard().setText(selected_text)
    
    def paste_from_clipboard(self):
        """Paste from clipboard - delegate to parent terminal widget"""
        clipboard_text = QApplication.clipboard().text()
        if clipboard_text:
            # Get parent PyteTerminalWidget and paste
            parent = self.parent()
            while parent and not isinstance(parent, PyteTerminalWidget):
                parent = parent.parent()
            if parent and hasattr(parent, 'write_to_pty'):
                parent.write_to_pty(clipboard_text)


class ColumnHeaderWidget(QWidget):
    """Fixed header widget for displaying column numbers"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.terminal_canvas = None  # Reference to TerminalCanvas
        self.parent_terminal = None  # Reference to PyteTerminalWidget for scroll access
        self.setStyleSheet("background-color: #252525;")
        
    def set_terminal_canvas(self, canvas):
        """Set reference to the terminal canvas"""
        self.terminal_canvas = canvas
        
    def set_parent_terminal(self, terminal):
        """Set reference to parent terminal widget for scroll access"""
        self.parent_terminal = terminal
        
    def paintEvent(self, event):
        """Paint column numbers"""
        if not self.terminal_canvas or not self.terminal_canvas.screen:
            return
        
        painter = QPainter(self)
        painter.setFont(self.terminal_canvas.font)
        
        # Draw background
        # Fallback if attribute missing
        bg_color = getattr(self.terminal_canvas, 'column_number_bg_color', QColor('#252525'))
        painter.fillRect(self.rect(), bg_color)
        
        # Draw column numbers
        pen_color = getattr(self.terminal_canvas, 'column_number_color', QColor('#808080'))
        painter.setPen(pen_color)
        
        # Calculate line number offset to match canvas rendering
        line_num_offset = 0
        if self.terminal_canvas.show_line_numbers:
            line_num_offset = self.terminal_canvas.line_number_width * self.terminal_canvas.char_width
        
        # Get horizontal scroll offset to match canvas scrolling
        scroll_x = 0
        if self.parent_terminal and hasattr(self.parent_terminal, 'scroll_area'):
            scroll_x = self.parent_terminal.scroll_area.horizontalScrollBar().value()
        
        # Calculate which columns are visible based on scroll position
        visible_start_col = 0
        visible_end_col = self.terminal_canvas.screen.columns
        
        if self.parent_terminal and hasattr(self.parent_terminal, 'scroll_area'):
            viewport_width = self.parent_terminal.scroll_area.viewport().width()
            # Account for line number offset in visible calculations
            available_width = viewport_width - line_num_offset
            
            # Calculate visible column range (with buffer for smooth scrolling)
            buffer_cols = 5
            visible_start_col = max(0, (scroll_x // self.terminal_canvas.char_width) - buffer_cols)
            visible_end_col = min(
                self.terminal_canvas.screen.columns,
                ((scroll_x + available_width) // self.terminal_canvas.char_width) + buffer_cols
            )
        
        # Only draw column numbers that are visible
        for x in range(visible_start_col, visible_end_col):
            # Only show every 10th column to avoid clutter
            if x % 10 == 0 or x == self.terminal_canvas.screen.columns - 1:
                col_text = str(x + 1)
                # Position at the start of the column (adjusted for horizontal scroll)
                px = line_num_offset + x * self.terminal_canvas.char_width + 10 - scroll_x
                # Left-align the text at the start of the column
                painter.drawText(px, 
                                self.terminal_canvas.char_height // 2 + self.terminal_canvas.char_ascent - 2, 
                                col_text)


class PyteTerminalWidget(QWidget):
    """Terminal widget with full terminal emulation using pyte"""
    
    command_finished = pyqtSignal(int)
    command_executed = pyqtSignal(str)  # Emits command text when executed
    prompt_ready = pyqtSignal()  # Emits when a new prompt appears (indicating command finished)
    viewport_scrolled = pyqtSignal(float, float)  # Emits (viewport_start, viewport_height) when scrolled
    
    # Feature flag for Qt file type coloring overlay
    ENABLE_QT_FILE_COLORING = True
    
    @staticmethod
    def sanitize_wide_chars(text):
        """Sanitize text to work around pyte wide character handling issues.
        
        Pyte has bugs with certain wide characters (especially emojis with variation selectors)
        that cause it to truncate text after the emoji. This function replaces problematic
        characters with ASCII equivalents to prevent data loss.
        
        Args:
            text: Input text string
            
        Returns:
            Sanitized text string
        """
        # Map of problematic emoji sequences to ASCII equivalents
        # These are known to cause pyte to truncate following text
        emoji_replacements = {
            '⚠️': '[!]',  # WARNING SIGN + VARIATION SELECTOR-16
            '⚠': '[!]',   # WARNING SIGN alone (just in case)
            '❌': '[X]',  # CROSS MARK
            '✅': '[✓]',  # CHECK MARK
            '❗': '[!]',  # EXCLAMATION MARK
            '⚡': '[*]',  # HIGH VOLTAGE
            '🔥': '[*]',  # FIRE
            '💀': '[X]',  # SKULL
            '⏰': '[T]',  # ALARM CLOCK
            '🚨': '[!]',  # POLICE CAR LIGHT
            '📝': '[N]',  # MEMO
            '📊': '[#]',  # BAR CHART
            '✨': '[*]',  # SPARKLES
            '🎯': '[O]',  # DIRECT HIT
            '🔔': '[B]',  # BELL
            '💡': '[i]',  # LIGHT BULB
            '🔍': '[?]',  # MAGNIFYING GLASS
            '📌': '[P]',  # PUSHPIN
            '🛑': '[S]',  # STOP SIGN
            '⭐': '[*]',  # STAR
            '💻': '[C]',  # LAPTOP
            '📁': '[D]',  # FOLDER
            '📄': '[F]',  # PAGE
            '🔗': '[L]',  # LINK
        }
        
        # Replace problematic emojis
        for emoji, replacement in emoji_replacements.items():
            text = text.replace(emoji, replacement)
        
        # Also remove VARIATION SELECTOR-16 (U+FE0F) which often causes issues
        # when combined with other characters
        text = text.replace('\uFE0F', '')
        
        return text
    
    def __init__(self, shell=None, prefs_manager=None):
        super().__init__()
        self.shell = shell or os.environ.get('SHELL', '/bin/bash')
        self.master_fd = None
        self.slave_fd = None
        self.pid = None
        self.reader_thread = None
        
        # Track the maximum column width we've ever used - never shrink below this
        # This prevents line wrapping when viewport temporarily shrinks
        self._max_cols_ever = 600  # Start with our minimum (matches initial self.cols)
        
        # Command tracking for recording
        self.current_command_buffer = ""
        self.tracking_command = True  # Always track commands
        self.last_tab_press_time = 0.0  # Track when Tab was last pressed (for completion timing)
        self.pending_enter = False  # Track if we're waiting for tab completion before Enter
        self.last_paste_time = 0.0  # Track when text was pasted
        self.last_executed_command = None  # Track last executed command to skip directory updates for certain commands
        
        # Prompt detection for playback
        self.waiting_for_prompt = False  # Track if we're waiting for a prompt to appear
        self.last_prompt_line = None  # Track the last line where we saw a prompt
        
        # Flag to suppress directory updates during auto session playback
        self.suppress_directory_updates = False
        
        # Load preferences
        self.prefs_manager = prefs_manager or PreferencesManager()
        default_dir = self.prefs_manager.get('terminal', 'default_directory', os.path.expanduser('~'))
        self.current_directory = default_dir
        
        # Create pyte screen and stream with large scrollback buffer
        self.rows = 24  # Visible rows
        self.cols = 600  # Columns - start with very wide width to accommodate long log lines (500+ chars)
        self.scrollback_lines = 10000  # Keep 10000 lines of history
        
        # Create screen with history
        self.screen = pyte.HistoryScreen(self.cols, self.rows, history=self.scrollback_lines)
        self.stream = pyte.Stream(self.screen)
        
        # Track alternate screen mode for saving/restoring screen state
        self.was_in_alternate_mode = False
        self.saved_screen_buffer = None
        self.saved_screen_history = None
        self.saved_cursor_pos = None
        
        # Track if we're in an editor like pico/nano/vim
        self.in_editor_mode = False
        
        # Flag to temporarily disable PTY resize during tab/group switching
        self.resize_enabled = True
        
        # Track if we're in scrolling mode (for Shift+PageUp/Down etc)
        self.scroll_mode_active = False
        
        # Track last scroll event time to throttle viewport updates
        self._last_scroll_emit_time = 0
        self._scroll_emit_throttle_ms = 16  # Emit at most every ~16ms (~60fps)
        
        # Track last modifier key pressed (for macOS Ctrl vs Cmd distinction)
        # 16777249 = Qt.Key_Control, 16777250 = Qt.Key_Meta
        self.last_modifier_key = None
        
        # Track user manual scrolling for autoscroll behavior
        self.user_has_scrolled = False  # True if user manually scrolled up
        self.last_autoscroll_position = 0  # Last position we programmatically scrolled to
        self._initialized_scroll = False  # Track if we've had first meaningful scroll
        self._doing_realtime_scroll = False  # True when doing programmatic real-time scrolling
        
        # Throttling for autoscroll to prevent excessive calls
        self._autoscroll_timer = QTimer()
        self._autoscroll_timer.setSingleShot(True)
        self._autoscroll_pending = False
        self._last_autoscroll_call_time = 0
        self._autoscroll_throttle_ms = 16  # Minimum time between autoscroll calls (~60fps)
        
        # Track viewport synchronization to prevent circular updates
        self._updating_from_minimap = False  # True when updating scrollbar from minimap
        self._updating_from_scrollbar = False  # True when updating minimap from scrollbar
        
        # Output buffering to reduce UI updates (async performance)
        self._output_buffer = []
        self._output_buffer_timer = QTimer()
        self._output_buffer_timer.setSingleShot(True)
        self._output_buffer_timer.timeout.connect(self._flush_output_buffer)
        self._output_buffer_flush_ms = 16  # ~60fps update rate
        
        # Sleep/wake detection to prevent empty line accumulation
        self._app_is_suspended = False
        self._buffer_on_suspend = []
        self._last_activity_time = time.time()
        
        # Canvas update coalescing (async performance)
        self._canvas_update_pending = False
        self._canvas_update_timer = QTimer()
        self._canvas_update_timer.setSingleShot(True)
        self._canvas_update_timer.timeout.connect(self._do_canvas_update)
        
        # Canvas resize throttling (critical for large outputs)
        self._canvas_resize_pending = False
        self._canvas_resize_timer = QTimer()
        self._canvas_resize_timer.setSingleShot(True)
        self._canvas_resize_timer.timeout.connect(self._do_canvas_resize)
        
        # History file manager and archival system
        from core.history_file_manager import HistoryFileManager
        self.tab_id = self._generate_tab_id()  # Unique ID for this terminal
        self.history_manager = HistoryFileManager()
        # Create history file IMMEDIATELY on terminal creation for continuous archiving
        self.history_file_path = self.history_manager.create_history_file(self.tab_id)
        
        # Streaming detection for archive markers (DISABLED)
        self._last_output_time = time.time()
        self._streaming_active = False
        self._streaming_stop_threshold = 3.0  # seconds of silence = stopped
        # Timer disabled to remove visual markers
        # self._streaming_check_timer = QTimer()
        # self._streaming_check_timer.timeout.connect(self._check_streaming_state)
        # self._streaming_check_timer.start(1000)  # Check every second
        self._streaming_events = []  # Track streaming events for archival
        
        # Auto-archive settings
        self._last_auto_archive_check = 0  # Track last time we checked for auto-archive
        self._auto_archive_in_progress = False  # Prevent recursive archival
        
        # Auto-archive monitoring timer (checks every 5 seconds)
        self.auto_archive_timer = QTimer()
        self.auto_archive_timer.timeout.connect(self._check_auto_archive_threshold)
        self.auto_archive_timer.start(5000)  # Check every 5 seconds
        
        # Suggestion system
        self.suggestion_manager = SuggestionManager()
        self.suggestion_widget = None  # Will be created in init_ui
        self.showing_suggestions = False
        self.suggestion_timer = QTimer()
        self.suggestion_timer.setSingleShot(True)
        self.suggestion_timer.timeout.connect(self._update_suggestions)
        
        # Search system
        self.search_widget = None  # Will be created in init_ui
        self.search_matches = []  # List of (row, col, length) tuples for matches
        self.current_match_index = -1  # Current match being viewed
        self.search_active = False  # True when search widget is open and user is navigating results
        
        self.init_ui()
        self.start_shell()

        # Network state
        self._online = True
        self._current_command_requires_network = False

        # Timer to periodically check connectivity and update warning visibility
        try:
            self._network_timer = QTimer(self)
            self._network_timer.setInterval(5000)  # 5 seconds
            self._network_timer.timeout.connect(self._check_network_status)
            self._network_timer.start()
        except Exception:
            pass
        
        # Timer for cursor blink
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.canvas.toggle_cursor_blink)
        self.cursor_timer.start(500)  # Blink every 500ms
        
        # Connect to application state changes for sleep/wake detection
        QApplication.instance().applicationStateChanged.connect(self._on_app_state_changed)
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Set focus policy to accept focus clicks anywhere in the widget
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Create font size spinbox (will be referenced from main window)
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
        self.font_size_spin.valueChanged.connect(self.change_font_size)
        # Note: font_size_spin is now added to main window's bottom bar
        
        # Terminal canvas - pass self as parent to enable key event delegation
        self.canvas = TerminalCanvas(parent=self)
        self.canvas.screen = self.screen
        self.canvas.setMinimumSize(400, 300)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        
        # Create a fixed column number header widget (outside of scroll area)
        self.column_header = ColumnHeaderWidget(parent=self)
        self.column_header.set_terminal_canvas(self.canvas)
        self.column_header.set_parent_terminal(self)  # Pass reference to this terminal widget
        self.column_header.setFixedHeight(0)  # Will be resized based on canvas state
        
        # Wrap canvas in a scroll area for scrolling support
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(False)  # Let canvas control its own size for scrolling
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # Enable horizontal scroll for long lines
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Hide scrollbar - using minimap instead
        self.scroll_area.setFocusPolicy(Qt.NoFocus)  # Don't steal focus from canvas
        
        # Connect scrollbar to detect user manual scrolling
        scroll_bar = self.scroll_area.verticalScrollBar()
        if scroll_bar:
            # Track when user manually scrolls (not programmatic scroll)
            scroll_bar.valueChanged.connect(self._on_scrollbar_value_changed)
        
        # Connect horizontal scrollbar to update column header
        h_scroll_bar = self.scroll_area.horizontalScrollBar()
        if h_scroll_bar:
            h_scroll_bar.valueChanged.connect(self._on_horizontal_scroll_changed)
        
        # Install event filter on scroll area itself to capture all clicks
        self.scroll_area.installEventFilter(self)
        
        # Enable all input methods for scrolling
        self.scroll_area.viewport().installEventFilter(self)  # Capture all viewport events
        
        # Enable kinetic scrolling for smooth trackpad gestures (macOS)
        try:
            # Enable momentum/kinetic scrolling for trackpad gestures
            self.scroll_area.viewport().setAttribute(Qt.WA_AcceptTouchEvents, True)
        except:
            pass
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #2b2b2b;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #555;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #666;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        
        # Network warning label (hidden by default)
        self.network_warning = QLabel("No internet access")
        self.network_warning.setObjectName('networkWarning')
        self.network_warning.setStyleSheet("background-color: #7f1d1d; color: white; padding: 6px; font-weight: bold;")
        self.network_warning.setVisible(False)
        layout.addWidget(self.network_warning)

        layout.addWidget(self.column_header)
        layout.addWidget(self.scroll_area, 1)  # Give it stretch factor
        
        # Create search widget (hidden by default)
        self.search_widget = TerminalSearchWidget(self)
        self.search_widget.search_requested.connect(self._on_search_requested)
        self.search_widget.next_requested.connect(self._on_search_next)
        self.search_widget.previous_requested.connect(self._on_search_previous)
        self.search_widget.close_requested.connect(self._on_search_closed)
        layout.addWidget(self.search_widget)
        
        # Connect scrollbar valueChanged to emit viewport scrolled signal
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar:
            scrollbar.valueChanged.connect(self._on_scrollbar_changed)
        
        # Set column header height based on canvas settings
        if self.canvas.show_column_numbers:
            self.column_header.setFixedHeight(self.canvas.column_number_height * self.canvas.char_height)
        
        # Set canvas as the initial focus widget
        self.canvas.setFocus()
        
        # Create suggestion widget (parented to canvas but shown as popup)
        self.suggestion_widget = SuggestionWidget(self)
        self.suggestion_widget.item_selected.connect(self._on_suggestion_selected)
        self.suggestion_widget.dismissed.connect(self._on_suggestion_dismissed)
        
        # Update suggestion manager with current directory
        self.suggestion_manager.set_current_directory(self.current_directory)
    
    def eventFilter(self, obj, event):
        """Filter events for the scroll area viewport to enable all input methods"""
        # Handle mouse press events to give canvas focus when clicking anywhere in scroll area
        if event.type() == QEvent.MouseButtonPress:
            # Give focus to canvas when clicking anywhere in the terminal area
            # This captures clicks on both viewport and scroll area itself
            self.canvas.setFocus()
            # Let the event propagate normally
        # Don't filter anything - let all events through
        return False
    
    def showEvent(self, event):
        """Handle widget show event"""
        super().showEvent(event)
        # Update PTY size when widget becomes visible
        QTimer.singleShot(100, self.update_pty_size_from_widget)
        # Ensure canvas has focus
        self.canvas.setFocus()
        
        # Cancel any pending suspend timer
        if hasattr(self, '_suspend_timer') and self._suspend_timer.isActive():
            self._suspend_timer.stop()
        
        # ALWAYS unsuspend when widget is shown - user is viewing it
        if self._app_is_suspended:
            self._app_is_suspended = False
            self._last_activity_time = time.time()
            
            # Flush suspend buffer if there's data
            if self._buffer_on_suspend:
                self._output_buffer.extend(self._buffer_on_suspend)
                self._buffer_on_suspend = []
                # Flush immediately
                QTimer.singleShot(0, self._flush_output_buffer)
        
        # Failsafe: schedule flush if buffer has data but timer stopped
        if self._output_buffer and not self._output_buffer_timer.isActive():
            QTimer.singleShot(0, self._flush_output_buffer)
    
    def _on_app_state_changed(self, state):
        """Handle application state changes (sleep/wake/background)"""
        from PyQt5.QtCore import Qt
        
        # Check if app is going inactive (sleep, lock screen, background)
        # Don't suspend immediately - use a timer to avoid flickering states
        if state != Qt.ApplicationActive:
            # Schedule suspend check after a delay to avoid rapid state changes
            if not self._app_is_suspended:
                # Use a timer to delay suspension - if app becomes active again quickly, don't suspend
                if not hasattr(self, '_suspend_timer'):
                    self._suspend_timer = QTimer()
                    self._suspend_timer.setSingleShot(True)
                    self._suspend_timer.timeout.connect(self._do_suspend)
                # Only suspend if inactive for >500ms
                self._suspend_timer.start(500)
        
        # Check if app is becoming active (wake up, unlock, foreground)
        elif state == Qt.ApplicationActive:
            # Cancel any pending suspend
            if hasattr(self, '_suspend_timer') and self._suspend_timer.isActive():
                self._suspend_timer.stop()
            
            was_suspended = self._app_is_suspended
            if was_suspended:
                current_time = time.time()
                time_suspended = current_time - self._last_activity_time
                
                # Clear suspended flag FIRST to allow new data to flow normally
                self._app_is_suspended = False
                self._last_activity_time = current_time
                
                # If we have buffered data from before suspend, intelligently process it
                if self._buffer_on_suspend or self._output_buffer:
                    combined_buffer = self._buffer_on_suspend + self._output_buffer
                    
                    # If suspended for a long time (>10s), aggressively limit buffer
                    if time_suspended > 10:
                        # Clean and limit buffer to prevent line explosion
                        if len(combined_buffer) > 20:
                            # Take last 20 items only
                            combined_buffer = combined_buffer[-20:]
                        
                        # Remove excessive newlines from accumulated output
                        cleaned_buffer = []
                        for item in combined_buffer:
                            # Replace multiple consecutive newlines with single newline
                            cleaned_item = re.sub(r'\n{3,}', '\n\n', item)
                            cleaned_buffer.append(cleaned_item)
                        combined_buffer = cleaned_buffer
                    
                    self._output_buffer = combined_buffer
                    self._buffer_on_suspend = []
                    
                    # Flush immediately on resume
                    QTimer.singleShot(0, self._flush_output_buffer)
                
                # Ensure timer is running for any new data that arrives
                if self._output_buffer and not self._output_buffer_timer.isActive():
                    self._output_buffer_timer.start(self._output_buffer_flush_ms)
    
    def _do_suspend(self):
        """Actually suspend the app after delay confirms it's still inactive"""
        # Don't suspend if widget is visible - user is watching it!
        if self.isVisible():
            return
        
        if not self._app_is_suspended:
            self._app_is_suspended = True
            # Stop the output buffer timer to prevent processing during sleep
            if self._output_buffer_timer.isActive():
                self._output_buffer_timer.stop()
            # Move current buffer to suspend buffer
            self._buffer_on_suspend = self._output_buffer.copy()
            self._output_buffer.clear()
    
    def focusInEvent(self, event):
        """Handle focus in event - pass focus to canvas"""
        super().focusInEvent(event)
        # Always pass focus to canvas when terminal widget gains focus
        self.canvas.setFocus()
        
        # Cancel any pending suspend timer
        if hasattr(self, '_suspend_timer') and self._suspend_timer.isActive():
            self._suspend_timer.stop()
        
        # ALWAYS unsuspend when widget gains focus - user is interacting
        if self._app_is_suspended:
            self._app_is_suspended = False
            self._last_activity_time = time.time()
            
            # Flush suspend buffer if there's data
            if self._buffer_on_suspend:
                self._output_buffer.extend(self._buffer_on_suspend)
                self._buffer_on_suspend = []
                # Flush immediately
                QTimer.singleShot(0, self._flush_output_buffer)
        
        # Failsafe: schedule flush if buffer has data but timer stopped
        if self._output_buffer and not self._output_buffer_timer.isActive():
            QTimer.singleShot(0, self._flush_output_buffer)
    
    def mousePressEvent(self, event):
        """Handle mouse press - give focus to canvas"""
        super().mousePressEvent(event)
        # Ensure canvas gets focus when clicking anywhere in terminal widget
        self.canvas.setFocus()
    
    def change_font_size(self, size):
        """Change font size"""
        self.canvas.set_font_size(size)
        # Update column header height if column numbers are shown
        if self.canvas.show_column_numbers:
            self.column_header.setFixedHeight(self.canvas.column_number_height * self.canvas.char_height)
            self.column_header.update()
        else:
            self.column_header.setFixedHeight(0)
        # Ensure canvas is resized to reflect new character dimensions
        # This ensures all lines are visible with the new font size
        self.canvas.resizeCanvas()
        # Don't update PTY size on font change - avoids extra line/prompt redraw
        # Font change is just a visual preference, shell doesn't need to know
    
    def update_pty_size_from_widget(self):
        """Update PTY size based on widget size"""
        if not self.resize_enabled:
            return
        
        # Calculate new rows and cols based on VIEWPORT size (not canvas size)
        # The PTY size should reflect what's visible, not the entire scrollback buffer
        if hasattr(self, 'scroll_area') and self.scroll_area:
            # Use viewport size (visible area)
            viewport_width = self.scroll_area.viewport().width() - 20
            viewport_height = self.scroll_area.viewport().height() - 20
        else:
            # Fallback to canvas size if scroll area not available
            viewport_width = self.canvas.width() - 20
            viewport_height = self.canvas.height() - 20
        
        # Subtract line number section width if line numbers are shown
        if self.canvas.show_line_numbers:
            line_num_width = self.canvas.line_number_width * self.canvas.char_width
            viewport_width -= line_num_width
        
        # Check if auto-fit width is enabled
        auto_fit_width = self.prefs_manager.get('terminal', 'auto_fit_width', True)
        
        if auto_fit_width:
            # Auto-fit mode: calculate columns from available viewport width
            calculated_cols = viewport_width // self.canvas.char_width
            # Use minimum of 80 columns (standard terminal width)
            new_cols = max(80, calculated_cols)
        else:
            # Fixed width mode: use user-set columns
            user_columns = self.prefs_manager.get('terminal', 'columns', 120)
            if user_columns and user_columns > 0:
                new_cols = user_columns
            else:
                # Fallback to calculated if no valid user setting
                calculated_cols = viewport_width // self.canvas.char_width
                new_cols = max(80, calculated_cols)
        
        new_rows = max(24, viewport_height // self.canvas.char_height)
        
        
        # CRITICAL: Cap rows and cols to reasonable limits to prevent struct.pack overflow
        # The 'H' format in struct.pack requires 0 <= number <= 65535
        # Most terminals don't exceed 500 rows even on very large screens
        # Increase column limit to 2000 to accommodate very long log lines without wrapping
        new_cols = min(new_cols, 2000)
        new_rows = min(new_rows, 500)
        
        if new_cols != self.cols or new_rows != self.rows:
            self.cols = new_cols
            self.rows = new_rows
            
            # Track maximum columns ever used
            self._max_cols_ever = max(self._max_cols_ever, new_cols)
            
            # Resize pyte screen
            self.screen.resize(self.rows, self.cols)
            
            # Update PTY size
            if self.master_fd is not None:
                try:
                    s = struct.pack('HHHH', self.rows, self.cols, 0, 0)
                    fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)
                except struct.error as e:
                    pass
    
    def _on_scrollbar_value_changed(self, value):
        """Detect when user manually scrolls (not programmatic scroll)"""
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return
        
        max_value = scroll_bar.maximum()
        
        # Check if scrollbar is effectively disabled (very small range)
        # This happens when content fits in viewport but padding creates minimal scrollbar
        if max_value > 0 and max_value < 50:  # Less than ~2-3 lines worth of scroll
            return
        
        # Ignore scroll changes during programmatic real-time scrolling
        if self._doing_realtime_scroll:
            return
        
        max_value = scroll_bar.maximum()
        current_value = value
        
        # During initial setup, scrollbar may have max=0 or be in transition
        # Mark as initialized once we have a meaningful scrollbar range
        if not self._initialized_scroll and max_value > 0:
            self._initialized_scroll = True
            # If we start at the bottom, ensure autoscroll is enabled
            if current_value == max_value:
                self.user_has_scrolled = False
        
        # Check if we're at the bottom - if so, never mark as user scroll
        # This is critical: being at the bottom means autoscroll should remain enabled
        if current_value == max_value:
            # At bottom - ensure autoscroll is enabled (unless search is active)
            if self.user_has_scrolled and not self.search_active:
                self.user_has_scrolled = False
            return
        
        # Check if this is a programmatic scroll (we're setting it to max)
        # If the value matches our last autoscroll position, it's programmatic
        if current_value == self.last_autoscroll_position:
            # Programmatic scroll - don't mark as user scroll
            return
        
        # Check if we're jumping to a line - don't clear preserve flag yet
        if hasattr(self, '_jumping_to_line') and self._jumping_to_line:
            return
        
        # User is manually scrolling - clear the preserve flag to allow recalculation
        if hasattr(self, '_preserve_clicked_line') and self._preserve_clicked_line:
            self._preserve_clicked_line = False
        
        # Check if user scrolled away from bottom
        pixels_per_line = self.canvas.char_height if hasattr(self.canvas, 'char_height') else 20
        threshold = 5 * pixels_per_line
        distance_from_bottom = max_value - current_value
        
        if distance_from_bottom > threshold:
            # User has scrolled up - disable autoscroll
            if not self.user_has_scrolled:
                self.user_has_scrolled = True
        else:
            # User scrolled back near bottom - re-enable autoscroll
            # BUT: Don't re-enable if user is actively using search
            if self.user_has_scrolled and not self.search_active:
                self.user_has_scrolled = False
    
    def _on_horizontal_scroll_changed(self, value):
        """Update column header when horizontal scroll position changes"""
        # Trigger repaint of column header to show correct column numbers
        if hasattr(self, 'column_header'):
            self.column_header.update()
    
    def _auto_scroll_to_bottom(self, max_increased=False):
        """Auto-scroll to bottom to show latest output (terminal-style)
        
        Args:
            max_increased: True if scrollbar maximum increased (new content arrived)
        
        Terminal-style autoscroll behavior:
        - Always scroll when new content arrives, UNLESS user has manually scrolled up
        - If user scrolled up, don't autoscroll (respect user's choice)
        - If user scrolls back near bottom, re-enable autoscroll
        """
        
        # Throttle: Don't call more than once per throttle period
        current_time = time.time() * 1000  # milliseconds
        if current_time - self._last_autoscroll_call_time < self._autoscroll_throttle_ms:
            # Too soon since last call, skip this one
            return
        
        # Get scroll bar
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return
        
        # Get current scrollbar state
        max_value = scroll_bar.maximum()
        current_value = scroll_bar.value()
        page_step = scroll_bar.pageStep()
        
        # Calculate total lines in buffer
        total_lines = len(self.screen.buffer) if self.screen else 0
        visible_lines = self.screen.lines if self.screen else 0
        
        # Early exit: Already at bottom, no need to process further
        if max_value > 0 and current_value == max_value:
            self._last_autoscroll_call_time = current_time
            return
        
        # Check if user has manually scrolled away from bottom
        # If so, don't auto-scroll (respect user's choice to stay at current position)
        if self.user_has_scrolled:
            return
        
        # Don't auto-scroll if user is actively using search
        if self.search_active:
            return
        
        # Check if content fits in viewport (no scrolling needed)
        # Calculate if the actual content height is less than viewport height
        viewport_height = self.scroll_area.viewport().height() if self.scroll_area else 0
        content_height = self.canvas.char_height * total_lines if hasattr(self.canvas, 'char_height') else 0
        
        if viewport_height > 0 and content_height > 0 and content_height <= viewport_height:
            return
        
        # Alternative check: if scrollbar range is effectively zero or minimal
        if max_value <= 0 or (max_value > 0 and max_value < 50):
            return
        
        # Terminal-style autoscroll: Scroll to bottom when not at bottom
        # Only auto-scroll if user hasn't manually scrolled away
        if max_value > 0 and current_value < max_value:
            scroll_bar.setValue(max_value)
            self.last_autoscroll_position = max_value
            self._last_autoscroll_call_time = current_time
            
            # Force viewport update to ensure visual refresh
            if self.scroll_area and self.scroll_area.viewport():
                self.scroll_area.viewport().update()
            
            # Force canvas repaint
            if self.canvas:
                self.canvas.update()
    
    def force_scroll_to_bottom(self):
        """Force scroll to bottom - useful when terminal gets stuck or user wants to see prompt
        
        This bypasses all throttling and user scroll tracking to immediately jump to bottom.
        """
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return
        
        max_value = scroll_bar.maximum()
        if max_value > 0:
            # Force scroll to absolute bottom
            scroll_bar.setValue(max_value)
            self.last_autoscroll_position = max_value
            self._last_autoscroll_call_time = time.time() * 1000
            # Reset user scroll flag so autoscroll resumes
            self.user_has_scrolled = False
            
            # Force viewport update to ensure visual refresh
            if self.scroll_area and self.scroll_area.viewport():
                self.scroll_area.viewport().update()
            if self.canvas:
                self.canvas.update()
            
            # Update viewport range immediately after force scroll
            total_range = max_value - scroll_bar.minimum() + scroll_bar.pageStep()
            if total_range > 0:
                viewport_start = max_value / total_range
                viewport_height = scroll_bar.pageStep() / total_range
                self.update_viewport_range(viewport_start, viewport_height)
                # Emit signal so main window can update minimap immediately
                self.viewport_scrolled.emit(viewport_start, viewport_height)
    
    def _on_scrollbar_changed(self, value):
        """Handle scrollbar value change to emit viewport update signal
        
        Args:
            value: New scrollbar value
        """
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return
        
        # Skip if we're jumping to a specific line (will emit viewport_scrolled explicitly)
        if hasattr(self, '_jumping_to_line') and self._jumping_to_line:
            return
        
        # Throttle scroll events to avoid flooding - only emit every 100ms
        import time
        current_time = time.time() * 1000  # milliseconds
        self._last_scroll_emit_time = current_time
        
        # Calculate viewport position and emit signal
        total_range = scroll_bar.maximum() - scroll_bar.minimum() + scroll_bar.pageStep()
        if total_range > 0:
            viewport_start = value / total_range
            viewport_height = scroll_bar.pageStep() / total_range
            # Emit signal so main window can update minimap
            self.viewport_scrolled.emit(viewport_start, viewport_height)
    
    def is_at_bottom(self):
        """Check if the scroll position is at or near the bottom
        
        Returns:
            bool: True if at bottom (within threshold), False otherwise
        """
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return True  # No scrollbar means we're at bottom
        
        max_value = scroll_bar.maximum()
        current_value = scroll_bar.value()
        
        # Consider "at bottom" if within 5 lines of the bottom
        pixels_per_line = self.canvas.char_height if hasattr(self.canvas, 'char_height') else 20
        threshold = 5 * pixels_per_line
        distance_from_bottom = max_value - current_value
        
        return distance_from_bottom <= threshold

    
    def resizeEvent(self, event):
        """Handle widget resize"""
        super().resizeEvent(event)
        # Update PTY size when widget is resized
        QTimer.singleShot(100, self.update_pty_size_from_widget)
        # Also resize canvas to fill viewport
        QTimer.singleShot(100, self.canvas.resizeCanvas)
    
    def start_shell(self):
        """Start a shell in a PTY"""
        try:
            # Create PTY
            self.master_fd, self.slave_fd = pty.openpty()
            
            # Set PTY size
            s = struct.pack('HHHH', self.rows, self.cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)
            
            # Fork process
            self.pid = os.fork()
            
            if self.pid == 0:
                # Child process
                os.close(self.master_fd)
                
                # Make slave the controlling terminal
                os.setsid()
                fcntl.ioctl(self.slave_fd, termios.TIOCSCTTY, 0)
                
                # Redirect stdin, stdout, stderr
                os.dup2(self.slave_fd, 0)
                os.dup2(self.slave_fd, 1)
                os.dup2(self.slave_fd, 2)
                
                if self.slave_fd > 2:
                    os.close(self.slave_fd)
                
                # Change to default directory before starting shell
                os.chdir(self.current_directory)
                
                # Set environment
                env = os.environ.copy()
                env['TERM'] = 'xterm-256color'
                env['COLORTERM'] = 'truecolor'
                env['CLICOLOR'] = '1'
                env['CLICOLOR_FORCE'] = '1'
                
                # Comprehensive LS_COLORS for different file types
                # Format: type=color_codes where color codes are ANSI (0-bold, 1-bold, 30-37 colors, 90-97 bright colors)
                ls_colors = [
                    # Basic file types
                    'di=1;94',          # Directories - bright blue, bold
                    'ln=1;96',          # Symbolic links - bright cyan, bold
                    'ex=1;92',          # Executables - bright green, bold
                    'or=1;91',          # Orphaned symlinks - bright red, bold
                    'mi=1;91',          # Missing file - bright red, bold
                    'pi=1;93',          # Named pipes (FIFO) - bright yellow, bold
                    'so=1;95',          # Sockets - bright magenta, bold
                    'bd=1;93;40',       # Block devices - bright yellow on black
                    'cd=1;93;40',       # Character devices - bright yellow on black
                    
                    # Archives and compressed files - bright red
                    '*.tar=1;91',
                    '*.tgz=1;91',
                    '*.arc=1;91',
                    '*.arj=1;91',
                    '*.taz=1;91',
                    '*.lha=1;91',
                    '*.lz4=1;91',
                    '*.lzh=1;91',
                    '*.lzma=1;91',
                    '*.tlz=1;91',
                    '*.txz=1;91',
                    '*.tzo=1;91',
                    '*.t7z=1;91',
                    '*.zip=1;91',
                    '*.z=1;91',
                    '*.dz=1;91',
                    '*.gz=1;91',
                    '*.lrz=1;91',
                    '*.lz=1;91',
                    '*.lzo=1;91',
                    '*.xz=1;91',
                    '*.zst=1;91',
                    '*.tzst=1;91',
                    '*.bz2=1;91',
                    '*.bz=1;91',
                    '*.tbz=1;91',
                    '*.tbz2=1;91',
                    '*.tz=1;91',
                    '*.deb=1;91',
                    '*.rpm=1;91',
                    '*.jar=1;91',
                    '*.war=1;91',
                    '*.ear=1;91',
                    '*.sar=1;91',
                    '*.rar=1;91',
                    '*.alz=1;91',
                    '*.ace=1;91',
                    '*.zoo=1;91',
                    '*.cpio=1;91',
                    '*.7z=1;91',
                    '*.rz=1;91',
                    '*.cab=1;91',
                    '*.wim=1;91',
                    '*.swm=1;91',
                    '*.dwm=1;91',
                    '*.esd=1;91',
                    
                    # Image files - bright magenta
                    '*.jpg=1;95',
                    '*.jpeg=1;95',
                    '*.mjpg=1;95',
                    '*.mjpeg=1;95',
                    '*.gif=1;95',
                    '*.bmp=1;95',
                    '*.pbm=1;95',
                    '*.pgm=1;95',
                    '*.ppm=1;95',
                    '*.tga=1;95',
                    '*.xbm=1;95',
                    '*.xpm=1;95',
                    '*.tif=1;95',
                    '*.tiff=1;95',
                    '*.png=1;95',
                    '*.svg=1;95',
                    '*.svgz=1;95',
                    '*.mng=1;95',
                    '*.pcx=1;95',
                    '*.webp=1;95',
                    '*.ico=1;95',
                    
                    # Video files - bright magenta (bold)
                    '*.mov=1;35',
                    '*.mpg=1;35',
                    '*.mpeg=1;35',
                    '*.m2v=1;35',
                    '*.mkv=1;35',
                    '*.webm=1;35',
                    '*.ogm=1;35',
                    '*.mp4=1;35',
                    '*.m4v=1;35',
                    '*.mp4v=1;35',
                    '*.vob=1;35',
                    '*.qt=1;35',
                    '*.nuv=1;35',
                    '*.wmv=1;35',
                    '*.asf=1;35',
                    '*.rm=1;35',
                    '*.rmvb=1;35',
                    '*.flc=1;35',
                    '*.avi=1;35',
                    '*.fli=1;35',
                    '*.flv=1;35',
                    '*.gl=1;35',
                    '*.dl=1;35',
                    '*.xcf=1;35',
                    '*.xwd=1;35',
                    '*.yuv=1;35',
                    '*.cgm=1;35',
                    '*.emf=1;35',
                    
                    # Audio files - bright cyan
                    '*.aac=1;96',
                    '*.au=1;96',
                    '*.flac=1;96',
                    '*.m4a=1;96',
                    '*.mid=1;96',
                    '*.midi=1;96',
                    '*.mka=1;96',
                    '*.mp3=1;96',
                    '*.mpc=1;96',
                    '*.ogg=1;96',
                    '*.ra=1;96',
                    '*.wav=1;96',
                    '*.oga=1;96',
                    '*.opus=1;96',
                    '*.spx=1;96',
                    '*.xspf=1;96',
                    
                    # Documents - bright yellow
                    '*.pdf=1;93',
                    '*.doc=1;93',
                    '*.docx=1;93',
                    '*.xls=1;93',
                    '*.xlsx=1;93',
                    '*.ppt=1;93',
                    '*.pptx=1;93',
                    '*.odt=1;93',
                    '*.ods=1;93',
                    '*.odp=1;93',
                    '*.rtf=1;93',
                    '*.txt=1;93',
                    '*.md=1;93',
                    '*.markdown=1;93',
                    
                    # Source code files - bright white/cyan
                    '*.py=1;97',
                    '*.js=1;97',
                    '*.jsx=1;97',
                    '*.ts=1;97',
                    '*.tsx=1;97',
                    '*.java=1;97',
                    '*.c=1;97',
                    '*.cpp=1;97',
                    '*.cc=1;97',
                    '*.h=1;97',
                    '*.hpp=1;97',
                    '*.go=1;97',
                    '*.rs=1;97',
                    '*.rb=1;97',
                    '*.php=1;97',
                    '*.pl=1;97',
                    '*.sh=1;97',
                    '*.bash=1;97',
                    '*.zsh=1;97',
                    '*.fish=1;97',
                    '*.vim=1;97',
                    '*.lua=1;97',
                    '*.swift=1;97',
                    '*.kt=1;97',
                    '*.sql=1;97',
                    '*.r=1;97',
                    '*.scala=1;97',
                    
                    # Config files - cyan
                    '*.json=0;96',
                    '*.yaml=0;96',
                    '*.yml=0;96',
                    '*.toml=0;96',
                    '*.xml=0;96',
                    '*.conf=0;96',
                    '*.config=0;96',
                    '*.ini=0;96',
                    '*.env=0;96',
                    
                    # Special files - green
                    '*Makefile=1;92',
                    '*Dockerfile=1;92',
                    '*README=1;92',
                    '*LICENSE=1;92',
                    '*.log=0;90',
                ]
                env['LS_COLORS'] = ':'.join(ls_colors)
                
                # For BSD ls (macOS) - LSCOLORS uses a different format
                # Order: di ln so pi ex bd cd su sg ow ow
                # Colors: a=black, b=red, c=green, d=brown, e=blue, f=magenta, g=cyan, h=light grey
                #         A-H are bold versions
                # Format: foreground+background for each type
                env['LSCOLORS'] = 'ExGxFxdxCxDxDxhbhdacEc'
                
                # Enable readline and tab completion
                env['INPUTRC'] = os.path.expanduser('~/.inputrc')
                
                # Start shell with interactive login mode
                # -i = interactive (enables tab completion)
                # -l = login (loads profiles)
                os.execve(self.shell, [self.shell, '-i', '-l'], env)
            else:
                # Parent process
                os.close(self.slave_fd)
                
                # Make master non-blocking
                flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
                fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                
                # Start reader thread
                self.reader_thread = PTYReader(self.master_fd)
                self.reader_thread.output_received.connect(self.handle_output)
                self.reader_thread.start()
                
                # Initialize viewport highlighter to cursor position (active line) after a short delay
                # This ensures the terminal is ready and has rendered initial prompt
                QTimer.singleShot(500, self.initialize_viewport_highlighter)
                
        except Exception as e:
            pass
    
    def write_to_pty(self, data):
        """Write data to the PTY"""
        if self.master_fd is not None:
            try:
                os.write(self.master_fd, data.encode('utf-8'))
            except OSError as e:
                pass
    
    def execute_command(self, command, env_vars=None):
        """Execute a command by writing it to the PTY"""
        if command.strip():
            # Detect clear commands and archive before clearing
            if command.strip() in ['clear', 'cls', 'reset', 'tput reset']:
                print(f"\n[DEBUG] Clear command detected: '{command.strip()}'")
                self._archive_before_clear(command.strip())
            
            # Store the last executed command for directory update logic
            self.last_executed_command = command.strip()
            
            # Set flag to wait for prompt (for playback)
            # Reset last_prompt_line to detect when a new prompt appears
            self.waiting_for_prompt = True
            
            # Store current prompt line as baseline - we'll detect when it changes
            if self.screen and self.screen.cursor.y >= 0:
                try:
                    cursor_y = self.screen.cursor.y
                    current_line_text = self._extract_line_text(cursor_y)
                    if self._has_prompt(current_line_text):
                        # Use current prompt line as baseline
                        self.last_prompt_line = cursor_y
                    else:
                        # No prompt on current line, reset baseline
                        self.last_prompt_line = None
                except Exception as e:
                    self.last_prompt_line = None
            else:
                self.last_prompt_line = None
            
            # Detect if this command may require network
            try:
                lower_cmd = command.lower() if command else ''
            except Exception:
                lower_cmd = ''
            # Keywords that likely require network
            NETWORK_COMMAND_KEYWORDS = [
                'wget', 'curl', 'git', 'ssh', 'scp', 'npm', 'yarn', 'pip install', 'pip3', 'pip',
                'apt-get', 'brew', 'ftp', 'sftp', 'rsync', 'telnet', 'ping', 'npm install',
                'composer', 'gh', 'git clone', 'git fetch', 'git pull'
            ]
            self._current_command_requires_network = any(k in lower_cmd for k in NETWORK_COMMAND_KEYWORDS)

            # Immediate connectivity check and debug output
            try:
                online = self.is_online()
            except Exception:
                online = True

            if self._current_command_requires_network and not online:
                try:
                    self.network_warning.setVisible(True)
                except Exception:
                    pass
                try:
                    self.handle_output(b"[No internet access - command may fail]\n")
                except Exception:
                    pass

            self.write_to_pty(command + '\n')
    
    def interrupt_process(self):
        """Send interrupt signal (Ctrl+C)"""
        self.write_to_pty('\x03')
    
    def kill_process(self):
        """Kill the shell process"""
        if hasattr(self, 'pid') and self.pid:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                print
    
    def clear(self):
        """
        Clear the terminal screen and archive current content to history file
        This method is called when the user presses clear button or shortcut
        """
        try:
            # Archive before clearing (same as typing 'clear' command)
            print("[DEBUG] clear() method called (button/shortcut)")
            if self.screen:
                history_size = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
                total_lines = history_size + self.screen.lines
                
                print(f"[DEBUG] clear(): total_lines={total_lines}")
                
                if total_lines > 3:
                    lines_to_archive = self._extract_lines_for_archive(0, total_lines)
                    
                    if lines_to_archive:
                        print(f"[DEBUG] clear(): Appending {len(lines_to_archive)} lines to archive")
                        # APPEND to existing history file (continuous mode)
                        self.history_manager.append_archive(
                            self.tab_id,
                            lines_to_archive,
                            command_context="clear_button"
                        )
            
            # Send clear screen command to PTY (Ctrl+L)
            self.write_to_pty('\x0c')
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Still try to clear even if archiving failed
            self.write_to_pty('\x0c')
    
    def initialize_viewport_highlighter(self):
        """Initialize viewport highlighter to the active cursor line (where prompt is)"""
        if not self.screen or not self.canvas:
            return
        
        try:
            # Calculate the active line (where cursor/prompt is)
            # cursor.y is relative to visible screen, add history offset to get absolute line
            history_offset = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
            active_line = history_offset + self.screen.cursor.y
            
            # Set viewport highlighter to active line
            self.canvas.viewport_center_line = active_line
            
            
            # Trigger canvas update to show highlighter
            self.canvas.update()
            
            # Update minimap to show highlighter position
            from ui.main_window import MainWindow
            from PyQt5.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, MainWindow):
                    if hasattr(widget, 'minimap_panel'):
                        widget.minimap_panel.update()
                    break
        except Exception as e:
            pass

    def is_online(self, timeout=2.0):
        """Return True if we can reach a public DNS server (simple offline check)."""
        try:
            sock = socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            sock.close()
            return True
        except Exception as e:
            return False

    def _check_network_status(self):
        """Check network connectivity and show/hide the warning label when needed."""
        online = self.is_online()
        self._online = online

        if getattr(self, '_current_command_requires_network', False) and not online:
            try:
                self.network_warning.setVisible(True)
            except Exception:
                pass
        else:
            try:
                self.network_warning.setVisible(False)
            except Exception:
                pass
    
    def handle_output(self, data):
        """Handle output from PTY - buffer for async processing"""
        try:
            text = data.decode('utf-8', errors='replace')
            
            # Sanitize wide characters to prevent pyte truncation bugs
            text = self.sanitize_wide_chars(text)
            
            # Update last activity time
            current_time = time.time()
            time_since_last = current_time - self._last_output_time
            self._last_activity_time = current_time
            
            # Detect streaming resume after stop (DISABLED - no visual markers)
            # if not self._streaming_active and time_since_last > self._streaming_stop_threshold:
            #     self._streaming_active = True
            #     self._on_streaming_resumed(time_since_last)
            
            self._last_output_time = current_time
            
            # If app is suspended (sleep/lock), buffer separately
            # The suspend buffer will be flushed when app becomes active again
            if self._app_is_suspended:
                self._buffer_on_suspend.append(text)
                # Don't start the timer - suspend buffer is flushed by app state handler
                return
            
            # Buffer output instead of processing immediately
            self._output_buffer.append(text)
            
            # Adaptive flush timing based on buffer size (for performance during heavy output)
            # If buffer is getting large (e.g., Docker logs), increase flush interval
            buffer_size = len(self._output_buffer)
            if buffer_size > 100:
                # Heavy output - reduce update frequency significantly
                flush_interval = 100  # ~10fps during heavy output
            elif buffer_size > 20:
                # Moderate output - slower updates
                flush_interval = 50  # ~20fps
            else:
                # Normal output - fast updates
                flush_interval = self._output_buffer_flush_ms  # ~60fps
            
            # Schedule flush if not already scheduled
            # Don't stop/restart as that causes race conditions
            if not self._output_buffer_timer.isActive():
                self._output_buffer_timer.start(flush_interval)
                
        except Exception as e:
            pass
    
    def _flush_output_buffer(self):
        """Process buffered output (async) - reduces UI blocking"""
        if not self._output_buffer:
            return
        
        try:
            # Combine all buffered text
            text = ''.join(self._output_buffer)
            self._output_buffer.clear()
            
            # Clean up excessive newlines that accumulate during sleep/wake cycles
            # This prevents empty line accumulation when laptop lid is closed
            if '\n\n\n' in text:
                # Replace 3+ consecutive newlines with just 2 (preserve paragraph breaks)
                text = re.sub(r'\n{3,}', '\n\n', text)
            
            # Extract directory from prompt in real-time
            # Try to detect current directory from prompt patterns
            self._extract_directory_from_prompt(text)
            
            # Check for clear screen sequences and archive before clearing
            # The 'clear' command sends \x1b[H\x1b[2J or \x1b[H\x1b[J sequences
            # We want to archive content before it gets cleared
            is_clear_command = (
                '\x1b[H\x1b[2J' in text or  # Move to home + clear entire screen
                '\x1b[H\x1b[J' in text or   # Move to home + clear from cursor to end
                '\x1b[2J' in text or        # Clear entire screen
                '\x1b[3J' in text           # Clear entire screen + scrollback
            )
            
            # Archive content before clear (only if not in alternate screen mode like vim/nano)
            # DISABLED: We now archive in execute_command() before clear is sent to PTY
            # This prevents duplicate archiving
            # if is_clear_command and not self.was_in_alternate_mode and self.screen:
            #     try:
            #         # Get total number of lines including history
            #         history_size = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
            #         total_lines = history_size + self.screen.lines
            #         
            #         # Only archive if there's meaningful content (more than just a few lines)
            #         if total_lines > 3:
            #             # Extract lines to archive
            #             lines_to_archive = self._extract_lines_for_archive(0, total_lines)
            #             
            #             if lines_to_archive:
            #                 print("[DEBUG] handle_output: Clear sequence detected, appending to archive")
            #                 # APPEND to existing history file (continuous mode)
            #                 self.history_manager.append_archive(
            #                     self.tab_id,
            #                     lines_to_archive,
            #                     row_range=f"0-{total_lines}",
            #                     command_context=f"clear_sequence: {self.last_executed_command or 'unknown'}"
            #                 )
            #     except Exception as e:
            #         # Don't let archiving errors prevent terminal from working
            #         import traceback
            #         traceback.print_exc()
            
            # Check for alternate screen escape sequences BEFORE feeding to pyte
            # This is critical because pyte corrupts the buffer when switching screens
            import copy
            entering_alternate = '\x1b[?1049h' in text or '\x1b[?47h' in text
            exiting_alternate = '\x1b[?1049l' in text or '\x1b[?47l' in text
            
            # Save state before entering alternate screen
            if entering_alternate and not self.was_in_alternate_mode:
                self.saved_screen_buffer = copy.deepcopy(self.screen.buffer)
                self.saved_screen_history = copy.deepcopy(self.screen.history)
                self.saved_cursor_pos = (self.screen.cursor.x, self.screen.cursor.y)
                # Save line numbering offset and reset it for text editors
                # This ensures line numbers start from 1 in nano/vim/etc.
                if self.canvas:
                    self.saved_cumulative_line_offset = self.canvas._cumulative_line_offset
                    self.canvas._cumulative_line_offset = 0
                    self.canvas._total_lines_count = 0
                self.was_in_alternate_mode = True
            
            # Track total lines BEFORE feeding data (to detect if new lines were actually added)
            total_lines_before = 0
            history_size_before = 0
            if self.screen:
                total_lines_before = self.screen.lines
                if hasattr(self.screen, 'history'):
                    history_size_before = len(self.screen.history.top)
                    total_lines_before += history_size_before
            
            # Track selection content BEFORE feeding new data
            # This is the ONLY reliable way to track selection when history auto-trims
            selection_content_snapshot = None
            if self.canvas and hasattr(self.canvas, 'selection_start') and self.canvas.selection_start:
                start_row, start_col = self.canvas.selection_start
                # Get the line content at selection
                line = self.canvas.get_line_at_row(start_row)
                if line:
                    line_text = ""
                    max_col = max(line.keys()) if line else 0
                    for c in range(max_col + 1):
                        if c in line:
                            char = line[c]
                            line_text += self.canvas.get_char_data(char)
                        else:
                            line_text += " "
                    selection_content_snapshot = line_text.rstrip()
            
            # Check if user is at bottom BEFORE feeding data
            # This determines if we should do real-time line-by-line scrolling
            scroll_bar = self.scroll_area.verticalScrollBar()
            scroll_max_before = scroll_bar.maximum() if scroll_bar else 0
            scroll_pos_before = scroll_bar.value() if scroll_bar else 0
            pixels_per_line = self.canvas.char_height if hasattr(self.canvas, 'char_height') else 20
            threshold = 5 * pixels_per_line
            was_at_bottom_before_feed = (scroll_max_before - scroll_pos_before) <= threshold
            should_do_realtime_scroll = (was_at_bottom_before_feed and 
                                        not self.user_has_scrolled and 
                                        not self.search_active)
            
            # Feed data to pyte stream with real-time line-by-line scrolling
            if should_do_realtime_scroll and '\n' in text:
                # Real-time scrolling: process line by line
                self._feed_with_realtime_scroll(text)
            else:
                # Normal feed without scrolling
                self.stream.feed(text)
            
            # Track how many lines were trimmed from history (for selection adjustment)
            lines_trimmed_from_history = 0
            
            # PERFORMANCE: Trim history if it exceeds the limit (critical for large outputs like Docker logs)
            # The pyte HistoryScreen doesn't automatically trim, so we need to do it manually
            if hasattr(self.screen, 'history') and hasattr(self.screen.history, 'top'):
                history_size_after = len(self.screen.history.top)
                
                # Check if buffer was at capacity and new content was added
                # When at capacity, pyte's deque auto-removes old lines from the top
                if history_size_before >= self.scrollback_lines and history_size_after >= self.scrollback_lines:
                    # Buffer is at capacity - calculate how many lines were actually added
                    # and thus how many old lines were removed
                    lines_in_text = text.count('\n')
                    if lines_in_text > 0:
                        lines_trimmed_from_history = lines_in_text
                
                if history_size_after > self.scrollback_lines:
                    # Manual trim if somehow exceeded limit
                    excess = history_size_after - self.scrollback_lines
                    lines_trimmed_from_history += excess
                    # Convert deque to list, slice it, and convert back
                    import collections
                    trimmed = list(self.screen.history.top)[excess:]
                    self.screen.history.top = collections.deque(trimmed, maxlen=self.scrollback_lines)
            
            # Restore state after exiting alternate screen
            if exiting_alternate and self.was_in_alternate_mode:
                if self.saved_screen_buffer is not None and self.saved_screen_history is not None:
                    # Restore the normal screen completely, removing all alternate screen content
                    self.screen.buffer = self.saved_screen_buffer
                    self.screen.history = self.saved_screen_history
                    if self.saved_cursor_pos:
                        self.screen.cursor.x = self.saved_cursor_pos[0]
                        self.screen.cursor.y = self.saved_cursor_pos[1]
                    # Restore line numbering offset after exiting text editor
                    # This ensures line numbers continue correctly for other operations
                    if self.canvas and hasattr(self, 'saved_cumulative_line_offset'):
                        self.canvas._cumulative_line_offset = self.saved_cumulative_line_offset
                        # Recalculate total lines count based on restored buffer
                        all_lines_count = self.screen.lines
                        if hasattr(self.screen, 'history'):
                            all_lines_count += len(self.screen.history.top)
                        self.canvas._total_lines_count = all_lines_count
                    # Clear saved state
                    self.saved_screen_buffer = None
                    self.saved_screen_history = None
                    self.saved_cursor_pos = None
                    if hasattr(self, 'saved_cumulative_line_offset'):
                        delattr(self, 'saved_cumulative_line_offset')
                self.was_in_alternate_mode = False
                # Force a full repaint
                self.canvas.resizeCanvas()
                self.canvas.update()
            
            # Check for editor start/end (for tracking purposes only)
            if 'UW PICO' in text or 'GNU nano' in text or 'VIM' in text:
                self.in_editor_mode = True
            elif self.in_editor_mode and ('(base)' in text or text.strip().endswith('%') or text.strip().endswith('$')):
                self.in_editor_mode = False
            
            # Apply file type colors by detecting extensions in the buffer - defer to avoid blocking
            QTimer.singleShot(50, self.apply_file_type_colors)
            
            # Get scrollbar state BEFORE resizeCanvas (resizeCanvas updates scrollbar)
            scroll_bar = self.scroll_area.verticalScrollBar()
            scroll_max_before_resize = scroll_bar.maximum() if scroll_bar else 0
            scroll_pos_before = scroll_bar.value() if scroll_bar else 0
            
            # Store last known max before resize (resizeCanvas might update scrollbar)
            last_known_max = getattr(self, '_last_known_scroll_max', 0)
            
            # Resize canvas to fit content (enables scrolling) - use throttled version for performance
            self._schedule_canvas_resize()
            
            # Schedule canvas update asynchronously instead of immediate update
            self._schedule_canvas_update()
            
            # Track total lines AFTER feeding data
            total_lines_after = 0
            history_size_after = 0
            if self.screen:
                total_lines_after = self.screen.lines
                if hasattr(self.screen, 'history'):
                    history_size_after = len(self.screen.history.top)
                    total_lines_after += history_size_after
            
            # Check if new lines were actually added to the terminal buffer
            new_lines_added = total_lines_after > total_lines_before
            
            # Also consider the case where buffer is at max capacity and lines were trimmed
            if lines_trimmed_from_history > 0:
                
                # Update search match positions if search is active
                if self.search_active and self.search_matches:
                    updated_matches = []
                    for row, col, length in self.search_matches:
                        new_row = row - lines_trimmed_from_history
                        if new_row >= 0:  # Only keep matches that are still visible
                            updated_matches.append((new_row, col, length))
                    
                    # Update search matches
                    old_count = len(self.search_matches)
                    self.search_matches = updated_matches
                    
                    # Update canvas search matches
                    if hasattr(self.canvas, 'search_matches'):
                        self.canvas.search_matches = self.search_matches
                        self.canvas.update()
                    
                    # Adjust current match index if matches were removed before it
                    if len(self.search_matches) > 0:
                        # Find how many matches were removed before current index
                        removed_before_current = 0
                        for row, col, length in self.search_matches[:self.current_match_index]:
                            if row < 0:
                                removed_before_current += 1
                        
                        # Adjust the index
                        self.current_match_index = max(0, self.current_match_index - removed_before_current)
                        if self.current_match_index >= len(self.search_matches):
                            self.current_match_index = max(0, len(self.search_matches) - 1)
                    else:
                        self.current_match_index = -1
                    
                    # Update match count display
                    if self.search_matches and self.search_widget:
                        self.search_widget.update_match_count(self.current_match_index + 1, len(self.search_matches))
                    
                    # Re-highlight current match at new position
                    if self.search_matches and self.current_match_index >= 0:
                        match_row, match_col, match_len = self.search_matches[self.current_match_index]
                        self._highlight_current_match()
                    
                    if old_count != len(self.search_matches):
                        pass
            
            # Check if we have a selection with content snapshot
            # Search for where that content moved to after feeding data
            if selection_content_snapshot and self.canvas:
                if hasattr(self.canvas, 'selection_start') and self.canvas.selection_start:
                    old_start_row, start_col = self.canvas.selection_start
                    old_end_row, end_col = self.canvas.selection_end if self.canvas.selection_end else (old_start_row, start_col)
                    
                    # Get all lines including history
                    all_lines = []
                    if hasattr(self.screen, 'history'):
                        all_lines.extend(list(self.screen.history.top))
                    for row_idx in range(self.screen.lines):
                        all_lines.append(self.screen.buffer[row_idx])
                    
                    # Search for the selected content near the old position
                    search_start = max(0, old_start_row - 100)  # Look above
                    search_end = min(len(all_lines), old_start_row + 50)  # Look below
                    
                    found_at_row = None
                    for new_row in range(search_start, search_end):
                        if new_row >= len(all_lines):
                            break
                        
                        line = all_lines[new_row]
                        if not line:
                            continue
                        
                        # Get line text
                        line_text = ""
                        max_col = max(line.keys()) if line else 0
                        for c in range(max_col + 1):
                            if c in line:
                                char = line[c]
                                line_text += self.canvas.get_char_data(char)
                            else:
                                line_text += " "
                        line_text = line_text.rstrip()
                        
                        # Check if this matches our selected content
                        if line_text == selection_content_snapshot:
                            found_at_row = new_row
                            break
                    
                    if found_at_row is not None and found_at_row != old_start_row:
                        # Content moved! Update selection
                        row_offset = found_at_row - old_start_row
                        
                        new_start_row = old_start_row + row_offset
                        new_end_row = old_end_row + row_offset
                        
                        self.canvas.selection_start = (new_start_row, start_col)
                        self.canvas.selection_end = (new_end_row, end_col)
                        
                        # Also adjust anchor if it exists
                        if hasattr(self.canvas, 'selection_anchor') and self.canvas.selection_anchor:
                            old_anchor_row, anchor_col = self.canvas.selection_anchor
                            self.canvas.selection_anchor = (old_anchor_row + row_offset, anchor_col)
                        
                        # Update the canvas display
                        self.canvas.update()
                        
            
            # Get scrollbar state after update
            scroll_max_after = scroll_bar.maximum() if scroll_bar else 0
            scroll_pos_after = scroll_bar.value() if scroll_bar else 0
            
            # Track if scrollbar max increased (new content arrived)
            # Check against before-resize max (resizeCanvas updates it)
            max_decreased = scroll_max_after < scroll_max_before_resize or (last_known_max > 0 and scroll_max_after < last_known_max)
            max_increased = scroll_max_after > scroll_max_before_resize or scroll_max_after > last_known_max
            
            # Calculate how much the scrollbar increased (if at all)
            pixels_per_line = self.canvas.char_height if hasattr(self.canvas, 'char_height') else 20
            scroll_increase = scroll_max_after - scroll_max_before_resize
            # Only consider it a meaningful increase if it's more than half a line
            meaningful_increase = scroll_increase > (pixels_per_line * 0.5)
            
            # Only scroll if new line data was actually added
            # If scrollbar max decreased (e.g., after 'clear' command), don't scroll
            if max_decreased:
                self._last_known_scroll_max = scroll_max_after
                # Don't trigger autoscroll when content was cleared
                should_autoscroll = False
                
                # Reset cumulative line offset when screen is cleared
                # This ensures line numbers start from 1 after a clear command
                if self.canvas and total_lines_after < total_lines_before * 0.5:
                    # Line count dropped by more than 50% - likely a screen clear
                    self.canvas._cumulative_line_offset = 0
                    self.canvas._total_lines_count = total_lines_after
            elif new_lines_added and meaningful_increase:
                # New lines were actually added AND scrollbar increased meaningfully - check if we should scroll
                self._last_known_scroll_max = scroll_max_after
                
                # Check if user WAS at bottom BEFORE new content arrived
                # We must check against the OLD scrollbar maximum (before resize), not the new one
                # Otherwise, user will appear to be "not at bottom" even though they were before the new data
                threshold = 5 * pixels_per_line
                was_at_bottom = (scroll_max_before_resize - scroll_pos_before) <= threshold
                
                # Only scroll if:
                # 1. User WAS at the bottom before new content arrived
                # 2. User hasn't manually scrolled up
                # 3. Search is not active
                # 4. Scrollbar actually increased meaningfully
                user_wants_autoscroll = not self.user_has_scrolled and not self.search_active
                should_autoscroll = was_at_bottom and user_wants_autoscroll and len(text) > 0
            else:
                # No new lines added - don't scroll
                self._last_known_scroll_max = scroll_max_after
                should_autoscroll = False
            
            # Only schedule autoscroll if we should actually autoscroll
            # This prevents unnecessary scrolls after commands like 'clear' that decrease scrollbar max
            if should_autoscroll:
                scroll_bar = self.scroll_area.verticalScrollBar()
                if scroll_bar:
                    # (no-op) scrollbar exists; keep logic explicit
                    pass

                # Set flag to trigger autoscroll after canvas resize completes
                # This ensures scrollbar maximum is updated before we try to scroll
                self._autoscroll_pending = True
            elif new_lines_added:
                pass
            
            # Ensure canvas maintains focus if this terminal widget is currently visible
            # This is crucial for input to work after interactive apps (nano/vim/pico) exit
            if self.isVisible() and not self.canvas.hasFocus():
                # Only restore focus if no other widget has actively taken it
                # Check if focus is within our terminal widget tree
                focus_widget = QApplication.focusWidget()
                if not focus_widget or focus_widget == self or self.isAncestorOf(focus_widget):
                    self.canvas.setFocus()
            
            # Check for automatic archival (throttled to avoid excessive checks)
            current_time = time.time()
            if current_time - self._last_auto_archive_check > 2.0:  # Check at most every 2 seconds
                self._last_auto_archive_check = current_time
                self._check_auto_archive()
            
            # Check for new prompt if we're waiting for one (for playback)
            if self.waiting_for_prompt:
                try:
                    # Check the current cursor line for a prompt
                    cursor_y = self.screen.cursor.y
                    
                    if cursor_y >= 0 and cursor_y < len(self.screen.buffer):
                        current_line_text = self._extract_line_text(cursor_y)
                        has_prompt = self._has_prompt(current_line_text)
                        
                        if has_prompt:
                            # New prompt detected - command finished
                            # Only emit if this is a different line than the last prompt we saw
                            # This ensures we detect when a new prompt appears after command execution
                            if self.last_prompt_line is None:
                                # First prompt detection - set baseline
                                self.last_prompt_line = cursor_y
                            elif self.last_prompt_line != cursor_y:
                                # New prompt on a different line - command finished!
                                self.last_prompt_line = cursor_y
                                self.waiting_for_prompt = False
                                
                                # Update current directory from shell after command finishes
                                # Skip directory update for commands that don't change the directory
                                # (like 'clear', 'pwd', built-in commands, etc.)
                                skip_directory_update_commands = ['clear', 'pwd']
                                should_update = True
                                if self.last_executed_command:
                                    cmd_lower = self.last_executed_command.lower().strip()
                                    # Check if command starts with any of the skip commands (handles 'clear', 'clear && ls', etc.)
                                    # Extract the first word to handle commands like 'clear && ls'
                                    first_word = cmd_lower.split()[0] if cmd_lower else ''
                                    if first_word in skip_directory_update_commands:
                                        should_update = False
                                
                                if should_update and not self.suppress_directory_updates:
                                    # Send pwd command to get current directory - defer to avoid blocking
                                    QTimer.singleShot(100, self._update_current_directory)
                                
                                # Emit both signals when prompt is ready (command has finished)
                                try:
                                    self.prompt_ready.emit()
                                    self.command_finished.emit(0)  # Emit with exit code 0 (we don't track actual exit codes in PTY mode)
                                except RuntimeError:
                                    # Widget deleted, skip signal emission
                                    pass
                except Exception as e:
                    import traceback
                    traceback.print_exc()
            
            # After receiving output, sync command buffer from screen if tab was recently pressed
            # This ensures we capture tab-completed commands
            if self.last_tab_press_time > 0:
                time_since_tab = time.time() - self.last_tab_press_time
                if time_since_tab < 0.5:  # Within 500ms of tab press
                    # Sync buffer from screen to capture completed command
                    screen_cmd = self.get_current_command_line().strip()
                    if screen_cmd and len(screen_cmd) > len(self.current_command_buffer):
                        # Screen has more complete command (tab completed)
                        self.current_command_buffer = screen_cmd
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _schedule_canvas_update(self):
        """Schedule canvas update asynchronously to prevent blocking"""
        if not self._canvas_update_pending:
            self._canvas_update_pending = True
            self._canvas_update_timer.start(8)  # ~120fps max update rate
    
    def _do_canvas_update(self):
        """Perform the actual canvas update"""
        self._canvas_update_pending = False
        self.canvas.update()
    
    def _feed_with_realtime_scroll(self, text):
        """Feed text to pyte stream with real-time line-by-line scrolling
        
        This processes the text character by character, scrolling incrementally
        whenever a newline is encountered, creating smooth line-by-line scrolling.
        
        Args:
            text: The text to feed to the stream
        """
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            # No scrollbar, just feed normally
            self.stream.feed(text)
            return
        
        # Set flag to indicate we're doing programmatic scrolling
        # This prevents _on_scrollbar_value_changed from marking as user scroll
        self._doing_realtime_scroll = True
        
        # Count newlines for debug
        newline_count = text.count('\n')
        
        # Track initial scroll position to detect manual intervention
        initial_scroll_pos = scroll_bar.value()
        initial_scroll_max = scroll_bar.maximum()
        
        # Process text character by character
        buffer = ""
        lines_scrolled = 0
        lines_processed = 0
        user_interrupted = False
        
        for i, char in enumerate(text):
            buffer += char
            
            # When we hit a newline, feed the buffer and scroll
            if char == '\n':
                lines_processed += 1
                
                # Feed this line to the stream
                self.stream.feed(buffer)
                buffer = ""
                
                # Only resize and scroll every few lines for better performance
                # and to avoid triggering false positives on scroll detection
                if lines_processed % 3 == 0 or lines_processed == newline_count:
                    # Resize canvas to account for new lines
                    self.canvas.resizeCanvas()
                    
                    # Force immediate scrollbar update
                    QApplication.processEvents()
                    
                    # Check if user manually scrolled during processing
                    # Only check if we've scrolled at least once
                    if lines_scrolled > 0:
                        current_value = scroll_bar.value()
                        expected_value = scroll_bar.maximum()
                        
                        # User scrolled if they're not at the bottom anymore
                        # Use a more lenient threshold since we're batch-processing
                        pixels_per_line = self.canvas.char_height if hasattr(self.canvas, 'char_height') else 20
                        threshold = 10 * pixels_per_line  # More lenient: 10 lines
                        
                        if expected_value > 0 and (expected_value - current_value) > threshold:
                            self.user_has_scrolled = True
                            user_interrupted = True
                            # Continue feeding data without scrolling
                    
                    # Only scroll if user hasn't interrupted
                    if not user_interrupted:
                        # Scroll to bottom
                        new_max = scroll_bar.maximum()
                        # Don't scroll if range is too small (content fits in viewport)
                        if new_max > 0 and new_max >= 50:
                            scroll_bar.setValue(new_max)
                            self.last_autoscroll_position = new_max
                            lines_scrolled += lines_processed
                            
                            # Force viewport refresh for smooth visual update
                            if self.scroll_area and self.scroll_area.viewport():
                                self.scroll_area.viewport().update()
                    
                    lines_processed = 0  # Reset counter for next batch
        
        # Feed any remaining characters (partial line)
        if buffer:
            self.stream.feed(buffer)
        
        # Clear the flag - we're done with programmatic scrolling
        self._doing_realtime_scroll = False
    
    def _schedule_canvas_resize(self):
        """Schedule canvas resize asynchronously to prevent blocking during heavy output"""
        if not self._canvas_resize_pending:
            self._canvas_resize_pending = True
            self._canvas_resize_timer.start(50)  # Throttle resizes more aggressively (20fps max)
    
    def _do_canvas_resize(self):
        """Perform the actual canvas resize"""
        self._canvas_resize_pending = False
        self.canvas.resizeCanvas()
        
        # Check if autoscroll is pending after resize
        if getattr(self, '_autoscroll_pending', False):
            self._autoscroll_pending = False
            # Use a small delay to ensure scrollbar is fully updated
            QTimer.singleShot(10, lambda: self._auto_scroll_to_bottom(True))
    
    def _extract_and_record_command(self):
        """Extract command from screen and record it (called after delay for tab completion)"""
        
        # Extract the final executable command from the screen
        # After Enter is sent, cursor is on new line, so command is on previous line
        if not self.screen:
            screen_command = ""
        else:
            cursor_y = self.screen.cursor.y
            
            # Try current line first (in case cursor hasn't moved yet)
            screen_command = self._extract_command_from_line(cursor_y, include_wrapped=True).strip()
            
            # If empty, try previous line (where command likely is after Enter)
            if not screen_command and cursor_y > 0:
                screen_command = self._extract_command_from_line(cursor_y - 1, include_wrapped=True).strip()
        
        # Fallback to buffer only if screen extraction failed
        buffer_command = self.current_command_buffer.strip()
        
        # Screen is authoritative - it contains the command that will be executed
        if screen_command:
            command = screen_command
        elif buffer_command:
            # Screen extraction failed, use buffer as fallback
            command = buffer_command
        else:
            command = ""

        # Emit command if we have something
        if command:
            try:
                self.command_executed.emit(command)
            except RuntimeError:
                # Widget deleted, skip signal emission
                pass

        # Reset command buffer for next command
        self.current_command_buffer = ""
        self.last_tab_press_time = 0.0
        self.last_paste_time = 0.0
        self.pending_enter = False
    
    def _has_prompt(self, line_text):
        """Check if a line contains a prompt pattern"""
        if not line_text or not line_text.strip():
            return False
        
        # Check for various prompt patterns
        prompt_patterns = [
            r'\[.*?\][$%>#]',  # [user@host dir]$
            r'\w+@[\w\-]+:.*?[$%>#]',  # user@host:path$
            r'\([^)]+\)\s+\w+@[\w\-]+.*?[$%>#]',  # (env) user@host path$
            r'[$%>#]',  # Simple $ % > #
        ]
        
        for pattern in prompt_patterns:
            if re.search(pattern, line_text):
                return True
        
        # Also check for prompt indicators at start of line
        for indicator in ['$ ', '% ', '> ', '# ']:
            if indicator in line_text:
                return True
        
        return False
    
    def _extract_line_text(self, line_y):
        """Extract raw text from a line (without prompt parsing)"""
        if not self.screen or line_y < 0 or line_y >= len(self.screen.buffer):
            return ""
        
        # screen.buffer[y] is a dictionary: {column_index: Char_object}
        line = self.screen.buffer[line_y]
        line_text = ""
        
        # Iterate through columns (0 to screen.columns - 1)
        for col in range(self.screen.columns):
            if col in line:
                char = line[col]
                # Extract character data using the same method as canvas
                if isinstance(char, str):
                    line_text += char
                elif hasattr(char, 'data'):
                    line_text += char.data if char.data else ' '
                else:
                    line_text += ' '
            else:
                # No character at this column, add space or skip
                line_text += ' '
        
        return line_text.rstrip()
    
    def _extract_command_from_line(self, line_y, include_wrapped=False):
        """Extract command from a specific line number (helper method)"""
        if not self.screen:
            return ""
        if line_y < 0 or line_y >= len(self.screen.buffer):
            return ""
        
        # Get raw line text
        line_text = self._extract_line_text(line_y)
        
        # Try multiple prompt patterns
        # 1. Match complex prompts like: [user@host dir]$ command
        bracket_prompt = re.search(r'\[.*?\][$%>#]\s*(.*)', line_text)
        if bracket_prompt:
            command = bracket_prompt.group(1).strip()
            # Check for wrapped continuation on next line
            if include_wrapped:
                command = self._check_wrapped_continuation(line_y, command)
            return command
        
        # 2. Match user@host:path$ command (bash/zsh style)
        userhost_prompt = re.search(r'\w+@[\w\-]+:.*?[$%>#]\s*(.*)', line_text)
        if userhost_prompt:
            command = userhost_prompt.group(1).strip()
            # Check for wrapped continuation on next line
            if include_wrapped:
                command = self._check_wrapped_continuation(line_y, command)
            return command
        
        # 3. Match (env) user@host path $ command (conda/virtualenv style)
        env_prompt = re.search(r'\([^)]+\)\s+\w+@[\w\-]+.*?[$%>#]\s*(.*)', line_text)
        if env_prompt:
            command = env_prompt.group(1).strip()
            # Check for wrapped continuation on next line
            if include_wrapped:
                command = self._check_wrapped_continuation(line_y, command)
            return command
        
        # 4. Simple prompt with just $ % > # 
        simple_prompt = re.search(r'[$%>#]\s*(.*)', line_text)
        if simple_prompt:
            command = simple_prompt.group(1).strip()
            # Check for wrapped continuation on next line
            if include_wrapped:
                command = self._check_wrapped_continuation(line_y, command)
            return command
        
        # 5. Fallback: split on common prompt indicators
        for indicator in ['$ ', '% ', '> ', '# ']:
            if indicator in line_text:
                parts = line_text.rsplit(indicator, 1)
                if len(parts) > 1:
                    command = parts[1].strip()
                    # Check for wrapped continuation on next line
                    if include_wrapped:
                        command = self._check_wrapped_continuation(line_y, command)
                    return command
        
        return ""
    
    def _check_wrapped_continuation(self, line_y, command):
        """Check if command continues on next line(s) (wrapped command)"""
        # Keep checking next lines until we find a prompt, empty line, or end of buffer
        full_command = command
        check_y = line_y + 1
        
        while check_y < len(self.screen.buffer):
            next_line_text = self._extract_line_text(check_y)
            
            # Stop if line is empty
            if not next_line_text.strip():
                break
            
            # Stop if line has a prompt (new command started)
            # Check for prompt patterns
            has_prompt = (
                re.match(r'^\s*\[.*?\][$%>#]', next_line_text) or
                re.match(r'^\s*\w+@[\w\-]+:.*?[$%>#]', next_line_text) or
                re.match(r'^\s*\([^)]+\)\s+\w+@', next_line_text) or
                re.match(r'^\s*[$%>#]', next_line_text) or
                any(next_line_text.strip().startswith(ind) for ind in ['$ ', '% ', '> ', '# '])
            )
            
            if has_prompt:
                break
            
            # This line is likely a continuation
            continuation = next_line_text.strip()
            if continuation:
                # Append continuation to command
                full_command = full_command + continuation
                check_y += 1
            else:
                # Empty line, stop
                break
        
        
        return full_command
    
    def get_current_command_line(self):
        """Extract the current command line from the terminal screen (without prompt)"""
        try:
            if not self.screen:
                return ""
            
            # CRITICAL: Extract current directory from prompt BEFORE extracting command
            # This ensures suggestions use the correct directory
            # Wrap in try-except to ensure it doesn't break command extraction
            try:
                self._extract_directory_from_current_line()
            except Exception:
                pass
            
            # Get the current cursor position
            cursor_y = self.screen.cursor.y
            cursor_x = self.screen.cursor.x
            
            # When Enter is pressed, cursor moves to the next line
            # We need to look at the previous line to get the command
            target_y = cursor_y
            
            # If cursor is at the beginning of a line (x=0 or very small x), 
            # the command is likely on the previous line
            if cursor_x <= 1 and cursor_y > 0:
                target_y = cursor_y - 1
            
            # Get the line at target position
            if target_y < len(self.screen.buffer):
                # Use helper method to extract text from line
                line_text = self._extract_command_from_line(target_y)
                
                # If empty and we're looking at cursor line, try previous line
                if not line_text and target_y == cursor_y and cursor_y > 0:
                    prev_text = self._extract_command_from_line(cursor_y - 1)
                    if prev_text:
                        line_text = prev_text
                        target_y = cursor_y - 1
                
                
                # Extract command from this line only (use _extract_command_from_line)
                # This method already handles prompt detection and extraction correctly
                command = self._extract_command_from_line(target_y, include_wrapped=False)
                if command:
                    return command
                
                return ""
            return ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            return ""
    
    def apply_file_type_colors(self):
        """Apply colors to files based on their extensions by modifying the screen buffer"""
        try:
            # Skip if feature is disabled
            if not self.ENABLE_QT_FILE_COLORING:
                return
            
            import re
            import os
            
            # Skip if screen is empty or just initialized
            if not hasattr(self, 'screen') or not self.screen:
                return
            
            # Define file type to color mapping
            file_colors = {
                # Archives - red
                'archives': ('red', ['.tar', '.tgz', '.zip', '.gz', '.bz2', '.7z', '.rar', 
                                     '.xz', '.deb', '.rpm', '.jar']),
                # Images - magenta
                'images': ('magenta', ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', 
                                       '.webp', '.ico', '.tiff', '.tif']),
                # Videos - magenta (darker)
                'videos': ('magenta', ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', 
                                       '.webm', '.mpeg', '.mpg']),
                # Audio - cyan
                'audio': ('cyan', ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', 
                                   '.opus', '.mid', '.midi']),
                # Documents - yellow
                'docs': ('yellow', ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', 
                                    '.pptx', '.txt', '.md', '.rtf']),
                # Source code - white (will use bright variant)
                'code': ('white', ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', 
                                   '.cpp', '.go', '.rs', '.rb', '.php', '.sh', '.sql']),
                # Config files - cyan
                'config': ('cyan', ['.json', '.yaml', '.yml', '.toml', '.xml', '.conf', 
                                    '.ini', '.env']),
                # Log files - bright_black (gray)
                'logs': ('bright_black', ['.log']),
            }
            
            # Build extension to color map
            ext_to_color = {}
            for category, (color, extensions) in file_colors.items():
                for ext in extensions:
                    ext_to_color[ext.lower()] = color
            
            # Special files (case-insensitive match)
            special_files = {
                'makefile': 'green',
                'dockerfile': 'green',
                'readme': 'green',
                'license': 'green',
            }
            
            # Scan each visible line in the screen buffer
            for row_idx in range(self.screen.lines):
                line = self.screen.buffer[row_idx]
                
                # Extract text from this line to find words
                line_text = ""
                for col_idx in range(self.screen.columns):
                    if col_idx in line:
                        line_text += line[col_idx].data
                    else:
                        line_text += " "
                
                # Find potential filenames with better handling of spaces
                # Use a smarter approach: look for patterns that indicate filenames
                # Only split on double spaces or tabs (typical ls output formatting)
                words = []
                current_word = ""
                word_start = 0
                consecutive_spaces = 0
                
                for i, char in enumerate(line_text):
                    if char in ['\t', '\n']:
                        # Always break on tabs and newlines
                        if current_word.strip():
                            words.append((current_word.strip(), word_start, i))
                            current_word = ""
                        consecutive_spaces = 0
                    elif char == ' ':
                        consecutive_spaces += 1
                        # Only break on multiple consecutive spaces (typical ls column separator)
                        if consecutive_spaces >= 2:
                            if current_word.strip():
                                words.append((current_word.strip(), word_start, i - consecutive_spaces + 1))
                                current_word = ""
                        else:
                            # Single space - could be part of filename
                            current_word += char
                    else:
                        consecutive_spaces = 0
                        if not current_word or current_word.isspace():
                            word_start = i
                            current_word = char
                        else:
                            current_word += char
                
                if current_word.strip():
                    words.append((current_word.strip(), word_start, len(line_text)))
                
                # Check each word for file extensions or special names
                for word, start_col, end_col in words:
                    word_lower = word.lower()
                    color_to_apply = None
                    
                    # Skip if word is too short or looks like a path with many segments
                    if len(word) < 2 or word.count('/') > 3:
                        continue
                    
                    # Skip if it looks like a URL, email, or command flag
                    if '://' in word or '@' in word or word.startswith('-'):
                        continue
                    
                    # Skip words that are too long (probably not filenames)
                    if len(word) > 100:
                        continue
                    
                    # Check special files first (only filename, not full path)
                    filename_only = word.split('/')[-1] if '/' in word else word
                    filename_lower = filename_only.lower()
                    
                    for special_name, color in special_files.items():
                        if filename_lower.startswith(special_name):
                            color_to_apply = color
                            break
                    
                    # Check file extensions
                    if not color_to_apply and '.' in filename_only:
                        # Get extension (including the dot)
                        parts = filename_only.rsplit('.', 1)
                        if len(parts) == 2:
                            ext = '.' + parts[1].lower()
                            # Only color if extension is recognized
                            if ext in ext_to_color:
                                color_to_apply = ext_to_color[ext]
                    
                    # Apply color if we found a match
                    if color_to_apply and color_to_apply != 'default':
                        # Color the entire word
                        for col_idx in range(start_col, min(end_col, self.screen.columns)):
                            if col_idx in line:
                                char = line[col_idx]
                                # Only colorize if it's currently default color (not already colored by shell)
                                # Don't override blue (directories), green (executables), cyan (symlinks)
                                if char.fg in ['default', 'white'] and not char.bold:
                                    # Create new Char with updated color
                                    from pyte.screens import Char
                                    line[col_idx] = Char(
                                        data=char.data,
                                        fg=color_to_apply,
                                        bg=char.bg,
                                        bold=True,  # Make file types bold
                                        italics=char.italics,
                                        underscore=char.underscore,
                                        strikethrough=char.strikethrough,
                                        reverse=char.reverse,
                                        blink=char.blink
                                    )
        
        except Exception:
            # Don't crash if color enhancement fails
            pass
    
    def _update_suggestions(self):
        """Update suggestions based on current command"""
        if not self.suggestion_widget or not self.screen:
            return
        
        # Get current command line from screen
        current_line = self.get_current_command_line()
        
        if not current_line or self.in_editor_mode:
            # Hide suggestions if no command or in editor
            self._hide_suggestions()
            return
        
        # Get suggestion preferences
        from core.preferences_manager import PreferencesManager
        prefs_manager = PreferencesManager()
        enable_files_folders = prefs_manager.get('terminal', 'suggestions_files_folders', True)
        enable_commands = prefs_manager.get('terminal', 'suggestions_commands', False)
        
        # Parse command to determine what to suggest
        parsed = self.suggestion_manager.parse_command(current_line)
        
        suggestions = []
        if parsed['type'] == 'command':
            # For commands, check if we should also show file suggestions
            # Only if prefix doesn't look like a command (no path chars)
            prefix = parsed['prefix']
            if '/' in prefix or prefix.startswith('~') or prefix.startswith('./') or prefix.startswith('../'):
                # Looks like a path, prioritize files
                # Use the actual current directory from the shell
                actual_dir = self.current_directory
                if enable_files_folders:
                    file_suggestions = self.suggestion_manager.get_file_suggestions(prefix, actual_dir)
                    suggestions.extend(file_suggestions)
                if enable_commands:
                    command_suggestions = self.suggestion_manager.get_command_suggestions(prefix)
                    suggestions.extend(command_suggestions)
            else:
                # Get suggestions based on preferences
                # Use the actual current directory from the shell
                actual_dir = self.current_directory
                if enable_files_folders:
                    file_suggestions = self.suggestion_manager.get_file_suggestions(prefix, actual_dir)
                    suggestions.extend(file_suggestions)
                if enable_commands:
                    command_suggestions = self.suggestion_manager.get_command_suggestions(prefix)
                    suggestions.extend(command_suggestions)
        elif parsed['type'] == 'file':
            # Suggest files/folders (prioritized)
            # Use the actual current directory from the shell
            actual_dir = self.current_directory
            if enable_files_folders:
                suggestions = self.suggestion_manager.get_file_suggestions(parsed['prefix'], actual_dir)
            # If no files found or files disabled, also check commands as fallback
            if not suggestions and enable_commands:
                suggestions = self.suggestion_manager.get_command_suggestions(parsed['prefix'])
        
        # Remove duplicates (same text) while preserving order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            text = s.get('text', '')
            if text and text not in seen:
                seen.add(text)
                unique_suggestions.append(s)
        
        # Sort: folders first, then files, then commands, all alphabetically
        unique_suggestions.sort(key=lambda x: (
            0 if x.get('type') == 'folder' else (1 if x.get('type') == 'file' else 2),
            x.get('text', '').lower()
        ))
        
        suggestions = unique_suggestions[:20]  # Limit to 20
        
        
        if suggestions:
            self.suggestion_widget.set_suggestions(suggestions, parsed['prefix'])
            
            # Get cursor position to show suggestions near cursor
            cursor = self.screen.cursor
            if cursor:
                # Calculate position on canvas
                line_num_offset = 0
                if self.canvas.show_line_numbers:
                    line_num_offset = self.canvas.line_number_width * self.canvas.char_width
                
                # Calculate cursor position (accounting for scroll)
                history_offset = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
                cx = line_num_offset + cursor.x * self.canvas.char_width + 10
                cy = (history_offset + cursor.y) * self.canvas.char_height + 10 + self.canvas.char_height
                
                
                # Convert to global coordinates
                canvas_pos = self.canvas.mapToGlobal(QPoint(cx, cy))
                widget_pos = self.mapFromGlobal(canvas_pos)
                
                
                # Show suggestions below cursor
                self.suggestion_widget.show_at_position(widget_pos)
                self.showing_suggestions = True
                
                
                # CRITICAL: Ensure canvas ALWAYS has focus - do this repeatedly to be sure
                self.canvas.setFocus()
                QTimer.singleShot(0, lambda: self.canvas.setFocus())
                QTimer.singleShot(50, lambda: self.canvas.setFocus())
                QTimer.singleShot(100, lambda: self.canvas.setFocus())
        else:
            self._hide_suggestions()
        
    
    def _show_suggestions(self):
        """Show suggestions if available"""
        if self.suggestion_widget:
            self._update_suggestions()
    
    def _hide_suggestions(self):
        """Hide suggestions"""
        if self.suggestion_widget:
            self.suggestion_widget.hide()
        self.showing_suggestions = False
    
    def _on_suggestion_selected(self, text):
        """Handle suggestion selection"""
        # Hide suggestions first
        self._hide_suggestions()
        
        # Get current command line to find what needs to be replaced
        current_line = self.get_current_command_line()
        parsed = self.suggestion_manager.parse_command(current_line)
        
        # Calculate what to replace
        prefix = parsed['prefix']
        
        # Escape the text if it contains spaces or special characters
        escaped_text = self._escape_path_for_shell(text)
        
        if parsed['type'] == 'command':
            # Replace the command
            if prefix:
                # Delete the prefix and insert the suggestion
                for _ in range(len(prefix)):
                    self.write_to_pty('\x08')  # Backspace
                self.write_to_pty(escaped_text)
            else:
                # Just insert the suggestion
                self.write_to_pty(escaped_text)
        elif parsed['type'] == 'file':
            # Replace the file/folder path
            if prefix:
                # Delete the prefix and insert the suggestion
                for _ in range(len(prefix)):
                    self.write_to_pty('\x08')  # Backspace
                self.write_to_pty(escaped_text)
            else:
                # Just insert the suggestion
                self.write_to_pty(escaped_text)
        
        # Update buffer (use original text for buffer, escaped for PTY)
        if prefix:
            if self.current_command_buffer.endswith(prefix):
                self.current_command_buffer = self.current_command_buffer[:-len(prefix)] + text
            else:
                self.current_command_buffer += text
        else:
            self.current_command_buffer += text
    
    def _escape_path_for_shell(self, path):
        """Escape a file/folder path for shell execution
        
        Escapes spaces and special characters in filenames/foldernames
        so they can be safely used in shell commands.
        """
        # If path contains spaces or special shell characters, escape it
        if ' ' in path or any(char in path for char in ['(', ')', '[', ']', '{', '}', '*', '?', '&', '|', '<', '>', ';', '$', '`', '"', "'", '\\']):
            # Use backslash escaping for spaces and special chars
            # Escape: space, $, `, ", ', \, and other shell special chars
            escaped = ''
            for char in path:
                if char == ' ':
                    escaped += '\\ '
                elif char in ['$', '`', '"', "'", '\\']:
                    escaped += '\\' + char
                elif char in ['(', ')', '[', ']', '{', '}', '*', '?', '&', '|', '<', '>', ';']:
                    escaped += '\\' + char
                else:
                    escaped += char
            return escaped
        return path
    
    def _on_suggestion_dismissed(self):
        """Handle suggestion dismissal"""
        self._hide_suggestions()
        # Return focus to canvas
        self.canvas.setFocus()
    
    def set_suppress_directory_updates(self, suppress):
        """Set flag to suppress directory updates (for auto session playback)"""
        self.suppress_directory_updates = suppress
    
    def _update_current_directory(self):
        """Update current directory by asking the shell"""
        # Send pwd command in background to get current directory
        # We'll extract it from the output
        try:
            # Get the working directory from the shell by sending pwd
            # This is done asynchronously - we'll parse it from the output
            self.write_to_pty('pwd\n')
            
            # Use a timer to check for pwd output and update directory
            QTimer.singleShot(200, self._parse_pwd_output)
        except Exception as e:
            pass
    
    def _extract_directory_from_current_line(self):
        """Extract current directory from the current prompt line on screen"""
        try:
            if not self.screen:
                return
            
            cursor_y = self.screen.cursor.y
            
            # Check the current line and a few previous lines for prompt
            for check_line in range(cursor_y, max(-1, cursor_y - 3), -1):
                if check_line < 0:
                    break
                
                try:
                    line_text = self._extract_line_text(check_line)
                    if not line_text:
                        continue
                    
                    # Look for prompt patterns with directory
                    import re
                    # Pattern 1: (base) user@host Documents % or [(base) user@host dir]$
                    match = re.search(r'\[?\([^)]+\)\s+\w+@[\w\-]+\s+([^\s%$\]]+)\]?\s*[%$]', line_text)
                    if match:
                        dir_name = match.group(1).strip()
                        # Strip any trailing brackets that might have been captured
                        dir_name = dir_name.rstrip(']')
                        new_dir = self._resolve_directory_name(dir_name)
                        if new_dir:
                            # Always update, even if same (in case it was wrong before)
                            self.current_directory = new_dir
                            self.suggestion_manager.set_current_directory(new_dir)
                            return
                    
                    # Pattern 2: user@host Documents % (without env)
                    # Also handle prompts with brackets: [user@host dir]$
                    match = re.search(r'\[?\w+@[\w\-]+\s+([^\s%$\]]+)\]?\s*[%$]', line_text)
                    if match:
                        dir_name = match.group(1).strip()
                        # Strip any trailing brackets that might have been captured
                        dir_name = dir_name.rstrip(']')
                        if dir_name != '~' and dir_name != '%' and dir_name != '$':
                            new_dir = self._resolve_directory_name(dir_name)
                            if new_dir:
                                # Always update, even if same (in case it was wrong before)
                                self.current_directory = new_dir
                                self.suggestion_manager.set_current_directory(new_dir)
                                return
                except Exception as line_error:
                    continue
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _resolve_directory_name(self, dir_name):
        """Resolve a directory name to full path"""
        try:
            if not dir_name or dir_name in ['%', '$', '~']:
                return None
            
            # Strip any trailing brackets that might have been captured
            dir_name = dir_name.rstrip(']')
            
            
            # If it's ~, use home directory
            if dir_name == '~':
                return os.path.expanduser('~')
            elif dir_name.startswith('~'):
                return os.path.expanduser(dir_name)
            
            # If it's absolute, use as-is
            if os.path.isabs(dir_name):
                if os.path.isdir(dir_name):
                    return dir_name
                return None
            
            # IMPORTANT: First check if it's a subdirectory of current directory
            # This handles cases where prompt shows just the directory name (like 'sabya')
            # when you're actually IN a subdirectory
            potential = os.path.join(self.current_directory, dir_name)
            if os.path.isdir(potential):
                return potential
            
            # Try in current directory's parent
            parent_dir = os.path.dirname(self.current_directory) if self.current_directory != '/' else '/'
            potential = os.path.join(parent_dir, dir_name)
            if os.path.isdir(potential):
                return potential
            
            # Try in home directory
            home = os.path.expanduser('~')
            potential = os.path.join(home, dir_name)
            if os.path.isdir(potential):
                return potential
            
            # Try in common parent directories
            # If we're in ~/Documents, try ~/
            if self.current_directory.startswith(home):
                # Try parent directories
                current = self.current_directory
                while current != home and current != '/':
                    parent = os.path.dirname(current)
                    potential = os.path.join(parent, dir_name)
                    if os.path.isdir(potential):
                        return potential
                    current = parent
            
            return None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_directory_from_prompt(self, text):
        """Extract current directory from prompt in real-time output"""
        try:
            import re
            # Look for prompt patterns that contain directory information
            # Pattern: (base) user@host dir % or (base) user@host dir$
            
            # Try to match directory from prompt patterns
            # Handle prompts with brackets: [user@host dir]$ or [(env) user@host dir]$
            prompt_patterns = [
                r'\[?\([^)]+\)\s+\w+@[\w\-]+\s+([^\s%$\]]+)\]?\s*[%$]',  # (env) user@host dir % or [(env) user@host dir]$
                r'\[?\w+@[\w\-]+\s+([^\s%$\]]+)\]?\s*[%$]',  # user@host dir % or [user@host dir]$
            ]
            
            for pattern in prompt_patterns:
                match = re.search(pattern, text)
                if match:
                    dir_name = match.group(1).strip()
                    # Strip any trailing brackets that might have been captured
                    dir_name = dir_name.rstrip(']')
                    if dir_name and dir_name not in ['%', '$', '~']:
                        new_dir = self._resolve_directory_name(dir_name)
                        if new_dir and os.path.isdir(new_dir) and new_dir != self.current_directory:
                            self.current_directory = new_dir
                            self.suggestion_manager.set_current_directory(new_dir)
                            return
        except Exception:
            pass  # Don't crash if extraction fails
    
    def _parse_pwd_output(self):
        """Parse pwd output from the terminal screen to update current directory"""
        try:
            if not self.screen:
                return
            
            # Look at recent output to find pwd result
            # Check the last few lines for a path
            cursor_y = self.screen.cursor.y
            history_offset = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
            
            # Check current line and previous lines for pwd output (more thoroughly)
            # Start from cursor and go backwards
            found_path = None
            for check_line in range(cursor_y, max(-1, cursor_y - 10), -1):
                if check_line < 0:
                    break
                    
                line_text = self._extract_line_text(check_line)
                # Look for a path that looks like output from pwd
                # pwd output is typically just a path, possibly with newline or prompt
                line_text = line_text.strip()
                
                # Remove any prompt patterns
                # Try to extract just the path from the line
                import re
                # Look for paths in the line (absolute paths or ~ paths)
                path_pattern = r'(~?/?[\w/._-]+)'
                matches = re.findall(path_pattern, line_text)
                
                for match in reversed(matches):  # Check from end of line
                    potential_path = match.strip()
                    # Check if this looks like a directory path
                    if potential_path and (os.path.isabs(potential_path) or potential_path.startswith('~')):
                        # This might be pwd output - check if it's a valid directory
                        if potential_path.startswith('~'):
                            expanded = os.path.expanduser(potential_path)
                        else:
                            expanded = potential_path
                        
                        if os.path.isdir(expanded):
                            found_path = expanded
                            break
                
                if found_path:
                    break
            
            if found_path:
                # Update current directory
                self.current_directory = found_path
                self.suggestion_manager.set_current_directory(found_path)
        except Exception as e:
            pass
    
    def handle_key_press(self, event: QKeyEvent):
        """Handle key presses and send to PTY"""
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()
        
        # CRITICAL: Ensure canvas has focus - suggestion widget must not steal it
        if not self.canvas.hasFocus():
            self.canvas.setFocus()
        
        
        # Get platform information
        platform_mgr = get_platform_manager()
        is_macos = platform_mgr.is_macos
        is_windows = platform_mgr.is_windows
        is_linux = platform_mgr.is_linux
        
        
        # Check modifier keys
        has_meta = bool(modifiers & Qt.MetaModifier)  # Cmd on Mac (but Qt is buggy on macOS)
        has_ctrl = bool(modifiers & Qt.ControlModifier)
        has_shift = bool(modifiers & Qt.ShiftModifier)
        has_alt = bool(modifiers & Qt.AltModifier)
        
        # On macOS, use native modifiers to correctly detect Cmd vs Ctrl
        # Qt incorrectly reports Cmd as ControlModifier on macOS
        has_native_cmd = False
        has_native_ctrl = False
        if is_macos and hasattr(event, 'nativeModifiers'):
            native_mods = event.nativeModifiers()
            # NSEventModifierFlagCommand = 1 << 20 = 1048576
            has_native_cmd = bool(native_mods & (1 << 20))
            # NSEventModifierFlagControl = 1 << 18 = 262144  
            has_native_ctrl = bool(native_mods & (1 << 18))
        
        # Reset last_modifier_key when no modifiers are active
        if not has_native_cmd and not has_native_ctrl:
            self.last_modifier_key = None
        
        # Determine if this is a Cmd or Ctrl shortcut
        # On macOS, use native modifiers for accurate detection
        # On other platforms, use Qt modifiers
        
        if is_macos:
            # Use native modifiers for accurate Cmd vs Ctrl detection on macOS
            has_cmd = has_native_cmd
            is_ctrl_shortcut = has_native_ctrl
        else:
            has_cmd = has_meta
            is_ctrl_shortcut = has_ctrl
        
        
        # DEBUG: Print key combinations for Cmd+A
        
        # ===== NAVIGATION SHORTCUTS (Jump to Bottom) =====
        
        # Cmd+End (macOS) or Ctrl+End (other platforms): Jump to bottom to see prompt
        if ((is_macos and has_cmd and key == Qt.Key_End) or 
            (not is_macos and has_ctrl and key == Qt.Key_End)):
            self.force_scroll_to_bottom()
            event.accept()
            return
        
        # Also support Cmd+Down or Ctrl+Down as alternative
        if ((is_macos and has_cmd and key == Qt.Key_Down) or 
            (not is_macos and has_ctrl and key == Qt.Key_Down)):
            self.force_scroll_to_bottom()
            event.accept()
            return
        
        # ===== PLATFORM-SPECIFIC GUI SHORTCUTS (Copy/Paste/Select All) =====
        
        # macOS: Use Cmd for GUI operations (check both Meta and Ctrl due to mapping issues)
        if is_macos and has_cmd and not has_shift and not has_alt:
            if key == Qt.Key_C:
                # Cmd+C: Copy
                if self.canvas.selection_start and self.canvas.selection_end:
                    selected_text = self.canvas.get_selected_text()
                    if selected_text:
                        QApplication.clipboard().setText(selected_text)
                event.accept()
                return
            elif key == Qt.Key_V:
                # Cmd+V: Paste
                clipboard_text = QApplication.clipboard().text()
                if clipboard_text:
                    self.write_to_pty(clipboard_text)
                event.accept()
                return
            elif key == Qt.Key_A:
                # Cmd+A: Select All
                self.canvas.select_all()
                event.accept()
                return
            elif key == Qt.Key_X:
                # Cmd+X: Cut
                if self.canvas.selection_start and self.canvas.selection_end:
                    selected_text = self.canvas.get_selected_text()
                    if selected_text:
                        QApplication.clipboard().setText(selected_text)
                event.accept()
                return
            elif key == Qt.Key_K:
                # Cmd+K: Clear screen (like macOS Terminal)
                self.clear()  # Use clear method to archive before clearing
                event.accept()
                return
            elif key == Qt.Key_F:
                # Cmd+F: Open search
                self.show_search()
                event.accept()
                return
        
        # Windows/Linux: Use Ctrl for copy/paste ONLY when text is selected
        # Otherwise, pass ALL Ctrl shortcuts to terminal (for nano, vim, etc.)
        if not is_macos and is_ctrl_shortcut and not has_shift and not has_alt:
            if key == Qt.Key_C:
                # Ctrl+C: Copy if selection exists, otherwise send interrupt (SIGINT)
                if self.canvas.selection_start and self.canvas.selection_end:
                    selected_text = self.canvas.get_selected_text()
                    if selected_text:
                        QApplication.clipboard().setText(selected_text)
                    return
                else:
                    # No selection: send interrupt signal to terminal
                    self.write_to_pty('\x03')
                    return
            elif key == Qt.Key_V:
                # Ctrl+V: Paste (if no interactive app needs it)
                # Check if text is selected - if so, copy first
                clipboard_text = QApplication.clipboard().text()
                if clipboard_text:
                    # Track paste time for command extraction priority
                    self.last_paste_time = time.time()
                    # Add pasted text to command buffer
                    self.current_command_buffer += clipboard_text
                    self.write_to_pty(clipboard_text)
                return
            # For ALL other Ctrl shortcuts on Windows/Linux, pass them to the terminal
            # This allows nano shortcuts like Ctrl+X (exit), Ctrl+O (save), etc. to work
            # Don't intercept Ctrl+A (nano uses it), Ctrl+X (nano exit), etc.
        
        # ===== TERMINAL-SPECIFIC CTRL SHORTCUTS FOR ALL PLATFORMS =====
        
        # On macOS: Ctrl+[key] are terminal shortcuts (Cmd is for GUI)
        # On Windows/Linux: Ctrl+[key] (except C/V handled above) are terminal shortcuts
        # We handle them uniformly here for all platforms
        # Use is_ctrl_shortcut to properly detect Ctrl (not Cmd) on macOS
        
        if is_ctrl_shortcut and not has_shift and not has_alt:
            # Map common Ctrl shortcuts to terminal control characters
            # These work in nano, vim, bash, zsh, and all terminal applications
            ctrl_key_map = {
                Qt.Key_A: '\x01',  # Ctrl+A - Beginning of line (bash) or Set Mark (nano)
                Qt.Key_B: '\x02',  # Ctrl+B - Back one character
                Qt.Key_C: '\x03',  # Ctrl+C - Interrupt (SIGINT)
                Qt.Key_D: '\x04',  # Ctrl+D - EOF / Exit / Delete character
                Qt.Key_E: '\x05',  # Ctrl+E - End of line
                Qt.Key_F: '\x06',  # Ctrl+F - Forward one character
                Qt.Key_G: '\x07',  # Ctrl+G - Get Help (nano) / Bell
                Qt.Key_H: '\x08',  # Ctrl+H - Backspace
                Qt.Key_K: '\x0b',  # Ctrl+K - Kill line / Cut text (nano)
                Qt.Key_L: '\x0c',  # Ctrl+L - Clear screen
                Qt.Key_N: '\x0e',  # Ctrl+N - Next line / Next search (nano)
                Qt.Key_O: '\x0f',  # Ctrl+O - Write Out / Save (nano)
                Qt.Key_P: '\x10',  # Ctrl+P - Previous line / Previous search (nano)
                Qt.Key_R: '\x12',  # Ctrl+R - Reverse search / Replace (nano)
                Qt.Key_T: '\x14',  # Ctrl+T - Transpose characters / To Spell (nano)
                Qt.Key_U: '\x15',  # Ctrl+U - Kill line backward / Uncut (nano)
                Qt.Key_W: '\x17',  # Ctrl+W - Delete word backward / Where Is (nano search)
                Qt.Key_X: '\x18',  # Ctrl+X - Exit (nano) / Delete character
                Qt.Key_Y: '\x19',  # Ctrl+Y - Page up (nano)
                Qt.Key_Z: '\x1a',  # Ctrl+Z - Suspend process
                Qt.Key_QuoteDbl: '\x1c',  # Ctrl+\ - Quit signal (SIGQUIT)
                Qt.Key_BracketLeft: '\x1b',  # Ctrl+[ - Escape
                Qt.Key_BracketRight: '\x1d',  # Ctrl+] - Group separator
                Qt.Key_QuoteLeft: '\x1e',  # Ctrl+^ - Record separator  
                Qt.Key_Underscore: '\x1f',  # Ctrl+_ - Unit separator / Undo (nano)
            }
            
            # On Windows/Linux, skip Ctrl+C and Ctrl+V as they're handled above
            # (on those platforms, Ctrl+C can copy if text is selected)
            if not is_macos and key in [Qt.Key_C, Qt.Key_V]:
                pass
            elif key in ctrl_key_map:
                # Special handling for Ctrl+L (clear screen)
                # Archive content before clearing if we're in normal mode (not in an editor)
                if key == Qt.Key_L and not self.was_in_alternate_mode:
                    self.clear()
                    return
                
                # Update command buffer for line-editing shortcuts
                if key == Qt.Key_U:
                    # Ctrl+U: Kill/clear line backward - clear buffer
                    self.current_command_buffer = ""
                elif key == Qt.Key_K:
                    # Ctrl+K: Kill line forward - keep what we have (it kills after cursor)
                    pass
                elif key == Qt.Key_W:
                    # Ctrl+W: Delete word backward
                    # Remove last word from buffer
                    self.current_command_buffer = self.current_command_buffer.rstrip()
                    if ' ' in self.current_command_buffer:
                        self.current_command_buffer = ' '.join(self.current_command_buffer.split()[:-1]) + ' '
                    else:
                        self.current_command_buffer = ""
                elif key == Qt.Key_C:
                    # Ctrl+C: Interrupt - clear buffer
                    self.current_command_buffer = ""
                
                self.write_to_pty(ctrl_key_map[key])
                return
        
        # ===== ALTERNATIVE TERMINAL SHORTCUTS FOR ALL PLATFORMS =====
        
        # Ctrl+Shift+C/V/A/F: Alternative shortcuts that work on all platforms
        if has_ctrl and has_shift and not has_meta and not has_alt:
            if key == Qt.Key_C:
                # Ctrl+Shift+C: Copy
                if self.canvas.selection_start and self.canvas.selection_end:
                    selected_text = self.canvas.get_selected_text()
                    if selected_text:
                        QApplication.clipboard().setText(selected_text)
                return
            elif key == Qt.Key_V:
                # Ctrl+Shift+V: Paste
                clipboard_text = QApplication.clipboard().text()
                if clipboard_text:
                    # Track paste time for command extraction priority
                    self.last_paste_time = time.time()
                    # Add pasted text to command buffer
                    self.current_command_buffer += clipboard_text
                    self.write_to_pty(clipboard_text)
                return
            elif key == Qt.Key_A:
                # Ctrl+Shift+A: Select All
                self.canvas.select_all()
                return
            elif key == Qt.Key_F:
                # Ctrl+Shift+F: Open search (alternative for Windows/Linux)
                self.show_search()
                event.accept()
                return
        
        # ===== OPTION/ALT KEY COMBINATIONS (macOS Terminal.app style) =====
        
        # Option+Backspace: Delete word to the left
        if has_alt and not has_ctrl and not has_meta and not has_shift:
            if key == Qt.Key_Backspace:
                # Send Ctrl+W to delete word backward
                self.write_to_pty('\x17')
                return
            elif key == Qt.Key_Left:
                # Option+Left Arrow: Move one word left
                # Send Esc+b (move backward one word in bash/readline)
                self.write_to_pty('\x1bb')
                return
            elif key == Qt.Key_Right:
                # Option+Right Arrow: Move one word right
                # Send Esc+f (move forward one word in bash/readline)
                self.write_to_pty('\x1bf')
                return
            elif key == Qt.Key_D:
                # Option+D: Delete word forward (non-standard but useful)
                # Send Esc+d (delete word forward in bash/readline)
                self.write_to_pty('\x1bd')
                return
            elif key == Qt.Key_Backspace:
                # Option+Backspace already handled above - delete word
                # Update buffer: remove last word
                self.current_command_buffer = self.current_command_buffer.rstrip()
                if ' ' in self.current_command_buffer:
                    self.current_command_buffer = ' '.join(self.current_command_buffer.split()[:-1]) + ' '
                else:
                    self.current_command_buffer = ""
        
        # Clear selection on any key press (except for modifier keys and copy/select shortcuts)
        if key not in [Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta]:
            # Don't clear if we're using copy/select all shortcuts
            is_copy_or_select = (
                (has_meta and key in [Qt.Key_A, Qt.Key_C]) or  # Cmd+A/C on Mac
                (has_ctrl and key in [Qt.Key_A, Qt.Key_C])      # Ctrl+A/C on all platforms
            )
            if not is_copy_or_select:
                self.canvas.clear_selection()
        
        # Handle special keys first
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            # Hide suggestions on Enter (Enter executes command, doesn't select suggestion)
            if self.showing_suggestions:
                self._hide_suggestions()
            
            # When Enter is pressed, extract the final executable command from the screen.
            # IMPORTANT: Extract BEFORE sending Enter to PTY, otherwise cursor moves and command is lost.
            # The screen is the source of truth because it contains what was actually typed/pasted/tab-completed.
            
            # Check if tab completion just happened (within last 200ms) - wait for it to finish
            time_since_tab = time.time() - self.last_tab_press_time if self.last_tab_press_time > 0 else 999
            
            # If tab was pressed recently, wait a bit for completion to finish on screen
            if time_since_tab < 0.2:
                # Use QTimer to delay command extraction slightly to let tab completion finish
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(100, lambda: self._extract_and_record_command())
                self.pending_enter = True
                # Send Enter AFTER we've scheduled the extraction
                self.write_to_pty('\r')
                return
            
            # Extract command from screen BEFORE sending Enter
            # This is critical - after Enter, cursor moves and command line is on previous line
            
            # Save current cursor position
            saved_cursor_y = self.screen.cursor.y if self.screen else 0
            saved_cursor_x = self.screen.cursor.x if self.screen else 0
            
            # Try to extract from current line (where cursor is before Enter)
            screen_command = self._extract_command_from_line(saved_cursor_y, include_wrapped=True)
            
            # If that failed, try previous line (in case cursor is already at start of new line)
            if not screen_command and saved_cursor_y > 0:
                screen_command = self._extract_command_from_line(saved_cursor_y - 1, include_wrapped=True)
            
            # Fallback to buffer only if screen extraction failed
            buffer_command = self.current_command_buffer.strip()
            
            # Screen is authoritative - it has what was actually executed
            # Use screen command if available, otherwise fall back to buffer
            if screen_command:
                command = screen_command
            elif buffer_command:
                # Screen extraction failed, use buffer as fallback
                command = buffer_command
            else:
                command = ""

            # Emit command if we have something (BEFORE sending Enter)
            if command:
                # Store the last executed command for directory update logic
                self.last_executed_command = command.strip()
                try:
                    self.command_executed.emit(command)
                except RuntimeError:
                    # Widget has been deleted, skip signal emission
                    pass
            else:
                self.last_executed_command = None

            # Reset command buffer for next command
            self.current_command_buffer = ""
            self.last_tab_press_time = 0.0
            self.last_paste_time = 0.0
            
            # NOW send Enter to PTY (after extraction)
            self.write_to_pty('\r')
        elif key == Qt.Key_Backspace:
            # Hide suggestions on backspace
            if self.showing_suggestions:
                self._hide_suggestions()
            
            # Remove last character from command buffer
            if len(self.current_command_buffer) > 0:
                self.current_command_buffer = self.current_command_buffer[:-1]
            self.write_to_pty('\x7f')
            
            # Trigger suggestion update after backspace
            self.suggestion_timer.stop()
            self.suggestion_timer.start(300)  # 300ms delay
        elif key == Qt.Key_Delete:
            # Send Ctrl+D (EOF) to terminal
            self.write_to_pty('\x04')
        elif key == Qt.Key_Escape:
            # Send Esc to terminal
            self.write_to_pty('\x1b')
        elif key == Qt.Key_Tab:
            # Check if suggestions are showing - if so, complete suggestion instead of shell completion
            if self.showing_suggestions and self.suggestion_widget and self.suggestion_widget.isVisible():
                # Complete the current suggestion
                selected = self.suggestion_widget.get_selected_text()
                if selected:
                    self._on_suggestion_selected(selected)
                event.accept()
                return
            # Otherwise, track when Tab is pressed for completion timing
            self.last_tab_press_time = time.time()
            # Send Tab to terminal (don't add to buffer, tab completion changes input)
            # We'll sync the buffer from the screen after completion
            self.write_to_pty('\t')
        elif key == Qt.Key_Up or key == Qt.Key_Down:
            # Arrow keys - check if suggestions are showing first
            if self.showing_suggestions and self.suggestion_widget and self.suggestion_widget.isVisible():
                # Navigate suggestions instead of history
                if key == Qt.Key_Up:
                    self.suggestion_widget.navigate_up()
                else:
                    self.suggestion_widget.navigate_down()
                event.accept()
                return
            
            # No suggestions - normal history navigation
            # Arrow keys for history navigation - clear current buffer
            # The shell will handle history, and we'll capture what's displayed
            self.current_command_buffer = ""
            # Send arrow key sequences
            if key == Qt.Key_Up:
                self.write_to_pty('\x1b[A')
            else:
                self.write_to_pty('\x1b[B')
        elif key == Qt.Key_Left or key == Qt.Key_Right:
            # Left/Right arrow keys - send but don't affect buffer
            # (user is just navigating, not changing content yet)
            if key == Qt.Key_Left:
                self.write_to_pty('\x1b[D')
            else:
                self.write_to_pty('\x1b[C')
        else:
            # For all other keys (typing, etc.)
            # CRITICAL: Process ALL typing FIRST - this must ALWAYS execute
            # Typing is NEVER blocked, regardless of suggestions
            
            # Process typing FIRST for ALL keys with text content
            # This ensures typing ALWAYS works even when suggestions are visible
            if len(text) > 0:
                # Normal typing - ALWAYS allow this, never block
                # Only add printable characters to the buffer
                if text.isprintable():
                    self.current_command_buffer += text
                self.write_to_pty(text)
                
                # Trigger suggestion update after a short delay
                # This avoids showing suggestions on every keystroke
                self.suggestion_timer.stop()
                self.suggestion_timer.start(300)  # 300ms delay
            
            # Handle suggestion-specific navigation ONLY for non-typing keys
            # Tab and Escape don't have text, so handle them separately
            if self.showing_suggestions and self.suggestion_widget and self.suggestion_widget.isVisible():
                # Tab and Escape are the only keys we handle for suggestions here
                # (Up/Down already handled above)
                if key == Qt.Key_Tab:
                    # TAB completes the current suggestion (only if no text was typed)
                    if not text:  # Only if Tab was pressed without text
                        selected = self.suggestion_widget.get_selected_text()
                        if selected:
                            self._on_suggestion_selected(selected)
                        event.accept()
                        return
                elif key == Qt.Key_Escape:
                    # Escape dismisses suggestions
                    self._hide_suggestions()
                    event.accept()
                    return
        
        # Event is handled
        event.accept()
    
    def get_all_text(self):
        """Get all terminal text including history as a single string
        
        Returns:
            str: All terminal content with newlines between lines
        """
        if not self.screen:
            return ""
        
        all_lines = []
        
        # Get history lines
        if hasattr(self.screen, 'history') and hasattr(self.screen.history, 'top'):
            for line in self.screen.history.top:
                line_text = ""
                for col in range(self.screen.columns):
                    if col in line:
                        char = line[col]
                        line_text += char.data if hasattr(char, 'data') else str(char)
                all_lines.append(line_text.rstrip())
        
        # Get current screen buffer
        for row_idx in range(self.screen.lines):
            line = self.screen.buffer[row_idx]
            line_text = ""
            for col in range(self.screen.columns):
                if col in line:
                    char = line[col]
                    line_text += char.data if hasattr(char, 'data') else str(char)
            all_lines.append(line_text.rstrip())
        
        return '\n'.join(all_lines)
    
    def update_viewport_range(self, start_ratio, height_ratio):
        """Update the viewport range for line number highlighting
        
        Args:
            start_ratio: Starting position as ratio of total content (0.0 to 1.0)
            height_ratio: Height of viewport as ratio of total content (0.0 to 1.0)
        """
        if not self.canvas or not self.screen:
            return

        # Prevent update if user moved highlighter and hasn't scrolled since
        if hasattr(self, '_block_scroll_highlighter_update_until_scroll') and self._block_scroll_highlighter_update_until_scroll:
            return

        if hasattr(self, '_jumping_to_line') and self._jumping_to_line:
            return

        # Skip update if we have a user-clicked line that should be preserved
        # Only recalculate if viewport_center_line is not set or if user manually scrolled
        if hasattr(self.canvas, 'viewport_center_line') and self.canvas.viewport_center_line >= 0:
            if hasattr(self, '_preserve_clicked_line') and self._preserve_clicked_line:
                return
        
        # Calculate total lines including history
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        # Calculate the center line of the viewport (where minimap picks color)
        center_ratio = start_ratio + (height_ratio / 2.0)
        center_line = int(center_ratio * total_lines)
        
        # Clamp to valid range
        center_line = max(0, min(center_line, total_lines - 1))
        
        # Add cumulative offset to get displayed line number
        displayed_line = center_line + 1  # Convert to 1-based
        if hasattr(self.canvas, '_cumulative_line_offset'):
            displayed_line += self.canvas._cumulative_line_offset
        
        # Update canvas center line
        old_center_line = self.canvas.viewport_center_line if hasattr(self.canvas, 'viewport_center_line') else -1
        self.canvas.viewport_center_line = center_line
        # Trigger repaint of line numbers
        self.canvas.update()
    
    def get_center_line_number(self):
        """Get the line number at the center of the current viewport
        
        Uses the viewport_center_line that's already tracked by update_viewport_range(),
        which is the SAME line number used for color selection and double-click.
        This ensures consistency across all line number references.
        
        Returns:
            int: The 0-indexed line number at viewport center, or 0 if unable to determine
        """
        if not self.canvas:
            return 0
        
        # Use the tracked viewport center line (already calculated by update_viewport_range)
        # This is the SAME line number used for:
        # - Line number highlighting in the terminal
        # - Color selection in minimap
        # - Double-click line number
        if hasattr(self.canvas, 'viewport_center_line') and self.canvas.viewport_center_line >= 0:
            return self.canvas.viewport_center_line
        
        # Fallback: return 0 if not yet initialized
        return 0
    
    def scroll_to_line(self, line_number):
        """Scroll to show a specific line number positioned near the top of viewport
        
        Calculates the exact scrollbar position needed to position the target line at about 1/3 from top.
        In alternate screen mode (nano/vim), sends arrow keys instead of scrolling.
        
        Args:
            line_number: The line number (0-indexed) to scroll to and highlight
        """
        
        if not self.canvas or not self.scroll_area:
            return
        
        # In alternate screen mode (nano/vim), send arrow keys to navigate
        if self.was_in_alternate_mode:
            # Get current cursor position in the editor
            current_line = self.screen.cursor.y if self.screen else 0
            
            # Calculate how many lines to move
            lines_to_move = line_number - current_line
            
            if lines_to_move != 0:
                # Send arrow key sequences
                if lines_to_move > 0:
                    # Move down
                    arrow_key = '\x1b[B'  # Down arrow
                else:
                    # Move up
                    arrow_key = '\x1b[A'  # Up arrow
                    lines_to_move = abs(lines_to_move)
                
                # Send arrow keys (limit to reasonable amount for responsiveness)
                lines_to_move = min(lines_to_move, 100)
                for _ in range(lines_to_move):
                    self.write_to_pty(arrow_key)
            
            return
        
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return
        
        # Calculate total lines including history
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        
        if total_lines == 0:
            return
        
        # Calculate the target viewport start position to place line at about 1/3 from top
        # This positions the line in a comfortable reading position
        # We want: start_ratio + (height_ratio * 0.33) = line_number / total_lines
        # Therefore: start_ratio = (line_number / total_lines) - (height_ratio * 0.33)
        
        # Get the viewport height ratio
        total_range = scroll_bar.maximum() - scroll_bar.minimum() + scroll_bar.pageStep()
        
        if total_range <= 0:
            return
        
        height_ratio = scroll_bar.pageStep() / total_range
        
        # Calculate target ratio (position line at about 1/3 from top of viewport)
        target_ratio = line_number / total_lines
        
        # Calculate target start ratio - position line at 1/3 down from viewport top
        target_start_ratio = target_ratio - (height_ratio * 0.33)
        
        # Clamp to valid range
        target_start_ratio = max(0.0, min(1.0 - height_ratio, target_start_ratio))
        
        # Convert ratio to scrollbar value
        new_scroll = int(target_start_ratio * total_range)
        
        # Clamp to valid range
        new_scroll = max(0, min(new_scroll, scroll_bar.maximum()))
        
        # Disable autoscroll when manually scrolling
        self.user_has_scrolled = True
        
        # Mark that we're updating from a line jump to prevent viewport_range recalculation
        self._jumping_to_line = True
        
        scroll_bar.setValue(new_scroll)
        
        # Set the viewport center line to the clicked line for highlighting
        # The highlight should move to the clicked line
        old_center_line = self.canvas.viewport_center_line if hasattr(self.canvas, 'viewport_center_line') else None
        self.canvas.viewport_center_line = line_number
        
        # Set flag to preserve the clicked line and prevent it from being recalculated
        self._preserve_clicked_line = True
        
        # Calculate viewport position for minimap update
        total_range = scroll_bar.maximum() - scroll_bar.minimum() + scroll_bar.pageStep()
        if total_range > 0:
            actual_viewport_start = scroll_bar.value() / total_range
            viewport_height_ratio = scroll_bar.pageStep() / total_range
            
            
            # Update viewport tracking (but don't recalculate center line since we set it explicitly)
            self.viewport_start = actual_viewport_start
            self.viewport_height = viewport_height_ratio
            
            # Emit signal immediately to update minimap (bypass throttling)
            self.viewport_scrolled.emit(actual_viewport_start, viewport_height_ratio)
        
        # Trigger repaint to show updated line number highlighting
        self.canvas.update()
        
        # Clear the jump flag after a delay to allow all viewport updates to complete
        def clear_jump_flag():
            self._jumping_to_line = False
        
        QTimer.singleShot(200, clear_jump_flag)
    
    # ===== SEARCH FUNCTIONALITY =====
    
    def show_search(self):
        """Show the search widget and focus it"""
        if self.search_widget:
            self.search_active = True
            self.search_widget.show_and_focus()
    
    def _on_search_requested(self, text, case_sensitive, whole_word):
        """Handle search request"""
        self.search_matches = []
        self.current_match_index = -1
        
        if not text.strip() or not self.screen:
            # Clear any existing highlights
            if hasattr(self.canvas, 'search_matches'):
                self.canvas.search_matches = []
                self.canvas.update()
            self.search_widget.update_match_count(0, 0)
            return
        
        # Search through all terminal text (history + buffer)
        all_lines = []
        
        # Get history lines
        if hasattr(self.screen, 'history') and hasattr(self.screen.history, 'top'):
            for line in self.screen.history.top:
                line_text = self._get_line_text_from_dict(line)
                all_lines.append(line_text)
        
        # Get current screen buffer
        for row_idx in range(self.screen.lines):
            line = self.screen.buffer[row_idx]
            line_text = self._get_line_text_from_dict(line)
            all_lines.append(line_text)
        
        # Search for text
        search_text = text if case_sensitive else text.lower()
        
        for row_idx, line_text in enumerate(all_lines):
            compare_text = line_text if case_sensitive else line_text.lower()
            
            # Find all occurrences in this line
            col = 0
            while col < len(compare_text):
                pos = compare_text.find(search_text, col)
                if pos == -1:
                    break
                
                # Check whole word if needed
                if whole_word:
                    # Check if it's a whole word
                    before_ok = pos == 0 or not compare_text[pos - 1].isalnum()
                    after_ok = pos + len(search_text) >= len(compare_text) or not compare_text[pos + len(search_text)].isalnum()
                    
                    if before_ok and after_ok:
                        self.search_matches.append((row_idx, pos, len(search_text)))
                else:
                    self.search_matches.append((row_idx, pos, len(search_text)))
                
                col = pos + 1
        
        # Update canvas with search matches for highlighting
        if hasattr(self.canvas, 'search_matches'):
            self.canvas.search_matches = self.search_matches
            self.canvas.current_search_match = -1
            self.canvas.update()
        
        # Update match count
        if self.search_matches:
            self.current_match_index = 0
            self._highlight_current_match()
            self.search_widget.update_match_count(1, len(self.search_matches))
        else:
            self.search_widget.update_match_count(0, 0)
    
    def _on_search_next(self):
        """Navigate to next search match"""
        if not self.search_matches:
            return
        
        self.current_match_index = (self.current_match_index + 1) % len(self.search_matches)
        self._highlight_current_match()
        self.search_widget.update_match_count(self.current_match_index + 1, len(self.search_matches))
    
    def _on_search_previous(self):
        """Navigate to previous search match"""
        if not self.search_matches:
            return
        
        self.current_match_index = (self.current_match_index - 1) % len(self.search_matches)
        self._highlight_current_match()
        self.search_widget.update_match_count(self.current_match_index + 1, len(self.search_matches))
    
    def _on_search_closed(self):
        """Handle search widget close"""
        # Hide the search widget
        if self.search_widget:
            self.search_widget.hide()
        
        # Clear search highlights
        self.search_matches = []
        self.current_match_index = -1
        self.search_active = False
        
        if hasattr(self.canvas, 'search_matches'):
            self.canvas.search_matches = []
            self.canvas.current_search_match = -1
            self.canvas.update()
        
        # Return focus to canvas
        self.canvas.setFocus()
    
    def _highlight_current_match(self):
        """Highlight the current match and scroll to it"""
        if not self.search_matches or self.current_match_index < 0:
            return
        
        match_row, match_col, match_len = self.search_matches[self.current_match_index]
        
        # Update canvas with current match
        if hasattr(self.canvas, 'current_search_match'):
            self.canvas.current_search_match = self.current_match_index
            self.canvas.update()
        
        # Scroll to the match
        scroll_bar = self.scroll_area.verticalScrollBar()
        if not scroll_bar:
            return
        
        # Calculate total lines including history
        total_lines = self.screen.lines
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        if total_lines <= 0:
            return
        
        # Calculate scroll position to center the match
        char_height = self.canvas.char_height if hasattr(self.canvas, 'char_height') else 20
        viewport_height = self.scroll_area.viewport().height()
        visible_lines = viewport_height // char_height
        
        # Position match at 1/3 from top
        target_top_line = max(0, match_row - visible_lines // 3)
        
        # Convert to pixel scroll position
        target_scroll = target_top_line * char_height
        target_scroll = max(0, min(target_scroll, scroll_bar.maximum()))
        
        # Disable autoscroll when navigating search results
        self.user_has_scrolled = True
        
        scroll_bar.setValue(target_scroll)
    
    def _get_line_text_from_dict(self, line_dict):
        """Extract text from a line dictionary
        
        Args:
            line_dict: Dictionary mapping column index to Char objects
            
        Returns:
            str: Text content of the line
        """
        if not line_dict:
            return ""
        
        max_col = max(line_dict.keys()) if line_dict else 0
        line_text = ""
        for col in range(max_col + 1):
            if col in line_dict:
                char = line_dict[col]
                line_text += self.canvas.get_char_data(char) if hasattr(self.canvas, 'get_char_data') else (char.data if hasattr(char, 'data') else str(char))
            else:
                line_text += " "
        return line_text.rstrip()
    
    def save_output_to_file(self, filepath):
        """Save terminal output to a text file with ANSI colors and line numbers
        
        Args:
            filepath: Path to the file where output will be saved
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # ANSI color codes for styling
            RESET = '\033[0m'
            BRIGHT_BLACK = '\033[90m'  # Gray for line numbers
            
            # Collect all lines (history + current buffer)
            all_lines = []
            
            # Add history lines if available
            if hasattr(self.screen, 'history') and hasattr(self.screen.history, 'top'):
                all_lines.extend(list(self.screen.history.top))
            
            # Add current visible lines
            for row_idx in range(self.screen.lines):
                all_lines.append(self.screen.buffer[row_idx])
            
            # Open file for writing
            with open(filepath, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"# Terminal Output Saved on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total Lines: {len(all_lines)}\n")
                f.write("# " + "=" * 80 + "\n\n")
                
                # Process each line
                for line_num, line_dict in enumerate(all_lines, start=1):
                    # Write line number with gray color
                    f.write(f"{BRIGHT_BLACK}{line_num:6d}:{RESET} ")
                    
                    # Process each character in the line with its colors
                    if line_dict:
                        max_col = max(line_dict.keys()) if line_dict else 0
                        current_fg = None
                        current_bg = None
                        current_bold = False
                        current_italics = False
                        current_underline = False
                        
                        for col in range(max_col + 1):
                            if col in line_dict:
                                char = line_dict[col]
                                char_data = char.data if hasattr(char, 'data') else str(char)
                                
                                # Get character attributes
                                fg = getattr(char, 'fg', 'default')
                                bg = getattr(char, 'bg', 'default')
                                bold = getattr(char, 'bold', False)
                                italics = getattr(char, 'italics', False)
                                underline = getattr(char, 'underline', False)
                                
                                # Check if style changed
                                style_changed = (fg != current_fg or bg != current_bg or 
                                               bold != current_bold or italics != current_italics or 
                                               underline != current_underline)
                                
                                if style_changed:
                                    # Reset and apply new style
                                    f.write(RESET)
                                    
                                    # Apply text formatting
                                    if bold:
                                        f.write('\033[1m')
                                    if italics:
                                        f.write('\033[3m')
                                    if underline:
                                        f.write('\033[4m')
                                    
                                    # Apply foreground color
                                    if fg != 'default':
                                        if isinstance(fg, str) and fg.isdigit():
                                            # 256-color mode
                                            f.write(f'\033[38;5;{fg}m')
                                        elif isinstance(fg, str):
                                            # Named color
                                            color_map = {
                                                'black': 30, 'red': 31, 'green': 32, 'yellow': 33,
                                                'blue': 34, 'magenta': 35, 'cyan': 36, 'white': 37,
                                                'brightblack': 90, 'brightred': 91, 'brightgreen': 92,
                                                'brightyellow': 93, 'brightblue': 94, 'brightmagenta': 95,
                                                'brightcyan': 96, 'brightwhite': 97
                                            }
                                            if fg.lower() in color_map:
                                                f.write(f'\033[{color_map[fg.lower()]}m')
                                    
                                    # Apply background color
                                    if bg != 'default':
                                        if isinstance(bg, str) and bg.isdigit():
                                            # 256-color mode
                                            f.write(f'\033[48;5;{bg}m')
                                        elif isinstance(bg, str):
                                            # Named color
                                            color_map = {
                                                'black': 40, 'red': 41, 'green': 42, 'yellow': 43,
                                                'blue': 44, 'magenta': 45, 'cyan': 46, 'white': 47,
                                                'brightblack': 100, 'brightred': 101, 'brightgreen': 102,
                                                'brightyellow': 103, 'brightblue': 104, 'brightmagenta': 105,
                                                'brightcyan': 106, 'brightwhite': 107
                                            }
                                            if bg.lower() in color_map:
                                                f.write(f'\033[{color_map[bg.lower()]}m')
                                    
                                    # Update current state
                                    current_fg = fg
                                    current_bg = bg
                                    current_bold = bold
                                    current_italics = italics
                                    current_underline = underline
                                
                                # Write the character
                                f.write(char_data)
                            else:
                                # Empty space
                                f.write(' ')
                        
                        # Reset at end of line
                        f.write(RESET)
                        f.write('\n')
            
            return True
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_tab_id(self):
        """Generate a unique ID for this terminal tab"""
        return str(uuid.uuid4())[:8]
    
    def _check_streaming_state(self):
        """Check if streaming has stopped (called every second)"""
        current_time = time.time()
        time_since_last_output = current_time - self._last_output_time
        
        # Was streaming, now stopped (no output for threshold period)
        if self._streaming_active and time_since_last_output > self._streaming_stop_threshold:
            self._streaming_active = False
            self._on_streaming_stopped(time_since_last_output)
    
    def _on_streaming_stopped(self, pause_duration):
        """Called when streaming stops (DISABLED - no visual markers)"""
        # Streaming markers disabled to remove visual output
        pass
        # current_line = self._get_current_visible_line_number()
        # event = {
        #     "event": "stopped",
        #     "timestamp": datetime.now().isoformat(),
        #     "line_number": current_line,
        #     "duration": pause_duration
        # }
        # self._streaming_events.append(event)
        # 
        # # If currently archiving to history, add marker
        # if self.history_file_path:
        #     self.history_manager.append_streaming_marker(
        #         self.tab_id,
        #         "stopped",
        #         event["timestamp"],
        #         pause_duration
        #     )
    
    def _on_streaming_resumed(self, gap_duration):
        """Called when streaming resumes after pause (DISABLED - no visual markers)"""
        # Streaming markers disabled to remove visual output
        pass
        # current_line = self._get_current_visible_line_number()
        # event = {
        #     "event": "resumed",
        #     "timestamp": datetime.now().isoformat(),
        #     "line_number": current_line,
        #     "gap_duration": gap_duration
        # }
        # self._streaming_events.append(event)
        # 
        # # If currently archiving to history, add marker
        # if self.history_file_path:
        #     self.history_manager.append_streaming_marker(
        #         self.tab_id,
        #         "resumed",
        #         event["timestamp"]
        #     )
    
    def _get_current_visible_line_number(self):
        """Get the current visible line number (including history)"""
        history_offset = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
        return history_offset + self.screen.cursor.y
    
    def clear_lines_above_and_archive(self, row_number):
        """
        Clear lines above specified row and archive them to history file
        
        Args:
            row_number: Row number (including history) above which to clear
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.screen:
                return False
            
            # Extract lines to archive
            lines_to_archive = self._extract_lines_for_archive(0, row_number)
            
            if not lines_to_archive:
                return False
            
            # APPEND to existing history file (continuous mode)
            self.history_manager.append_archive(
                self.tab_id,
                lines_to_archive,
                row_range=f"0-{row_number}",
                command_context=self.last_executed_command or "manual_archive"
            )
            
            # Clear the lines from buffer
            self._clear_lines_from_buffer(0, row_number)
            
            # Update canvas and scrollbar
            self._update_after_clear()
            
            return True
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def _archive_before_clear(self, clear_command):
        """
        Archive all current buffer before clear command executes
        This ensures no data loss when user clears terminal
        
        Args:
            clear_command: The clear command being executed (for context)
        """
        try:
            if not self.screen:
                print("[DEBUG] _archive_before_clear: No screen, returning")
                return
            
            # Get total number of lines including history
            history_size = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
            total_lines = history_size + self.screen.lines
            
            print(f"[DEBUG] _archive_before_clear: history_size={history_size}, screen.lines={self.screen.lines}, total={total_lines}")
            
            # Only archive if there's meaningful content (more than just a prompt)
            if total_lines > 3:
                # Extract all current lines
                lines_to_archive = self._extract_lines_for_archive(0, total_lines)
                
                print(f"[DEBUG] _archive_before_clear: Extracted {len(lines_to_archive)} lines to archive")
                
                if lines_to_archive:
                    # APPEND to existing history file (continuous mode)
                    print(f"[DEBUG] _archive_before_clear: Calling append_archive with tab_id={self.tab_id}")
                    self.history_manager.append_archive(
                        tab_id=self.tab_id,
                        lines_data=lines_to_archive,
                        row_range=f"0-{total_lines}",
                        command_context=f"before_clear: {clear_command}"
                    )
                    print(f"[DEBUG] _archive_before_clear: Archive complete")
                    
                    # Emit signal to update history button
                    try:
                        # Find main window and update history button
                        from PyQt5.QtWidgets import QApplication
                        for widget in QApplication.topLevelWidgets():
                            if hasattr(widget, 'update_history_button'):
                                widget.update_history_button()
                                break
                    except Exception:
                        pass
                else:
                    print("[DEBUG] _archive_before_clear: No lines extracted, skipping archive")
            else:
                print(f"[DEBUG] _archive_before_clear: Only {total_lines} lines, skipping (threshold is 3)")
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            traceback.print_exc()
    
    def _check_auto_archive_threshold(self):
        """
        Background monitoring: Check if buffer has reached threshold for auto-archiving
        This runs every 5 seconds via QTimer
        """
        # Skip if auto-archive is disabled or already in progress
        if self._auto_archive_in_progress:
            return
        
        # Get preferences
        auto_archive_enabled = self.prefs_manager.get('terminal', 'auto_archive_enabled', True)
        if not auto_archive_enabled:
            return
        
        auto_archive_threshold = self.prefs_manager.get('terminal', 'auto_archive_threshold', 9500)
        auto_archive_keep_lines = self.prefs_manager.get('terminal', 'auto_archive_keep_lines', 5000)
        
        # Validate settings
        if auto_archive_keep_lines >= auto_archive_threshold:
            return  # Invalid configuration
        
        # Calculate total lines in buffer
        total_lines = self.screen.lines if self.screen else 0
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        # Check if we've reached threshold
        if total_lines >= auto_archive_threshold:
            self._auto_archive_in_progress = True
            try:
                # Calculate how many lines to archive (oldest lines)
                lines_to_archive_count = auto_archive_threshold - auto_archive_keep_lines
                
                if lines_to_archive_count > 0:
                    # Extract oldest lines
                    lines_to_archive = self._extract_lines_for_archive(0, lines_to_archive_count)
                    
                    if lines_to_archive:
                        # APPEND to history file (continuous mode)
                        self.history_manager.append_archive(
                            tab_id=self.tab_id,
                            lines_data=lines_to_archive,
                            row_range=f"auto-archive-{lines_to_archive_count}-lines",
                            command_context="auto_archive"
                        )
                        
                        # Clear those lines from buffer
                        self._clear_lines_from_buffer(0, lines_to_archive_count)
                        
                        # Update UI
                        self._update_after_clear()
                        
                        # Update history button
                        try:
                            from PyQt5.QtWidgets import QApplication
                            for widget in QApplication.topLevelWidgets():
                                if hasattr(widget, 'update_history_button'):
                                    widget.update_history_button()
                                    break
                        except Exception:
                            pass
                        
                        # Show notification (optional)
                        # Disabled to reduce UI clutter during background archiving
                        
            except Exception as e:
                import traceback
                traceback.print_exc()
            finally:
                self._auto_archive_in_progress = False
    
    def _check_auto_archive(self):
        """
        Check if automatic archival should be triggered based on preferences
        """
        # Skip if auto-archive is disabled or already in progress
        if self._auto_archive_in_progress:
            return
        
        # Get preferences
        auto_archive_enabled = self.prefs_manager.get('terminal', 'auto_archive_enabled', False)
        if not auto_archive_enabled:
            return
        
        auto_archive_threshold = self.prefs_manager.get('terminal', 'auto_archive_threshold', 2000)
        auto_archive_keep_lines = self.prefs_manager.get('terminal', 'auto_archive_keep_lines', 1000)
        
        # Validate settings
        if auto_archive_keep_lines >= auto_archive_threshold:
            return  # Invalid configuration, keep lines must be less than threshold
        
        # Calculate total lines in buffer
        total_lines = self.screen.lines if self.screen else 0
        if hasattr(self.screen, 'history'):
            total_lines += len(self.screen.history.top)
        
        # Check if we need to archive
        if total_lines >= auto_archive_threshold:
            self._auto_archive_in_progress = True
            try:
                # Calculate how many lines to archive
                lines_to_archive = total_lines - auto_archive_keep_lines
                
                if lines_to_archive > 0:
                    # Perform the archival
                    success = self.clear_lines_above_and_archive(lines_to_archive)
                    
                    if success:
                        # Show notification
                        from PyQt5.QtWidgets import QApplication
                        if hasattr(self, 'parent') and hasattr(self.parent(), 'statusBar'):
                            main_window = self.parent()
                            while main_window and not hasattr(main_window, 'statusBar'):
                                main_window = main_window.parent()
                            if main_window:
                                main_window.statusBar().showMessage(
                                    f"Auto-archived {lines_to_archive} lines to history (keeping recent {auto_archive_keep_lines} lines)",
                                    5000
                                )
            except Exception as e:
                import traceback
                traceback.print_exc()
            finally:
                self._auto_archive_in_progress = False
    
    def _extract_lines_for_archive(self, start_row, end_row):
        """
        Extract lines from buffer for archiving
        
        Args:
            start_row: Starting row (inclusive)
            end_row: Ending row (exclusive)
            
        Returns:
            list: List of line dictionaries with content and color info
        """
        lines_data = []
        
        # Get all lines including history
        all_lines = []
        if hasattr(self.screen, 'history'):
            all_lines.extend(list(self.screen.history.top))
        for row_idx in range(self.screen.lines):
            all_lines.append(self.screen.buffer[row_idx])
        
        # Extract lines in range
        for row in range(start_row, min(end_row, len(all_lines))):
            line = all_lines[row]
            if not line:
                continue
            
            # Extract line text and color info
            line_text = ""
            max_col = max(line.keys()) if line else 0
            
            for col in range(max_col + 1):
                if col in line:
                    char = line[col]
                    char_data = self.canvas.get_char_data(char) if hasattr(char, 'data') or isinstance(char, str) else ' '
                    line_text += char_data
                else:
                    line_text += " "
            
            # Get color info from first character (representative)
            colors = {"fg": "default", "bg": "default"}
            if 0 in line:
                char = line[0]
                if hasattr(char, 'fg'):
                    colors["fg"] = char.fg
                if hasattr(char, 'bg'):
                    colors["bg"] = char.bg
            
            line_data = {
                "row": row,
                "type": "content",
                "content": line_text.rstrip(),
                "colors": colors
            }
            
            lines_data.append(line_data)
        
        return lines_data
    
    def _clear_lines_from_buffer(self, start_row, end_row):
        """
        Clear lines from pyte buffer
        
        Args:
            start_row: Starting row (inclusive)
            end_row: Ending row (exclusive)
        """
        if not self.screen:
            return
        
        history_size = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
        
        # If clearing history lines
        if start_row < history_size and hasattr(self.screen, 'history'):
            # Clear from history by removing from the left (oldest lines)
            lines_to_remove = min(end_row, history_size) - start_row
            if lines_to_remove > 0:
                # Remove lines from the left of the deque (oldest first)
                for _ in range(lines_to_remove):
                    if self.screen.history.top:
                        self.screen.history.top.popleft()
        
        # Update canvas line numbering offset
        if self.canvas:
            self.canvas._cumulative_line_offset += (end_row - start_row)
            self.canvas._total_lines_count = len(self.screen.history.top) if hasattr(self.screen, 'history') else 0
            self.canvas._total_lines_count += self.screen.lines
    
    def _update_after_clear(self):
        """Update UI after clearing lines"""
        # Resize canvas to reflect new content
        self.canvas.resizeCanvas()
        self.canvas.update()
        
        # Update scrollbar
        scroll_bar = self.scroll_area.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.minimum())
        
        # Reset user scroll flag
        self.user_has_scrolled = False
    
    def get_history_file_size(self):
        """Get formatted file size of history file"""
        if not self.history_file_path:
            return "0B"
        return self.history_manager.get_file_size(self.tab_id)
    
    def view_history_in_terminal(self):
        """Open history viewer dialog"""
        if not self.history_file_path:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "No History",
                "This terminal tab has no archived history yet.\n\n"
                "Right-click on the line number highlighter to archive lines."
            )
            return
        
        # Load history data
        history_data = self.history_manager.load_history(self.history_file_path)
        
        # Show history viewer dialog
        from ui.history_viewer_dialog import HistoryViewerDialog
        dialog = HistoryViewerDialog(history_data, parent=self)
        dialog.import_requested.connect(self._import_history_lines)
        dialog.exec_()
    
    def _import_history_lines(self, lines):
        """Import lines from history back to terminal"""
        # Insert lines at the beginning of history
        if not self.screen or not hasattr(self.screen, 'history'):
            return
        
        # Convert lines to pyte format and prepend to history
        import collections
        current_history = list(self.screen.history.top)
        
        # Create simple line dictionaries for imported content
        for line_data in lines:
            content = line_data.get("content", "")
            line_dict = {}
            for col, char in enumerate(content):
                # Create a simple char object
                import pyte
                char_obj = pyte.Char(char)
                line_dict[col] = char_obj
            
            current_history.insert(0, line_dict)
        
        # Update history
        self.screen.history.top = collections.deque(
            current_history[-self.scrollback_lines:],
            maxlen=self.scrollback_lines
        )
        
        # Update canvas
        self.canvas.resizeCanvas()
        self.canvas.update()
    
    def import_history_file(self, file_path):
        """Import a .tbhist file into this terminal"""
        try:
            history_data = self.history_manager.import_history(file_path, self.tab_id)
            
            # Update file path
            self.history_file_path = self.history_manager.get_history_file_path(self.tab_id)
            
            from PyQt5.QtWidgets import QMessageBox
            archive_count = len(history_data.get("archives", []))
            QMessageBox.information(
                self,
                "Import Successful",
                f"Successfully imported {archive_count} archive(s) from:\n{file_path}"
            )
        
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Import Failed",
                f"Failed to import history file:\n{str(e)}"
            )



