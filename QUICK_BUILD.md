# Quick Build Guide

## Build the Executable

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Build the Executable
```bash
python build.py
```

That's it! The executable will be in the `dist/` folder.

## What Was Created

- **`terminal_browser.spec`** - PyInstaller configuration file
- **`build.py`** - Automated build script
- **`BUILD.md`** - Detailed build documentation
- **Updated `requirements.txt`** - Now includes PyInstaller

## Running the Executable

After building:
- **macOS/Linux**: `./dist/Terminal\ Browser`
- **Windows**: `dist\Terminal Browser.exe`

## Troubleshooting

If the build fails:
1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check that you have Python 3.7+ installed
3. Try building directly: `pyinstaller terminal_browser.spec`

For more details, see `BUILD.md`.




