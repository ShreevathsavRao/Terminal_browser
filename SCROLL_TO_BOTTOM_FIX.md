# Scroll to Bottom Fix

## Problem
When running long-running commands that produce continuous output (like `docker-compose logs -f`), the terminal buffer fills up and the user loses sight of the current prompt/input area. The terminal stays scrolled in the middle of the output rather than following the latest output to the bottom.

## Solution
Added multiple ways to quickly jump to the bottom of the terminal to see the prompt:

### 1. Jump to Bottom Button
- Added a new **"↓ Jump to Bottom"** button in the terminal control bar (next to Font Size)
- Click this button to immediately scroll to the bottom of the terminal
- Useful when you're lost in scrollback and want to see the current prompt

### 2. Keyboard Shortcuts
Added two keyboard shortcuts to jump to bottom:

**macOS:**
- `Cmd+End` - Jump to bottom
- `Cmd+Down` - Jump to bottom (alternative)

**Windows/Linux:**
- `Ctrl+End` - Jump to bottom
- `Ctrl+Down` - Jump to bottom (alternative)

### 3. Implementation Details
- Added `force_scroll_to_bottom()` method that bypasses all throttling and user scroll tracking
- This ensures immediate jump to bottom regardless of terminal state
- Resets auto-scroll behavior so terminal continues following new output

## Usage
When running a command with continuous output like:
```bash
docker-compose logs -f backend
```

And you lose sight of the prompt:
1. **Click** the "↓ Jump to Bottom" button, OR
2. **Press** `Cmd+End` (Mac) or `Ctrl+End` (Windows/Linux)

The terminal will immediately scroll to the bottom where you can see the latest output and your prompt.

## Files Modified
- `ui/pyte_terminal_widget.py`:
  - Added "↓ Jump to Bottom" button to control bar
  - Added `force_scroll_to_bottom()` method
  - Added keyboard shortcuts in `handle_key_press()` method
