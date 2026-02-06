"""Debug configuration - Edit this file to control debug logging

To enable debug logging:
1. Set ENABLE_DEBUG = True
2. Choose which categories to enable in ENABLED_CATEGORIES
3. Restart the application

Available categories:
- 'ui': UI events and interactions
- 'terminal': Terminal operations and PTY
- 'keys': Keyboard input and shortcuts
- 'output': Terminal output processing
- 'canvas': Canvas rendering and painting
- 'scroll': Scrolling and autoscroll
- 'commands': Command execution and history
- 'suggestions': Command suggestions and autocomplete
- 'sessions': Session recording and playback
- 'directory': Directory changes and tracking
- 'selection': Text selection and copying
- 'hover': Hover detection and file paths
- 'prompt': Prompt detection
- 'buffer': Output buffering and async operations
- 'state': State management
- 'performance': Performance metrics
- 'error': Errors and exceptions
"""

# Master switch - set to True to enable debug logging
ENABLE_DEBUG = False

# Enable all categories (overrides ENABLED_CATEGORIES if True)
ENABLE_ALL = False

# List of enabled categories (only used if ENABLE_ALL is False)
# Uncomment the categories you want to debug:
ENABLED_CATEGORIES = [
    # 'ui',
    # 'terminal',
    # 'keys',
    # 'output',
    # 'canvas',
    # 'scroll',
    # 'commands',
    # 'suggestions',
    # 'sessions',
    # 'directory',
    # 'selection',
    # 'hover',
    # 'prompt',
    # 'buffer',
    # 'state',
    # 'performance',
    # 'error',
]

# Quick presets - uncomment one to use
# ENABLED_CATEGORIES = ['terminal', 'commands', 'output']  # Terminal operations only
# ENABLED_CATEGORIES = ['ui', 'keys', 'selection']  # UI interactions only
# ENABLED_CATEGORIES = ['performance', 'buffer', 'canvas']  # Performance debugging
