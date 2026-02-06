# Multi-Platform Architecture for Terminal Browser

## Overview
This document describes the architecture for supporting Windows, macOS, and Linux platforms in Terminal Browser application, following design patterns from OBS Studio.

## Current State (Before Changes)
- **Platform**: macOS/Linux only
- **Implementation**: Single `pyte_terminal_widget.py` using Unix PTY system calls
- **Limitations**: Cannot run on Windows due to `pty`, `termios`, and `os.fork()` dependencies

## Target State (After Changes)
- **Platforms**: Windows, macOS, and Linux
- **Implementation**: Platform-specific terminal widgets with shared interface
- **Benefits**: Native support for each platform while maintaining all existing features

---

## Architecture Design

### 1. Directory Structure

```
ui/
├── terminal_widgets/
│   ├── __init__.py                      # Module initialization with platform detection
│   ├── base_terminal_widget.py          # Abstract base class (interface definition)
│   ├── unix_terminal_widget.py          # macOS/Linux implementation (PTY-based)
│   └── windows_terminal_widget.py       # Windows implementation (subprocess-based)
├── terminal_tabs.py                     # Modified to use platform-detected widget
└── [other existing files...]
```

### 2. Component Responsibilities

#### 2.1 Base Terminal Widget (`base_terminal_widget.py`)
**Purpose**: Define the common interface that all platform-specific implementations must follow.

**Key Features**:
- Abstract base class using Python's `ABC` module
- Defines all public methods that terminal_tabs and other components depend on
- Ensures API compatibility across platforms

**Critical Methods** (must be implemented by all subclasses):
```python
- start_shell()                    # Initialize terminal process
- write_to_terminal(data)          # Send input to terminal
- close_terminal()                 # Clean shutdown
- get_current_directory()          # Get working directory
- set_current_directory(path)      # Change working directory
- get_all_text()                   # Get terminal content
- clear_terminal()                 # Clear screen
- resize_terminal(cols, rows)      # Handle resize
```

**Signals** (PyQt signals for communication):
```python
- output_received                  # Terminal output available
- command_executed                 # Command finished
- directory_changed               # Working directory changed
- terminal_closed                 # Terminal process ended
```

#### 2.2 Unix Terminal Widget (`unix_terminal_widget.py`)
**Purpose**: Maintain ALL existing functionality for macOS and Linux using PTY.

**Implementation**: 
- Rename current `pyte_terminal_widget.py` → `unix_terminal_widget.py`
- Change class name: `PyteTerminalWidget` → `UnixTerminalWidget`
- Inherits from `BaseTerminalWidget`
- Uses existing PTY-based implementation:
  - `pty.openpty()` for pseudo-terminal
  - `os.fork()` for process creation
  - `termios` for terminal control
  - `pyte` for terminal emulation

**Features Preserved**:
- ✅ Full PTY support with proper signal handling
- ✅ Interactive command execution
- ✅ Tab completion support
- ✅ Ctrl+C/Ctrl+Z signal handling
- ✅ Terminal resizing
- ✅ History management
- ✅ Command recording
- ✅ Search functionality
- ✅ Syntax highlighting
- ✅ Minimap support
- ✅ File/URL click detection
- ✅ Copy/paste with selection
- ✅ All existing color and formatting

#### 2.3 Windows Terminal Widget (`windows_terminal_widget.py`)
**Purpose**: Provide Windows-native terminal support using subprocess.

**Implementation**:
- Inherits from `BaseTerminalWidget`
- Uses `subprocess.Popen` instead of PTY
- Default shell: PowerShell (configurable to cmd.exe)
- Communicates via PIPE instead of PTY
- Still uses `pyte` for screen rendering

**Windows-Specific Approach**:
```python
# Process creation
self.process = subprocess.Popen(
    ['powershell.exe', '-NoLogo'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    cwd=self.current_directory,
    bufsize=0
)
```

**Features to Implement**:
- ✅ Basic command execution
- ✅ Output capture and display
- ✅ Working directory tracking
- ✅ Terminal resizing (via environment variables)
- ✅ Copy/paste support
- ✅ History management
- ✅ Command recording
- ⚠️ Limited signal handling (no Ctrl+C forwarding - subprocess limitation)
- ⚠️ No true PTY (some interactive programs may not work fully)

**Known Limitations on Windows**:
- Interactive programs requiring PTY (vim, nano) may not work correctly
- Signal handling is limited compared to Unix PTY
- Can be improved later with `winpty` or `conpty` libraries

#### 2.4 Platform Detection (`terminal_widgets/__init__.py`)
**Purpose**: Auto-detect platform and export the correct widget class.

**Implementation**:
```python
from core.platform_manager import get_platform_manager

platform_mgr = get_platform_manager()

if platform_mgr.is_windows:
    from ui.terminal_widgets.windows_terminal_widget import WindowsTerminalWidget as TerminalWidget
else:
    # macOS and Linux use PTY-based implementation
    from ui.terminal_widgets.unix_terminal_widget import UnixTerminalWidget as TerminalWidget

__all__ = ['TerminalWidget']
```

#### 2.5 Terminal Tabs Update (`terminal_tabs.py`)
**Purpose**: Use platform-detected terminal widget transparently.

**Change Required**:
```python
# OLD:
from ui.pyte_terminal_widget import PyteTerminalWidget as TerminalWidget

# NEW:
from ui.terminal_widgets import TerminalWidget
```

---

## Implementation Strategy

### Phase 1: Setup (No Breaking Changes)
1. ✅ Create new git branch: `feature/multi-platform-support`
2. ✅ Create architecture documentation (this file)
3. Create `ui/terminal_widgets/` directory
4. Create `base_terminal_widget.py` with abstract base class

### Phase 2: Refactoring Existing Code
5. Copy `pyte_terminal_widget.py` → `unix_terminal_widget.py`
6. Update class name and inheritance
7. Keep all existing functionality intact
8. Update imports to use base class

### Phase 3: Windows Implementation
9. Create `windows_terminal_widget.py` with subprocess-based implementation
10. Implement all required base class methods
11. Test basic functionality on Windows

### Phase 4: Integration
12. Create `terminal_widgets/__init__.py` with platform detection
13. Update `terminal_tabs.py` to use new import
14. Test on all platforms (Windows, macOS, Linux if possible)

### Phase 5: Testing & Validation
15. Verify all features work on Unix platforms (no regressions)
16. Verify basic functionality works on Windows
17. Document any platform-specific limitations
18. Update README with platform compatibility notes

---

## Testing Checklist

### macOS/Linux Testing (Regression Prevention)
- [ ] Terminal opens and shows prompt
- [ ] Commands execute correctly
- [ ] Ctrl+C interrupts running commands
- [ ] Tab completion works
- [ ] Multi-line commands work
- [ ] History navigation (up/down arrows)
- [ ] Terminal resizing works
- [ ] Copy/paste with mouse selection
- [ ] File paths are clickable
- [ ] URLs are clickable
- [ ] Search functionality works
- [ ] Minimap displays correctly
- [ ] Command recording works
- [ ] Session playback works
- [ ] Terminal tabs can be created/closed
- [ ] Working directory tracking works

### Windows Testing (New Features)
- [ ] Terminal opens and shows PowerShell prompt
- [ ] Basic commands execute (dir, echo, cd, etc.)
- [ ] Output is displayed correctly
- [ ] Working directory changes persist
- [ ] Copy/paste works
- [ ] Terminal resizing works
- [ ] History navigation works
- [ ] Multiple tabs can be opened
- [ ] Terminal can be closed gracefully

---

## API Compatibility Matrix

| Method/Property | Unix (PTY) | Windows (Subprocess) | Notes |
|----------------|------------|----------------------|-------|
| `start_shell()` | ✅ Full PTY | ✅ Subprocess | Different underlying tech |
| `write_to_terminal()` | ✅ PTY write | ✅ PIPE write | Same interface |
| `output_received` signal | ✅ PTY read | ✅ PIPE read | Same interface |
| Ctrl+C handling | ✅ Signal forwarding | ⚠️ Limited | Windows limitation |
| Interactive programs | ✅ Full support | ⚠️ Limited | vim/nano may not work on Windows |
| Tab completion | ✅ Shell native | ✅ Shell native | Works on both |
| Terminal resize | ✅ ioctl TIOCSWINSZ | ⚠️ Environment var | Different mechanism |
| Working directory | ✅ Real-time tracking | ✅ Command parsing | Same result |

---

## Future Enhancements

### Windows Improvements (Optional)
1. **winpty Integration**: Use `winpty` library for better Windows PTY emulation
2. **ConPTY Support**: Use Windows 10+ ConPTY API for native PTY support
3. **Improved Signal Handling**: Better Ctrl+C forwarding
4. **Interactive Program Support**: Enable vim, nano, etc. on Windows

### Cross-Platform Improvements
1. **Terminal Profiles**: Per-platform default shells and settings
2. **Custom Shell Support**: Let users configure shell per platform
3. **Theme Adjustments**: Platform-specific color schemes
4. **Keyboard Shortcuts**: Platform-specific key bindings

---

## Risk Mitigation

### Preserving Existing Functionality
- ✅ Use abstract base class to enforce API contract
- ✅ No changes to existing Unix/PTY code logic
- ✅ Separate branch for development and testing
- ✅ Comprehensive testing checklist
- ✅ Git allows easy rollback if issues found

### Handling Platform Differences
- ✅ Clear documentation of limitations
- ✅ Graceful degradation on Windows (e.g., interactive programs)
- ✅ User-facing messages for unsupported features
- ✅ Future-proof design allows for enhancements

---

## File Change Summary

### New Files
- `ui/terminal_widgets/__init__.py`
- `ui/terminal_widgets/base_terminal_widget.py`
- `ui/terminal_widgets/unix_terminal_widget.py` (copy of pyte_terminal_widget.py)
- `ui/terminal_widgets/windows_terminal_widget.py`
- `MULTI_PLATFORM_ARCHITECTURE.md` (this file)

### Modified Files
- `ui/terminal_tabs.py` (import statement only)

### Deprecated Files (keep for reference, can remove later)
- `ui/pyte_terminal_widget.py` (replaced by unix_terminal_widget.py)
- `ui/pty_terminal_widget.py` (unused, can remove)

---

## Success Criteria

1. ✅ Application runs on Windows without import errors
2. ✅ Application runs on macOS/Linux with NO feature regression
3. ✅ Basic terminal functionality works on Windows (commands, output, tabs)
4. ✅ Code is maintainable with clear separation of concerns
5. ✅ Architecture supports future platform enhancements
6. ✅ All existing tests pass on Unix platforms
7. ✅ Documentation is complete and accurate

---

## References

### Inspiration
- **OBS Studio**: https://github.com/obsproject/obs-studio
  - Platform-specific implementations in separate files
  - CMake-based conditional compilation
  - Clean separation of platform code

### Similar Projects
- **xterm.js**: Cross-platform terminal in JavaScript
- **Windows Terminal**: Modern Windows terminal with ConPTY
- **kitty**: Cross-platform GPU-accelerated terminal

### Technical Documentation
- Python subprocess: https://docs.python.org/3/library/subprocess.html
- PTY module: https://docs.python.org/3/library/pty.html
- pyte terminal emulator: https://github.com/selectel/pyte
- Windows ConPTY: https://docs.microsoft.com/en-us/windows/console/creating-a-pseudoconsole-session

---

**Document Version**: 1.0  
**Created**: 2026-02-06  
**Branch**: feature/multi-platform-support  
**Status**: Implementation in progress
