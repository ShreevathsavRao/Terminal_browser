"""Windows Terminal Widget - Subprocess-based implementation for Windows

This module provides terminal emulation for Windows using subprocess.Popen with pipes.
Unlike Unix PTY-based terminals, this implementation has some limitations but provides
functional terminal access on Windows systems.

Key Differences from Unix Implementation:
- Uses subprocess.Popen instead of pty.openpty()
- No true PTY support (some interactive programs may not work)
- Limited signal handling (Ctrl+C forwarding is restricted)
- Default shell: PowerShell (configurable to cmd.exe)

Future Improvements:
- Add winpty library support for better PTY emulation
- Use Windows 10+ ConPTY API for native PTY support
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QSpinBox, QPushButton, QApplication, QMenu, QAction, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QEvent, QPointF
from PyQt5.QtGui import QFont, QColor, QPainter, QPalette, QKeyEvent, QFontMetrics, QMouseEvent, QPen, QPolygonF
import os
import sys
import subprocess
import threading
import queue
import re
import time
import platform
import pyte
import uuid
from datetime import datetime
from core.preferences_manager import PreferencesManager
from core.platform_manager import get_platform_manager
from ui.suggestion_widget import SuggestionWidget, SuggestionManager
from ui.terminal_search_widget import TerminalSearchWidget
from ui.terminal_widgets.base_terminal_widget import BaseTerminalWidget
import socket

# Toggle UI debug logging
UI_DEBUG = False


class WindowsProcessReader(QThread):
    """Thread to read from Windows subprocess stdout"""
    
    output_received = pyqtSignal(bytes)
    
    def __init__(self, process):
        super().__init__()
        self.process = process
        self.running = True
        
    def run(self):
        """Read from subprocess and emit output"""
        try:
            while self.running and self.process and self.process.poll() is None:
                # Read output in chunks
                data = self.process.stdout.read(4096)
                if data:
                    self.output_received.emit(data)
                else:
                    # Small delay to prevent CPU spinning
                    time.sleep(0.01)
        except Exception as e:
            if UI_DEBUG:
                print(f"[WindowsProcessReader] Error: {e}")
    
    def stop(self):
        """Stop reading thread"""
        self.running = False


# Import the same Canvas and Scrollbar classes from unix_terminal_widget
# These are UI components that don't depend on PTY vs subprocess
try:
    from ui.terminal_widgets.unix_terminal_widget import TerminalCanvas, TerminalScrollbar
except ImportError:
    # Fallback: define minimal versions if unix_terminal_widget not available
    class TerminalCanvas(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
        
        def set_terminal_canvas(self, canvas):
            pass
        
        def paintEvent(self, event):
            pass
    
    class TerminalScrollbar(QScrollArea):
        def __init__(self, parent=None):
            super().__init__(parent)


class WindowsTerminalWidget(BaseTerminalWidget):
    """Windows terminal widget using subprocess.Popen
    
    This implementation provides terminal functionality on Windows using
    subprocess with pipes. While not as feature-rich as Unix PTY terminals,
    it enables basic terminal operations on Windows platforms.
    """
    
    # Signals inherited from BaseTerminalWidget
    # command_finished = pyqtSignal(int)
    # command_executed = pyqtSignal(str)
    # prompt_ready = pyqtSignal()
    # viewport_scrolled = pyqtSignal(float, float)
    
    # Feature flag for Qt file type coloring overlay
    ENABLE_QT_FILE_COLORING = True
    
    def __init__(self, shell=None, prefs_manager=None):
        super().__init__(shell, prefs_manager)
        
        # Default to PowerShell on Windows
        if not self.shell:
            self.shell = 'powershell.exe'
        
        self.process = None
        self.reader_thread = None
        self.input_queue = queue.Queue()
        
        # Terminal state
        self.current_directory = os.path.expanduser('~')
        self.current_command_buffer = ""
        self.tracking_command = True
        
        # Load preferences
        self.prefs_manager = prefs_manager or PreferencesManager()
        default_dir = self.prefs_manager.get('terminal', 'default_directory', os.path.expanduser('~'))
        self.current_directory = default_dir
        
        # Create pyte screen and stream
        self.rows = 24
        self.cols = 120
        self.scrollback_lines = 10000
        
        self.screen = pyte.HistoryScreen(self.cols, self.rows, history=self.scrollback_lines)
        self.stream = pyte.Stream(self.screen)
        
        # History tracking
        from core.history_file_manager import HistoryFileManager
        self.tab_id = self._generate_tab_id()
        self.history_manager = HistoryFileManager()
        self.history_file_path = self.history_manager.create_history_file(self.tab_id)
        
        # Initialize UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the terminal UI"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create canvas for terminal display
        self._canvas = TerminalCanvas(self)
        self._canvas.set_font_size = lambda size: self.change_font_size(size)
        
        # Create scrollbar
        self._scrollbar = TerminalScrollbar(self)
        
        # Create search widget
        self._search_widget = TerminalSearchWidget(self)
        self._search_widget.hide()
        
        # Layout
        terminal_layout = QHBoxLayout()
        terminal_layout.addWidget(self._canvas, 1)
        terminal_layout.addWidget(self._scrollbar)
        
        layout.addLayout(terminal_layout)
        layout.addWidget(self._search_widget)
        
        self.setLayout(layout)
        
        # Font settings
        self.font_size = 11
        self.font_family = "Consolas"  # Good monospace font for Windows
        self.update_font()
    
    def update_font(self):
        """Update terminal font"""
        font = QFont(self.font_family, self.font_size)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # Calculate character size
        metrics = QFontMetrics(font)
        self.char_width = metrics.horizontalAdvance('M')
        self.char_height = metrics.height()
    
    def start_shell(self):
        """Start Windows shell process using subprocess"""
        if UI_DEBUG:
            print(f"[WindowsTerminalWidget] Starting shell: {self.shell}")
        
        try:
            # Create subprocess with pipes
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Environment variables
            env = os.environ.copy()
            env['COLUMNS'] = str(self.cols)
            env['LINES'] = str(self.rows)
            
            self.process = subprocess.Popen(
                [self.shell, '-NoLogo'] if 'powershell' in self.shell.lower() else [self.shell],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                cwd=self.current_directory,
                bufsize=0,
                startupinfo=startupinfo,
                env=env
            )
            
            if UI_DEBUG:
                print(f"[WindowsTerminalWidget] Process started with PID: {self.process.pid}")
            
            # Start reader thread
            self.reader_thread = WindowsProcessReader(self.process)
            self.reader_thread.output_received.connect(self.handle_output)
            self.reader_thread.start()
            
        except Exception as e:
            print(f"[WindowsTerminalWidget] Error starting shell: {e}")
            import traceback
            traceback.print_exc()
    
    def write_to_pty(self, data):
        """Write data to subprocess stdin"""
        if not self.process or not self.process.stdin:
            if UI_DEBUG:
                print("[WindowsTerminalWidget] No process to write to")
            return
        
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            self.process.stdin.write(data)
            self.process.stdin.flush()
            
            if UI_DEBUG:
                print(f"[WindowsTerminalWidget] Wrote {len(data)} bytes to stdin")
        
        except Exception as e:
            if UI_DEBUG:
                print(f"[WindowsTerminalWidget] Error writing to stdin: {e}")
    
    def execute_command(self, command, env_vars=None):
        """Execute a command in the terminal"""
        if env_vars:
            # Set environment variables first
            for key, value in env_vars.items():
                env_command = f"$env:{key} = '{value}'\r\n"
                self.write_to_pty(env_command)
        
        # Send command
        self.write_to_pty(command + '\r\n')
        self.command_executed.emit(command)
    
    def interrupt_process(self):
        """Send interrupt signal (limited support on Windows)"""
        if self.process:
            try:
                # On Windows, this is limited - we can try to terminate gracefully
                if UI_DEBUG:
                    print("[WindowsTerminalWidget] Interrupt requested (limited on Windows)")
                # Send Ctrl+C sequence
                self.write_to_pty('\x03')
            except Exception as e:
                if UI_DEBUG:
                    print(f"[WindowsTerminalWidget] Error interrupting: {e}")
    
    def kill_process(self):
        """Forcefully terminate the process"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
    
    def clear(self):
        """Clear the terminal screen"""
        if 'powershell' in self.shell.lower():
            self.execute_command('Clear-Host')
        else:
            self.execute_command('cls')
    
    def get_all_text(self):
        """Get all text from terminal buffer"""
        lines = []
        # Get history
        for line_data in self.screen.history.top:
            line_text = ''.join(char.data for char in line_data)
            lines.append(line_text)
        # Get visible screen
        for y in range(self.screen.lines):
            line_text = ''.join(self.screen.buffer[y][x].data for x in range(self.screen.columns))
            lines.append(line_text)
        return '\n'.join(lines)
    
    def get_selected_text(self):
        """Get currently selected text"""
        # TODO: Implement selection support
        return ""
    
    def copy_selection(self):
        """Copy selected text to clipboard"""
        text = self.get_selected_text()
        if text:
            QApplication.clipboard().setText(text)
    
    def paste_from_clipboard(self):
        """Paste text from clipboard"""
        text = QApplication.clipboard().text()
        if text:
            self.write_to_pty(text)
    
    def select_all(self):
        """Select all terminal content"""
        # TODO: Implement selection support
        pass
    
    def clear_selection(self):
        """Clear current selection"""
        # TODO: Implement selection support
        pass
    
    def update_pty_size_from_widget(self):
        """Update terminal size (Windows uses environment variables)"""
        if self.process:
            # On Windows, we can't resize a running process easily
            # This would need to be set before process creation
            pass
    
    def handle_output(self, data):
        """Process output data from terminal"""
        try:
            # Decode data
            text = data.decode('utf-8', errors='replace')
            
            # Feed to pyte stream for terminal emulation
            self.stream.feed(text)
            
            # Update canvas
            if hasattr(self, '_canvas'):
                self._canvas.update()
            
            # Track directory changes (basic parsing)
            self._track_directory_from_output(text)
            
        except Exception as e:
            if UI_DEBUG:
                print(f"[WindowsTerminalWidget] Error handling output: {e}")
    
    def _track_directory_from_output(self, text):
        """Try to track directory changes from output"""
        # Look for PowerShell prompt pattern or CD commands
        # This is a simple heuristic and may not catch all cases
        cd_match = re.search(r'(?:^|\n)([A-Za-z]:\\[^\r\n]+)>', text, re.MULTILINE)
        if cd_match:
            new_dir = cd_match.group(1).strip()
            if os.path.isdir(new_dir):
                self.current_directory = new_dir
    
    def change_font_size(self, size):
        """Change terminal font size"""
        self.font_size = size
        self.update_font()
        if hasattr(self, '_canvas'):
            self._canvas.update()
    
    def force_scroll_to_bottom(self):
        """Scroll to bottom of terminal"""
        if hasattr(self, '_scrollbar'):
            self._scrollbar.setValue(self._scrollbar.maximum())
    
    def is_at_bottom(self):
        """Check if scrolled to bottom"""
        if hasattr(self, '_scrollbar'):
            return self._scrollbar.value() >= self._scrollbar.maximum() - 10
        return True
    
    def close_terminal(self):
        """Clean shutdown of terminal"""
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread.wait(1000)
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events"""
        key = event.key()
        modifiers = event.modifiers()
        text = event.text()
        
        # Handle special keys
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            self.write_to_pty('\r\n')
        elif key == Qt.Key_Backspace:
            self.write_to_pty('\x08')
        elif key == Qt.Key_Tab:
            self.write_to_pty('\t')
        elif key == Qt.Key_Escape:
            self.write_to_pty('\x1b')
        elif key == Qt.Key_Up:
            self.write_to_pty('\x1b[A')
        elif key == Qt.Key_Down:
            self.write_to_pty('\x1b[B')
        elif key == Qt.Key_Right:
            self.write_to_pty('\x1b[C')
        elif key == Qt.Key_Left:
            self.write_to_pty('\x1b[D')
        elif modifiers & Qt.ControlModifier:
            # Handle Ctrl+C, Ctrl+V, etc.
            if key == Qt.Key_C and not (modifiers & Qt.ShiftModifier):
                self.interrupt_process()
            elif key == Qt.Key_V:
                self.paste_from_clipboard()
            else:
                # Send Ctrl+key
                if text and ord(text[0]) > 0:
                    ctrl_char = chr(ord(text[0]) & 0x1f)
                    self.write_to_pty(ctrl_char)
        elif text:
            self.write_to_pty(text)
        else:
            super().keyPressEvent(event)
