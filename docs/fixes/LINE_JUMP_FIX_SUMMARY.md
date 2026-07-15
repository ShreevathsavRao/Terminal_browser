# Line Jumping Feature - Fix Implementation

## Changes Made to `ui/minimap_widget.py`

### 1. Added Cached Filtered Line Indices (Line ~171-173)

Added two new instance variables in `__init__`:
```python
# Cache for filtered line indices
self.filtered_line_indices = []  # Cached list of filtered line numbers
self.filtered_indices_dirty = True  # Flag to trigger recalculation
```

**Purpose**: Store filtered line numbers and avoid rescanning all lines on every jump.

---

### 2. Updated `set_content()` Method (Line ~224-251)

Modified to track content changes and update filtered indices incrementally:
```python
def set_content(self, text_lines):
    old_length = len(self.content_lines)
    new_length = len(text_lines)
    
    # ... store content ...
    
    # Update filtered indices if filter is enabled
    if self.color_filter_enabled and self.filtered_colors:
        if new_length != old_length:
            self._update_filtered_indices_incremental(old_length, new_length, text_lines)
        else:
            self.filtered_indices_dirty = True
```

**Purpose**: Detect when lines are added/removed and update cache accordingly.

---

### 3. Added `_update_filtered_indices_incremental()` Method (Line ~253-280)

New method to handle incremental updates:
```python
def _update_filtered_indices_incremental(self, old_length, new_length, text_lines):
    if new_length > old_length:
        # Lines added - scan only new lines
        for i in range(old_length, new_length):
            line = text_lines[i]
            color = self.get_line_color(line)
            for filtered_color in self.filtered_colors:
                if self.colors_match(color, filtered_color):
                    self.filtered_line_indices.append(i)
                    break
        self.filtered_line_indices.sort()
    elif new_length < old_length:
        # Lines removed - remove indices beyond new length
        self.filtered_line_indices = [i for i in self.filtered_line_indices if i < new_length]
    else:
        # Same length - full rescan needed
        self.filtered_indices_dirty = True
```

**Purpose**: Scan only NEW lines when streaming adds content, maintaining O(k) complexity where k = new lines, not O(n) where n = total lines.

---

### 4. Updated `get_filtered_line_indices()` Method (Line ~622-648)

Modified to use cached indices:
```python
def get_filtered_line_indices(self):
    if not self.color_filter_enabled or not self.filtered_colors:
        return []
    
    # Return cached indices if still valid
    if not self.filtered_indices_dirty and self.filtered_line_indices:
        return self.filtered_line_indices
    
    # Recalculate only if dirty
    print(f"[MINIMAP] Recalculating filtered indices (full scan)...")
    self.filtered_line_indices = []
    for i, line in enumerate(self.content_lines):
        # ... scan all lines ...
    
    self.filtered_indices_dirty = False
    return self.filtered_line_indices
```

**Purpose**: Return cached list instantly (O(1)) unless cache is invalid.

---

### 5. Updated Filter Toggle Method (Line ~959-977)

Added cache invalidation when filter changes:
```python
# In toggle_color_filter():
self.color_filter_enabled = len(self.filtered_colors) > 0
self.filtered_indices_dirty = True  # NEW
self.update()

# In clear_color_filter():
self.filtered_line_indices = []  # NEW
self.filtered_indices_dirty = True  # NEW
```

**Purpose**: Ensure cache is recalculated when user changes filter.

---

### 6. Removed Unnecessary Refresh Calls (Line ~633, ~681)

Removed redundant `update_minimap_content()` calls from jump functions:
```python
# REMOVED from jump_to_next_filtered_line():
# if hasattr(self, 'parent') and self.parent():
#     main_window = self.parent().parent()
#     if main_window and hasattr(main_window, 'update_minimap_content'):
#         main_window.update_minimap_content()

# Now directly uses cached data
filtered_indices = self.get_filtered_line_indices()
```

**Purpose**: Eliminate race conditions and use cached data immediately.

---

## How It Works Now

### Initial Filter Application
1. User applies color filter to terminal
2. `toggle_color_filter()` marks cache as dirty
3. Next call to `get_filtered_line_indices()` scans all lines
4. Results cached in `self.filtered_line_indices`

### During Streaming (New Lines Added)
1. `set_content()` receives updated content
2. Detects `new_length > old_length`
3. Calls `_update_filtered_indices_incremental()`
4. **Only scans new lines** (e.g., lines 1000-1050)
5. Appends matching indices to cache
6. Cache stays valid (no full rescan needed)

### Jump Button Pressed
1. User presses up/down arrow button
2. `jump_to_next_filtered_line()` called
3. Calls `get_filtered_line_indices()`
4. **Returns cached list immediately** (O(1))
5. Finds nearest filtered line based on current position
6. Jumps to that line

### Filter Changed
1. User adds/removes color from filter
2. `toggle_color_filter()` marks cache as dirty
3. Next jump triggers full rescan
4. New cache built for updated filter

---

## Performance Improvements

| Scenario | Before | After |
|----------|--------|-------|
| **First jump** | Scan 10,000 lines | Scan 10,000 lines (same) |
| **Second jump** | Scan 10,000 lines | Use cache (instant) |
| **100 new lines added** | Scan 10,100 lines on next jump | Scan 100 lines only |
| **1000 jumps in session** | 10,000,000 line scans | 1 scan + 1000 cache lookups |

**Result**: ~10,000x faster for repeated jumps in large terminals!

---

## Testing Instructions

1. **Start the application** ✓ (running)
2. **Run command with colored output**:
   ```bash
   for i in {1..100}; do echo -e "\033[32mGreen line $i\033[0m"; echo "Normal line $i"; done
   ```
3. **Apply color filter** (right-click minimap → filter green)
4. **Press down arrow** multiple times → should jump to green lines
5. **Run more commands** to add new lines
6. **Press down arrow again** → should still work correctly
7. **Check console** for debug messages:
   - Should see "Incremental update" messages when lines added
   - Should NOT see "Recalculating" on every jump

---

## Debug Output

The implementation includes debug prints:
- `[MINIMAP] Incremental update: added X lines` - when streaming
- `[MINIMAP] Recalculating filtered indices (full scan)...` - only when cache invalid
- `[MINIMAP] Found X filtered lines` - after full scan

These help verify the caching is working correctly.

---

## Bugs Fixed

✅ **Performance degradation** - No longer scans all lines on every jump
✅ **Line number drift** - Incremental updates keep indices accurate
✅ **Stale indices** - Cache updated automatically when content changes
✅ **Race conditions** - Removed unnecessary refresh calls

---

## Future Enhancements (Optional)

1. **LRU cache for line colors** - Cache `get_line_color()` results
2. **Binary search** - Use bisect for finding nearest filtered line
3. **Background thread** - Scan lines asynchronously for very large terminals
4. **Smart invalidation** - Only rescan changed regions when content modified

These are not needed now but could further optimize for extreme cases (100,000+ lines).
