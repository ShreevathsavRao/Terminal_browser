# Sleep/Wake Detection Fix - Enhanced

## Problem
When the laptop lid is closed or the screen is locked, empty lines accumulate in the terminal buffer. This happens because:

1. The PTY reader thread continues receiving data during sleep/lock
2. Output gets buffered in `_output_buffer` 
3. GUI timers pause or slow down during system sleep
4. On wake, all accumulated data gets processed at once, causing pyte to interpret control sequences as empty lines
5. Multiple newlines in the accumulated buffer create visible empty line gaps

## Solution Implemented

Added sleep/wake detection with aggressive buffer management and newline cleanup:

### Changes Made

1. **Added state tracking variables** (line ~1800):
   ```python
   self._app_is_suspended = False
   self._buffer_on_suspend = []
   self._last_activity_time = time.time()
   ```

2. **Connected to application state changes** (line ~1828):
   ```python
   QApplication.instance().applicationStateChanged.connect(self._on_app_state_changed)
   ```

3. **Added state change handler** (`_on_app_state_changed`):
   - Detects when app goes inactive (sleep/lock/background)
   - Pauses output buffer timer to prevent processing
   - Moves current buffer to suspend buffer
   - On wake, intelligently processes accumulated data:
     - **If suspended >10 seconds, trims buffer to last 20 items** (reduced from 50)
     - **Cleans excessive newlines** using regex: `r'\n{3,}' → '\n\n'`
     - Prevents massive line dumps from accumulated output
     - Delays flush by 100ms to allow UI to stabilize

4. **Updated `handle_output` method**:
   - Tracks activity time
   - If app is suspended, buffers to `_buffer_on_suspend` instead
   - Skips scheduling timer during suspend

5. **Added newline cleanup in `_flush_output_buffer`** (NEW):
   - Detects patterns with 3+ consecutive newlines
   - Collapses them to just 2 newlines (preserves paragraph breaks)
   - Runs on every buffer flush, catching sleep/wake and normal cases

## How It Works

### During Normal Operation
- Output buffered every 16-100ms (adaptive based on volume)
- Timer flushes buffer regularly
- **Excessive newlines cleaned automatically**
- UI updates smoothly

### When Laptop Sleeps/Locks
1. App state changes to inactive
2. Output buffer timer stops
3. New output goes to `_buffer_on_suspend`
4. No processing occurs

### When Laptop Wakes/Unlocks
1. App state changes to active
2. Checks how long was suspended
3. **If >10 seconds:**
   - Limits buffer to **20 items** (more aggressive than before)
   - Cleans multiple newlines from each item
4. Waits 100ms for UI stability
5. Flushes cleaned buffer
6. Resumes normal operation

### Continuous Protection
- Every buffer flush checks for `\n\n\n+` patterns
- Automatically collapses to `\n\n` (max 2 newlines)
- Works during normal operation and after wake

## Benefits

- **No more empty lines** from accumulated sleep output
- **Aggressive buffer trimming** - only 20 items after long sleep
- **Newline cleanup** - removes excessive line breaks automatically
- **Smoother wake experience** - delayed flush prevents UI freeze
- **Data preservation** - still processes recent output, just limits volume
- **Automatic** - no user intervention needed
- **Works for all cases** - catches newlines from any source

## Testing

To test:
1. Start the application
2. Run a command that produces continuous output (e.g., `docker logs -f`)
3. Close laptop lid or lock screen for 10+ seconds
4. Wake/unlock
5. Observe: **No burst of empty lines**, recent logs appear normally, maximum 2 consecutive blank lines

## Debug Output

When sleep/wake occurs, you'll see console messages:
- `[SLEEP/WAKE] App going inactive - pausing output processing`
- `[SLEEP/WAKE] App becoming active after X.Xs - resuming output`
- `[SLEEP/WAKE] Trimming buffer from X to 20 items` (if needed)

## Technical Details

**Buffer Limits:**
- Normal operation: Unlimited buffer items
- After 10s+ sleep: **20 items max** (keeps ~1-2 seconds of recent output)

**Newline Handling:**
- Pattern: `\n{3,}` (3 or more consecutive newlines)
- Replacement: `\n\n` (exactly 2 newlines)
- Applied: Every buffer flush + wake cycle cleanup

**Timing:**
- Wake flush delay: 100ms (allows UI to stabilize)
- Normal flush interval: 16-100ms (adaptive)

