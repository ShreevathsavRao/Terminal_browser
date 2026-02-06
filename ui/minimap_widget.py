"""Minimap widget for terminal content visualization"""

import re
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QMenu, QAction, QLineEdit, QApplication, QCheckBox, QWidgetAction, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPointF, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF
from core.preferences_manager import PreferencesManager


class ExtendedPreviewWidget(QWidget):
    """Floating widget showing extended preview of minimap content"""
    
    line_clicked = pyqtSignal(int)  # Emits line number when clicked
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self.content_lines = []
        self.center_line = 0
        self.start_line = 0
        self.end_line = 0
        self.line_height = 20
        self.prefs_manager = PreferencesManager()
        
        self.setMouseTracking(True)
        
    def set_content(self, lines, center_line, context=10):
        """Set the content to display
        
        Args:
            lines: List of all content lines
            center_line: Index of center line
            context: Number of lines to show above and below
        """
        self.content_lines = lines
        self.center_line = center_line
        self.start_line = max(0, center_line - context)
        self.end_line = min(len(lines) - 1, center_line + context)
        
        # Calculate required size
        num_lines = self.end_line - self.start_line + 1
        width = 500
        height = num_lines * self.line_height + 50  # +50 for header/footer
        
        self.setFixedSize(width, height)
        self.update()
    
    def get_line_color(self, line_text):
        """Get color for a line based on content"""
        line_lower = line_text.lower()
        
        # Error patterns
        if re.search(r'\b(error|exception|traceback|failed|failure)\b', line_lower):
            return QColor(255, 80, 80)
        
        # Warning patterns
        if re.search(r'\b(warning|warn|deprecated)\b', line_lower):
            return QColor(255, 200, 80)
        
        # Success patterns
        if re.search(r'\b(success|successful|completed|passed|ok)\b', line_lower):
            return QColor(80, 255, 120)
        
        # Info patterns
        if re.search(r'\b(info|information)\b', line_lower):
            return QColor(80, 180, 255)
        
        return QColor(180, 180, 180)
    
    def paintEvent(self, event):
        """Draw the extended preview"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Draw background with shadow effect
        painter.setPen(QPen(QColor(60, 60, 60), 3))
        painter.setBrush(QBrush(QColor(30, 30, 30, 250)))
        painter.drawRoundedRect(2, 2, width - 4, height - 4, 8, 8)
        
        # Draw header
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        header_text = f"Lines {self.start_line + 1}-{self.end_line + 1} (Center: {self.center_line + 1})"
        painter.drawText(QRect(10, 5, width - 20, 25), Qt.AlignLeft | Qt.AlignVCenter, header_text)
        
        # Draw line content
        y_offset = 35
        font = QFont("Courier", 10)
        painter.setFont(font)
        
        for i in range(self.start_line, self.end_line + 1):
            if i < len(self.content_lines):
                line_text = self.content_lines[i]
                line_num = i + 1
                
                # Highlight center line
                if i == self.center_line:
                    painter.fillRect(5, y_offset - 15, width - 10, self.line_height,
                                   QColor(70, 70, 120, 180))
                
                # Draw line number with bright color
                painter.setPen(QPen(QColor(255, 200, 100)))  # Brighter yellow-orange
                painter.setFont(QFont("Courier", 10, QFont.Bold))
                line_num_text = f"{line_num:5d}"
                painter.drawText(QRect(10, y_offset - 15, 50, self.line_height), 
                               Qt.AlignLeft | Qt.AlignVCenter, line_num_text)
                
                # Draw separator
                painter.setPen(QPen(QColor(120, 120, 120)))
                painter.setFont(QFont("Courier", 10))
                painter.drawText(QRect(60, y_offset - 15, 15, self.line_height),
                               Qt.AlignCenter | Qt.AlignVCenter, "│")
                
                # Draw line content
                line_color = self.get_line_color(line_text)
                painter.setPen(QPen(line_color))
                painter.setFont(QFont("Courier", 9))
                
                # Truncate if too long
                max_chars = 50
                display_text = line_text[:max_chars]
                if len(line_text) > max_chars:
                    display_text += "..."
                
                painter.drawText(QRect(80, y_offset - 15, width - 90, self.line_height),
                               Qt.AlignLeft | Qt.AlignVCenter, display_text)
                
                y_offset += self.line_height
        
        # Draw footer
        painter.setFont(QFont("Arial", 9))
        painter.setPen(QPen(QColor(150, 150, 150)))
        painter.drawText(QRect(10, height - 20, width - 20, 15),
                        Qt.AlignCenter, "Double-click minimap viewport to jump to line")
        
        painter.end()
    
    def mousePressEvent(self, event):
        """Handle clicks on line numbers"""
        if event.button() == Qt.LeftButton:
            # Calculate which line was clicked
            y = event.y() - 35  # Account for header
            if y >= 0:
                line_idx = int(y / self.line_height)
                actual_line = self.start_line + line_idx
                if self.start_line <= actual_line <= self.end_line:
                    self.line_clicked.emit(actual_line)
                    self.hide()


class MinimapWidget(QWidget):
    """A minimap that shows a scaled-down view of terminal content"""
    
    # Signal emitted when user clicks on minimap (outside viewport box) - moves highlighter only
    position_clicked = pyqtSignal(float)  # Emits normalized position (0.0 to 1.0)
    # Signal emitted when user drags viewport box - scrolls terminal
    viewport_dragged = pyqtSignal(float)  # Emits normalized position (0.0 to 1.0)
    # Signal emitted when center line changes (for syncing with terminal highlight)
    center_line_changed = pyqtSignal(int)  # Emits actual line number in full content
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.content_lines = []
        self.content_line_indices = []  # Track original line indices for mapping
        self.total_content_lines = 0     # Track total number of lines
        self.viewport_start = 0.0  # Normalized position (0.0 to 1.0)
        self.viewport_height = 0.1  # Normalized height (0.0 to 1.0)
        self.last_center_line = -1  # Track last emitted center line to avoid redundant signals
        
        # Cache for filtered line indices
        self.filtered_line_indices = []  # Cached list of filtered line numbers
        self.filtered_indices_dirty = True  # Flag to trigger recalculation
        
        # Extended preview widget
        self.preview_widget = None
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.show_preview)
        
        # Line number editor for jumping
        self.line_editor = None
        
        # Initialize preferences manager
        self.prefs_manager = PreferencesManager()
        
        # Scrollbar-style dimensions
        self.setMinimumWidth(20)
        self.setMaximumWidth(20)
        self.setMinimumHeight(200)
        
        # Disable mouse tracking for hover events (hover functionality disabled)
        self.setMouseTracking(False)
        
        # Styling - no borders for seamless scrollbar look
        self.setStyleSheet("""
            MinimapWidget {
                background-color: #1e1e1e;
                border: none;
            }
        """)
        
        # Update timer to batch updates
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update)
        
        # Drag tracking
        self.is_dragging = False
        self.drag_start_y = 0
        self.drag_start_viewport = 0.0
        
        # Color filtering
        self.color_filter_enabled = False
        self.filtered_colors = []  # List of QColor objects for filtering (supports multiple)
        self.filtered_color_names = {}  # Dict mapping color hex to human-readable name
        
        self.setMouseTracking(True)
        
        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def set_content(self, text_lines):
        """Update the minimap content with terminal text lines
        
        Draws every line without sampling for perfect synchronization.
        """
        if isinstance(text_lines, str):
            text_lines = text_lines.split('\n')
        
        old_length = len(self.content_lines)
        new_length = len(text_lines)
        
        # Store all lines without sampling
        self.content_lines = text_lines
        self.content_line_indices = list(range(len(text_lines)))
        
        # Store total lines count
        self.total_content_lines = new_length
        
        # Update filtered indices if filter is enabled
        if self.color_filter_enabled and self.filtered_colors:
            # If content length changed, update incrementally
            if new_length != old_length:
                # Do incremental update if we have a previous cache to work from
                # Only skip if cache is completely empty (filter just enabled)
                if self.filtered_line_indices or not self.filtered_indices_dirty:
                    self._update_filtered_indices_incremental(old_length, new_length, text_lines)
                else:
                    # Cache stays dirty and will be fully recalculated on next use
                    pass
            elif new_length == old_length and new_length >= 10000:
                # Buffer at max capacity - lines removed from top, added at bottom
                # Since content length is same but we're streaming, we need to check
                # what changed. The safest approach: do periodic full rescans.
                # Mark cache dirty every N updates to trigger rescan
                if not hasattr(self, '_scrollback_update_count'):
                    self._scrollback_update_count = 0
                self._scrollback_update_count += 1
                
                # Do full rescan every 10 updates or if cache has gaps
                if self._scrollback_update_count >= 10 or len(self.filtered_line_indices) < 10:
                    self.filtered_indices_dirty = True
                    self._scrollback_update_count = 0
                elif self.filtered_line_indices and not self.filtered_indices_dirty:
                    self._update_filtered_indices_for_scrollback(text_lines)
            # If same length and not at buffer limit, keep existing cache (content likely unchanged)
        
        # Schedule update (batch multiple calls)
        if not self.update_timer.isActive():
            self.update_timer.start(100)  # Update at most every 100ms
    
    def _update_filtered_indices_incremental(self, old_length, new_length, text_lines):
        """Update filtered indices incrementally when lines are added/removed
        
        Args:
            old_length: Previous number of lines
            new_length: New number of lines
            text_lines: New content lines
        """
        if new_length > old_length:
            # Lines were added at the end - scan only new lines
            new_lines_start = old_length
            for i in range(new_lines_start, new_length):
                line = text_lines[i]
                color = self.get_line_color(line)
                for filtered_color in self.filtered_colors:
                    if self.colors_match(color, filtered_color):
                        self.filtered_line_indices.append(i)
                        break
            # Keep list sorted
            self.filtered_line_indices.sort()
            # Mark cache as valid after incremental update
            self.filtered_indices_dirty = False
        elif new_length < old_length:
            # Lines were removed from the top (scrollback buffer limit reached)
            # All cached indices need to be decremented by the number of lines removed
            lines_removed = old_length - new_length
            
            # Shift all indices down and filter out any that became negative
            self.filtered_line_indices = [i - lines_removed for i in self.filtered_line_indices if i >= lines_removed]
            
            # Mark cache as valid after incremental update
            self.filtered_indices_dirty = False
        else:
            # Same length but content changed - full rescan needed
            self.filtered_indices_dirty = True
    
    def _update_filtered_indices_for_scrollback(self, text_lines):
        """Update filtered indices when scrollback buffer is at max capacity
        
        When the buffer is full, old lines are removed from top and new lines added at bottom.
        We check the bottom portion of the buffer for new filtered lines since content 
        may have changed significantly since last update.
        
        Args:
            text_lines: Current content lines
        """
        # Get the maximum current index
        max_current_idx = max(self.filtered_line_indices) if self.filtered_line_indices else 0
        
        # Shift all existing indices down by 1 (one line removed from top)
        self.filtered_line_indices = [i - 1 for i in self.filtered_line_indices if i > 0]
        
        # Scan the bottom ~100 lines for any new filtered lines
        # This handles the case where multiple new lines were added since last check
        total_lines = len(text_lines)
        scan_start = max(max_current_idx - 1, total_lines - 100, 0)
        
        for i in range(scan_start, total_lines):
            # Skip if already in our cache
            if i in self.filtered_line_indices:
                continue
            
            line = text_lines[i]
            color = self.get_line_color(line)
            for filtered_color in self.filtered_colors:
                if self.colors_match(color, filtered_color):
                    self.filtered_line_indices.append(i)
                    break
        
        # Keep list sorted
        self.filtered_line_indices.sort()
    
    def set_viewport(self, start_ratio, height_ratio):
        """Set the visible viewport position and size
        
        Args:
            start_ratio: Starting position as ratio of total content (0.0 to 1.0)
            height_ratio: Height of viewport as ratio of total content (0.0 to 1.0)
        """
        self.viewport_start = max(0.0, min(1.0, start_ratio))
        self.viewport_height = max(0.0, min(1.0, height_ratio))
        self.update()
    
    def refresh_colors(self):
        """Refresh the minimap colors based on current preferences"""
        # Reload preferences
        self.prefs_manager = PreferencesManager()
        # Trigger a repaint
        self.update()
    
    def get_line_color(self, line):
        """Determine color based on keywords with severity gradient
        
        Returns QColor based on severity and custom keywords.
        Uses priority system: lower priority number = higher importance.
        KEYWORDS have HIGHEST PRIORITY, then HTTP status codes.
        """
        line_lower = line.lower()
        
        # Check if success/failure colors should be shown
        show_success_failure = self.prefs_manager.get('terminal', 'minimap_show_success_failure_colors', True)
        
        # Built-in keyword detection - HIGHEST PRIORITY
        # Critical Errors - Bright Red
        if any(keyword in line_lower for keyword in ['error', 'exception', 'crash', 'fatal', 'critical']):
            return QColor(255, 100, 100, 200)  # Bright Red
        
        # Failures - Orange/Red
        if any(keyword in line_lower for keyword in ['fail', 'failed', 'failure', 'denied']):
            return QColor(255, 160, 60, 180)  # Orange
        
        # Warnings - Yellow
        if any(keyword in line_lower for keyword in ['warn', 'warning', 'caution']):
            return QColor(255, 220, 100, 180)  # Yellow
        
        # HTTP Status codes - SECOND PRIORITY (after keywords)
        # Use regex patterns to match status codes in proper context to avoid false positives
        # Patterns: "Status: XXX", "HTTP/1.X XXX", or standalone " XXX " with spaces
        
        # Server Errors (Red) - HTTP 5xx
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])5[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(255, 80, 80, 200)  # Bright Red
        
        # Client Errors (Orange) - HTTP 4xx
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])4[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(255, 180, 80, 180)  # Orange
        
        # Redirects (Cyan) - HTTP 3xx
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])3[0-9]{2}(?:\s|$|\))', line_lower):
            return QColor(0, 200, 200, 160)  # Cyan
        
        # Success (Green) - HTTP 2xx
        if re.search(r'(?:status:\s*|http/\d\.\d\s+|[\s\|])2[0-9]{2}(?:\s|$|\))', line_lower):
            if show_success_failure:
                return QColor(100, 255, 100, 180)  # Bright Green
            # If success colors disabled, continue to check other patterns
        
        # Get custom keywords from preferences (for user-defined keywords)
        # CHECK CUSTOM KEYWORDS BEFORE BUILT-IN INFO/DEBUG KEYWORDS
        # This ensures custom keywords have priority over generic info/debug coloring
        custom_keywords = self.prefs_manager.get('terminal', 'minimap_custom_keywords', {})
        
        # Find matching keywords with their priorities
        matches = []
        for keyword, config in custom_keywords.items():
            if keyword.lower() in line_lower:
                # Check if keyword is visible
                if not config.get('visible', True):
                    continue  # Skip invisible keywords
                
                priority = config.get('priority', 99)
                color = config.get('color', '#808080')
                
                # Check if this is a success/info keyword and filter is disabled
                if not show_success_failure:
                    # Priority 5+ are success/info keywords (lower severity)
                    if priority >= 5:
                        continue  # Skip success/info colors when disabled
                
                matches.append((priority, color, keyword))
        
        # Return color of highest priority match (lowest priority number)
        if matches:
            matches.sort(key=lambda x: x[0])  # Sort by priority
            color_hex = matches[0][1]
            # Convert hex color to QColor with some transparency
            color = QColor(color_hex)
            color.setAlpha(180)
            return color
        
        # Success keywords - Green
        if show_success_failure and any(keyword in line_lower for keyword in ['success', 'passed', 'complete']):
            return QColor(80, 240, 80, 180)  # Green
        
        # Info - Blue (including HTTP methods)
        if any(keyword in line_lower for keyword in ['info', 'get ', 'post ', 'put ', 'patch ', 'delete ']):
            return QColor(120, 180, 255, 150)  # Blue
        
        # Debug - Purple
        if any(keyword in line_lower for keyword in ['debug', 'trace', 'verbose']):
            return QColor(180, 140, 255, 150)  # Purple
        
        # Prompt lines (Light Blue) - check before default
        if line.startswith('$') or line.startswith('%') or '@' in line[:20]:
            return QColor(100, 150, 220, 150)  # Light Blue
        
        # Default - has content (Gray)
        if line.strip():
            return QColor(120, 120, 120, 100)  # Gray
        
        # Empty line (very faint)
        return QColor(50, 50, 50, 50)  # Very dark gray
    
    def paintEvent(self, event):
        """Draw scrollbar-style minimap with transparent scroll box showing center color"""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            
            width = self.width()
            height = self.height()
            
            # Background - scrollbar track
            painter.fillRect(0, 0, width, height, QColor(30, 30, 30))
            
            # Draw content as a thin colored strip
            if self.content_lines:
                # Always calculate line_height based on total lines to maintain consistent positioning
                # DON'T use max(1, ...) here - allow fractional line heights for proper positioning
                line_height = height / max(len(self.content_lines), 1)
                
                drawn_rects = []  # Debug: track what we draw
                
                for i, line in enumerate(self.content_lines):
                    y = int(i * line_height)
                    
                    # Get color based on keywords
                    color = self.get_line_color(line)
                    
                    # Apply color filter if enabled (multiple colors supported)
                    if self.color_filter_enabled and self.filtered_colors:
                        # Only show lines matching any of the filtered colors
                        matches_filter = False
                        for filtered_color in self.filtered_colors:
                            if self.colors_match(color, filtered_color):
                                matches_filter = True
                                break
                        if not matches_filter:
                            # Skip drawing non-matching lines (don't draw them at all)
                            continue
                        
                        # When filtering, make lines thicker so they're visible
                        # Use minimum 10 pixels height for filtered lines
                        draw_height = max(1, int(line_height))
                        drawn_rects.append((y, draw_height, color.red(), color.green(), color.blue()))
                    else:
                        # Normal unfiltered view
                        draw_height = max(1, int(line_height))
                    
                    # Draw thin vertical bar across full width
                    painter.fillRect(0, y, width, draw_height, color)
                
                # Debug output for first paint with filtering
                if self.color_filter_enabled and drawn_rects and len(drawn_rects) <= 100:
                    pass  # Debug removed for cleaner output
            
            # Calculate viewport (scroll box) position and dimensions
            viewport_h = max(20, int(self.viewport_height * height))  # Minimum 20px height
            viewport_y = int(self.viewport_start * height)
            
            # Ensure viewport box stays within bounds (important when at bottom)
            if viewport_y + viewport_h > height:
                viewport_y = height - viewport_h
            viewport_y = max(0, viewport_y)
            
            # Get the color at the center of the viewport
            # Calculate center_y position for drawing (always needed for drawing the center box)
            center_y = viewport_y + viewport_h // 2
            
            # Try to get the center line from the terminal's viewport_center_line if available
            # This ensures consistency with line number highlighting, especially during jumps
            center_line_idx = None
            actual_center_line = None
            
            # Try to get center line from terminal widget if available
            from ui.main_window import MainWindow
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, MainWindow):
                    current_terminal = widget.terminal_tabs.get_current_terminal()
                    if (current_terminal and hasattr(current_terminal, 'canvas') and 
                        hasattr(current_terminal.canvas, 'viewport_center_line') and
                        current_terminal.canvas.viewport_center_line >= 0):
                        actual_center_line = current_terminal.canvas.viewport_center_line
                        # Convert actual line index to content_lines index
                        if self.content_line_indices and actual_center_line in self.content_line_indices:
                            center_line_idx = self.content_line_indices.index(actual_center_line)
                        else:
                            center_line_idx = actual_center_line
                        break
                    break
            
            # Fallback: calculate from viewport position if terminal center line not available
            if center_line_idx is None:
                center_line_idx = int((center_y / height) * len(self.content_lines))
                center_line_idx = max(0, min(len(self.content_lines) - 1, center_line_idx))
                
                # Get the actual line index in the full content
                if self.content_line_indices and center_line_idx < len(self.content_line_indices):
                    actual_center_line = self.content_line_indices[center_line_idx]
                else:
                    actual_center_line = center_line_idx
            
            # DON'T emit signal during automatic updates - only emit on user interaction
            # The signal was causing feedback loops where tiny rounding differences
            # would trigger scroll_to_line() repeatedly
            # if actual_center_line is not None and actual_center_line != self.last_center_line:
            #     self.last_center_line = actual_center_line
            #     self.center_line_changed.emit(actual_center_line)
            
            # Get color for the center line
            if self.content_lines and center_line_idx is not None and center_line_idx < len(self.content_lines):
                center_color = self.get_line_color(self.content_lines[center_line_idx])
            else:
                center_color = QColor(120, 120, 120, 100)
            
            # Draw transparent scroll box with border
            # Outer border - stronger opacity
            painter.setPen(QPen(QColor(200, 200, 200, 180), 1))
            painter.setBrush(QBrush(QColor(40, 40, 40, 80)))  # Semi-transparent dark background
            painter.drawRoundedRect(2, viewport_y, width - 4, viewport_h, 3, 3)
            
            # Inner center box showing exact color - funnel if filtering, box otherwise
            center_box_size = 10
            center_box_y = center_y - center_box_size // 2
            
            # Draw center color indicator
            center_color_display = QColor(center_color)
            center_color_display.setAlpha(200)  # Make center color more visible
            painter.setBrush(QBrush(center_color_display))
            painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
            
            if self.color_filter_enabled:
                # Draw funnel shape to indicate filtering is active
                self.draw_funnel(painter, (width - center_box_size) // 2, center_box_y, 
                               center_box_size, center_box_size, center_color_display)
                
                # Draw jump to next/previous filtered line buttons
                self.draw_filter_jump_buttons(painter, width, height, viewport_y, viewport_h)
            else:
                # Draw regular rounded box
                painter.drawRoundedRect(
                    (width - center_box_size) // 2,
                    center_box_y,
                    center_box_size,
                    center_box_size,
                    2, 2
                )
            
        finally:
            # Always end the painter
            painter.end()
    
    def draw_funnel(self, painter, x, y, width, height, color):
        """Draw a funnel shape to indicate filtering
        
        Args:
            painter: QPainter object
            x, y: Top-left corner position
            width, height: Dimensions
            color: QColor for the funnel
        """
        # Funnel shape: wide at top, narrow at bottom
        top_width = width
        bottom_width = width * 0.4
        
        points = [
            QPointF(x, y),                                    # Top-left
            QPointF(x + top_width, y),                        # Top-right
            QPointF(x + top_width - (top_width - bottom_width) / 2, y + height),  # Bottom-right
            QPointF(x + (top_width - bottom_width) / 2, y + height),  # Bottom-left
            QPointF(x, y)                                     # Close path
        ]
        
        polygon = QPolygonF(points)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(polygon)
    
    def draw_filter_jump_buttons(self, painter, width, height, viewport_y, viewport_h):
        """Draw up/down arrow buttons for jumping to next/previous filtered line
        Only shows buttons if there are actually next/previous lines to jump to.
        
        Args:
            painter: QPainter object
            width: Minimap width
            height: Minimap height
            viewport_y: Viewport Y position
            viewport_h: Viewport height
        """
        # Get filtered line indices
        filtered_indices = self.get_filtered_line_indices()
        if not filtered_indices:
            return  # No filtered lines, don't show any buttons
        
        # Get current center line
        center_y = viewport_y + viewport_h // 2
        current_line = int((center_y / height) * len(self.content_lines))
        
        # Check if there are previous filtered lines
        has_previous = any(idx < current_line for idx in filtered_indices)
        
        # Check if there are next filtered lines
        has_next = any(idx > current_line for idx in filtered_indices)
        
        button_size = 16
        button_margin = 4
        
        # Up arrow button (only if there are previous filtered lines)
        if has_previous:
            up_button_y = viewport_y - button_size - button_margin
            if up_button_y >= 0:
                # Draw button background
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.setBrush(QBrush(QColor(60, 60, 60, 200)))
                painter.drawRoundedRect(2, up_button_y, width - 4, button_size, 3, 3)
                
                # Draw up arrow
                arrow_center_x = width // 2
                arrow_center_y = up_button_y + button_size // 2
                arrow_points = [
                    QPointF(arrow_center_x, arrow_center_y - 4),      # Top point
                    QPointF(arrow_center_x - 4, arrow_center_y + 2),  # Bottom left
                    QPointF(arrow_center_x + 4, arrow_center_y + 2),  # Bottom right
                ]
                painter.setPen(QPen(QColor(150, 200, 255), 2))
                painter.setBrush(QBrush(QColor(150, 200, 255)))
                painter.drawPolygon(QPolygonF(arrow_points))
        
        # Down arrow button (only if there are next filtered lines)
        if has_next:
            down_button_y = viewport_y + viewport_h + button_margin
            if down_button_y + button_size <= height:
                # Draw button background
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.setBrush(QBrush(QColor(60, 60, 60, 200)))
                painter.drawRoundedRect(2, down_button_y, width - 4, button_size, 3, 3)
                
                # Draw down arrow
                arrow_center_x = width // 2
                arrow_center_y = down_button_y + button_size // 2
                arrow_points = [
                    QPointF(arrow_center_x, arrow_center_y + 4),      # Bottom point
                    QPointF(arrow_center_x - 4, arrow_center_y - 2),  # Top left
                    QPointF(arrow_center_x + 4, arrow_center_y - 2),  # Top right
                ]
                painter.setPen(QPen(QColor(150, 200, 255), 2))
                painter.setBrush(QBrush(QColor(150, 200, 255)))
                painter.drawPolygon(QPolygonF(arrow_points))
    
    def get_filtered_line_indices(self):
        """Get list of line indices that match the current filter
        
        Returns cached indices if available, otherwise recalculates.
        
        Returns:
            List of line indices (0-based) that match the filter
        """
        if not self.color_filter_enabled or not self.filtered_colors:
            return []
        
        # Return cached indices if still valid
        if not self.filtered_indices_dirty and self.filtered_line_indices:
            # Validate cache: check if a sample of cached indices still match the filter
            # This detects when scrollback has moved content significantly
            if len(self.content_lines) > 0:
                # Check first, middle, and last cached indices
                sample_indices = []
                if len(self.filtered_line_indices) >= 3:
                    sample_indices = [
                        self.filtered_line_indices[0],
                        self.filtered_line_indices[len(self.filtered_line_indices) // 2],
                        self.filtered_line_indices[-1]
                    ]
                else:
                    sample_indices = self.filtered_line_indices[:]
                
                invalid_count = 0
                for idx in sample_indices:
                    # Check if index is out of bounds
                    if idx < 0 or idx >= len(self.content_lines):
                        invalid_count += 1
                        continue
                    
                    # Check if line at this index still matches the filter
                    line = self.content_lines[idx]
                    color = self.get_line_color(line)
                    matches = False
                    for filtered_color in self.filtered_colors:
                        if self.colors_match(color, filtered_color):
                            matches = True
                            break
                    
                    if not matches:
                        invalid_count += 1
                
                # If any sample failed validation, cache is stale - trigger full rescan
                if invalid_count > 0:
                    self.filtered_indices_dirty = True
                    # Fall through to recalculation below
                else:
                    # Cache is valid
                    return self.filtered_line_indices
        
        # Recalculate filtered indices
        self.filtered_line_indices = []
        for i, line in enumerate(self.content_lines):
            color = self.get_line_color(line)
            for filtered_color in self.filtered_colors:
                if self.colors_match(color, filtered_color):
                    self.filtered_line_indices.append(i)
                    break
        
        self.filtered_indices_dirty = False
        return self.filtered_line_indices
    
    def jump_to_next_filtered_line(self):
        """Jump to the next filtered line after current position"""
        filtered_indices = self.get_filtered_line_indices()
        if not filtered_indices:
            return
        
        # Try to get terminal from MainWindow, otherwise look for TextViewer canvas
        current_line = self._get_current_viewport_line()
        if current_line is None:
            return
        
        # Add tolerance to avoid jumping to the same line
        # Use tolerance of 0 to find the immediate next filtered line
        tolerance = 0
        search_from = current_line + tolerance
        
        # Find next: First filtered line > search_from
        target_line = None
        for line_idx in filtered_indices:
            if line_idx > search_from:
                target_line = line_idx
                break
        
        # Wrap to first if no next line found
        if target_line is None and filtered_indices:
            first_line = filtered_indices[0]
            if current_line > first_line + tolerance or current_line < first_line - tolerance:
                target_line = first_line
        
        # Jump: Scroll to line
        if target_line is not None:
            self._scroll_to_line(target_line)
    
    def jump_to_previous_filtered_line(self):
        """Jump to the previous filtered line before current position"""
        filtered_indices = self.get_filtered_line_indices()
        if not filtered_indices:
            return
        
        # Try to get terminal from MainWindow, otherwise look for TextViewer canvas
        current_line = self._get_current_viewport_line()
        if current_line is None:
            return
        
        # Subtract tolerance to avoid jumping to the same line or one too close
        tolerance = 1  # At least 1 line away
        search_from = current_line - tolerance
        
        # Find previous: Last filtered line < search_from
        target_line = None
        for line_idx in reversed(filtered_indices):
            if line_idx < search_from:
                target_line = line_idx
                break
        
        # Wrap to last if no previous line found
        if target_line is None and filtered_indices:
            last_line = filtered_indices[-1]
            if current_line < last_line - tolerance or current_line > last_line + tolerance:
                target_line = last_line
        
        # Jump: Scroll to line
        if target_line is not None:
            self._scroll_to_line(target_line)
    
    def _get_current_viewport_line(self):
        """Get the current viewport center line from terminal or text viewer"""
        
        # Try TextViewer canvas FIRST (search through all top level widgets)
        for widget in QApplication.topLevelWidgets():
            # Check if this is a TextViewerDialog
            if hasattr(widget, 'canvas') and hasattr(widget.canvas, 'viewport_center_line'):
                # Verify this widget contains our minimap
                if hasattr(widget, 'minimap'):
                    if widget.minimap == self:
                        line = widget.canvas.viewport_center_line
                        return line
        
        # Fall back to MainWindow terminal
        from ui.main_window import MainWindow
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, MainWindow):
                current_terminal = widget.terminal_tabs.get_current_terminal()
                if current_terminal and hasattr(current_terminal, 'canvas'):
                    if hasattr(current_terminal.canvas, 'viewport_center_line'):
                        line = current_terminal.canvas.viewport_center_line
                        return line
                break
        
        return None
    
    def _scroll_to_line(self, line_number):
        """Scroll to a specific line in terminal or text viewer"""
        # Try TextViewer dialog FIRST
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'scroll_to_line') and hasattr(widget, 'minimap'):
                if widget.minimap == self:
                    widget.scroll_to_line(line_number)
                    return
        
        # Fall back to MainWindow terminal
        from ui.main_window import MainWindow
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, MainWindow):
                current_terminal = widget.terminal_tabs.get_current_terminal()
                if current_terminal and hasattr(current_terminal, 'scroll_to_line'):
                    current_terminal.scroll_to_line(line_number)
                    return
                break


    
    def show_preview(self):
        """Show the extended preview widget"""
        if not self.content_lines:
            return
        
        # Calculate center line
        height = self.height()
        viewport_h = max(20, int(self.viewport_height * height))
        viewport_y = int(self.viewport_start * height)
        if viewport_y + viewport_h > height:
            viewport_y = height - viewport_h
        viewport_y = max(0, viewport_y)
        
        center_y = viewport_y + viewport_h // 2
        center_line_idx = int((center_y / height) * len(self.content_lines))
        center_line_idx = max(0, min(len(self.content_lines) - 1, center_line_idx))
        
        # Create preview widget if needed
        if not self.preview_widget:
            self.preview_widget = ExtendedPreviewWidget()
            self.preview_widget.line_clicked.connect(self.on_preview_line_clicked)
        
        # Update preview content
        self.preview_widget.set_content(self.content_lines, center_line_idx, 10)
        
        # Position preview to the left of minimap
        global_pos = self.mapToGlobal(QPoint(0, viewport_y + viewport_h // 2))
        preview_x = global_pos.x() - self.preview_widget.width() - 10
        preview_y = global_pos.y() - self.preview_widget.height() // 2
        
        self.preview_widget.move(preview_x, preview_y)
        self.preview_widget.show()
        self.preview_widget.raise_()
    
    def hide_preview(self):
        """Hide the extended preview widget"""
        if self.preview_widget:
            self.preview_widget.hide()
    
    def on_preview_line_clicked(self, line_idx):
        """Handle click on preview line"""
        # Jump to the clicked line - position it at the top of viewport
        if len(self.content_lines) > 0:
            ratio = line_idx / len(self.content_lines)
            # Position the clicked line at the top of viewport instead of centering
            new_pos = ratio
            new_pos = max(0.0, min(1.0 - self.viewport_height, new_pos))
            self.position_clicked.emit(new_pos)
    
    def colors_match(self, color1, color2, tolerance=10):
        """Check if two colors match within a tolerance
        
        Args:
            color1: First QColor
            color2: Second QColor
            tolerance: RGB difference tolerance (0-255), default 10 for strict matching
            
        Returns:
            bool: True if colors match within tolerance
        """
        if not color1 or not color2:
            return False
        
        r_diff = abs(color1.red() - color2.red())
        g_diff = abs(color1.green() - color2.green())
        b_diff = abs(color1.blue() - color2.blue())
        
        return r_diff <= tolerance and g_diff <= tolerance and b_diff <= tolerance
    
    def show_context_menu(self, pos):
        """Show context menu for color filtering with multiple color selection"""
        # Only show context menu if right-clicking on the viewport box
        height = self.height()
        viewport_h = max(20, int(self.viewport_height * height))
        viewport_y = int(self.viewport_start * height)
        
        # Ensure viewport box stays within bounds
        if viewport_y + viewport_h > height:
            viewport_y = height - viewport_h
        viewport_y = max(0, viewport_y)
        
        # Check if click is within viewport box
        if not (viewport_y <= pos.y() <= viewport_y + viewport_h):
            return
        
        menu = QMenu(self)
        
        # Collect all unique colors from the content
        color_map = {}  # Maps color hex to (QColor, name, count)
        
        for line in self.content_lines:
            color = self.get_line_color(line)
            color_hex = color.name()
            
            if color_hex not in color_map:
                color_name = self.get_color_name(color)
                color_map[color_hex] = [color, color_name, 0]
            color_map[color_hex][2] += 1
        
        # Sort colors by count (most common first)
        sorted_colors = sorted(color_map.items(), key=lambda x: x[1][2], reverse=True)
        
        # Add title
        title_action = QAction("Filter by Color (select multiple):", self)
        title_action.setEnabled(False)
        menu.addAction(title_action)
        
        menu.addSeparator()
        
        # Add each color as a checkbox widget (stays open when clicked)
        for color_hex, (color, name, count) in sorted_colors:
            # Create a custom widget with checkbox
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            
            checkbox = QCheckBox(f"{name} ({count} lines)")
            
            # Check if this color is currently filtered
            is_checked = False
            for filtered_color in self.filtered_colors:
                if self.colors_match(color, filtered_color):
                    is_checked = True
                    break
            checkbox.setChecked(is_checked)
            
            # Connect checkbox state change
            checkbox.stateChanged.connect(lambda state, c=color, n=name: 
                                         self.toggle_color_filter(c, n, state == Qt.Checked))
            
            layout.addWidget(checkbox)
            widget.setLayout(layout)
            
            # Create QWidgetAction to hold the checkbox
            widget_action = QWidgetAction(menu)
            widget_action.setDefaultWidget(widget)
            menu.addAction(widget_action)
        
        menu.addSeparator()
        
        # Clear all filters action
        clear_filter_action = QAction("✖ Clear All Filters", self)
        clear_filter_action.setEnabled(self.color_filter_enabled)
        clear_filter_action.triggered.connect(self.clear_color_filter)
        menu.addAction(clear_filter_action)
        
        menu.exec_(self.mapToGlobal(pos))
    
    def get_color_name(self, color):
        """Get a human-readable name for a color
        
        Args:
            color: QColor object
            
        Returns:
            str: Color name
        """
        # Check common colors
        r, g, b = color.red(), color.green(), color.blue()
        
        # Reds (errors)
        if r > 200 and g < 150 and b < 150:
            return "Errors (Red)"
        # Oranges (warnings/failures)
        elif r > 200 and g > 100 and g < 200 and b < 150:
            return "Warnings (Orange)"
        # Yellows
        elif r > 200 and g > 180 and b < 150:
            return "Warnings (Yellow)"
        # Greens (success)
        elif r < 150 and g > 180 and b < 150:
            return "Success (Green)"
        # Blues (info)
        elif r < 150 and g < 200 and b > 180:
            return "Info (Blue)"
        # Cyans
        elif r < 100 and g > 150 and b > 150:
            return "Redirects (Cyan)"
        # Purples
        elif r > 150 and g < 180 and b > 180:
            return "Debug (Purple)"
        # Grays
        elif abs(r - g) < 30 and abs(g - b) < 30 and abs(r - b) < 30:
            return "Normal (Gray)"
        else:
            return f"Custom ({color.name()})"
    
    def toggle_color_filter(self, color, name, checked):
        """Toggle a color filter on/off
        
        Args:
            color: QColor to filter by
            name: Human-readable name
            checked: Whether the filter should be enabled
        """
        color_hex = color.name()
        
        if checked:
            # Add color to filter list if not already there
            already_exists = False
            for filtered_color in self.filtered_colors:
                if self.colors_match(color, filtered_color):
                    already_exists = True
                    break
            
            if not already_exists:
                self.filtered_colors.append(color)
                self.filtered_color_names[color_hex] = name
        else:
            # Remove color from filter list
            self.filtered_colors = [fc for fc in self.filtered_colors 
                                   if not self.colors_match(fc, color)]
            if color_hex in self.filtered_color_names:
                del self.filtered_color_names[color_hex]
        
        # Update filter enabled state
        self.color_filter_enabled = len(self.filtered_colors) > 0
        
        # Mark cache as dirty when filter changes
        self.filtered_indices_dirty = True
        
        self.update()
    
    def clear_color_filter(self):
        """Clear all color filters"""
        self.color_filter_enabled = False
        self.filtered_colors = []
        self.filtered_color_names = {}
        
        # Clear cached indices
        self.filtered_line_indices = []
        self.filtered_indices_dirty = True
        
        self.update()
    
    def mousePressEvent(self, event):
        """Handle click to jump to position or start dragging viewport or click filter buttons"""
        if event.button() == Qt.LeftButton:
            mouse_y = event.y()
            height = self.height()
            
            # Calculate viewport position in pixels with bounds checking
            viewport_h = max(20, int(self.viewport_height * height))
            viewport_y = int(self.viewport_start * height)
            
            # Ensure viewport box stays within bounds
            if viewport_y + viewport_h > height:
                viewport_y = height - viewport_h
            viewport_y = max(0, viewport_y)
            
            # Check for filter navigation button clicks when filtering is active
            if self.color_filter_enabled:
                # Get filtered line indices to check if buttons should exist
                filtered_indices = self.get_filtered_line_indices()
                if filtered_indices:
                    # Get current center line
                    center_y = viewport_y + viewport_h // 2
                    current_line = int((center_y / height) * len(self.content_lines))
                    
                    # Check if there are previous/next filtered lines
                    has_previous = any(idx < current_line for idx in filtered_indices)
                    has_next = any(idx > current_line for idx in filtered_indices)
                    
                    button_size = 16
                    button_margin = 4
                    
                    # Check up button click (only if button exists)
                    if has_previous:
                        up_button_y = viewport_y - button_size - button_margin
                        if up_button_y >= 0 and up_button_y <= mouse_y <= up_button_y + button_size:
                            self.jump_to_previous_filtered_line()
                            return
                    
                    # Check down button click (only if button exists)
                    if has_next:
                        down_button_y = viewport_y + viewport_h + button_margin
                        if down_button_y + button_size <= height and down_button_y <= mouse_y <= down_button_y + button_size:
                            self.jump_to_next_filtered_line()
                            return
            
            # Check if click is within viewport box (for dragging)
            if viewport_y <= mouse_y <= viewport_y + viewport_h:
                self.is_dragging = True
                self.drag_start_y = mouse_y
                self.drag_start_viewport = self.viewport_start
                self.setCursor(Qt.ClosedHandCursor)
            else:
                # Click outside viewport - jump to that position
                # Position the viewport to start at the clicked position
                ratio = mouse_y / height
                # Position viewport to start at clicked position instead of centering
                new_pos = ratio
                new_pos = max(0.0, min(1.0 - self.viewport_height, new_pos))
                self.position_clicked.emit(new_pos)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to show line editor for jumping to specific line"""
        if event.button() == Qt.LeftButton:
            mouse_y = event.y()
            height = self.height()
            
            # Calculate viewport position
            viewport_h = max(20, int(self.viewport_height * height))
            viewport_y = int(self.viewport_start * height)
            if viewport_y + viewport_h > height:
                viewport_y = height - viewport_h
            viewport_y = max(0, viewport_y)
            
            # Check if double-clicking on viewport box
            if viewport_y <= mouse_y <= viewport_y + viewport_h:
                self.show_line_editor()
    
    def show_line_editor(self):
        """Show a line editor to jump to a specific line"""
        if not self.line_editor:
            self.line_editor = QLineEdit()
            # Use Popup instead of ToolTip to allow keyboard input
            self.line_editor.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
            self.line_editor.setAttribute(Qt.WA_DeleteOnClose, False)
            self.line_editor.setFocusPolicy(Qt.StrongFocus)
            self.line_editor.setAlignment(Qt.AlignCenter)
            self.line_editor.setStyleSheet("""
                QLineEdit {
                    background-color: #3d3d3d;
                    color: #ffffff;
                    border: 3px solid #4a90e2;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            self.line_editor.returnPressed.connect(self.on_line_editor_submit)
            self.line_editor.editingFinished.connect(self.hide_line_editor)
        
        # Hide preview while editing
        self.hide_preview()
        
        # Calculate center position
        height = self.height()
        viewport_h = max(20, int(self.viewport_height * height))
        viewport_y = int(self.viewport_start * height)
        if viewport_y + viewport_h > height:
            viewport_y = height - viewport_h
        viewport_y = max(0, viewport_y)
        
        # Position editor next to minimap
        global_pos = self.mapToGlobal(QPoint(0, viewport_y + viewport_h // 2))
        editor_width = 180
        editor_height = 45
        editor_x = global_pos.x() - editor_width - 15
        editor_y = global_pos.y() - editor_height // 2
        
        self.line_editor.setGeometry(editor_x, editor_y, editor_width, editor_height)
        
        # Calculate current line
        center_y = viewport_y + viewport_h // 2
        center_line_idx = int((center_y / height) * len(self.content_lines)) if len(self.content_lines) > 0 else 0
        center_line_idx = max(0, min(len(self.content_lines) - 1, center_line_idx))
        current_line = center_line_idx + 1
        
        self.line_editor.setPlaceholderText(f"Go to line (1-{len(self.content_lines)})")
        self.line_editor.setText(str(current_line))
        self.line_editor.selectAll()
        self.line_editor.show()
        self.line_editor.raise_()
        self.line_editor.activateWindow()
        self.line_editor.setFocus()
    
    def on_line_editor_submit(self):
        """Handle line number submission"""
        try:
            line_num = int(self.line_editor.text())
            if 1 <= line_num <= len(self.content_lines):
                # Convert to 0-based index
                target_line = line_num - 1
                
                # Calculate position to center on this line
                if len(self.content_lines) > 0:
                    ratio = target_line / len(self.content_lines)
                    new_pos = ratio - (self.viewport_height / 2)
                    new_pos = max(0.0, min(1.0 - self.viewport_height, new_pos))
                    self.position_clicked.emit(new_pos)
        except ValueError:
            pass
        
        self.hide_line_editor()
    
    def hide_line_editor(self):
        """Hide the line editor"""
        if self.line_editor:
            self.line_editor.hide()
    
    def mouseMoveEvent(self, event):
        """Handle dragging to scroll (hover preview disabled)"""
        if self.is_dragging:
            # Calculate how much we've moved
            delta_y = event.y() - self.drag_start_y
            height = self.height()
            
            # Convert pixel movement to ratio
            delta_ratio = delta_y / height
            
            # Calculate new viewport position
            new_pos = self.drag_start_viewport + delta_ratio
            new_pos = max(0.0, min(1.0 - self.viewport_height, new_pos))
            
            # Emit viewport_dragged signal (for scrolling terminal)
            self.viewport_dragged.emit(new_pos)
        else:
            # Update cursor based on hover position for filter buttons only
            mouse_y = event.y()
            height = self.height()
            
            # Calculate viewport position in pixels with bounds checking
            viewport_h = max(20, int(self.viewport_height * height))
            viewport_y = int(self.viewport_start * height)
            
            # Ensure viewport box stays within bounds
            if viewport_y + viewport_h > height:
                viewport_y = height - viewport_h
            viewport_y = max(0, viewport_y)
            
            # Check if hovering over filter navigation buttons
            if self.color_filter_enabled:
                # Get filtered line indices to check if buttons should exist
                filtered_indices = self.get_filtered_line_indices()
                if filtered_indices:
                    # Get current center line
                    center_y = viewport_y + viewport_h // 2
                    current_line = int((center_y / height) * len(self.content_lines))
                    
                    # Check if there are previous/next filtered lines
                    has_previous = any(idx < current_line for idx in filtered_indices)
                    has_next = any(idx > current_line for idx in filtered_indices)
                    
                    button_size = 16
                    button_margin = 4
                    
                    # Check up button hover (only if button exists)
                    if has_previous:
                        up_button_y = viewport_y - button_size - button_margin
                        if up_button_y >= 0 and up_button_y <= mouse_y <= up_button_y + button_size:
                            self.setCursor(Qt.PointingHandCursor)
                            self.setToolTip("Jump to previous filtered line")
                            return
                    
                    # Check down button hover (only if button exists)
                    if has_next:
                        down_button_y = viewport_y + viewport_h + button_margin
                        if down_button_y + button_size <= height and down_button_y <= mouse_y <= down_button_y + button_size:
                            self.setCursor(Qt.PointingHandCursor)
                            self.setToolTip("Jump to next filtered line")
                            return
            
            if viewport_y <= mouse_y <= viewport_y + viewport_h:
                self.setCursor(Qt.OpenHandCursor)
                self.setToolTip("Double-click: Jump to line")
            else:
                self.setCursor(Qt.ArrowCursor)
                self.setToolTip("")
    
    def leaveEvent(self, event):
        """Handle mouse leaving widget"""
        super().leaveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Stop dragging"""
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.setCursor(Qt.ArrowCursor)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for scrolling"""
        # Calculate scroll delta
        delta = event.angleDelta().y()
        scroll_amount = -delta / 1200.0  # Normalize to reasonable scroll amount
        
        new_pos = self.viewport_start + scroll_amount
        new_pos = max(0.0, min(1.0 - self.viewport_height, new_pos))
        
        self.position_clicked.emit(new_pos)


class MinimapPanel(QWidget):
    """Panel containing minimap with title"""
    
    position_clicked = pyqtSignal(float)
    viewport_dragged = pyqtSignal(float)  # Forward viewport drag signal
    center_line_changed = pyqtSignal(int)  # Forward center line signal
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Style the panel itself to have no margins/padding
        self.setStyleSheet("""
            MinimapPanel {
                background-color: #1e1e1e;
                border: none;
                margin: 0px;
                padding: 0px;
            }
        """)
        
        # No title label for scrollbar style - just the minimap
        
        # Minimap widget
        self.minimap = MinimapWidget()
        self.minimap.position_clicked.connect(self.position_clicked.emit)
        self.minimap.viewport_dragged.connect(self.viewport_dragged.emit)
        self.minimap.center_line_changed.connect(self.center_line_changed.emit)
        layout.addWidget(self.minimap, 1)
    
    def set_content(self, text_lines):
        """Update minimap content"""
        self.minimap.set_content(text_lines)
    
    def set_viewport(self, start_ratio, height_ratio):
        """Update viewport indicator"""
        self.minimap.set_viewport(start_ratio, height_ratio)
    
    def refresh_colors(self):
        """Refresh the minimap colors based on current preferences"""
        self.minimap.refresh_colors()
