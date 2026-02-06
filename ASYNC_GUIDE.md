# Async Implementation Guide

## Overview

The Terminal Browser application has been fully converted to use asynchronous I/O operations. This document provides a guide for developers working with the new async architecture.

## Quick Start

### Installing Dependencies

```bash
pip install -r requirements.txt
```

The new dependencies are:
- `qasync>=0.24.0` - Qt + asyncio event loop integration
- `aiofiles>=23.0.0` - Async file I/O

### Running the Application

The application starts the same way as before:

```bash
python main.py
```

The async event loop is automatically set up and managed by `qasync`.

### Testing Async Operations

Run the async test suite:

```bash
python test_async.py
```

This demonstrates:
- Concurrent save operations (3x faster)
- Concurrent load operations
- Independent operation execution

## Core Concepts

### 1. Event Loop Integration

The application uses `qasync` to integrate Qt's event loop with Python's asyncio:

```python
import qasync
import asyncio

app = QApplication(sys.argv)
loop = qasync.QEventLoop(app)
asyncio.set_event_loop(loop)

# Now you can use both Qt signals/slots and async/await
```

### 2. Async File Operations

All file I/O uses `aiofiles` for non-blocking operations:

```python
import aiofiles

# Async read
async with aiofiles.open(filename, 'r') as f:
    content = await f.read()
    data = json.loads(content)

# Async write
async with aiofiles.open(filename, 'w') as f:
    await f.write(json.dumps(data))
```

### 3. Concurrent Operations

Use `asyncio.gather()` to run independent operations concurrently:

```python
# Load multiple files at once
state, prefs, history = await asyncio.gather(
    state_manager.load_state(),
    prefs_manager.load_preferences(),
    history_manager.load_history()
)
```

### 4. Fire-and-Forget Saves

Use `asyncio.create_task()` for background saves:

```python
# Save without waiting for completion
asyncio.create_task(state_manager.save_state(data))
```

## Updated API Reference

### StateManager

```python
# Async methods
await state_manager.save_state(state_data)    # Save state
await state_manager.load_state()              # Load state
await state_manager.clear_state()             # Clear state
```

### PreferencesManager

```python
# Async methods
await prefs_manager.load_preferences()        # Load prefs
await prefs_manager.save_preferences()        # Save prefs
await prefs_manager.reset_to_defaults_async() # Reset prefs

# Sync wrappers (for UI callbacks)
prefs_manager.load_preferences_sync()         # Sync load
prefs_manager.save_preferences_sync()         # Sync save
prefs_manager.reset_to_defaults()             # Sync reset
```

### CommandHistoryManager

```python
# Async methods
await history_manager.load_history()          # Load history
await history_manager.save_history()          # Save history
await history_manager.clear_history_async()   # Clear history
await history_manager.flush_save_async()      # Force save

# Sync wrappers (for compatibility)
history_manager.load_history_sync()           # Sync load
history_manager.save_history_sync()           # Sync save
history_manager.flush_save()                  # Sync flush
```

## Best Practices

### 1. When to Use Async

✅ **Use async for:**
- File I/O operations (save/load)
- Network requests
- Database operations
- Long-running operations
- Independent operations that can run concurrently

❌ **Don't use async for:**
- Simple calculations
- UI updates (use Qt signals instead)
- Operations that must be synchronous

### 2. Concurrent Operations

Group independent operations with `asyncio.gather()`:

```python
# Good - runs concurrently
await asyncio.gather(
    save_state(),
    save_preferences(),
    save_history()
)

# Bad - runs sequentially
await save_state()
await save_preferences()
await save_history()
```

### 3. Error Handling

Always handle exceptions in async operations:

```python
async def save_data(self):
    try:
        async with aiofiles.open(self.file, 'w') as f:
            await f.write(json.dumps(self.data))
        return True
    except Exception as e:
        print(f"Error saving: {e}")
        return False
```

### 4. Thread Safety

Use asyncio locks for shared resources:

```python
class Manager:
    def __init__(self):
        self._lock = asyncio.Lock()
    
    async def save(self):
        async with self._lock:
            # Critical section - only one save at a time
            await self._write_to_file()
```

### 5. Sync Wrappers

Provide sync wrappers for UI callbacks:

```python
# Async implementation
async def load_data(self):
    async with self._lock:
        # Load asynchronously
        ...

# Sync wrapper for UI
def load_data_sync(self):
    # Fallback for synchronous contexts
    with open(self.file) as f:
        ...
```

## Migration Guide

### Converting Sync to Async

**Before:**
```python
def load_state(self):
    with open(self.file, 'r') as f:
        return json.load(f)
```

**After:**
```python
async def load_state(self):
    async with aiofiles.open(self.file, 'r') as f:
        content = await f.read()
        return json.loads(content)
```

### Using in Qt Callbacks

**Option 1: Use sync wrapper**
```python
def on_button_clicked(self):
    # Use sync version in Qt callback
    self.manager.save_data_sync()
```

**Option 2: Create async task**
```python
def on_button_clicked(self):
    # Fire and forget
    asyncio.create_task(self.manager.save_data())
```

**Option 3: Run with loop**
```python
def on_button_clicked(self):
    # Wait for completion
    loop = asyncio.get_event_loop()
    loop.run_until_complete(self.manager.save_data())
```

## Common Patterns

### Pattern 1: Startup Initialization

```python
async def initialize(self):
    """Initialize all components concurrently"""
    await asyncio.gather(
        self.load_config(),
        self.load_data(),
        self.load_cache(),
        self.connect_services()
    )
```

### Pattern 2: Shutdown Cleanup

```python
async def shutdown(self):
    """Save all state concurrently before exit"""
    await asyncio.gather(
        self.save_state(),
        self.save_preferences(),
        self.flush_cache()
    )
```

### Pattern 3: Background Auto-Save

```python
async def auto_save_loop(self):
    """Periodically save data in background"""
    while self.running:
        await asyncio.sleep(60)  # Every minute
        asyncio.create_task(self.save_data())
```

### Pattern 4: Progress Tracking

```python
async def load_with_progress(self):
    """Load multiple items with progress updates"""
    items = [item1, item2, item3]
    for i, item in enumerate(items):
        await self.load_item(item)
        self.progress_signal.emit(i + 1, len(items))
```

## Performance Tips

### 1. Batch Operations

```python
# Good - batch related operations
async def save_all(self):
    await asyncio.gather(*[
        self.save_item(item) for item in self.items
    ])

# Bad - save one at a time
for item in self.items:
    await self.save_item(item)
```

### 2. Use Timeouts

```python
try:
    await asyncio.wait_for(
        long_operation(),
        timeout=5.0
    )
except asyncio.TimeoutError:
    print("Operation timed out")
```

### 3. Limit Concurrency

```python
# Limit to 5 concurrent operations
semaphore = asyncio.Semaphore(5)

async def limited_operation(item):
    async with semaphore:
        await process_item(item)

await asyncio.gather(*[
    limited_operation(item) for item in items
])
```

## Debugging

### Enable Asyncio Debug Mode

```python
import asyncio
asyncio.get_event_loop().set_debug(True)
```

### Check for Unawaited Coroutines

Look for warnings like:
```
RuntimeWarning: coroutine 'save_data' was never awaited
```

Fix by adding `await`:
```python
# Wrong
self.save_data()  # Forgot await!

# Right
await self.save_data()
```

### Monitor Event Loop

```python
loop = asyncio.get_event_loop()
print(f"Running: {loop.is_running()}")
print(f"Closed: {loop.is_closed()}")
```

## Troubleshooting

### Issue: "RuntimeError: This event loop is already running"

**Solution:** Use `asyncio.create_task()` instead of `loop.run_until_complete()` in async contexts.

### Issue: "QObject::startTimer: Timers can only be used with threads started with QThread"

**Solution:** This is a warning when using QTimer outside Qt threads. It's safe to ignore in test scripts.

### Issue: Operations not running concurrently

**Solution:** Check that you're using `asyncio.gather()` and not awaiting operations sequentially.

### Issue: File not saved

**Solution:** Ensure you await the save operation or use sync wrappers in appropriate contexts.

## Further Reading

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [qasync documentation](https://github.com/CabbageDevelopment/qasync)
- [aiofiles documentation](https://github.com/Tinche/aiofiles)

## Support

For issues or questions about the async implementation:
1. Check this guide first
2. Review `ASYNC_ARCHITECTURE.md` for architecture details
3. Run `test_async.py` to verify your environment
4. Check existing code examples in the core modules
