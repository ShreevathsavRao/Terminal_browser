# Terminal Search Feature

## Overview
Added in-terminal search functionality with Command+F (macOS) and Ctrl+Shift+F (Windows/Linux) keyboard shortcuts.

## Features

### Search Widget
- **Location**: `ui/terminal_search_widget.py`
- Modern search bar UI with:
  - Search input field with placeholder text
  - Match counter showing "X/Y" results
  - Previous (↑) and Next (↓) navigation buttons
  - Case sensitivity toggle (Aa)
  - Whole word matching toggle (Ab)
  - Close button (✕)

### Search Functionality
- **Real-time search**: Results update as you type
- **Highlight all matches**: Yellow highlighting for all matches
- **Current match emphasis**: Orange highlighting for the currently selected match
- **Smart scrolling**: Automatically scrolls to position matches at 1/3 from viewport top
- **Full history search**: Searches through both visible content and scrollback history

### Keyboard Shortcuts
- **macOS**: `Command+F` - Opens search
- **Windows/Linux**: `Ctrl+Shift+F` - Opens search (Ctrl+F conflicts with terminal navigation)
- **Enter**: Navigate to next match
- **Shift+Enter**: Navigate to previous match
- **Escape**: Close search and clear highlights

### Search Options
1. **Case Sensitive**: Match exact case when enabled
2. **Whole Word**: Only match complete words (not substrings)

## Implementation Details

### Files Modified
1. `ui/pyte_terminal_widget.py`
   - Added search widget integration in `init_ui()`
   - Implemented search methods: `show_search()`, `_on_search_requested()`, `_on_search_next()`, `_on_search_previous()`, `_on_search_closed()`, `_highlight_current_match()`
   - Added keyboard shortcuts in `handle_key_press()`: Cmd+F (macOS) and Ctrl+Shift+F (Windows/Linux)
   - Added search state variables: `search_matches`, `current_match_index`

2. `ui/terminal_search_widget.py` (NEW FILE)
   - Created search widget with all UI components
   - Signals for search requests, navigation, and closing
   - Keyboard event handling for Enter/Shift+Enter/Escape

### Canvas Rendering
- Added `search_matches` and `current_search_match` variables to `TerminalCanvas`
- Implemented `draw_search_highlights()` method to render match highlights
- Integrated search highlighting in `paintEvent()` after selection highlight

### Color Scheme
- **All matches**: Yellow (`#ffff00`) with 100 alpha (transparency)
- **Current match**: Orange (`#ff8800`) with 150 alpha (more prominent)

## Usage Example

1. Open the terminal browser application
2. Run some commands to generate output (e.g., `ls -la`, `cat README.md`)
3. Press `Command+F` (macOS) or `Ctrl+Shift+F` (Windows/Linux)
4. Type text to search for (e.g., "python")
5. Use Enter/Shift+Enter or arrow buttons to navigate matches
6. Toggle case sensitivity or whole word matching as needed
7. Press Escape to close search

## Future Enhancements
- Regex search support
- Search within selection
- Search history (remember recent searches)
- Keyboard shortcut to jump to search bar without closing it
- Find and replace functionality
