"""Preferences management for application settings"""

import json
import os
import asyncio
import aiofiles
from PyQt5.QtCore import QSettings

class PreferencesManager:
    """Manages application preferences and settings"""
    
    # Default preferences
    DEFAULT_PREFERENCES = {
        'terminal': {
            'default_directory': os.path.expanduser('~'),
            'font_size': 13,
            'font_family': 'Menlo',
            'columns': 600,  # Default terminal columns for width
            'cursor_blink': True,
            'scroll_on_output': True,
            'scroll_on_keystroke': True,
            'show_minimap': True,
            'suggestions_files_folders': True,  # Default: enabled
            'suggestions_commands': False,  # Default: disabled
            'colored_line_numbers': True,  # Default: enabled - color line numbers based on severity
            'minimap_show_success_failure_colors': True,  # Default: enabled - show green/blue for success/info in minimap
            'minimap_custom_keywords': {  # Custom keywords for minimap highlighting
                'error': {'color': '#dc3232', 'priority': 1, 'visible': True},  # Red
                'exception': {'color': '#dc3232', 'priority': 1, 'visible': True},
                'fatal': {'color': '#dc3232', 'priority': 1, 'visible': True},
                'critical': {'color': '#dc3232', 'priority': 1, 'visible': True},
                'crash': {'color': '#dc3232', 'priority': 1, 'visible': True},
                'bug': {'color': '#ff6b68', 'priority': 2, 'visible': True},  # Light Red
                'fail': {'color': '#e67800', 'priority': 3, 'visible': True},  # Orange
                'failed': {'color': '#e67800', 'priority': 3, 'visible': True},
                'failure': {'color': '#e67800', 'priority': 3, 'visible': True},
                'denied': {'color': '#e67800', 'priority': 3, 'visible': True},
                'timeout': {'color': '#e67800', 'priority': 3, 'visible': True},
                'warn': {'color': '#ffc800', 'priority': 4, 'visible': True},  # Yellow
                'warning': {'color': '#ffc800', 'priority': 4, 'visible': True},
                'caution': {'color': '#ffc800', 'priority': 4, 'visible': True},
                'deprecated': {'color': '#ffc800', 'priority': 4, 'visible': True},
                'todo': {'color': '#ff9500', 'priority': 4, 'visible': True},  # Orange-Yellow
                'fixme': {'color': '#ff9500', 'priority': 4, 'visible': True},
                'hack': {'color': '#ff9500', 'priority': 4, 'visible': True},
                'success': {'color': '#28b428', 'priority': 5, 'visible': True},  # Green
                'passed': {'color': '#28b428', 'priority': 5, 'visible': True},
                'complete': {'color': '#28b428', 'priority': 5, 'visible': True},
                'done': {'color': '#28b428', 'priority': 5, 'visible': True},
                'info': {'color': '#4682c8', 'priority': 6, 'visible': True},  # Blue
                'note': {'color': '#4682c8', 'priority': 6, 'visible': True},
                'debug': {'color': '#9664c8', 'priority': 7, 'visible': True},  # Purple
                'trace': {'color': '#9664c8', 'priority': 7, 'visible': True},
                'verbose': {'color': '#9664c8', 'priority': 7, 'visible': True},
            },
            'auto_archive_enabled': True,  # Auto-archive old lines to history file (DEFAULT ENABLED)
            'auto_archive_threshold': 9500,  # Total lines before triggering auto-archive (95% of 10000)
            'auto_archive_keep_lines': 5000,  # How many lines to archive when threshold reached
        },
        'appearance': {
            'theme': 'dark',
            'background_color': '#1e1e1e',
            'foreground_color': '#e5e5e5',
            'cursor_color': '#00ff00',
            'selection_color': '#3399ff',
        },
        'colors': {
            'black': '#000000',
            'red': '#ff6b68',
            'green': '#5af78e',
            'yellow': '#f4f99d',
            'blue': '#57c7ff',
            'magenta': '#ff6ac1',
            'cyan': '#9aedfe',
            'white': '#f1f1f0',
            'bright_black': '#686868',
            'bright_red': '#ff8b88',
            'bright_green': '#6fff9e',
            'bright_yellow': '#ffffa5',
            'bright_blue': '#6dddff',
            'bright_magenta': '#ff7ad1',
            'bright_cyan': '#b0ffff',
            'bright_white': '#ffffff',
        },
        'behavior': {
            'confirm_on_close': True,
            'save_session_on_exit': True,
            'restore_session_on_startup': True,
            'tab_position': 'top',
        }
        ,
        'network': {
            'probe_host': '8.8.8.8',
            'probe_port': 53,
            'probe_interval': 5,
            'probe_timeout': 2
        }
    }
    
    # Color themes
    THEMES = {
        'dark': {
            'name': 'Dark (Default)',
            'background_color': '#1e1e1e',
            'foreground_color': '#e5e5e5',
            'cursor_color': '#00ff00',
            'selection_color': '#3399ff',
            'colors': {
                'black': '#000000',
                'red': '#ff6b68',
                'green': '#5af78e',
                'yellow': '#f4f99d',
                'blue': '#57c7ff',
                'magenta': '#ff6ac1',
                'cyan': '#9aedfe',
                'white': '#f1f1f0',
                'bright_black': '#686868',
                'bright_red': '#ff8b88',
                'bright_green': '#6fff9e',
                'bright_yellow': '#ffffa5',
                'bright_blue': '#6dddff',
                'bright_magenta': '#ff7ad1',
                'bright_cyan': '#b0ffff',
                'bright_white': '#ffffff',
            }
        },
        'light': {
            'name': 'Light',
            'background_color': '#ffffff',
            'foreground_color': '#000000',
            'cursor_color': '#0000ff',
            'selection_color': '#add6ff',
            'colors': {
                'black': '#000000',
                'red': '#cd3131',
                'green': '#00bc00',
                'yellow': '#949800',
                'blue': '#0451a5',
                'magenta': '#bc05bc',
                'cyan': '#0598bc',
                'white': '#555555',
                'bright_black': '#666666',
                'bright_red': '#cd3131',
                'bright_green': '#14ce14',
                'bright_yellow': '#b5ba00',
                'bright_blue': '#0451a5',
                'bright_magenta': '#bc05bc',
                'bright_cyan': '#0598bc',
                'bright_white': '#a5a5a5',
            }
        },
        'monokai': {
            'name': 'Monokai',
            'background_color': '#272822',
            'foreground_color': '#f8f8f2',
            'cursor_color': '#f8f8f0',
            'selection_color': '#49483e',
            'colors': {
                'black': '#272822',
                'red': '#f92672',
                'green': '#a6e22e',
                'yellow': '#f4bf75',
                'blue': '#66d9ef',
                'magenta': '#ae81ff',
                'cyan': '#a1efe4',
                'white': '#f8f8f2',
                'bright_black': '#75715e',
                'bright_red': '#f92672',
                'bright_green': '#a6e22e',
                'bright_yellow': '#f4bf75',
                'bright_blue': '#66d9ef',
                'bright_magenta': '#ae81ff',
                'bright_cyan': '#a1efe4',
                'bright_white': '#f9f8f5',
            }
        },
        'solarized_dark': {
            'name': 'Solarized Dark',
            'background_color': '#002b36',
            'foreground_color': '#839496',
            'cursor_color': '#93a1a1',
            'selection_color': '#073642',
            'colors': {
                'black': '#073642',
                'red': '#dc322f',
                'green': '#859900',
                'yellow': '#b58900',
                'blue': '#268bd2',
                'magenta': '#d33682',
                'cyan': '#2aa198',
                'white': '#eee8d5',
                'bright_black': '#002b36',
                'bright_red': '#cb4b16',
                'bright_green': '#586e75',
                'bright_yellow': '#657b83',
                'bright_blue': '#839496',
                'bright_magenta': '#6c71c4',
                'bright_cyan': '#93a1a1',
                'bright_white': '#fdf6e3',
            }
        },
        'dracula': {
            'name': 'Dracula',
            'background_color': '#282a36',
            'foreground_color': '#f8f8f2',
            'cursor_color': '#f8f8f2',
            'selection_color': '#44475a',
            'colors': {
                'black': '#21222c',
                'red': '#ff5555',
                'green': '#50fa7b',
                'yellow': '#f1fa8c',
                'blue': '#bd93f9',
                'magenta': '#ff79c6',
                'cyan': '#8be9fd',
                'white': '#f8f8f2',
                'bright_black': '#6272a4',
                'bright_red': '#ff6e6e',
                'bright_green': '#69ff94',
                'bright_yellow': '#ffffa5',
                'bright_blue': '#d6acff',
                'bright_magenta': '#ff92df',
                'bright_cyan': '#a4ffff',
                'bright_white': '#ffffff',
            }
        }
    }
    
    def __init__(self):
        self.settings = QSettings()
        self.preferences_file = os.path.expanduser("~/.terminal_browser_preferences.json")
        self._preferences = None
        self._load_lock = asyncio.Lock()
        self._save_lock = asyncio.Lock()
        # Load synchronously on init for immediate availability
        self.load_preferences_sync()
    
    async def load_preferences(self):
        """Load preferences from file or use defaults asynchronously"""
        async with self._load_lock:
            try:
                if os.path.exists(self.preferences_file):
                    async with aiofiles.open(self.preferences_file, 'r') as f:
                        content = await f.read()
                        loaded_prefs = json.loads(content)
                        # Merge with defaults to ensure all keys exist
                        self._preferences = self._deep_merge(self.DEFAULT_PREFERENCES.copy(), loaded_prefs)
                else:
                    self._preferences = self.DEFAULT_PREFERENCES.copy()
            except Exception as e:
                self._preferences = self.DEFAULT_PREFERENCES.copy()
    
    def load_preferences_sync(self):
        """Synchronous wrapper for backwards compatibility"""
        try:
            if os.path.exists(self.preferences_file):
                with open(self.preferences_file, 'r') as f:
                    loaded_prefs = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._preferences = self._deep_merge(self.DEFAULT_PREFERENCES.copy(), loaded_prefs)
            else:
                self._preferences = self.DEFAULT_PREFERENCES.copy()
        except Exception as e:
            self._preferences = self.DEFAULT_PREFERENCES.copy()
    
    async def save_preferences(self):
        """Save preferences to file asynchronously"""
        async with self._save_lock:
            try:
                async with aiofiles.open(self.preferences_file, 'w') as f:
                    await f.write(json.dumps(self._preferences, indent=2))
                return True
            except Exception as e:
                return False
    
    def save_preferences_sync(self):
        """Synchronous wrapper for backwards compatibility"""
        try:
            with open(self.preferences_file, 'w') as f:
                json.dump(self._preferences, f, indent=2)
            return True
        except Exception as e:
            return False
    
    def get(self, category, key, default=None):
        """Get a specific preference value"""
        try:
            return self._preferences.get(category, {}).get(key, default)
        except:
            return default
    
    def set(self, category, key, value):
        """Set a specific preference value"""
        if category not in self._preferences:
            self._preferences[category] = {}
        self._preferences[category][key] = value
    
    def get_category(self, category):
        """Get all preferences for a category"""
        return self._preferences.get(category, {}).copy()
    
    def set_category(self, category, values):
        """Set all preferences for a category"""
        self._preferences[category] = values.copy()
    
    def get_all(self):
        """Get all preferences"""
        return self._preferences.copy()
    
    def reset_to_defaults(self):
        """Reset all preferences to defaults"""
        self._preferences = self.DEFAULT_PREFERENCES.copy()
        self.save_preferences_sync()
    
    async def reset_to_defaults_async(self):
        """Reset all preferences to defaults asynchronously"""
        self._preferences = self.DEFAULT_PREFERENCES.copy()
        await self.save_preferences()
    
    def apply_theme(self, theme_name):
        """Apply a color theme"""
        if theme_name in self.THEMES:
            theme = self.THEMES[theme_name]
            self.set('appearance', 'theme', theme_name)
            self.set('appearance', 'background_color', theme['background_color'])
            self.set('appearance', 'foreground_color', theme['foreground_color'])
            self.set('appearance', 'cursor_color', theme['cursor_color'])
            self.set('appearance', 'selection_color', theme['selection_color'])
            self._preferences['colors'] = theme['colors'].copy()
            return True
        return False
    
    def get_theme_names(self):
        """Get list of available theme names"""
        return [(name, theme['name']) for name, theme in self.THEMES.items()]
    
    def _deep_merge(self, base, update):
        """Deep merge two dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

