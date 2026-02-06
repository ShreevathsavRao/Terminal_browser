"""Platform detection and OS-specific configurations"""

import sys
import platform
from enum import Enum


class OSType(Enum):
    """Operating system types"""
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    UNKNOWN = "unknown"


class PlatformManager:
    """Manages platform-specific settings and configurations"""
    
    def __init__(self):
        self._os_type = self._detect_os()
        self._os_version = platform.version()
        self._os_release = platform.release()
    
    @staticmethod
    def _detect_os():
        """Detect the operating system"""
        system = sys.platform.lower()
        
        if system == 'darwin':
            return OSType.MACOS
        elif system.startswith('win'):
            return OSType.WINDOWS
        elif system.startswith('linux'):
            return OSType.LINUX
        else:
            return OSType.UNKNOWN
    
    @property
    def os_type(self):
        """Get the OS type"""
        return self._os_type
    
    @property
    def is_macos(self):
        """Check if running on macOS"""
        return self._os_type == OSType.MACOS
    
    @property
    def is_windows(self):
        """Check if running on Windows"""
        return self._os_type == OSType.WINDOWS
    
    @property
    def is_linux(self):
        """Check if running on Linux"""
        return self._os_type == OSType.LINUX
    
    @property
    def os_name(self):
        """Get human-readable OS name"""
        if self.is_macos:
            return "macOS"
        elif self.is_windows:
            return "Windows"
        elif self.is_linux:
            return "Linux"
        else:
            return "Unknown"
    
    @property
    def os_version(self):
        """Get OS version"""
        return self._os_version
    
    def get_modifier_key_name(self, key_type='primary'):
        """Get the name of modifier keys for this platform
        
        Args:
            key_type: 'primary' for main modifier (Cmd/Ctrl),
                     'secondary' for Alt/Option,
                     'tertiary' for shift
        
        Returns:
            Human-readable key name
        """
        if key_type == 'primary':
            return "Cmd" if self.is_macos else "Ctrl"
        elif key_type == 'secondary':
            return "Option" if self.is_macos else "Alt"
        elif key_type == 'tertiary':
            return "Shift"
        return ""
    
    def get_shortcut_display(self, keys):
        """Convert shortcut keys to platform-specific display format
        
        Args:
            keys: List of keys, e.g., ['primary', 'C'] or ['primary', 'shift', 'V']
        
        Returns:
            Platform-specific shortcut string, e.g., "Cmd+C" or "Ctrl+C"
        """
        display_keys = []
        
        for key in keys:
            if key == 'primary':
                display_keys.append(self.get_modifier_key_name('primary'))
            elif key == 'secondary':
                display_keys.append(self.get_modifier_key_name('secondary'))
            elif key == 'shift':
                display_keys.append("Shift")
            else:
                display_keys.append(key)
        
        return "+".join(display_keys)
    
    def get_copy_shortcut(self):
        """Get the copy shortcut for this platform"""
        if self.is_macos:
            return "Cmd+C"
        else:
            return "Ctrl+Shift+C"
    
    def get_paste_shortcut(self):
        """Get the paste shortcut for this platform"""
        if self.is_macos:
            return "Cmd+V"
        else:
            return "Ctrl+Shift+V"
    
    def get_select_all_shortcut(self):
        """Get the select all shortcut for this platform"""
        if self.is_macos:
            return "Cmd+A"
        else:
            return "Ctrl+Shift+A"
    
    def get_clear_screen_shortcut(self):
        """Get the clear screen shortcut for this platform"""
        if self.is_macos:
            return "Cmd+K"
        else:
            return "Ctrl+L"
    
    def get_new_tab_shortcut(self):
        """Get the new tab shortcut for this platform"""
        if self.is_macos:
            return "Shift+Cmd+T"
        else:
            return "Ctrl+Shift+T"
    
    def get_close_tab_shortcut(self):
        """Get the close tab shortcut for this platform"""
        if self.is_macos:
            return "Shift+Cmd+W"
        else:
            return "Ctrl+Shift+W"
    
    def get_all_shortcuts(self):
        """Get all platform-specific shortcuts
        
        Returns:
            Dictionary of shortcut descriptions and their keys
        """
        shortcuts = {
            'copy': {
                'description': 'Copy selected text',
                'shortcut': self.get_copy_shortcut(),
                'category': 'editing'
            },
            'paste': {
                'description': 'Paste text',
                'shortcut': self.get_paste_shortcut(),
                'category': 'editing'
            },
            'select_all': {
                'description': 'Select all text',
                'shortcut': self.get_select_all_shortcut(),
                'category': 'editing'
            },
            'clear_screen': {
                'description': 'Clear terminal screen',
                'shortcut': self.get_clear_screen_shortcut(),
                'category': 'terminal'
            },
            'new_tab': {
                'description': 'Open new tab',
                'shortcut': self.get_new_tab_shortcut(),
                'category': 'window'
            },
            'close_tab': {
                'description': 'Close current tab',
                'shortcut': self.get_close_tab_shortcut(),
                'category': 'window'
            }
        }
        
        # macOS-specific shortcuts
        if self.is_macos:
            shortcuts.update({
                'cut': {
                    'description': 'Cut selected text',
                    'shortcut': 'Cmd+X',
                    'category': 'editing'
                },
                'word_left': {
                    'description': 'Move cursor one word left',
                    'shortcut': 'Option+Left',
                    'category': 'navigation'
                },
                'word_right': {
                    'description': 'Move cursor one word right',
                    'shortcut': 'Option+Right',
                    'category': 'navigation'
                },
                'delete_word': {
                    'description': 'Delete word to the left',
                    'shortcut': 'Option+Backspace',
                    'category': 'editing'
                },
                'close_other_tabs': {
                    'description': 'Close all other tabs',
                    'shortcut': 'Option+Cmd+W',
                    'category': 'window'
                }
            })
        
        # Terminal shortcuts (same on all platforms)
        terminal_shortcuts = {
            'beginning_of_line': {
                'description': 'Move to beginning of line',
                'shortcut': 'Ctrl+A',
                'category': 'terminal'
            },
            'end_of_line': {
                'description': 'Move to end of line',
                'shortcut': 'Ctrl+E',
                'category': 'terminal'
            },
            'delete_word_bash': {
                'description': 'Delete word before cursor',
                'shortcut': 'Ctrl+W',
                'category': 'terminal'
            },
            'kill_to_end': {
                'description': 'Cut text to end of line',
                'shortcut': 'Ctrl+K',
                'category': 'terminal'
            },
            'kill_to_start': {
                'description': 'Cut text to start of line',
                'shortcut': 'Ctrl+U',
                'category': 'terminal'
            },
            'reverse_search': {
                'description': 'Reverse search history',
                'shortcut': 'Ctrl+R',
                'category': 'terminal'
            },
            'interrupt': {
                'description': 'Send interrupt signal',
                'shortcut': 'Ctrl+C',
                'category': 'terminal'
            },
            'suspend': {
                'description': 'Suspend current process',
                'shortcut': 'Ctrl+Z',
                'category': 'terminal'
            }
        }
        
        shortcuts.update(terminal_shortcuts)
        return shortcuts
    
    def format_info(self):
        """Get formatted platform information"""
        return {
            'os_type': self.os_name,
            'os_version': self._os_version,
            'os_release': self._os_release,
            'platform': sys.platform,
            'python_version': sys.version,
            'shortcuts': self.get_all_shortcuts()
        }
    
    def __str__(self):
        """String representation"""
        return f"PlatformManager({self.os_name}, {sys.platform})"
    
    def __repr__(self):
        """Debug representation"""
        return f"PlatformManager(os_type={self._os_type}, platform={sys.platform})"


# Singleton instance
_platform_manager = None

def get_platform_manager():
    """Get the singleton platform manager instance"""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager





