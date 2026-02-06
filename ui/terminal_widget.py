"""Terminal widget for command execution"""

from PyQt5.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import Qt, QProcess, QProcessEnvironment, pyqtSignal, QTimer
from PyQt5.QtGui import QTextCursor, QFont, QColor, QPalette, QKeyEvent
import os
import glob
import socket
import getpass
from datetime import datetime

# Toggle UI debug logging in hot paths (set to True only when debugging)
UI_DEBUG = False

class InteractiveTerminal(QTextEdit):
    """Interactive terminal that accepts user input"""
    
    command_executed = pyqtSignal(str)  # Emits when user presses Enter
    interrupt_signal = pyqtSignal()  # Emits on Ctrl+C
    clear_signal = pyqtSignal()  # Emits on Ctrl+L
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompt_position = 0
        self.command_history = []
        self.history_index = -1
        self.current_command = ""
        self.current_directory = os.path.expanduser("~")
        
        # Get user and hostname
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        
        # Detect virtual environment
        self.venv_name = self.detect_venv()
        
        # Prompt symbol (% for zsh, $ for bash)
        self.prompt_symbol = "% " if "zsh" in os.environ.get('SHELL', '') else "$ "
        
        # Common commands for autocomplete
        self.common_commands = [
            'ls', 'cd', 'pwd', 'cat', 'echo', 'grep', 'find', 'mkdir', 'rm', 'cp', 'mv',
            'touch', 'chmod', 'chown', 'ps', 'kill', 'top', 'df', 'du', 'tar', 'zip',
            'unzip', 'wget', 'curl', 'git', 'python', 'pip', 'npm', 'node', 'java',
            'clear', 'exit', 'history', 'man', 'which', 'whereis', 'locate'
        ]
    
    def detect_venv(self):
        """Detect if running in a virtual environment"""
        # Check for conda
        conda_env = os.environ.get('CONDA_DEFAULT_ENV')
        if conda_env:
            return conda_env
        
        # Check for virtualenv
        venv = os.environ.get('VIRTUAL_ENV')
        if venv:
            return os.path.basename(venv)
        
        return None
    
    def get_prompt(self):
        """Generate the current prompt string"""
        # Get current directory - use ~ for home
        home = os.path.expanduser("~")
        if self.current_directory.startswith(home):
            display_dir = "~" + self.current_directory[len(home):]
        else:
            display_dir = self.current_directory
        
        # Just show the directory name if not home
        if display_dir != "~":
            display_dir = os.path.basename(self.current_directory) or self.current_directory
        
        # Build prompt
        prompt_parts = []
        
        # Add virtual environment name if present
        if self.venv_name:
            prompt_parts.append(f"({self.venv_name}) ")
        
        # Add username@hostname
        prompt_parts.append(f"{self.username}@{self.hostname} ")
        
        # Add current directory
        prompt_parts.append(f"{display_dir} ")
        
        # Add prompt symbol
        prompt_parts.append(self.prompt_symbol)
        
        return "".join(prompt_parts)
        
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key presses with terminal shortcuts"""
        cursor = self.textCursor()
        modifiers = event.modifiers()
        
        # Prevent editing before the prompt
        if cursor.position() < self.prompt_position:
            if event.key() not in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, Qt.Key_Down, 
                                   Qt.Key_Home, Qt.Key_End):
                cursor.movePosition(QTextCursor.End)
                self.setTextCursor(cursor)
        
        # ============ Terminal Shortcuts ============
        
        # Ctrl+C - Interrupt/Kill current process
        if event.key() == Qt.Key_C and modifiers == Qt.ControlModifier:
            self.interrupt_signal.emit()
            self.insertPlainText("\n^C\n")
            self.show_prompt()
            return
        
        # Ctrl+D - EOF/Exit (if line is empty)
        if event.key() == Qt.Key_D and modifiers == Qt.ControlModifier:
            current_line = self.get_current_command()
            if not current_line:
                self.insertPlainText("\nexit\n")
                self.command_executed.emit("exit")
            return
        
        # Ctrl+L - Clear screen
        if event.key() == Qt.Key_L and modifiers == Qt.ControlModifier:
            self.clear_signal.emit()
            return
        
        # Ctrl+A - Move to beginning of line (after prompt)
        if event.key() == Qt.Key_A and modifiers == Qt.ControlModifier:
            cursor.setPosition(self.prompt_position)
            self.setTextCursor(cursor)
            return
        
        # Ctrl+E - Move to end of line
        if event.key() == Qt.Key_E and modifiers == Qt.ControlModifier:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            return
        
        # Ctrl+U - Clear line (delete from cursor to beginning)
        if event.key() == Qt.Key_U and modifiers == Qt.ControlModifier:
            cursor.setPosition(self.prompt_position)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            return
        
        # Ctrl+K - Delete from cursor to end of line
        if event.key() == Qt.Key_K and modifiers == Qt.ControlModifier:
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            return
        
        # Ctrl+W - Delete word backwards
        if event.key() == Qt.Key_W and modifiers == Qt.ControlModifier:
            if cursor.position() > self.prompt_position:
                cursor.movePosition(QTextCursor.PreviousWord, QTextCursor.KeepAnchor)
                if cursor.position() < self.prompt_position:
                    cursor.setPosition(self.prompt_position)
                    cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
            return
        
        # ============ Navigation and History ============
        
        # Up Arrow - Previous command from history
        if event.key() == Qt.Key_Up and modifiers == Qt.NoModifier:
            self.navigate_history(-1)
            return
        
        # Down Arrow - Next command from history
        if event.key() == Qt.Key_Down and modifiers == Qt.NoModifier:
            self.navigate_history(1)
            return
        
        # Home key - go to start of command, not line
        if event.key() == Qt.Key_Home:
            cursor.setPosition(self.prompt_position)
            self.setTextCursor(cursor)
            return
        
        # End key - go to end of line
        if event.key() == Qt.Key_End:
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            return
        
        # ============ Enter/Return ============
        
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            command = self.get_current_command()
            
            cursor.movePosition(QTextCursor.End)
            self.setTextCursor(cursor)
            super().keyPressEvent(event)
            
            if command:
                # Add to history
                self.command_history.append(command)
                self.history_index = len(self.command_history)
                self.command_executed.emit(command)
            else:
                self.show_prompt()
            
            return
        
        # ============ Tab - Autocomplete ============
        
        if event.key() == Qt.Key_Tab:
            self.handle_tab_complete()
            return
        
        # ============ Backspace ============
        
        if event.key() == Qt.Key_Backspace:
            if cursor.position() <= self.prompt_position:
                return
        
        # Allow normal key handling for other keys
        super().keyPressEvent(event)
    
    def get_current_command(self):
        """Get the current command being typed"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Get text from prompt position to end
        full_text = self.toPlainText()
        command_text = full_text[self.prompt_position:]
        
        return command_text.strip()
    
    def navigate_history(self, direction):
        """Navigate through command history"""
        if not self.command_history:
            return
        
        # Save current command if at the end
        if self.history_index == len(self.command_history):
            self.current_command = self.get_current_command()
        
        # Update index
        self.history_index += direction
        self.history_index = max(0, min(len(self.command_history), self.history_index))
        
        # Clear current command
        cursor = self.textCursor()
        cursor.setPosition(self.prompt_position)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        
        # Insert history command or saved command
        if self.history_index < len(self.command_history):
            self.insertPlainText(self.command_history[self.history_index])
        else:
            self.insertPlainText(self.current_command)
    
    def handle_tab_complete(self):
        """Handle Tab key for autocomplete"""
        command_line = self.get_current_command()
        if not command_line:
            return
        
        parts = command_line.split()
        if not parts:
            return
        
        # If we're completing the first word (command), complete from command list
        if len(parts) == 1 and not command_line.endswith(' '):
            prefix = parts[0]
            matches = [cmd for cmd in self.common_commands if cmd.startswith(prefix)]
            
            if len(matches) == 1:
                # Single match - complete it
                self.replace_current_word(matches[0])
            elif len(matches) > 1:
                # Multiple matches - show them
                self.show_completions(matches)
        else:
            # Complete file/directory paths
            if len(parts) > 0:
                # Get the word being completed
                if command_line.endswith(' '):
                    prefix = ""
                else:
                    prefix = parts[-1]
                
                matches = self.get_path_completions(prefix)
                
                if len(matches) == 1:
                    # Single match - complete it
                    self.replace_current_word(matches[0])
                elif len(matches) > 1:
                    # Find common prefix
                    common_prefix = os.path.commonprefix(matches)
                    if len(common_prefix) > len(prefix):
                        # Complete to common prefix
                        self.replace_current_word(common_prefix)
                    else:
                        # Show all matches
                        self.show_completions(matches)
    
    def get_path_completions(self, prefix):
        """Get file/directory path completions"""
        try:
            # Expand user home directory
            if prefix.startswith('~'):
                prefix = os.path.expanduser(prefix)
            
            # If no directory separator, search in current directory
            if '/' not in prefix:
                search_dir = self.current_directory
                pattern = prefix + '*'
            else:
                # Split into directory and filename
                if prefix.endswith('/'):
                    search_dir = prefix
                    pattern = '*'
                else:
                    search_dir = os.path.dirname(prefix) or '.'
                    pattern = os.path.basename(prefix) + '*'
            
            # Make search_dir absolute
            if not os.path.isabs(search_dir):
                search_dir = os.path.join(self.current_directory, search_dir)
            
            # Get matches
            search_pattern = os.path.join(search_dir, pattern)
            matches = glob.glob(search_pattern)
            
            # Convert to relative paths if appropriate
            result = []
            for match in matches:
                # Add trailing slash for directories
                if os.path.isdir(match):
                    match += '/'
                
                # Make relative to current directory if possible
                try:
                    if match.startswith(self.current_directory):
                        rel_path = os.path.relpath(match, self.current_directory)
                        result.append(rel_path)
                    else:
                        result.append(match)
                except ValueError:
                    result.append(match)
            
            return sorted(result)
        except Exception:
            return []
    
    def replace_current_word(self, replacement):
        """Replace the current word being typed with the completion"""
        command_line = self.get_current_command()
        parts = command_line.split()
        
        if not parts:
            return
        
        # Calculate positions
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # If line ends with space, just append
        if command_line.endswith(' '):
            self.insertPlainText(replacement)
        else:
            # Remove last word and replace
            last_word = parts[-1]
            for _ in range(len(last_word)):
                cursor.deletePreviousChar()
            self.setTextCursor(cursor)
            self.insertPlainText(replacement)
    
    def show_completions(self, matches):
        """Show available completions"""
        # Save current command before showing matches
        current_cmd = self.get_current_command()
        
        # Move to new line and show matches
        self.insertPlainText("\n")
        
        # Show matches in columns
        max_len = max(len(m) for m in matches) if matches else 0
        cols = max(1, 80 // (max_len + 2))
        
        for i, match in enumerate(matches):
            self.insertPlainText(match.ljust(max_len + 2))
            if (i + 1) % cols == 0:
                self.insertPlainText("\n")
        
        if len(matches) % cols != 0:
            self.insertPlainText("\n")
        
        # Restore prompt and current command
        self.show_prompt()
        self.insertPlainText(current_cmd)
    
    def show_prompt(self):
        """Display the command prompt"""
        self.moveCursor(QTextCursor.End)
        prompt = self.get_prompt()
        self.insertPlainText(prompt)
        self.prompt_position = self.textCursor().position()
        self.ensureCursorVisible()

class TerminalWidget(QWidget):
    """Widget that emulates a terminal"""
    
    command_finished = pyqtSignal(int)  # exit code
    command_executed = pyqtSignal(str)  # Emitted when user presses Enter with full command text
    
    # Maximum number of lines to keep in scrollback buffer
    # Note: This is a performance optimization - QTextEdit becomes slow with very large documents
    # Lower default to reduce memory/layout pressure while scrolling.
    MAX_SCROLLBACK_LINES = 2000
    
    def __init__(self, shell=None):
        super().__init__()
        self.process = None
        self.current_directory = os.path.expanduser("~")
        self.shell = shell or os.environ.get('SHELL', '/bin/bash')
        self.last_command = ""  # Track last command for output colorization
        self.init_ui()

    # Commands/keywords that likely require network access
    NETWORK_COMMAND_KEYWORDS = [
        'wget', 'curl', 'git', 'ssh', 'scp', 'npm', 'yarn', 'pip install', 'pip3', 'pip',
        'apt-get', 'brew', 'ftp', 'sftp', 'rsync', 'telnet', 'ping', 'npm install',
        'composer', 'gh', 'git clone', 'git fetch', 'git pull'
    ]
        
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Network warning label (hidden by default)
        self.network_warning = QLabel("No internet access")
        self.network_warning.setObjectName('networkWarning')
        self.network_warning.setStyleSheet("background-color: #7f1d1d; color: white; padding: 6px; font-weight: bold;")
        self.network_warning.setVisible(False)
        layout.addWidget(self.network_warning)

        # Terminal display - now interactive
        self.terminal_display = InteractiveTerminal()
        self.terminal_display.current_directory = self.current_directory
        self.terminal_display.setFont(QFont("Courier New", 10))
        
        # Set terminal-like colors (white text by default, like real terminals)
        self.terminal_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d0d0d0;
                border: none;
                padding: 10px;
            }
        """)
        
        # Connect command execution and signals
        self.terminal_display.command_executed.connect(self.execute_command_from_input)
        self.terminal_display.interrupt_signal.connect(self.interrupt_process)
        self.terminal_display.clear_signal.connect(self.clear_terminal)
        
        layout.addWidget(self.terminal_display)
        
        # Show welcome message (like real terminals)
        shell_name = os.path.basename(self.shell)
        self.append_output(f"Last login: {self.get_current_time()} on ttys000\n", color="gray")
        self.terminal_display.show_prompt()
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
            # If timers are not available for some reason, continue without periodic checks
            pass
        
    def execute_command_from_input(self, command):
        """Execute command from user input"""
        # Emit the command_executed signal with the full command text
        # This is captured before execution, so it includes exactly what the user typed/pasted
        self.command_executed.emit(command)
        
        # Now execute the command
        self.execute_command(command)
    
    def execute_command(self, command, env_vars=None):
        """Execute a command in the terminal"""
        # Mark whether this command appears to require network
        try:
            lower_cmd = command.lower() if command else ''
        except Exception:
            lower_cmd = ''
        self._current_command_requires_network = any(k in lower_cmd for k in self.NETWORK_COMMAND_KEYWORDS)

        # Immediately check connectivity and show warning before starting the process
        try:
            online = self.is_online()
        except Exception:
            online = True

        if getattr(self, '_current_command_requires_network', False) and not online:
            try:
                self.network_warning.setVisible(True)
            except Exception:
                pass
            # Also append an inline terminal message so it's visible in sessions/screenshots
            try:
                self.append_output("\n[No internet access — command may fail]\n", color="yellow")
            except Exception:
                pass

        if self.process and self.process.state() == QProcess.Running:
            self.append_output("\n[WARNING] A command is already running...\n", color="yellow")
            self.terminal_display.show_prompt()
            return
        
        # Store command for output colorization
        self.last_command = command
        
        # Handle built-in commands
        if command.strip() == "clear":
            self.clear_terminal()
            return
        elif command.strip() == "exit":
            self.append_output("\n[Terminal session closed]\n", color="gray")
            self.terminal_display.show_prompt()
            return
        elif command.strip().startswith("cd "):
            self.change_directory(command.strip()[3:].strip())
            self.terminal_display.show_prompt()
            return
        
        # Create process
        self.process = QProcess(self)
        self.process.setWorkingDirectory(self.current_directory)
        
        # Set environment variables if provided
        if env_vars:
            env = QProcessEnvironment.systemEnvironment()
            for key, value in env_vars.items():
                env.insert(key, value)
            self.process.setProcessEnvironment(env)
        
        # Connect signals
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished)
        
        # Start the process
        # Use the actual shell selected by the user
        if os.name == 'nt':  # Windows
            self.process.start('cmd', ['/c', command])
        else:  # Unix-like - use the selected shell
            # Set up environment for colored output
            env = self.process.processEnvironment()
            if not env.isEmpty():
                env.insert('CLICOLOR', '1')
                env.insert('CLICOLOR_FORCE', '1')
                self.process.setProcessEnvironment(env)
            
            self.process.start(self.shell, ['-c', command])

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

        # Show warning only if the current command requires network and we're offline
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
    
    def handle_stdout(self):
        """Handle standard output from process"""
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')
        
        # Colorize output based on content
        self.append_colorized_output(text)
    
    def handle_stderr(self):
        """Handle standard error from process"""
        data = self.process.readAllStandardError()
        text = bytes(data).decode('utf-8', errors='replace')
        self.append_output(text, color="red")
    
    def handle_finished(self, exit_code, exit_status):
        """Handle process completion"""
        # Don't show success/failure message - just show prompt
        # Real terminals don't print these messages
        
        self.command_finished.emit(exit_code)
        
        # Show prompt for next command
        self.terminal_display.show_prompt()
    
    def append_colorized_output(self, text):
        """Append colorized output based on content (ls, file types, etc.)"""
        # Check if this is ls output
        is_ls_output = False
        if self.last_command and self.last_command.strip():
            cmd_parts = self.last_command.strip().split()
            if cmd_parts and cmd_parts[0] in ['ls', 'll', 'la']:
                is_ls_output = True
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if i > 0:
                self.append_output("\n")
            
            if is_ls_output and line.strip():
                self.append_colorized_ls_line(line)
            else:
                # Regular output - just white text
                self.append_output(line)
    
    def append_colorized_ls_line(self, line):
        """Colorize ls command output based on file types"""
        if not line.strip():
            return
        
        # Split by whitespace but preserve spacing
        parts = line.split(None)  # None splits on any whitespace
        if not parts:
            return
        
        # Check if it's a detailed listing (starts with permissions like drwx or -rw-)
        if len(parts) > 0 and len(parts[0]) >= 10 and parts[0][0] in ('-', 'd', 'l', 'c', 'b', 'p', 's'):
            # Detailed format: drwxr-xr-x 1 user group size date time filename
            # Find where the filename starts (after date/time)
            # Typical format has 8+ parts before filename
            filename_start_idx = 8
            
            if len(parts) >= filename_start_idx + 1:
                # Print metadata in gray (permissions, links, owner, group, size, date, time)
                for i in range(min(filename_start_idx, len(parts) - 1)):
                    if i > 0:
                        self.append_output("  ")
                    self.append_output(parts[i], color="gray")
                
                # Print filename with appropriate color
                if filename_start_idx < len(parts):
                    self.append_output("  ")
                    filename = ' '.join(parts[filename_start_idx:])
                    
                    # Determine color based on permissions and file type
                    perms = parts[0]
                    if perms.startswith('d'):
                        # Directory - blue and bold
                        self.append_output(filename, color="blue_bold")
                    elif perms.startswith('l'):
                        # Symlink - cyan
                        self.append_output(filename, color="cyan")
                    elif 'x' in perms[3:6] or 'x' in perms[6:9] or 'x' in perms[0:3]:
                        # Executable - green (check user, group, or other execute bits)
                        self.append_output(filename, color="green")
                    else:
                        # Use extension-based coloring for regular files
                        color = self.get_file_color(filename)
                        self.append_output(filename, color=color)
            else:
                # Not enough parts, just print the line
                self.append_output(line)
        else:
            # Simple format - just filenames in columns
            # Split into individual items and colorize each
            items = line.split()
            for i, item in enumerate(items):
                if i > 0:
                    self.append_output("  ")
                
                # Determine file color
                color = self.get_file_color(item)
                self.append_output(item, color=color)
    
    def get_file_color(self, filename):
        """Determine color for a file based on its name/extension"""
        # Check if it's a directory in current directory
        full_path = os.path.join(self.current_directory, filename)
        if os.path.isdir(full_path):
            return "blue_bold"
        
        # Common directory names (if not found in filesystem)
        if filename in ['Desktop', 'Documents', 'Downloads', 'Library', 'Movies', 'Music', 'Pictures', 'Public', 
                       'Applications', 'bin', 'etc', 'var', 'tmp', 'usr', 'opt', 'home',
                       'backend', 'frontend', 'src', 'dist', 'build', 'node_modules', 'logs']:
            return "blue_bold"
        
        # Get lowercase for extension checking
        lower_name = filename.lower()
        
        # Archives and compressed files - RED
        if lower_name.endswith(('.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.tgz', '.tar.gz')):
            return "red"
        
        # Executables and scripts - GREEN
        if lower_name.endswith(('.sh', '.bash', '.zsh', '.py', '.rb', '.pl', '.js', '.jsx', '.ts', '.tsx')):
            return "green"
        
        # Images and media - MAGENTA
        if lower_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.ico', '.webp',
                               '.mp4', '.avi', '.mov', '.mp3', '.wav', '.pdf')):
            return "magenta"
        
        # Config files - YELLOW
        if (lower_name.endswith(('.conf', '.config', '.cfg', '.ini', '.env', '.yaml', '.yml', 
                                 '.toml', '.json', '.xml')) or
            lower_name.startswith('.') and len(lower_name) > 1):  # Hidden config files
            return "yellow"
        
        # Docker files - CYAN
        if 'dockerfile' in lower_name or 'docker-compose' in lower_name:
            return "cyan"
        
        # Documentation - BLUE (light)
        if lower_name.endswith(('.md', '.txt', '.rst', '.doc', '.docx', '.readme')):
            return "blue"
        
        # Source code - GREEN (if not already caught)
        if lower_name.endswith(('.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs', '.php', '.html', '.css', '.scss')):
            return "green"
        
        # Data files - MAGENTA
        if lower_name.endswith(('.sql', '.db', '.sqlite', '.csv', '.tsv', '.parquet')):
            return "magenta"
        
        # Requirements/dependency files - CYAN
        if 'requirements' in lower_name or 'package.json' in lower_name or 'gemfile' in lower_name:
            return "cyan"
        
        # Default - white for regular files
        return "white"
    
    def append_output(self, text, color=None):
        """Append text to terminal display"""
        
        doc = self.terminal_display.document()
        scrollbar = self.terminal_display.verticalScrollBar()
        scroll_pos_before = scrollbar.value()
        scroll_max_before = scrollbar.maximum()
        
        cursor = self.terminal_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if color:
            color_map = {
                "red": "#ff5555",
                "green": "#50fa7b",
                "yellow": "#f1fa8c",
                "cyan": "#8be9fd",
                "blue": "#6FA8DC",
                "blue_bold": "#5BA8FF",
                "magenta": "#ff79c6",
                "gray": "#6c6c6c",
                "white": "#d0d0d0"
            }
            color_code = color_map.get(color, "#d0d0d0")
            
            # Apply bold for certain colors
            weight = "bold" if "bold" in color else "normal"
            
            # Escape HTML
            escaped_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            cursor.insertHtml(f'<span style="color: {color_code}; font-weight: {weight};">{escaped_text}</span>')
        else:
            cursor.insertText(text)
        
        self.terminal_display.setTextCursor(cursor)
        
        # Get scrollbar state before scheduling scroll
        scrollbar = self.terminal_display.verticalScrollBar()
        scroll_max_before_timer = scrollbar.maximum() if scrollbar else 0
        scroll_pos_before_timer = scrollbar.value() if scrollbar else 0
        
        # Trim old lines if buffer is too large
        self._trim_scrollback_buffer()
        
        # Auto-scroll to bottom after layout update
        # Use QTimer to ensure document layout is complete before scrolling
        QTimer.singleShot(0, self._scroll_to_bottom)
        
        # Update prompt position
        self.terminal_display.prompt_position = self.terminal_display.textCursor().position()
    
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
            
            # Get position before removal for prompt position adjustment
            end_remove_position = cursor.position()
            
            # Select from start to the cursor position (this includes all lines to remove)
            cursor_start = QTextCursor(doc)
            cursor_start.movePosition(QTextCursor.Start)
            cursor.setPosition(cursor_start.position(), QTextCursor.KeepAnchor)
            
            # Remove the selected text
            cursor.removeSelectedText()
            
            # Update prompt position if it was affected
            if hasattr(self.terminal_display, 'prompt_position'):
                # Recalculate prompt position after trimming
                # The prompt position should be adjusted by the number of characters removed
                self.terminal_display.prompt_position = max(0, self.terminal_display.prompt_position - end_remove_position)
    
    def _scroll_to_bottom(self):
        """Scroll terminal display to bottom to show latest output"""
        
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

            # Also ensure cursor is visible as a fallback
            self.terminal_display.ensureCursorVisible()
            final_value = scrollbar.value()
            final_max = scrollbar.maximum()
    
    def get_working_directory(self):
        """Get the current working directory of the terminal"""
        return self.current_directory
    
    def clear_terminal(self):
        """Clear the terminal display"""
        self.terminal_display.clear()
        self.terminal_display.show_prompt()
    
    def change_directory(self, path):
        """Change the current working directory"""
        try:
            if path.startswith("~"):
                path = os.path.expanduser(path)
            
            if not os.path.isabs(path):
                path = os.path.join(self.current_directory, path)
            
            path = os.path.abspath(path)
            
            if os.path.isdir(path):
                self.current_directory = path
                self.terminal_display.current_directory = path  # Update terminal's directory
                # Don't print anything, just show new prompt
            else:
                self.append_output(f"cd: no such file or directory: {path}\n", color="red")
        except Exception as e:
            self.append_output(f"cd: {str(e)}\n", color="red")
    
    def interrupt_process(self):
        """Interrupt the running process (Ctrl+C)"""
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()  # Try graceful termination first
            # Real terminals don't show a message, they just stop
            self.terminal_display.show_prompt()
        else:
            # No process running, just show new prompt
            self.terminal_display.show_prompt()
    
    def kill_process(self):
        """Kill the running process"""
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.terminal_display.show_prompt()
    
    def get_current_time(self):
        """Get current time in terminal format"""
        now = datetime.now()
        return now.strftime("%a %b %d %H:%M:%S")

