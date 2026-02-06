# Minimap and Quick Actions Feature

## Overview
Added two new features to the Terminal Browser application:
1. **Minimap** - A visual overview of terminal content with scroll navigation
2. **Quick Actions Button** - A bottom toolbar with quick access to common actions

## Features Added

### 1. Minimap Widget (`ui/minimap_widget.py`)
- **MinimapWidget**: Core minimap component that displays a scaled-down view of terminal content
  - Shows up to 100 lines of content with intelligent sampling for larger content
  - Color-coded display: prompts in blue, errors in red, regular content in gray
  - Viewport indicator showing current visible area
  - Click-to-scroll functionality
  - Mouse wheel scrolling support
  
- **MinimapPanel**: Container panel with title label
  - Clean, styled interface matching application theme
  - Integrates seamlessly with existing layout

### 2. Main Window Integration
- Added minimap panel to the main splitter (4 panels now: Groups | Terminals | Minimap | Buttons)
- Toggle button in toolbar (🗺 Map) to show/hide minimap
- Menu item: View → Toggle Minimap
- Minimap automatically updates every second
- Syncs with terminal tab changes and group switches
- Click on minimap to jump to position in terminal
- Settings persistence (remembers show/hide state across sessions)

### 3. Quick Actions Bottom Button
- Added bottom toolbar with quick access to common actions
- Shows as "⚡ Quick Actions: Clear Terminal | New Tab | Focus Terminal"
- Click to open context menu with:
  - 🧹 Clear Terminal - Clears current terminal
  - 📄 New Tab - Creates a new terminal tab
  - 🎯 Focus Terminal - Sets focus to terminal
  - 📋 Copy Last Command - Copies last executed command to clipboard
  - 📜 Command History - Opens command history search
  - 🔍+/🔍-/🔍= Zoom controls - In/Out/Reset
- Provides visual feedback when copying commands

## Layout Changes
- Previous layout: Groups (20%) | Terminals (55%) | Buttons (25%)
- New layout: Groups (15%) | Terminals (45%) | Minimap (10%) | Buttons (30%)
- All panels can be toggled independently
- Sizes are stored and restored across sessions

## Usage

### Minimap
1. **Toggle visibility**: Click "🗺 Map" button in toolbar or View → Toggle Minimap
2. **Navigate**: Click anywhere on minimap to jump to that position
3. **Scroll**: Use mouse wheel on minimap to scroll terminal
4. **Visual cues**: 
   - Blue rectangles = command prompts
   - Red rectangles = errors or failures
   - Gray rectangles = normal content
   - Light blue overlay = current viewport

### Quick Actions
1. **Open menu**: Click the bottom "⚡ Quick Actions" button
2. **Select action**: Click any menu item to execute
3. **Copy feedback**: When copying last command, button shows "✓ Copied: [command]" for 2 seconds

## Technical Details

### New Files
- `ui/minimap_widget.py` - Minimap widget implementation (201 lines)

### Modified Files
- `ui/main_window.py`:
  - Added minimap panel to splitter
  - Added quick actions button and menu
  - Connected signals for minimap updates
  - Added minimap toggle functionality
  - Added quick action methods
  - Updated settings persistence

### Key Methods
- `update_minimap_content()` - Updates minimap with current terminal content
- `on_minimap_clicked(position_ratio)` - Handles minimap click navigation
- `toggle_minimap_panel()` - Shows/hides minimap
- `show_quick_actions()` - Displays quick action menu
- `quick_clear_terminal()` - Clears current terminal
- `quick_focus_terminal()` - Focuses current terminal
- `quick_copy_last_command()` - Copies last command to clipboard

## Performance Considerations
- Minimap updates are batched (max every 100ms)
- Content sampling for large terminals (max 100 lines)
- Antialiasing disabled for faster rendering
- Update timer runs every 1 second to reduce overhead

## Future Enhancements
- Add syntax highlighting to minimap
- Show search results in minimap
- Add bookmark markers
- Customize minimap width
- Add minimap zoom levels
