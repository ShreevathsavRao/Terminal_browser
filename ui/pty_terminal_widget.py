"""PTY-based terminal widget for proper interactive command support"""

from PyQt5.QtWidgets import (QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, 
                             QApplication, QLabel, QSpinBox, QDoubleSpinBox, QPushButton)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QTextCursor, QFont, QColor, QKeyEvent, QTextCharFormat
import os
import sys
import pty
import select
import termios
import struct
import fcntl
import signal
import re
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/terminal_browser_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PTYReader(QThread):
    """Thread to read from PTY master"""
    
    output_received = pyqtSignal(str)
    
    def __init__(self, master_fd):
        super().__init__()
        self.master_fd = master_fd
        self.running = True
        
    def run(self):
        """Read from PTY and emit output"""
        while self.running:
            try:
                # Use select to avoid blocking
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)
                if ready:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        text = data.decode('utf-8', errors='replace')
                        self.output_received.emit(text)
                    else:
                        break
            except OSError:
                break
    
    def stop(self):
        """Stop the reader thread"""
        self.running = False


class TerminalTextEdit(QTextEdit):
    """Custom QTextEdit that intercepts Tab key for terminal completion"""
    
    def event(self, event):
        """Override event to intercept Tab key before focus navigation"""
        if event.type() == QEvent.KeyPress:
            key_event = QKeyEvent(event)
            
            # Intercept Tab and Shift+Tab to prevent focus navigation
            if key_event.key() == Qt.Key_Tab or key_event.key() == Qt.Key_Backtab:
                # Call keyPressEvent directly and mark event as accepted
                self.keyPressEvent(key_event)
                event.accept()
                return True
            
            # Let Cmd/Ctrl+C, Cmd/Ctrl+V, Cmd/Ctrl+A pass through normally
            # These are handled in keyPressEvent
            modifiers = key_event.modifiers()
            if (modifiers & Qt.ControlModifier) or (modifiers & Qt.MetaModifier):
                if key_event.key() in [Qt.Key_C, Qt.Key_V, Qt.Key_A, Qt.Key_X]:
                    # Let these pass through to keyPressEvent
                    pass
        
        # For all other events, use default processing
        return super().event(event)


class PTYTerminalWidget(QWidget):
    """Terminal widget with PTY support for interactive commands"""
    
    command_finished = pyqtSignal(int)
    
    # Maximum number of lines to keep in scrollback buffer
    # Note: This is a performance optimization - QTextEdit becomes slow with very large documents
    # Set to 10000 to match pyte_terminal_widget behavior
    MAX_SCROLLBACK_LINES = 10000
    
    def __init__(self, shell=None):
        super().__init__()
        self.shell = shell or os.environ.get('SHELL', '/bin/bash')
        self.master_fd = None
        self.slave_fd = None
        self.pid = None
        self.reader_thread = None
        self.current_directory = "/"  # Start from system root
        
        # State persistence across output chunks
        self.pending_escape_buffer = ""  # Buffer for incomplete escape sequences
        self.persist_overwrite_mode = False  # Track overwrite mode across chunks
        self.suppress_overwrite_count = 0  # Suppress overwrite mode after line clear
        
        # Flag to temporarily disable PTY resize during tab/group switching
        self.resize_enabled = True
        
        # Track current PTY size to avoid redundant updates
        self.current_pty_rows = 0
        self.current_pty_cols = 0
        
        # Flag to track first output to handle duplicate initial prompt
        self.is_first_output = True
        
        # Track if user is at the bottom for auto-scroll behavior
        self.user_at_bottom = True
        
        self.init_ui()
        self.start_shell()
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Settings for font and spacing
        self.font_size = 13
        self.line_spacing = 1.2
        
        # Control bar
        control_bar = QWidget()
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(5, 5, 5, 5)
        
        # Font size control
        font_size_label = QLabel("Font Size:")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(self.font_size)
        self.font_size_spin.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #555; padding: 3px;")
        self.font_size_spin.valueChanged.connect(self.change_font_size)
        
        # Line spacing control
        spacing_label = QLabel("Line Spacing:")
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(1.0, 2.5)
        self.spacing_spin.setSingleStep(0.1)
        self.spacing_spin.setValue(self.line_spacing)
        self.spacing_spin.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #555; padding: 3px;")
        self.spacing_spin.valueChanged.connect(self.change_line_spacing)
        
        control_layout.addWidget(font_size_label)
        control_layout.addWidget(self.font_size_spin)
        control_layout.addSpacing(10)
        control_layout.addWidget(spacing_label)
        control_layout.addWidget(self.spacing_spin)
        control_layout.addSpacing(20)
        
        # Debug logging button
        self.debug_btn = QPushButton("View Debug Log")
        self.debug_btn.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px;")
        self.debug_btn.clicked.connect(self.show_debug_log)
        control_layout.addWidget(self.debug_btn)
        
        control_layout.addStretch()
        
        control_bar.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0;")
        layout.addWidget(control_bar)
        
        # Terminal display - use custom QTextEdit that handles Tab correctly
        self.terminal_display = TerminalTextEdit()
        self.terminal_display.setReadOnly(False)
        self.update_font_and_spacing()
        self.terminal_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                padding: 10px;
            }
        """)
        
        # Enable context menu for copy/paste
        self.terminal_display.setContextMenuPolicy(Qt.DefaultContextMenu)
        
        # Connect key events
        self.terminal_display.keyPressEvent = self.handle_key_press
        
        # Connect mouse events to prevent cursor movement
        self.terminal_display.mousePressEvent = self.handle_mouse_press
        self.terminal_display.mouseReleaseEvent = self.handle_mouse_release
        
        # Connect scroll bar events to track user position
        scrollbar = self.terminal_display.verticalScrollBar()
        if scrollbar:
            scrollbar.valueChanged.connect(self._on_scroll_changed)
        
        # ANSI color map
        self.ansi_colors = {
            '0': None,  # Reset
            '1': 'bold',  # Bold
            '30': QColor('#2e3436'),  # Black
            '31': QColor('#cc0000'),  # Red
            '32': QColor('#4e9a06'),  # Green
            '33': QColor('#c4a000'),  # Yellow
            '34': QColor('#3465a4'),  # Blue
            '35': QColor('#75507b'),  # Magenta
            '36': QColor('#06989a'),  # Cyan
            '37': QColor('#d3d7cf'),  # White
            '39': None,  # Default foreground
            '49': None,  # Default background
            '90': QColor('#555753'),  # Bright Black (Gray)
            '91': QColor('#ef2929'),  # Bright Red
            '92': QColor('#8ae234'),  # Bright Green
            '93': QColor('#fce94f'),  # Bright Yellow
            '94': QColor('#729fcf'),  # Bright Blue
            '95': QColor('#ad7fa8'),  # Bright Magenta
            '96': QColor('#34e2e2'),  # Bright Cyan
            '97': QColor('#eeeeec'),  # Bright White
        }
        
        # Current text format
        self.current_format = QTextCharFormat()
        self.current_format.setForeground(QColor('#e0e0e0'))
        
        layout.addWidget(self.terminal_display)
        
        # Connect resize event
        self.terminal_display.resizeEvent = self.handle_resize
    
    def handle_resize(self, event):
        """Handle terminal display resize"""
        # Call the original resize event
        from PyQt5.QtWidgets import QTextEdit
        QTextEdit.resizeEvent(self.terminal_display, event)
        
        # Update PTY size only if resize is enabled (not during tab switching)
        if hasattr(self, 'resize_enabled') and self.resize_enabled:
            if hasattr(self, 'master_fd') and self.master_fd is not None:
                logger.debug(f"handle_resize: Calling set_pty_size (resize_enabled={self.resize_enabled})")
                self.set_pty_size()
        else:
            logger.debug(f"handle_resize: Skipping set_pty_size (resize_enabled={getattr(self, 'resize_enabled', 'N/A')})")
    
    def update_font_and_spacing(self):
        """Update font and line spacing"""
        font = QFont("Menlo", self.font_size)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        self.terminal_display.setFont(font)
        
        # Set line height using document
        fmt = QTextCharFormat()
        fmt.setFontPointSize(self.font_size)
        cursor = self.terminal_display.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.mergeCharFormat(fmt)
        
        # Set line spacing using HTML if needed
        doc = self.terminal_display.document()
        option = doc.defaultTextOption()
        # Note: Line spacing in QTextEdit is limited, but font size helps
    
    def change_font_size(self, size):
        """Change font size"""
        self.font_size = size
        self.update_font_and_spacing()
        # Don't update PTY size on font change - avoids prompt redraw
        # Font change is just a visual preference, shell doesn't need to know
        logger.debug(f"change_font_size: Font changed to {size}, NOT updating PTY size")
    
    def change_line_spacing(self, spacing):
        """Change line spacing"""
        self.line_spacing = spacing
        # Line spacing is harder to control in QTextEdit
        # But we can adjust font leading
        font = self.terminal_display.font()
        font.setLetterSpacing(QFont.PercentageSpacing, 100)
        self.terminal_display.setFont(font)
    
    def show_debug_log(self):
        """Open debug log in system viewer"""
        import subprocess
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', '-a', 'Console', '/tmp/terminal_browser_debug.log'])
            elif sys.platform == 'win32':  # Windows
                subprocess.run(['notepad', '/tmp/terminal_browser_debug.log'])
            else:  # Linux
                subprocess.run(['xdg-open', '/tmp/terminal_browser_debug.log'])
        except Exception as e:
            logger.error(f"Could not open debug log: {e}")
            # Fallback: print last 50 lines
            try:
                with open('/tmp/terminal_browser_debug.log', 'r') as f:
                    lines = f.readlines()
            except:
                pass
    
    def start_shell(self):
        """Start a shell in a PTY"""
        try:
            # Create PTY
            self.master_fd, self.slave_fd = pty.openpty()
            
            # Set PTY size
            self.set_pty_size()
            
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
                
                # Change to root directory before starting shell
                os.chdir('/')
                
                # Set environment
                env = os.environ.copy()
                env['TERM'] = 'xterm-256color'
                env['COLORTERM'] = 'truecolor'
                env['CLICOLOR'] = '1'
                env['CLICOLOR_FORCE'] = '1'
                env['LS_COLORS'] = 'di=34:ln=35:so=32:pi=33:ex=31:bd=34;46:cd=34;43:su=30;41:sg=30;46:tw=30;42:ow=30;43'
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
                self.reader_thread.output_received.connect(self.append_output)
                self.reader_thread.start()
                
        except Exception as e:
            self.append_output(f"Error starting shell: {e}\n", color="red")
    
    def set_pty_size(self):
        """Set the PTY size based on terminal display size"""
        if self.master_fd is not None:
            # Calculate size based on terminal display widget
            if hasattr(self, 'terminal_display'):
                # Get font metrics
                font_metrics = self.terminal_display.fontMetrics()
                char_width = font_metrics.averageCharWidth()
                char_height = font_metrics.height()
                
                # Get widget size
                width = self.terminal_display.viewport().width() - 20  # Account for padding
                height = self.terminal_display.viewport().height() - 20
                
                # Calculate rows and columns
                cols = max(80, int(width / char_width))
                rows = max(24, int(height / char_height))
                
                logger.debug(f"Calculated PTY size: {rows}x{cols} (current: {self.current_pty_rows}x{self.current_pty_cols})")
            else:
                # Fallback to reasonable defaults
                rows = 24
                cols = 80
            
            # Only update if size actually changed
            if rows != self.current_pty_rows or cols != self.current_pty_cols:
                logger.debug(f"PTY size changed from {self.current_pty_rows}x{self.current_pty_cols} to {rows}x{cols} - updating")
                self.current_pty_rows = rows
                self.current_pty_cols = cols
                s = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)
            else:
                logger.debug(f"PTY size unchanged ({rows}x{cols}) - skipping update")
    
    def update_pty_size_from_widget(self):
        """Update PTY size when widget is resized (called from splitter movements)"""
        if self.resize_enabled:
            logger.debug("update_pty_size_from_widget: Updating PTY size from widget resize")
            self.set_pty_size()
        else:
            logger.debug("update_pty_size_from_widget: Skipping PTY size update (resize disabled)")
    
    def handle_mouse_press(self, event):
        """Handle mouse press to prevent cursor movement from end"""
        from PyQt5.QtWidgets import QTextEdit
        
        # Allow right-click for context menu (copy/paste)
        if event.button() == Qt.RightButton:
            QTextEdit.mousePressEvent(self.terminal_display, event)
            return
        
        # For left-click, allow selection but move cursor back to end after
        # This allows text selection for copying while keeping input at the end
        if event.button() == Qt.LeftButton:
            # If user is clicking and dragging to select text, allow it
            QTextEdit.mousePressEvent(self.terminal_display, event)
            
            # Only move cursor to end if no selection is being made
            # We'll move to end when mouse is released if there's no selection
            return
        
        # For any other button, just ignore it
        event.accept()
    
    def handle_mouse_release(self, event):
        """Handle mouse release to move cursor back to end if no selection"""
        from PyQt5.QtWidgets import QTextEdit
        
        # Call the default handler first
        QTextEdit.mouseReleaseEvent(self.terminal_display, event)
        
        # If there's no text selection, move cursor to end
        cursor = self.terminal_display.textCursor()
        if not cursor.hasSelection():
            cursor.movePosition(QTextCursor.End)
            self.terminal_display.setTextCursor(cursor)
        
        event.accept()
    
    def handle_key_press(self, event: QKeyEvent):
        """Handle key presses and send to PTY"""
        # Always ensure cursor is at the end before processing any key
        # This prevents typing in the middle of previous output
        cursor = self.terminal_display.textCursor()
        if not cursor.hasSelection():
            cursor.movePosition(QTextCursor.End)
            self.terminal_display.setTextCursor(cursor)
        
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()
        
        # Log the key press for debugging
        logger.debug(f"Key pressed: key={key}, text=repr({text}), modifiers={modifiers}, "
                    f"key_name={event.key()}, text_bytes={text.encode('utf-8') if text else b''}")
        
        # Handle copy/paste shortcuts
        if modifiers & Qt.ControlModifier or modifiers & Qt.MetaModifier:
            if key == Qt.Key_C and self.terminal_display.textCursor().hasSelection():
                # Copy if there's a selection
                logger.debug("Copy operation")
                QApplication.clipboard().setText(self.terminal_display.textCursor().selectedText())
                return
            elif key == Qt.Key_V:
                # Paste from clipboard
                clipboard_text = QApplication.clipboard().text()
                logger.debug(f"Paste operation: {repr(clipboard_text)}")
                # Use bracketed paste mode to prevent shell from echoing/processing
                # characters individually, which causes line redraw artifacts
                self.write_to_pty('\x1b[200~')  # Start bracketed paste
                self.write_to_pty(clipboard_text)
                self.write_to_pty('\x1b[201~')  # End bracketed paste
                return
            elif key == Qt.Key_A:
                # Select all
                logger.debug("Select all operation")
                self.terminal_display.selectAll()
                return
            elif key == Qt.Key_X and self.terminal_display.textCursor().hasSelection():
                # Cut
                logger.debug("Cut operation")
                QApplication.clipboard().setText(self.terminal_display.textCursor().selectedText())
                return
        
        # Handle Ctrl shortcuts for terminal control
        if modifiers & Qt.ControlModifier:
            if key == Qt.Key_C and not self.terminal_display.textCursor().hasSelection():
                # Ctrl+C without selection - send SIGINT
                logger.debug("Sending Ctrl+C (SIGINT)")
                self.write_to_pty('\x03')
                return
            elif key == Qt.Key_D:
                # Ctrl+D - send EOF
                logger.debug("Sending Ctrl+D (EOF)")
                self.write_to_pty('\x04')
                return
            elif key == Qt.Key_Z:
                # Ctrl+Z - send SIGTSTP
                logger.debug("Sending Ctrl+Z (SIGTSTP)")
                self.write_to_pty('\x1a')
                return
            elif key == Qt.Key_L:
                # Ctrl+L - send clear to shell
                logger.debug("Sending Ctrl+L (clear)")
                self.write_to_pty('\x0c')
                return
        
        # Handle regular keys - IMPORTANT: prevent QTextEdit from processing these
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            logger.debug("Sending Enter/Return")
            self.write_to_pty('\n')
            event.accept()
            return
        elif key == Qt.Key_Backspace:
            # Try multiple backspace sequences for compatibility
            logger.debug("Backspace pressed - sending \\x08")
            self.write_to_pty('\x08')  # Try BS (backspace) instead of DEL
            event.accept()
            return
        elif key == Qt.Key_Delete:
            self.write_to_pty('\x1b[3~')  # Delete key escape sequence
            event.accept()
            return
        elif key == Qt.Key_Tab:
            self.write_to_pty('\t')
            event.accept()
            return
        elif key == Qt.Key_Up:
            self.write_to_pty('\x1b[A')
            event.accept()
            return
        elif key == Qt.Key_Down:
            self.write_to_pty('\x1b[B')
            event.accept()
            return
        elif key == Qt.Key_Right:
            self.write_to_pty('\x1b[C')
            event.accept()
            return
        elif key == Qt.Key_Left:
            self.write_to_pty('\x1b[D')
            event.accept()
            return
        elif key == Qt.Key_Home:
            self.write_to_pty('\x1b[H')
            event.accept()
            return
        elif key == Qt.Key_End:
            self.write_to_pty('\x1b[F')
            event.accept()
            return
        elif key == Qt.Key_PageUp:
            self.write_to_pty('\x1b[5~')
            event.accept()
            return
        elif key == Qt.Key_PageDown:
            self.write_to_pty('\x1b[6~')
            event.accept()
            return
        elif text:
            self.write_to_pty(text)
            event.accept()
            return
    
    def write_to_pty(self, data):
        """Write data to the PTY"""
        if self.master_fd is not None:
            try:
                logger.debug(f"Writing to PTY: {repr(data)}, bytes={data.encode('utf-8')}")
                os.write(self.master_fd, data.encode('utf-8'))
            except OSError as e:
                logger.error(f"Error writing to PTY: {e}")
    
    def parse_ansi_and_append(self, text):
        """Parse ANSI codes and append formatted text"""
        # Log raw output for debugging
        logger.debug(f"Raw output received: {repr(text[:200])}")  # First 200 chars
        
        # Prepend any pending incomplete escape sequence from previous chunk
        if self.pending_escape_buffer:
            text = self.pending_escape_buffer + text
            self.pending_escape_buffer = ""
            logger.debug(f"Prepended buffered escape sequence, text now starts with: {repr(text[:50])}")
        
        # Check if text ends with an incomplete escape sequence and buffer it
        if '\x1b' in text:
            last_escape_pos = text.rfind('\x1b')
            if last_escape_pos != -1:
                remaining = text[last_escape_pos:]
                should_buffer = False
                
                # Check if it's a CSI sequence without terminator
                if len(remaining) > 1 and remaining[1] == '[':
                    # CSI sequences end with a letter
                    has_terminator = any(c.isalpha() for c in remaining[2:])
                    if not has_terminator:
                        should_buffer = True
                # Check if it's an OSC sequence without terminator  
                elif len(remaining) > 1 and remaining[1] == ']':
                    # OSC sequences end with \x07 or \x1b\\
                    if '\x07' not in remaining and '\x1b\\' not in remaining:
                        should_buffer = True
                # Check for other escape sequences
                elif len(remaining) < 3:
                    # Potentially incomplete, buffer it
                    should_buffer = True
                
                if should_buffer:
                    self.pending_escape_buffer = remaining
                    text = text[:last_escape_pos]
                    logger.debug(f"Buffering incomplete escape sequence: {repr(remaining)}")
        
        # Early return if all text was buffered
        if not text:
            return
        
        cursor = self.terminal_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Process character by character to handle special chars like backspace
        i = 0
        current_fmt = QTextCharFormat()
        current_fmt.setForeground(QColor('#e0e0e0'))
        current_fmt.setFontPointSize(self.font_size)
        
        # Use persistent overwrite mode that carries across chunks
        overwrite_mode = self.persist_overwrite_mode
        
        while i < len(text):
            ch = text[i]
            
            # Decrement suppress counter for each character processed
            if self.suppress_overwrite_count > 0:
                self.suppress_overwrite_count -= 1
            
            # Handle backspace - move cursor back one position
            if ch == '\x08':
                # Check if there's a following space (backspace-space-backspace pattern for deletion)
                if i + 2 < len(text) and text[i+1:i+3] == ' \x08':
                    # This is a delete sequence: \x08 \x08 (backspace, space, backspace)
                    # Move back, write space to clear, move back again
                    if cursor.position() > 0:
                        cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
                        cursor.deleteChar()  # Delete the character
                        self.terminal_display.setTextCursor(cursor)
                    i += 3  # Skip the space and second backspace
                else:
                    # Simple backspace for line editing - delete the previous character
                    # The shell uses this when redrawing the line (e.g., '\x08ls' means delete one char and write 'ls')
                    if cursor.position() > 0:
                        cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
                        cursor.deleteChar()
                        self.terminal_display.setTextCursor(cursor)
                    i += 1
                continue
            
            # Handle newline
            elif ch == '\n':
                cursor.insertText('\n', current_fmt)
                cursor = self.terminal_display.textCursor()
                overwrite_mode = False  # Reset overwrite on newline
                self.suppress_overwrite_count = 0  # Reset suppress counter on newline
                i += 1
                continue
            
            # Handle tab - convert to spaces
            elif ch == '\t':
                cursor.insertText('    ', current_fmt)  # 4 spaces
                cursor = self.terminal_display.textCursor()
                i += 1
                continue
            
            # Handle carriage return
            elif ch == '\r':
                i += 1
                # Check if next char is \n - this is a common line ending (CRLF)
                if i < len(text) and text[i] == '\n':
                    # CRLF sequence - treat as single newline
                    cursor.insertText('\n', current_fmt)
                    cursor = self.terminal_display.textCursor()
                    overwrite_mode = False
                    i += 1
                else:
                    # Check for '\r\x1b[K' pattern (carriage return + erase line) - common in paste/redraw
                    if i + 2 < len(text) and text[i:i+3] == '\x1b[K':
                        # This is a line redraw: go to start and clear to end
                        cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.MoveAnchor)
                        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        self.terminal_display.setTextCursor(cursor)
                        cursor = self.terminal_display.textCursor()
                        i += 3  # Skip the \x1b[K
                        overwrite_mode = False  # Don't enable overwrite after clearing
                        # Suppress overwrite mode for the next several characters
                        # This prevents issues with paste sequences like '\r\x1b[K...\r'
                        self.suppress_overwrite_count = 10
                        continue
                    # Check for '\r <spaces> \r' pattern (zsh right prompt) - skip it entirely
                    # This pattern is: \r followed by spaces, then another \r
                    j = i
                    while j < len(text) and text[j] == ' ':
                        j += 1
                    if j < len(text) and text[j] == '\r':
                        # Skip this entire sequence (it's the zsh rprompt)
                        i = j + 1
                        continue
                    # Standalone \r - handle based on suppress state
                    if self.suppress_overwrite_count > 0:
                        # We're in suppress mode (after line clear) - ignore this \r completely
                        # This prevents cursor repositioning during paste sequences
                        continue
                    # Normal mode: move to beginning of line and enable overwrite mode
                    cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.MoveAnchor)
                    self.terminal_display.setTextCursor(cursor)
                    overwrite_mode = True
                continue
            
            # Handle escape sequences
            elif ch == '\x1b':
                # Find the end of the escape sequence
                match = None
                
                # Try to match various escape sequence patterns
                remaining = text[i:]
                
                # Title sequence
                if remaining.startswith('\x1b]0;'):
                    end = remaining.find('\x07')
                    if end != -1:
                        i += end + 1
                        continue
                
                # CSI sequences
                if len(remaining) > 1 and remaining[1] == '[':
                    # Match CSI sequences: [<params><letter> or [<params>~
                    # Params can include: numbers, semicolons, ?, >, =, etc.
                    m = re.match(r'\x1b\[([?>=<0-9;]*[A-Za-z~])', remaining)
                    if m:
                        seq = m.group(1)
                        cmd = seq[-1]
                        params_str = seq[:-1]
                        
                        # Skip private/special sequences (starting with ?, >, =, <)
                        if params_str and params_str[0] in '?>=<':
                            # These are terminal mode settings, just skip them
                            i += len(m.group(0))
                            continue
                        
                        # Handle specific CSI commands
                        if cmd == '~':
                            # Handle sequences ending with ~ (like bracketed paste markers)
                            if params_str == '200':
                                # Start bracketed paste - just skip
                                pass
                            elif params_str == '201':
                                # End bracketed paste - just skip
                                pass
                            # Skip other ~ sequences (function keys, etc.)
                            i += len(m.group(0))
                            continue
                        elif cmd == 'K':
                            # Erase line
                            if not params_str or params_str == '0':
                                # Erase from cursor to end of line
                                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif params_str == '1':
                                # Erase from start of line to cursor
                                cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif params_str == '2':
                                # Erase entire line
                                cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.MoveAnchor)
                                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            overwrite_mode = False  # Reset after erase
                        elif cmd == 'J':
                            # Clear screen/display
                            if not params_str or params_str == '0':
                                # Clear from cursor to end of screen
                                # In a QTextEdit context at end of document, this means clear to end of current line
                                # Check if we're on the last line
                                cursor_block = cursor.block()
                                doc = self.terminal_display.document()
                                last_block = doc.lastBlock()
                                
                                if cursor_block == last_block:
                                    # On last line - just clear to end of this line
                                    cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
                                    cursor.removeSelectedText()
                                else:
                                    # Not on last line - clear to end of document
                                    cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                                    cursor.removeSelectedText()
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif params_str == '1':
                                # Clear from start of screen to cursor
                                cursor.movePosition(QTextCursor.Start, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif params_str == '2':
                                # Clear entire screen
                                self.terminal_display.clear()
                                cursor = self.terminal_display.textCursor()
                            elif params_str == '3':
                                # Clear scrollback - same as clear screen for us
                                self.terminal_display.clear()
                                cursor = self.terminal_display.textCursor()
                            overwrite_mode = False  # Reset after clear
                        elif cmd == 'H':
                            # Move cursor to position (row, col)
                            # For simplicity, we'll move to start of document
                            if not params_str or params_str == '1;1' or params_str == ';':
                                cursor.movePosition(QTextCursor.Start)
                                self.terminal_display.setTextCursor(cursor)
                        elif cmd == 'G':
                            # Move cursor to column
                            # Move to start of current line
                            cursor.movePosition(QTextCursor.StartOfLine)
                            self.terminal_display.setTextCursor(cursor)
                        elif cmd in 'ABCD':
                            # Cursor movement - A=up, B=down, C=forward, D=back
                            # Parse the count parameter (default is 1 if not specified)
                            count = int(params_str) if params_str and params_str.isdigit() else 1
                            
                            if cmd == 'A':
                                # Move cursor up
                                cursor.movePosition(QTextCursor.Up, QTextCursor.MoveAnchor, count)
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif cmd == 'B':
                                # Move cursor down
                                cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, count)
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif cmd == 'C':
                                # Move cursor forward (right)
                                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, count)
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            elif cmd == 'D':
                                # Move cursor back (left)
                                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, count)
                                self.terminal_display.setTextCursor(cursor)
                                cursor = self.terminal_display.textCursor()
                            # Reset overwrite mode after cursor movement
                            overwrite_mode = False
                        elif cmd == 'm':
                            # SGR - Color/style code
                            params = params_str.split(';') if params_str else ['0']
                            reverse_video = False
                            for param in params:
                                if param == '0' or param == '':
                                    # Reset
                                    current_fmt = QTextCharFormat()
                                    current_fmt.setForeground(QColor('#e0e0e0'))
                                    current_fmt.setFontPointSize(self.font_size)
                                    reverse_video = False
                                elif param == '1':
                                    # Bold
                                    current_fmt.setFontWeight(QFont.Bold)
                                elif param == '7':
                                    # Reverse video - mark that we're in reverse video mode
                                    # This is used by zsh for the right prompt marker
                                    reverse_video = True
                                elif param in ['22', '24', '27']:
                                    # 22: Normal intensity
                                    # 24: Not underlined
                                    # 27: Not reversed
                                    if param == '22':
                                        current_fmt.setFontWeight(QFont.Normal)
                                    elif param == '27':
                                        reverse_video = False
                                elif param == '39':
                                    # Default foreground color
                                    current_fmt.setForeground(QColor('#e0e0e0'))
                                elif param == '49':
                                    # Default background - just ignore for now
                                    pass
                                elif param == '4':
                                    # Underline - ignore for now
                                    pass
                                elif param in self.ansi_colors:
                                    color = self.ansi_colors[param]
                                    if isinstance(color, QColor):
                                        current_fmt.setForeground(color)
                        
                        i += len(m.group(0))
                        continue
                
                # Single character escapes (like \x1b=, \x1b>, etc.)
                if len(remaining) > 1 and remaining[1] in '=><':
                    i += 2  # Skip the escape and the character
                    continue
                
                # Other escape sequences - try to skip them
                if len(remaining) > 1:
                    # Try to find the end of the sequence
                    # Most escape sequences end with a letter
                    for j in range(2, min(len(remaining), 10)):
                        if remaining[j].isalpha():
                            i += j + 1
                            break
                    else:
                        i += 2  # Just skip two chars if we can't find end
                    continue
                else:
                    i += 1
                    continue
            
            # Regular character - insert or overwrite
            else:
                if overwrite_mode:
                    # Overwrite mode: delete character at cursor position first (if not at end of line)
                    # Check if we're at the end of the line
                    cursor_pos = cursor.position()
                    cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.MoveAnchor)
                    at_end = (cursor_pos == cursor.position())
                    
                    # Move back to original position
                    cursor.setPosition(cursor_pos)
                    
                    if not at_end:
                        # Not at end of line - delete one character and insert new one
                        cursor.deleteChar()
                    
                    # Insert the new character
                    cursor.insertText(ch, current_fmt)
                    
                    # Keep overwrite mode active until we hit a newline or explicit reset
                    # (backspace sequences typically overwrite multiple characters)
                else:
                    # Normal insert mode
                    cursor.insertText(ch, current_fmt)
                
                cursor = self.terminal_display.textCursor()
                i += 1
        
        self.terminal_display.setTextCursor(cursor)
        
        # Persist overwrite mode for next chunk
        self.persist_overwrite_mode = overwrite_mode
        
        # Trim old lines if buffer is too large
        self._trim_scrollback_buffer()
        
        # Get scrollbar state before scheduling scroll
        scrollbar = self.terminal_display.verticalScrollBar()
        scroll_max_before_timer = scrollbar.maximum() if scrollbar else 0
        scroll_pos_before_timer = scrollbar.value() if scrollbar else 0
        
        # Auto-scroll to bottom after layout update
        # Use QTimer to ensure document layout is complete before scrolling
        QTimer.singleShot(0, self._scroll_to_bottom)
        
        # Old approach below - commenting out for now
        return
        
        # Remove/handle various escape sequences
        # Remove title sequences
        text = re.sub(r'\x1b\]0;[^\x07]*\x07', '', text)
        # Remove bracketed paste mode
        text = text.replace('\x1b[?2004h', '')
        text = text.replace('\x1b[?2004l', '')
        # Remove application cursor keys
        text = text.replace('\x1b[?1h', '')
        text = text.replace('\x1b[?1l', '')
        # Remove application keypad
        text = text.replace('\x1b=', '')
        text = text.replace('\x1b>', '')
        # Remove cursor save/restore
        text = text.replace('\x1b[s', '')
        text = text.replace('\x1b[u', '')
        
        # Handle cursor movement and clear sequences
        # [K - Erase from cursor to end of line
        text = re.sub(r'\x1b\[K', '', text)
        # [J - Erase from cursor to end of screen
        text = re.sub(r'\x1b\[J', '', text)
        # [<n>J - Various clear screen modes
        text = re.sub(r'\x1b\[[0-2]J', '', text)
        # [<n>K - Various erase line modes
        text = re.sub(r'\x1b\[[0-2]K', '', text)
        # Cursor positioning [<row>;<col>H or [<row>;<col>f
        text = re.sub(r'\x1b\[\d*;\d*[Hf]', '', text)
        text = re.sub(r'\x1b\[\d*[Hf]', '', text)
        # Cursor movement
        text = re.sub(r'\x1b\[\d*[ABCD]', '', text)  # Up, Down, Forward, Backward
        
        # Handle carriage returns and line feeds
        text = text.replace('\r\n', '\n')
        
        # Pattern to match ANSI escape sequences
        ansi_pattern = re.compile(r'\x1b\[([0-9;]+)m')
        
        last_pos = 0
        fmt = QTextCharFormat()
        fmt.setForeground(QColor('#e0e0e0'))
        fmt.setFontPointSize(self.font_size)
        
        for match in ansi_pattern.finditer(text):
            # Insert text before this code with current format
            if match.start() > last_pos:
                plain_text = text[last_pos:match.start()]
                cursor.insertText(plain_text, fmt)
            
            # Parse the ANSI code
            codes = match.group(1).split(';')
            for code in codes:
                if code == '0' or code == '':
                    # Reset
                    fmt = QTextCharFormat()
                    fmt.setForeground(QColor('#e0e0e0'))
                    fmt.setFontPointSize(self.font_size)
                elif code == '1':
                    # Bold
                    fmt.setFontWeight(QFont.Bold)
                elif code in self.ansi_colors:
                    color = self.ansi_colors[code]
                    if isinstance(color, QColor):
                        fmt.setForeground(color)
            
            last_pos = match.end()
        
        # Insert remaining text
        if last_pos < len(text):
            plain_text = text[last_pos:]
            cursor.insertText(plain_text, fmt)
        
        self.terminal_display.setTextCursor(cursor)
        self.terminal_display.ensureCursorVisible()
    
    def append_output(self, text):
        """Append output to terminal display with ANSI color support"""
        if text:
            doc = self.terminal_display.document()
            
            # Get viewport position before append
            scrollbar = self.terminal_display.verticalScrollBar()
            scroll_pos_before = scrollbar.value()
            scroll_max_before = scrollbar.maximum()
            
            self.parse_ansi_and_append(text)
            
            # Check viewport position after append (but before timer callback)
            doc_after = self.terminal_display.document()
            scroll_pos_after = scrollbar.value()
            scroll_max_after = scrollbar.maximum()
            cursor_pos = self.terminal_display.textCursor().position()
            
            # After first output is processed, check for duplicate prompt on first line
            if self.is_first_output:
                self.is_first_output = False
                # Use a timer to clean up after initial rendering settles
                QTimer.singleShot(100, self.cleanup_duplicate_initial_prompt)
    
    def _trim_scrollback_buffer(self):
        """Trim old lines from the scrollback buffer to maintain performance"""
        doc = self.terminal_display.document()
        line_count = doc.lineCount()
        
        # Only trim if we exceed the maximum
        if line_count > self.MAX_SCROLLBACK_LINES:
            # Calculate how many lines to remove (keep MAX_SCROLLBACK_LINES)
            lines_to_remove = line_count - self.MAX_SCROLLBACK_LINES
            
            # Get cursor at the start
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.Start)
            
            # Move down to the end of the lines we want to remove
            # We remove from the top, keeping the most recent lines
            for _ in range(lines_to_remove):
                if not cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor):
                    break
                # Move to end of line to ensure we capture the full line including newline
                cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.MoveAnchor)
            
            # Get position before removal
            end_remove_position = cursor.position()
            
            # Select from start to the cursor position (this includes all lines to remove)
            cursor_start = QTextCursor(doc)
            cursor_start.movePosition(QTextCursor.Start)
            cursor.setPosition(cursor_start.position(), QTextCursor.KeepAnchor)
            
            # Remove the selected text
            cursor.removeSelectedText()
    
    def _on_scroll_changed(self, value):
        """Track when user manually scrolls"""
        scrollbar = self.terminal_display.verticalScrollBar()
        if scrollbar:
            # Check if user is at the bottom (within a small threshold)
            # We use a threshold of 10 pixels to account for rounding errors
            max_value = scrollbar.maximum()
            self.user_at_bottom = (max_value - value) <= 10
    
    def _scroll_to_bottom(self):
        """Scroll terminal display to bottom to show latest output (only if user is already at bottom)"""
        
        # Only auto-scroll if user is at the bottom
        if not self.user_at_bottom:
            return
        
        # Ensure cursor is at the end
        cursor = self.terminal_display.textCursor()
        cursor_before = cursor.position()
        cursor.movePosition(QTextCursor.End)
        cursor_after = cursor.position()
        self.terminal_display.setTextCursor(cursor)
        
        # Get document info
        doc = self.terminal_display.document()
        char_count = doc.characterCount()
        line_count = doc.lineCount()
        
        # Scroll to bottom
        scrollbar = self.terminal_display.verticalScrollBar()
        if scrollbar:
            # Get the maximum scroll value (this should be updated after layout)
            max_value = scrollbar.maximum()
            current_value = scrollbar.value()
            min_value = scrollbar.minimum()
            
            
            if max_value > 0:
                if current_value < max_value:
                    scrollbar.setValue(max_value)
                    new_value = scrollbar.value()
                else:
                    pass
            else:
                pass
            
            # Also ensure cursor is visible as a fallback
            self.terminal_display.ensureCursorVisible()
            final_value = scrollbar.value()
            final_max = scrollbar.maximum()
        else:
            pass
        
    
    def cleanup_duplicate_initial_prompt(self):
        """Clean up duplicate prompt on the first line after shell initialization"""
        try:
            # Get the first line of text
            doc = self.terminal_display.document()
            if doc.lineCount() > 0:
                first_block = doc.firstBlock()
                first_line = first_block.text()
                
                # Check if the line has duplicate content (same text appearing twice)
                if first_line:
                    line_len = len(first_line)
                    # Check if the line might be a duplicate by looking for repeated pattern
                    # Common pattern: "prompt prompt" where prompt appears twice
                    mid_point = line_len // 2
                    if mid_point > 10:  # Only check if line is long enough
                        first_half = first_line[:mid_point].strip()
                        second_half = first_line[mid_point:mid_point * 2].strip()
                        
                        # If both halves are the same, we have a duplicate
                        if first_half == second_half and first_half:
                            logger.debug(f"Detected duplicate prompt: '{first_half}' appears twice")
                            # Remove the first half
                            cursor = QTextCursor(first_block)
                            cursor.movePosition(QTextCursor.StartOfBlock)
                            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, mid_point)
                            cursor.removeSelectedText()
                            logger.debug("Cleaned up duplicate prompt")
        except Exception as e:
            logger.error(f"Error cleaning up duplicate prompt: {e}")
    
    def insert_text(self, text):
        """Insert text into the terminal (for multi-line commands from buttons/dialogs)
        This method simulates typing the text character by character to preserve newlines
        """
        if not text:
            return
        
        # Send the text character by character to preserve newlines properly
        # For PTY terminals, we write directly to preserve all characters including newlines
        self.write_to_pty(text)
    
    def execute_command(self, command, env_vars=None):
        """Execute a command by writing it to the PTY"""
        if command.strip():
            self.write_to_pty(command + '\n')
    
    def interrupt_process(self):
        """Send interrupt signal"""
        self.write_to_pty('\x03')
    
    def kill_process(self):
        """Kill the shell process"""
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    
    def closeEvent(self, event):
        """Clean up when widget is closed"""
        self.cleanup()
        event.accept()
    
    def cleanup(self):
        """Clean up PTY and processes"""
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread.wait()
        
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
        
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass
    
    def __del__(self):
        """Destructor"""
        self.cleanup()

