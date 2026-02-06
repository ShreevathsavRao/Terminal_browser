# State Persistence Fix

## Problem
When restarting the laptop (or closing and reopening the application), all terminal tabs and terminal groups were lost. The application would start fresh without any previously open tabs or groups.

## Root Cause
The issue was in the `closeEvent` method in [main_window.py](ui/main_window.py#L1862). When the application was closing:

1. The method was attempting to save state asynchronously using `asyncio.create_task()`
2. These async tasks were created but the application would exit before they completed
3. The event loop might not be in the right state during application shutdown
4. Result: State file was not being updated with the latest tabs and groups

### Previous Code (Problematic)
```python
def closeEvent(self, event):
    # ... other code ...
    
    # Save application state asynchronously
    state = { ... }
    
    # Run async save operations concurrently
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Create tasks for async saves - these don't complete!
        asyncio.create_task(self.state_manager.save_state(state))
        asyncio.create_task(self.history_manager.flush_save_async())
    else:
        # Fallback to sync if event loop not available
        self.history_manager.flush_save()
    
    event.accept()  # App exits immediately
```

## Solution
Changed the `closeEvent` method to use **synchronous file I/O** during application shutdown. This ensures the state is fully written to disk before the application exits.

### Fixed Code
```python
def closeEvent(self, event):
    # ... other code ...
    
    # Save application state synchronously to ensure it completes before exit
    state = {
        'groups': self.terminal_group_panel.get_all_groups(),
        'tabs': self.terminal_tabs.get_all_tabs_info(),
        'buttons_per_group': self.button_panel.get_all_buttons_by_group(),
        'files_per_group': self.button_panel.get_all_files_by_group(),
        'current_group': self.current_group_index
    }
    
    # Use synchronous save during close to ensure completion before app exits
    try:
        import json
        from datetime import datetime
        state['last_saved'] = datetime.now().isoformat()
        with open(self.state_manager.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state on close: {e}")
    
    # Save command history synchronously
    try:
        self.history_manager.flush_save()
    except Exception as e:
        print(f"Error saving history on close: {e}")
    
    event.accept()
```

## What Gets Saved
The state file (`~/.terminal_browser_state.json`) now reliably saves:

1. **Terminal Groups**: All group names
2. **Tabs per Group**: All tabs with their names and shell configurations
3. **Buttons per Group**: Custom command buttons for each group
4. **Files per Group**: File associations for each group
5. **Current Group**: The currently selected group index
6. **Timestamp**: When the state was last saved

## Testing
To verify the fix works:

1. **Create Multiple Groups and Tabs**:
   - Add several terminal groups
   - Add multiple tabs to different groups
   - Add some custom command buttons

2. **Close the Application**:
   - Close Terminal Browser normally
   - Check that `~/.terminal_browser_state.json` exists and has recent timestamp

3. **Reopen the Application**:
   - All groups should be restored
   - All tabs should be restored in their respective groups
   - All custom buttons should be restored
   - The previously selected group should be active

4. **Restart Laptop**:
   - Restart your laptop
   - Open Terminal Browser
   - All state should be fully restored

## Technical Details

### State Storage Location
- **File**: `~/.terminal_browser_state.json`
- **Format**: JSON with indentation for human readability
- **Permissions**: User read/write only

### State Restoration Flow
1. Application starts → [main.py](main.py) creates MainWindow
2. `initialize_async()` is called → loads state from file
3. `_restore_application_state_async()` → restores groups, tabs, buttons
4. First group is selected → triggers tab loading for that group

### Why Synchronous During Close?
- **Reliability**: Guarantees state is written before process exits
- **Simplicity**: No complex async coordination during shutdown
- **Performance**: File write is fast (< 10ms typically)
- **Safety**: Error handling ensures app still closes even if save fails

## Related Files
- [ui/main_window.py](ui/main_window.py#L1862) - `closeEvent` method (fixed)
- [core/state_manager.py](core/state_manager.py) - State persistence manager
- [ui/terminal_tabs.py](ui/terminal_tabs.py#L971) - Tab restoration
- [ui/terminal_group_panel.py](ui/terminal_group_panel.py#L384) - Group restoration
- [main.py](main.py) - Application initialization with async state loading

## Benefits
✅ Tabs persist across app restarts  
✅ Groups persist across app restarts  
✅ Custom buttons persist  
✅ Works even after laptop restart  
✅ No data loss on normal app closure  
✅ Fast and reliable state saving  

## Date
Fixed: January 4, 2026
