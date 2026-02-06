"""
Terminal Widgets Module - Platform-Specific Terminal Implementations
=====================================================================

This module automatically selects and exports the appropriate terminal widget
implementation based on the detected operating system.

Platform Support:
- Windows: Uses subprocess.Popen with pipes (WindowsTerminalWidget)
- macOS/Linux: Uses PTY with pty.openpty() and os.fork() (UnixTerminalWidget)

Usage:
    from ui.terminal_widgets import TerminalWidget
    
    # TerminalWidget will be the correct implementation for current platform
    terminal = TerminalWidget(shell=None, prefs_manager=None)
    terminal.start_shell()

The platform detection happens at import time using the platform_manager module,
ensuring zero runtime overhead for platform checking.
"""

from core.platform_manager import get_platform_manager

# Detect platform at import time
platform_mgr = get_platform_manager()

if platform_mgr.is_windows:
    # Windows: Use subprocess-based implementation
    from ui.terminal_widgets.windows_terminal_widget import WindowsTerminalWidget as TerminalWidget
else:
    # macOS and Linux: Use PTY-based implementation
    from ui.terminal_widgets.unix_terminal_widget import UnixTerminalWidget as TerminalWidget

# Export the platform-appropriate widget
__all__ = ['TerminalWidget']
