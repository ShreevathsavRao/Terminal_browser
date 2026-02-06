"""Centralized debug logging system for terminal browser

This module provides a configurable debug logging system that can be enabled/disabled
globally or per-category for detailed diagnostics.

Usage:
    from core.debug_logger import debug_log, set_debug_enabled, set_category_enabled
    
    # Enable all debug logging
    set_debug_enabled(True)
    
    # Enable specific categories only
    set_category_enabled('ui', True)
    set_category_enabled('terminal', True)
    
    # Use in code
    debug_log('ui', 'Button clicked', button_id=123)
    debug_log('terminal', 'Command executed', command='ls -la', exit_code=0)
"""

import time
from typing import Any, Dict, Optional
from datetime import datetime

# Global debug settings
_DEBUG_ENABLED = False  # Master switch - set to True to enable all debug logging
_CATEGORY_SETTINGS = {}  # Per-category settings

# Available debug categories
DEBUG_CATEGORIES = {
    'ui': 'UI events and interactions',
    'terminal': 'Terminal operations and PTY',
    'keys': 'Keyboard input and shortcuts',
    'output': 'Terminal output processing',
    'canvas': 'Canvas rendering and painting',
    'scroll': 'Scrolling and autoscroll',
    'commands': 'Command execution and history',
    'suggestions': 'Command suggestions and autocomplete',
    'sessions': 'Session recording and playback',
    'directory': 'Directory changes and tracking',
    'selection': 'Text selection and copying',
    'hover': 'Hover detection and file paths',
    'prompt': 'Prompt detection',
    'buffer': 'Output buffering and async operations',
    'state': 'State management',
    'performance': 'Performance metrics',
    'error': 'Errors and exceptions',
}

# Color codes for terminal output
COLORS = {
    'reset': '\033[0m',
    'bold': '\033[1m',
    'dim': '\033[2m',
    'red': '\033[91m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
}

# Category colors
CATEGORY_COLORS = {
    'ui': 'cyan',
    'terminal': 'green',
    'keys': 'yellow',
    'output': 'blue',
    'canvas': 'magenta',
    'scroll': 'cyan',
    'commands': 'green',
    'suggestions': 'blue',
    'sessions': 'magenta',
    'directory': 'yellow',
    'selection': 'cyan',
    'hover': 'blue',
    'prompt': 'green',
    'buffer': 'magenta',
    'state': 'yellow',
    'performance': 'red',
    'error': 'red',
}


def set_debug_enabled(enabled: bool):
    """Enable or disable all debug logging globally
    
    Args:
        enabled: True to enable, False to disable
    """
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = enabled


def set_category_enabled(category: str, enabled: bool):
    """Enable or disable debug logging for a specific category
    
    Args:
        category: Category name (e.g., 'ui', 'terminal', 'keys')
        enabled: True to enable, False to disable
    """
    global _CATEGORY_SETTINGS
    _CATEGORY_SETTINGS[category] = enabled
    status = 'ENABLED' if enabled else 'DISABLED'


def is_debug_enabled(category: str = None) -> bool:
    """Check if debug logging is enabled
    
    Args:
        category: Optional category to check. If None, checks global setting.
    
    Returns:
        True if debug logging is enabled for this category
    """
    if not _DEBUG_ENABLED:
        return False
    
    if category is None:
        return True
    
    # Check category-specific setting (defaults to enabled if not set)
    return _CATEGORY_SETTINGS.get(category, True)


def debug_log(category: str, message: str, **kwargs):
    """Log a debug message with optional key-value pairs
    
    Args:
        category: Debug category (e.g., 'ui', 'terminal', 'keys')
        message: Debug message
        **kwargs: Optional key-value pairs to include in the log
    
    Example:
        debug_log('ui', 'Button clicked', button_id=5, action='submit')
        debug_log('terminal', 'Command executed', command='ls', exit_code=0)
    """
    if not is_debug_enabled(category):
        return
    
    # Get timestamp
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    
    # Get color for category
    color_name = CATEGORY_COLORS.get(category, 'white')
    color = COLORS.get(color_name, '')
    reset = COLORS['reset']
    bold = COLORS['bold']
    
    # Format category tag
    category_tag = f"[{category.upper():12s}]"
    
    # Format message with kwargs
    if kwargs:
        kwargs_str = ' | ' + ', '.join(f"{k}={repr(v)}" for k, v in kwargs.items())
    else:
        kwargs_str = ''
    
    # Print formatted log


def debug_section(category: str, title: str):
    """Log a debug section header for better readability
    
    Args:
        category: Debug category
        title: Section title
    
    Example:
        debug_section('terminal', 'EXECUTING COMMAND')
    """
    if not is_debug_enabled(category):
        return
    
    color_name = CATEGORY_COLORS.get(category, 'white')
    color = COLORS.get(color_name, '')
    reset = COLORS['reset']
    bold = COLORS['bold']
    
    separator = '=' * 60


def debug_func_entry(category: str, func_name: str, **kwargs):
    """Log function entry with parameters
    
    Args:
        category: Debug category
        func_name: Function name
        **kwargs: Function parameters
    
    Example:
        debug_func_entry('terminal', 'execute_command', command='ls', env={})
    """
    if not is_debug_enabled(category):
        return
    
    params_str = ', '.join(f"{k}={repr(v)}" for k, v in kwargs.items())
    debug_log(category, f"→ {func_name}({params_str})")


def debug_func_exit(category: str, func_name: str, result: Any = None):
    """Log function exit with return value
    
    Args:
        category: Debug category
        func_name: Function name
        result: Return value (optional)
    
    Example:
        debug_func_exit('terminal', 'execute_command', result=0)
    """
    if not is_debug_enabled(category):
        return
    
    if result is not None:
        debug_log(category, f"← {func_name} → {repr(result)}")
    else:
        debug_log(category, f"← {func_name}")


def debug_timer_start(category: str, operation: str) -> float:
    """Start a performance timer
    
    Args:
        category: Debug category
        operation: Operation name
    
    Returns:
        Start time (for passing to debug_timer_end)
    
    Example:
        start = debug_timer_start('canvas', 'paintEvent')
        # ... do work ...
        debug_timer_end('canvas', 'paintEvent', start)
    """
    if not is_debug_enabled(category):
        return 0
    
    start_time = time.perf_counter()
    debug_log(category, f"⏱️  {operation} started")
    return start_time


def debug_timer_end(category: str, operation: str, start_time: float):
    """End a performance timer and log duration
    
    Args:
        category: Debug category
        operation: Operation name
        start_time: Start time from debug_timer_start
    
    Example:
        start = debug_timer_start('canvas', 'paintEvent')
        # ... do work ...
        debug_timer_end('canvas', 'paintEvent', start)
    """
    if not is_debug_enabled(category):
        return
    
    if start_time > 0:
        duration_ms = (time.perf_counter() - start_time) * 1000
        debug_log(category, f"⏱️  {operation} completed", duration_ms=f"{duration_ms:.2f}ms")


def debug_error(category: str, message: str, exception: Exception = None, **kwargs):
    """Log an error with optional exception
    
    Args:
        category: Debug category
        message: Error message
        exception: Optional exception object
        **kwargs: Additional context
    
    Example:
        try:
            # ... some code ...
        except Exception as e:
            debug_error('terminal', 'Failed to execute command', exception=e, command='ls')
    """
    # Always log errors, even if debug is disabled for this category
    color = COLORS['red']
    reset = COLORS['reset']
    bold = COLORS['bold']
    
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    category_tag = f"[{category.upper():12s}]"
    
    # Format message with kwargs
    if kwargs:
        kwargs_str = ' | ' + ', '.join(f"{k}={repr(v)}" for k, v in kwargs.items())
    else:
        kwargs_str = ''
    
    
    if exception:
        # Optionally print traceback
        import traceback
        if is_debug_enabled(category):
            traceback.print_exc()


def print_debug_config():
    """Print current debug configuration"""
    for category, description in DEBUG_CATEGORIES.items():
        enabled = _CATEGORY_SETTINGS.get(category, True) if _DEBUG_ENABLED else False
        status = '✓' if enabled else '✗'


# Convenience function to enable common debug categories
def enable_common_categories():
    """Enable commonly used debug categories"""
    set_debug_enabled(True)
    set_category_enabled('terminal', True)
    set_category_enabled('commands', True)
    set_category_enabled('output', True)
    set_category_enabled('keys', True)


def enable_all_categories():
    """Enable all debug categories"""
    set_debug_enabled(True)
    for category in DEBUG_CATEGORIES:
        set_category_enabled(category, True)


def disable_all_categories():
    """Disable all debug categories"""
    set_debug_enabled(False)
