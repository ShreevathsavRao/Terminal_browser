"""
Base Terminal Widget - Abstract Interface
==========================================

This module defines the abstract base class that all platform-specific terminal
widget implementations must inherit from. It ensures API compatibility across
Windows, macOS, and Linux implementations.

Key Design Principles:
- All public methods must be implemented by subclasses
- PyQt signals provide async communication
- Common interface hides platform-specific details
"""

from abc import ABC, abstractmethod
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal


class BaseTerminalWidget(QWidget, ABC):
    """
    Abstract base class for platform-specific terminal widget implementations.
    
    This class defines the interface that all terminal widgets must implement,
    ensuring consistent behavior across Windows, macOS, and Linux platforms.
    
    Signals:
        command_finished(int): Emitted when a command completes with exit code
        command_executed(str): Emitted when a command is executed with command text
        prompt_ready(): Emitted when a new prompt appears (command finished)
        viewport_scrolled(float, float): Emitted when viewport scrolls (start, height)
    """
    
    # PyQt Signals - must be defined at class level
    command_finished = pyqtSignal(int)
    command_executed = pyqtSignal(str)
    prompt_ready = pyqtSignal()
    viewport_scrolled = pyqtSignal(float, float)
    
    def __init__(self, shell=None, prefs_manager=None):
        """
        Initialize the terminal widget.
        
        Args:
            shell (str, optional): Shell command to execute (e.g., '/bin/bash', 'powershell.exe')
            prefs_manager (PreferencesManager, optional): Preferences manager instance
        """
        super().__init__()
        self.shell = shell
        self.prefs_manager = prefs_manager
    
    # ============================================================================
    # Abstract Methods - Must be implemented by all subclasses
    # ============================================================================
    
    @abstractmethod
    def start_shell(self):
        """
        Start the terminal shell process.
        
        This method initializes the terminal subprocess/PTY and begins
        reading output. Platform implementations differ significantly:
        - Unix: Uses pty.openpty() and os.fork()
        - Windows: Uses subprocess.Popen with pipes
        """
        pass
    
    @abstractmethod
    def write_to_pty(self, data):
        """
        Write data to the terminal input.
        
        Args:
            data (str or bytes): Data to send to terminal
            
        Platform implementations:
        - Unix: Writes to PTY master file descriptor
        - Windows: Writes to subprocess stdin pipe
        """
        pass
    
    @abstractmethod
    def execute_command(self, command, env_vars=None):
        """
        Execute a command in the terminal.
        
        Args:
            command (str): Command to execute
            env_vars (dict, optional): Environment variables to set
            
        Note: This should write the command to the terminal and press Enter
        """
        pass
    
    @abstractmethod
    def interrupt_process(self):
        """
        Send interrupt signal (Ctrl+C) to running process.
        
        Platform implementations:
        - Unix: Sends SIGINT to process group
        - Windows: Limited support, may send Ctrl+C event
        """
        pass
    
    @abstractmethod
    def kill_process(self):
        """
        Forcefully terminate the terminal process.
        
        Platform implementations:
        - Unix: Sends SIGKILL
        - Windows: Uses TerminateProcess
        """
        pass
    
    @abstractmethod
    def clear(self):
        """
        Clear the terminal screen.
        
        This should execute the appropriate clear command for the platform
        (e.g., 'clear' on Unix, 'cls' on Windows)
        """
        pass
    
    @abstractmethod
    def get_all_text(self):
        """
        Get all text content from the terminal buffer.
        
        Returns:
            str: All visible and scrollback text content
        """
        pass
    
    @abstractmethod
    def get_selected_text(self):
        """
        Get currently selected text.
        
        Returns:
            str: Selected text, or empty string if no selection
        """
        pass
    
    @abstractmethod
    def copy_selection(self):
        """
        Copy selected text to clipboard.
        """
        pass
    
    @abstractmethod
    def paste_from_clipboard(self):
        """
        Paste text from clipboard into terminal.
        """
        pass
    
    @abstractmethod
    def select_all(self):
        """
        Select all terminal content.
        """
        pass
    
    @abstractmethod
    def clear_selection(self):
        """
        Clear current text selection.
        """
        pass
    
    @abstractmethod
    def update_pty_size_from_widget(self):
        """
        Update terminal size based on widget dimensions.
        
        Platform implementations:
        - Unix: Uses ioctl with TIOCSWINSZ
        - Windows: Sets environment variables COLUMNS and LINES
        """
        pass
    
    @abstractmethod
    def handle_output(self, data):
        """
        Process output data from terminal.
        
        Args:
            data (bytes): Raw output data from terminal process
            
        This method should:
        1. Feed data to terminal emulator (pyte)
        2. Update display
        3. Track commands and directory changes
        """
        pass
    
    @abstractmethod
    def change_font_size(self, size):
        """
        Change terminal font size.
        
        Args:
            size (int): Font size in points
        """
        pass
    
    @abstractmethod
    def force_scroll_to_bottom(self):
        """
        Force scroll to bottom of terminal output.
        """
        pass
    
    @abstractmethod
    def is_at_bottom(self):
        """
        Check if terminal is scrolled to bottom.
        
        Returns:
            bool: True if at bottom, False otherwise
        """
        pass
    
    # ============================================================================
    # Optional Methods - Subclasses may override but have default implementations
    # ============================================================================
    
    def get_current_directory(self):
        """
        Get current working directory of terminal.
        
        Returns:
            str: Current directory path
            
        Default implementation returns None. Subclasses should override
        to provide actual directory tracking.
        """
        return getattr(self, 'current_directory', None)
    
    def set_current_directory(self, path):
        """
        Set current working directory.
        
        Args:
            path (str): Directory path
            
        Default implementation sets self.current_directory.
        Subclasses may override for platform-specific handling.
        """
        self.current_directory = path
    
    def close_terminal(self):
        """
        Clean shutdown of terminal.
        
        Default implementation does nothing. Subclasses should override
        to properly close PTY/subprocess and cleanup resources.
        """
        pass
    
    def is_online(self, timeout=2.0):
        """
        Check if network is available.
        
        Args:
            timeout (float): Timeout in seconds
            
        Returns:
            bool: True if online, False otherwise
            
        Default returns True. Subclasses may implement network checking.
        """
        return True
    
    def get_tab_id(self):
        """
        Get unique identifier for this terminal tab.
        
        Returns:
            str: Tab ID
        """
        return getattr(self, 'tab_id', None)
    
    # ============================================================================
    # Helper Methods - Available to all subclasses
    # ============================================================================
    
    @staticmethod
    def sanitize_wide_chars(text):
        """
        Sanitize text to work around wide character handling issues.
        
        Args:
            text (str): Input text
            
        Returns:
            str: Sanitized text
            
        This is a common utility that all implementations can use.
        """
        # Replace problematic wide characters with safe equivalents
        replacements = {
            '\u2014': '--',  # em dash
            '\u2013': '-',   # en dash
            '\u2018': "'",   # left single quote
            '\u2019': "'",   # right single quote
            '\u201c': '"',   # left double quote
            '\u201d': '"',   # right double quote
            '\u2026': '...', # ellipsis
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def _generate_tab_id(self):
        """
        Generate a unique tab ID.
        
        Returns:
            str: Unique tab ID
        """
        import uuid
        return str(uuid.uuid4())
    
    # ============================================================================
    # Property Accessors - Common to all implementations
    # ============================================================================
    
    @property
    def canvas(self):
        """Get the terminal canvas widget (for rendering)."""
        return getattr(self, '_canvas', None)
    
    @property
    def minimap(self):
        """Get the minimap widget if available."""
        return getattr(self, '_minimap', None)
    
    @property
    def search_widget(self):
        """Get the search widget if available."""
        return getattr(self, '_search_widget', None)


# Feature flag for Qt file type coloring overlay (shared across all implementations)
ENABLE_QT_FILE_COLORING = True
