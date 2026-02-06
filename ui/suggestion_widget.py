"""Autocomplete suggestion widget for terminal commands and file/folder names"""

from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QVBoxLayout,
                             QApplication, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer, QPoint, QEvent
from PyQt5.QtGui import QFont, QColor, QIcon, QPainter, QPixmap, QPen, QKeyEvent
import os
import glob
import shutil


class SuggestionItem(QListWidgetItem):
    """Custom list item for suggestions with type information"""
    
    def __init__(self, text, item_type="file", parent=None):
        super().__init__(text, parent)
        self.item_type = item_type  # "file", "folder", "command"
        self.setData(Qt.UserRole, item_type)
    
    def icon_pixmap(self):
        """Generate an icon based on item type"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.item_type == "folder":
            # Blue folder icon - more detailed
            folder_color = QColor('#5BA8FF')
            painter.setPen(QPen(folder_color, 1))
            painter.setBrush(QColor(folder_color))
            # Folder body
            painter.drawRect(3, 6, 10, 8)
            # Folder tab
            folder_tab_path = [
                QPoint(3, 6),
                QPoint(5, 4),
                QPoint(8, 4),
                QPoint(10, 6)
            ]
            painter.drawPolygon(folder_tab_path)
        elif self.item_type == "command":
            # Purple cube icon - more detailed
            cmd_color = QColor('#BC3FBC')
            painter.setPen(QPen(cmd_color, 1))
            painter.setBrush(QColor(cmd_color))
            # Draw a 3D cube
            # Front face
            painter.drawRect(4, 4, 8, 8)
            # Top face (trapezoid)
            top_path = [
                QPoint(4, 4),
                QPoint(6, 2),
                QPoint(14, 2),
                QPoint(12, 4)
            ]
            painter.drawPolygon(top_path)
            # Right face (trapezoid)
            right_path = [
                QPoint(12, 4),
                QPoint(14, 2),
                QPoint(14, 10),
                QPoint(12, 12)
            ]
            painter.drawPolygon(right_path)
        else:
            # White file icon - document shape
            file_color = QColor('#E5E5E5')
            painter.setPen(QPen(file_color, 1))
            painter.setBrush(QColor(file_color))
            # Document with folded corner
            # Main body
            painter.drawRect(3, 2, 10, 12)
            # Folded corner (small triangle at top-right)
            corner_path = [
                QPoint(11, 2),
                QPoint(13, 4),
                QPoint(13, 2)
            ]
            painter.drawPolygon(corner_path)
            # Draw lines to make it look like a document
            painter.setPen(QPen(QColor('#2b2b2b'), 1))
            painter.drawLine(5, 6, 11, 6)
            painter.drawLine(5, 8, 11, 8)
            painter.drawLine(5, 10, 9, 10)
        
        painter.end()
        return pixmap


class SuggestionWidget(QFrame):
    """Dropdown widget showing autocomplete suggestions"""
    
    item_selected = pyqtSignal(str)  # Emits when user selects a suggestion
    dismissed = pyqtSignal()  # Emits when suggestions are dismissed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # IMPORTANT: Use BypassWindowManagerHint to keep within application
        # DO NOT use WindowStaysOnTopHint - that causes it to appear over other apps
        
        # Use ToolTip flag without WindowStaysOnTopHint
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)  # Don't activate when shown
        self.setFocusPolicy(Qt.NoFocus)  # Don't steal focus - let parent handle keys
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)  # Allow mouse clicks on suggestions
        # Important: Don't accept keyboard events at all
        self.setAttribute(Qt.WA_InputMethodEnabled, False)
        # Make sure this widget doesn't grab keyboard focus
        self.setWindowModality(Qt.NonModal)
        # Prevent this widget from receiving keyboard events
        self.setAttribute(Qt.WA_KeyCompression, False)
        # Constrain to parent window - don't show over other applications
        self.setParent(parent)  # Ensure parent relationship
        
        # Setup UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Menlo", 12))
        self.list_widget.setFocusPolicy(Qt.NoFocus)  # Don't steal focus
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: #0d47a1;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #424242;
            }
        """)
        
        self.list_widget.itemActivated.connect(self.on_item_activated)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        
        # Make sure list widget doesn't intercept keyboard events
        self.list_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)  # Allow mouse clicks
        self.list_widget.installEventFilter(self)  # Install event filter to catch key events
        
        layout.addWidget(self.list_widget)
        
        # Hide by default
        self.hide()
        
        # Current selection index
        self.current_index = 0
    
    def set_suggestions(self, suggestions, prefix=""):
        """Set the suggestions to display"""
        self.list_widget.clear()
        
        if not suggestions:
            self.hide()
            return
        
        for suggestion in suggestions[:20]:  # Limit to 20 items
            item = SuggestionItem(suggestion['text'], suggestion.get('type', 'file'))
            self.list_widget.addItem(item)
            
            # Set icon
            icon = QIcon(item.icon_pixmap())
            item.setIcon(icon)
            
            # Add type hint if provided
            if 'hint' in suggestion:
                item.setText(f"{suggestion['text']}  {suggestion['hint']}")
        
        # Select first item
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.current_index = 0
        
        # Adjust size
        self.adjust_size()
    
    def adjust_size(self):
        """Adjust widget size based on content"""
        count = self.list_widget.count()
        if count == 0:
            return
        
        # Calculate optimal size
        item_height = self.list_widget.sizeHintForRow(0)
        max_items = min(count, 10)  # Show max 10 items at once
        
        width = 300
        height = item_height * max_items + 4  # Add padding
        
        self.list_widget.setFixedSize(width, height)
        self.setFixedSize(width + 2, height + 2)  # Account for border
    
    def show_at_position(self, pos):
        """Show the widget at the given position"""
        
        # CRITICAL: Set all focus-blocking attributes BEFORE showing
        self.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_InputMethodEnabled, False)
        
        # Find the main application window to parent to
        parent_window = self.parent()
        if parent_window:
            # Walk up the parent chain to find the main window
            current = parent_window
            while current and current.parent():
                current = current.parent()
                if current and current.isWindow():
                    parent_window = current
                    break
        
        if parent_window and parent_window.isWindow():
            # Set parent to main window to constrain visibility
            self.setParent(parent_window)
            # Ensure window flags don't allow appearing over other apps
            # Remove WindowStaysOnTopHint if it exists
            flags = Qt.ToolTip | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint
            self.setWindowFlags(flags)
            
            # Get parent window geometry
            parent_geo = parent_window.geometry()
            # Position is relative to parent, constrain to parent window
            widget_width = self.width()
            widget_height = self.height()
            
            # Constrain position to parent window bounds
            constrained_x = max(0, min(pos.x(), parent_geo.width() - widget_width))
            constrained_y = max(0, min(pos.y(), parent_geo.height() - widget_height))
            
            self.move(QPoint(constrained_x, constrained_y))
        else:
            self.move(pos)
        
        self.show()
        self.raise_()
        
        # Ensure parent canvas keeps focus immediately after showing
        if self.parent():
            parent = self.parent()
            while parent and not hasattr(parent, 'canvas'):
                parent = parent.parent()
            if parent and hasattr(parent, 'canvas'):
                # Use QTimer to restore focus after widget is shown
                QTimer.singleShot(10, lambda: parent.canvas.setFocus())
    
    def on_item_activated(self, item):
        """Handle item selection via Enter/Tab"""
        text = item.text().split('  ')[0]  # Remove hint if present
        self.item_selected.emit(text)
        self.hide()
    
    def on_item_clicked(self, item):
        """Handle item selection via mouse click"""
        text = item.text().split('  ')[0]  # Remove hint if present
        self.item_selected.emit(text)
        self.hide()
    
    def navigate_up(self):
        """Navigate to previous suggestion"""
        if self.list_widget.count() == 0:
            return
        
        self.current_index = max(0, self.current_index - 1)
        self.list_widget.setCurrentRow(self.current_index)
    
    def navigate_down(self):
        """Navigate to next suggestion"""
        if self.list_widget.count() == 0:
            return
        
        self.current_index = min(self.list_widget.count() - 1, self.current_index + 1)
        self.list_widget.setCurrentRow(self.current_index)
    
    def get_selected_text(self):
        """Get the currently selected suggestion text"""
        item = self.list_widget.currentItem()
        if item:
            text = item.text().split('  ')[0]  # Remove hint if present
            return text
        return None
    
    def select_current(self):
        """Select the currently highlighted item"""
        item = self.list_widget.currentItem()
        if item:
            self.on_item_activated(item)
    
    def keyPressEvent(self, event):
        """Handle keyboard navigation - but we shouldn't receive these events due to NoFocus"""
        # This should never be called since we have NoFocus, but if it is, ignore everything
        # All keyboard handling is done in the parent terminal widget
        event.ignore()
        return
    
    def event(self, event):
        """Override event to prevent this widget from receiving keyboard events"""
        # If this is a keyboard event, ignore it completely - let parent handle it
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.Shortcut):
            event.ignore()
            return False  # Don't process, let it bubble to parent
        return super().event(event)
    
    def eventFilter(self, obj, event):
        """Filter events to prevent list widget from stealing focus"""
        if obj == self.list_widget:
            if event.type() == QEvent.KeyPress:
                # Block ALL key events from reaching list widget
                # The terminal handles all keyboard input
                event.ignore()
                return True  # Block the event completely
            elif event.type() == QEvent.FocusIn:
                # Prevent list widget from gaining focus
                if self.parent():
                    # Give focus back to parent terminal canvas
                    parent = self.parent()
                    while parent and not hasattr(parent, 'canvas'):
                        parent = parent.parent()
                    if parent and hasattr(parent, 'canvas'):
                        parent.canvas.setFocus()
                return True  # Block focus event
        return super().eventFilter(obj, event)
    
    def hideEvent(self, event):
        """Reset selection when hidden"""
        self.current_index = 0
        super().hideEvent(event)


class SuggestionManager:
    """Manager for providing suggestions based on context"""
    
    # Common shell commands
    COMMON_COMMANDS = [
        'ls', 'cd', 'pwd', 'cat', 'echo', 'grep', 'find', 'mkdir', 'rm', 'cp', 'mv',
        'touch', 'chmod', 'chown', 'ps', 'kill', 'top', 'df', 'du', 'tar', 'zip',
        'unzip', 'wget', 'curl', 'git', 'python', 'pip', 'npm', 'node', 'java',
        'clear', 'exit', 'history', 'man', 'which', 'whereis', 'locate', 'head',
        'tail', 'less', 'more', 'vim', 'nano', 'emacs', 'ssh', 'scp', 'rsync',
        'gzip', 'gunzip', 'bzip2', 'xz', 'chmod', 'chown', 'sudo', 'su', 'whoami',
        'date', 'cal', 'uptime', 'uname', 'hostname', 'ifconfig', 'ping', 'netstat'
    ]
    
    # Commands that expect file/folder arguments
    FILE_COMMANDS = ['cd', 'cat', 'less', 'more', 'vim', 'nano', 'emacs', 'head', 'tail',
                    'grep', 'find', 'rm', 'cp', 'mv', 'chmod', 'chown', 'touch', 'mkdir']
    
    def __init__(self):
        self.current_directory = os.path.expanduser("~")
        # Get PATH commands
        self.path_commands = self._get_path_commands()
    
    def _get_path_commands(self):
        """Get all executable commands from PATH"""
        commands = set()
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        
        for path_dir in path_dirs:
            if os.path.isdir(path_dir):
                try:
                    for item in os.listdir(path_dir):
                        full_path = os.path.join(path_dir, item)
                        if os.access(full_path, os.X_OK) and os.path.isfile(full_path):
                            commands.add(item)
                except (OSError, PermissionError):
                    pass
        
        return sorted(list(commands))
    
    def set_current_directory(self, directory):
        """Set the current working directory for file suggestions"""
        # Clean up directory name - strip any trailing brackets that might have been captured
        if directory:
            directory = directory.rstrip(']')
        self.current_directory = directory
    
    def get_command_suggestions(self, prefix):
        """Get command suggestions matching the prefix"""
        suggestions = []
        prefix_lower = prefix.lower()
        
        # Search in common commands
        for cmd in self.COMMON_COMMANDS:
            if cmd.lower().startswith(prefix_lower):
                suggestions.append({
                    'text': cmd,
                    'type': 'command',
                    'hint': 'command'
                })
        
        # Search in PATH commands
        for cmd in self.path_commands:
            if cmd.lower().startswith(prefix_lower) and cmd not in [s['text'] for s in suggestions]:
                suggestions.append({
                    'text': cmd,
                    'type': 'command',
                    'hint': 'command'
                })
        
        # Remove duplicates and sort
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s['text'] not in seen:
                seen.add(s['text'])
                unique_suggestions.append(s)
        
        return sorted(unique_suggestions, key=lambda x: x['text'])[:20]
    
    def get_file_suggestions(self, prefix, base_dir=None):
        """Get file/folder suggestions matching the prefix"""
        
        # Clean up any trailing brackets from current_directory (safety check)
        if self.current_directory:
            self.current_directory = self.current_directory.rstrip(']')
        
        if base_dir is None:
            base_dir = self.current_directory
        else:
            # Clean up any trailing brackets from base_dir (safety check)
            base_dir = base_dir.rstrip(']') if base_dir else None
        
        suggestions = []
        
        try:
            original_prefix = prefix
            # Expand ~ in prefix
            if prefix.startswith('~'):
                prefix = os.path.expanduser(prefix)
            
            # Handle absolute paths
            if os.path.isabs(prefix):
                search_dir = os.path.dirname(prefix) or '/'
                pattern = os.path.basename(prefix) + '*'
            elif '/' in prefix:
                # Relative path with directory
                search_dir = os.path.join(base_dir, os.path.dirname(prefix))
                pattern = os.path.basename(prefix) + '*'
            else:
                # Simple filename
                search_dir = base_dir
                pattern = prefix + '*'
            
            # Ensure search_dir is absolute
            if not os.path.isabs(search_dir):
                search_dir = os.path.abspath(os.path.join(base_dir, search_dir))
            
            
            if not os.path.isdir(search_dir):
                return suggestions
            
            # Initialize matches list
            matches = []
            
            # Get matches - use listdir for better handling of spaces and special chars
            # glob can sometimes have issues with spaces in filenames
            try:
                all_items = os.listdir(search_dir)
                prefix_lower = prefix.lower()
                
                # Filter items that match the prefix (case-insensitive)
                # Clean prefix to remove any whitespace issues
                prefix_lower_clean = prefix_lower.strip()
                
                for item in all_items:
                    item_lower = item.lower()
                    # Direct prefix match (handles "pe" matching "pem files")
                    if item_lower.startswith(prefix_lower_clean):
                        full_path = os.path.join(search_dir, item)
                        matches.append(full_path)
                
                # Also try glob as a fallback (for wildcard patterns)
                if not matches:
                    search_pattern = os.path.join(search_dir, pattern)
                    glob_matches = glob.glob(search_pattern)
                    matches.extend(glob_matches)
            except (OSError, PermissionError):
                # Fallback to glob only if listdir fails
                try:
                    search_pattern = os.path.join(search_dir, pattern)
                    matches = glob.glob(search_pattern)
                except (OSError, PermissionError):
                    matches = []
            
            for match in matches:
                # Skip hidden files if prefix doesn't start with .
                basename = os.path.basename(match)
                if basename.startswith('.') and not prefix.startswith('.'):
                    continue
                
                # Get the actual basename (handles spaces and special chars)
                if os.path.isdir(match):
                    suggestions.append({
                        'text': basename,
                        'type': 'folder',
                        'hint': 'folder'
                    })
                else:
                    suggestions.append({
                        'text': basename,
                        'type': 'file',
                        'hint': 'file'
                    })
            
            # Sort: folders first, then files, both alphabetically
            suggestions.sort(key=lambda x: (x['type'] != 'folder', x['text'].lower()))
            
        except (OSError, PermissionError) as e:
            pass
        
        result = suggestions[:20]
        return result
    
    def parse_command(self, command_line):
        """Parse command line to determine what to suggest
        
        Priority: Files/Folders > Commands
        When both could match, prefer files/folders
        """
        parts = command_line.strip().split()
        
        if not parts:
            # Empty command - suggest commands
            return {
                'type': 'command',
                'prefix': '',
                'command': None
            }
        
        command = parts[0]
        remaining = command_line[len(command):].strip() if len(command_line) > len(command) else ''
        
        # Check if we're typing a command (first word)
        # But first, check if there's any text that could be a file/folder path
        if len(parts) > 1:
            # We have a command and an argument - prioritize files/folders
            last_arg = parts[-1].strip()  # Remove any trailing whitespace
            
            # Check if the command expects file arguments
            if command.lower() in self.FILE_COMMANDS:
                return {
                    'type': 'file',
                    'prefix': last_arg,
                    'command': command
                }
            
            # Even if not a file command, check if argument looks like a path
            # (contains / or . or starts with ~)
            if '/' in last_arg or '.' in last_arg or last_arg.startswith('~'):
                return {
                    'type': 'file',
                    'prefix': last_arg,
                    'command': command
                }
        
        # Check if we're still typing the command (no space after command or partial command)
        if not remaining or (remaining and not remaining.startswith(' ')):
            # Still typing the command - but check if it could be a file/folder first
            # If it contains path-like characters, prefer file suggestions
            if '/' in command or command.startswith('~') or command.startswith('./') or command.startswith('../'):
                return {
                    'type': 'file',
                    'prefix': command,
                    'command': None
                }
            
            # Otherwise, suggest commands
            return {
                'type': 'command',
                'prefix': command,
                'command': None
            }
        
        # Command is complete, check if it expects file arguments
        if command.lower() in self.FILE_COMMANDS:
            # Get the last argument or empty string
            if len(parts) > 1:
                last_arg = parts[-1]
            else:
                last_arg = ''
            
            return {
                'type': 'file',
                'prefix': last_arg,
                'command': command
            }
        
        # Default: suggest commands (but only if we're clearly typing a command)
        return {
            'type': 'command',
            'prefix': command if len(parts) == 1 else '',
            'command': command if len(parts) > 1 else None
        }
    
    def get_combined_suggestions(self, prefix, base_dir=None):
        """Get combined suggestions prioritizing files/folders over commands"""
        if base_dir is None:
            base_dir = self.current_directory
        
        # Get file suggestions first
        file_suggestions = self.get_file_suggestions(prefix, base_dir)
        
        # Only get command suggestions if no file suggestions found or prefix is clearly a command
        command_suggestions = []
        if not file_suggestions or (not '/' in prefix and not prefix.startswith('~') and not prefix.startswith('./')):
            command_suggestions = self.get_command_suggestions(prefix)
        
        # Combine: files/folders first, then commands
        combined = file_suggestions + command_suggestions
        
        # Remove duplicates (keep first occurrence)
        seen = set()
        unique_suggestions = []
        for s in combined:
            if s['text'] not in seen:
                seen.add(s['text'])
                unique_suggestions.append(s)
        
        return unique_suggestions[:20]  # Limit to 20

