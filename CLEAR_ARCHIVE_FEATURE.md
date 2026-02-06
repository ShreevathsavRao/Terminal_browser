# Clear Screen Archive Feature

## Overview
When the terminal screen is cleared (using the clear command, Cmd+K, or Ctrl+L), all terminal content is now automatically archived to a history file before being cleared. This ensures that no data is lost when you clear the screen.

## How It Works

### Automatic Archiving
When you clear the terminal screen, the system:
1. **Captures all content**: Extracts all visible lines and scrollback history
2. **Archives to history file**: Saves the content to a compressed `.tbhist` file
3. **Labels the archive**: Tags it with "clear" as the command context
4. **Clears the screen**: Sends the clear command to the terminal

### Triggering Clear with Archive

The archive-before-clear feature is triggered by:

1. **Typing the `clear` command**: When you type `clear` and press Enter in the terminal

2. **Keyboard Shortcuts**:
   - **macOS**: `Cmd+K` (like macOS Terminal)
   - **All platforms**: `Ctrl+L` (standard clear screen shortcut)

3. **Quick Action Menu**:
   - Click the Quick Action button (⚡) in the top toolbar
   - Select "Clear Terminal"

### Viewing Archived Content

To view content that was archived when you cleared the screen:

1. **Right-click** in the terminal window
2. Select **"View History in Terminal"** from the context menu
3. Browse through the archived content in the History Viewer dialog
4. Look for entries with "clear" as the command context

## History File Location

Archived content is stored in:
```
~/.terminal_browser/history/terminal_history_<tab_id>_<timestamp>.tbhist
```

Files are compressed (gzip) to save disk space.

## Features

- **Selective Archiving**: Only archives content if there are more than 3 lines (skips nearly empty screens)
- **Editor-Aware**: When using editors like nano or vim (alternate screen mode), Ctrl+L is passed through without archiving since editors handle their own display
- **No Data Loss**: Even if archiving fails for any reason, the clear command still executes

## Integration with Existing Features

This feature works seamlessly with:
- **History Viewer**: View all archived content including clear operations
- **Auto-Archive**: Works alongside automatic archival when buffer gets too large
- **Session Recording**: Clear operations are captured in session recordings

## Technical Details

- Archives include text content, colors, and row information
- Command context is set to "clear" for easy identification
- Archiving happens before the clear command is sent to the PTY
- Thread-safe and doesn't block the UI

## Benefits

1. **Never lose important output**: Accidentally cleared the screen? Your data is safely archived
2. **Review past sessions**: Browse through all your terminal history, including cleared content
3. **Debugging**: Recover error messages or logs that were cleared
4. **Audit trail**: Complete record of all terminal activity

## Example Use Cases

- **Cleared before saving output**: Retrieve important logs that were cleared before you could copy them
- **Long-running processes**: Clear screen periodically without losing historical output
- **Debugging sessions**: Review multiple iterations of output even after clearing
- **Command history**: See the context around specific commands even if the screen was cleared

## Notes

- Archiving is lightweight and doesn't noticeably impact performance
- History files are compressed to minimize disk usage
- You can manage history files through the History Viewer dialog
- The feature respects your privacy - archives are stored locally only
