# History Archival System - Implementation Summary

## Overview
Implemented a comprehensive history archival system with streaming detection for the Terminal Browser application. This feature allows users to archive old terminal output to compressed files while detecting and marking streaming pauses/resumes.

## Files Created

### 1. `core/history_file_manager.py`
- **HistoryFileManager** class for managing `.tbhist` files
- Compressed JSON format using gzip
- Features:
  - Create/delete history files per terminal tab
  - Append archived content with metadata
  - Track streaming events (stopped/resumed)
  - Get file size in human-readable format
  - Import/export functionality
  - Load and decompress archives

### 2. `ui/history_viewer_dialog.py`
- **HistoryViewerDialog** class for viewing archived content
- Features:
  - Display archived content with terminal colors
  - Navigate between multiple archives
  - Filter view (All / Content Only / Markers Only)
  - Import archives back to terminal
  - Export as plain text
  - Streaming markers with special styling

## Files Modified

### 3. `ui/pyte_terminal_widget.py`
Added streaming detection and archival capabilities:
- **New attributes:**
  - `tab_id`: Unique identifier for each terminal
  - `history_manager`: Instance of HistoryFileManager
  - `history_file_path`: Path to current history file
  - `_streaming_active`, `_streaming_stop_threshold`: Streaming state tracking
  - `_streaming_check_timer`: Timer for detecting streaming pauses
  - `_streaming_events`: List of streaming events

- **New methods:**
  - `_generate_tab_id()`: Generate unique tab ID
  - `_check_streaming_state()`: Check if streaming stopped
  - `_on_streaming_stopped()`: Handle streaming pause
  - `_on_streaming_resumed()`: Handle streaming resume
  - `_get_current_visible_line_number()`: Get current line number
  - `clear_lines_above_and_archive(row)`: Main archival method
  - `_extract_lines_for_archive()`: Extract lines with color info
  - `_clear_lines_from_buffer()`: Remove lines from pyte buffer
  - `_update_after_clear()`: Update UI after clearing
  - `get_history_file_size()`: Get formatted file size
  - `view_history_in_terminal()`: Open history viewer dialog
  - `_import_history_lines()`: Import lines from archive
  - `import_history_file()`: Import .tbhist file

- **Modified methods:**
  - `handle_output()`: Added streaming state detection
  - `show_context_menu()`: Detect clicks on viewport highlighter
  - `show_highlighter_context_menu()`: New context menu for archival

### 4. `ui/main_window.py`
Added history button and import functionality:
- **New UI element:**
  - History button in bottom bar: "📁 Check History: XMB"
  - Shows current history file size
  - Click to open history viewer

- **New methods:**
  - `open_history_viewer()`: Open history viewer for current tab
  - `update_history_button()`: Update button with file size
  - `import_history_file()`: Import .tbhist file via dialog

- **Modified methods:**
  - `update_jump_button_visibility()`: Also updates history button
  - Added "Import History File..." to File menu

### 5. `ui/terminal_tabs.py`
Added cleanup prompt when closing tabs:
- **Modified method:**
  - `close_tab()`: Prompts user to delete history file before closing
  - Options: Yes (delete) / No (keep) / Cancel (don't close)

## Features Implemented

### 1. History Archival
- **Right-click on viewport highlighter** → "Clear Lines Above Row X & Archive"
- Archives lines to compressed `.tbhist` file
- Preserves text content and color information
- Each tab has its own history file
- Files stored in `~/.terminal_browser/history/`

### 2. Streaming Detection
- **Automatic detection** of streaming pauses
- Configurable threshold (default: 3 seconds of silence)
- **Visual markers** inserted when:
  - Streaming stops (shows pause duration)
  - Streaming resumes (shows time resumed)
- Markers stored in history file with metadata

### 3. History Viewer
- View archived content within the application
- **Navigate between archives**
- **Filter options**: All / Content Only / Markers Only
- **Import** archives back to terminal
- **Export** as plain text file
- Terminal-like display with color preservation

### 4. File Format
- **Extension**: `.tbhist` (Terminal Browser History)
- **Format**: Compressed JSON (gzip)
- **Structure**:
  ```json
  {
    "version": "1.0",
    "tab_id": "abc123",
    "created_at": "2025-11-17T14:30:45",
    "archives": [
      {
        "timestamp": "...",
        "row_range": "0-500",
        "command_context": "docker-compose logs",
        "lines": [
          {"row": 1, "type": "content", "content": "...", "colors": {...}},
          {"row": 150, "type": "streaming_marker", "marker_type": "stopped", ...}
        ]
      }
    ],
    "streaming_events": [...]
  }
  ```

### 5. Import/Export
- **Import**: File → Import History File...
  - Opens file dialog filtered to `.tbhist` files
  - Validates and merges into current tab
- **Export**: From history viewer
  - Save as plain text with headers
  - Preserves structure and metadata

### 6. Cleanup on Close
- Prompts user when closing tab with history
- Options to delete or keep history file
- Shows file size in prompt

## User Workflow

### Archive Old Output
1. Long-running command generates lots of output
2. Right-click on the line number highlighter (arrow box)
3. Select "Clear Lines Above Row X & Archive"
4. Lines are archived and cleared from view
5. History button updates with file size

### View Archived Content
1. Click "📁 Check History: XMB" button in bottom bar
2. History viewer opens
3. Navigate between archives using dropdown
4. Filter view as needed
5. Option to import back to terminal or export

### Streaming Markers
- Automatically added during archival
- Show when streaming paused/resumed
- Visual separators with timestamps
- Example:
  ```
  |||||||||||||||||||||||||||||||||||||||||||||||||||||
  ⏸ Streaming paused (5.2s gap detected)
     Stopped at: 2025-11-17 14:31:02
  |||||||||||||||||||||||||||||||||||||||||||||||||||||
  ```

## Configuration
Streaming detection settings (in code):
- `_streaming_stop_threshold = 3.0`: Seconds of silence = "stopped"
- Can be made configurable via preferences in future

## Benefits
1. **Memory management**: Clear old output while preserving it
2. **Performance**: Reduces terminal buffer size for better performance
3. **Data preservation**: Never lose important logs
4. **Streaming awareness**: Track when data flow pauses/resumes
5. **Portable archives**: Share `.tbhist` files between sessions/machines
6. **Easy review**: View old output without cluttering current terminal

## Technical Details
- **Compression ratio**: Typically 5-10x reduction in file size
- **Color preservation**: ANSI color codes or pyte color attributes
- **Streaming detection**: Based on time gaps between outputs
- **Non-blocking**: Archival operations don't freeze UI
- **Scalable**: Handles large archives efficiently

## Future Enhancements (Potential)
1. Auto-archive when buffer reaches certain size
2. Search within archived content
3. Compress very old archives further
4. Cloud sync for history files
5. Configurable streaming detection threshold in preferences
6. Archive management UI (list all archives, bulk delete, etc.)
