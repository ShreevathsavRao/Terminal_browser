# Quick Package Guide

## Create Distributable Package

### Step 1: Build Executable
```bash
python build.py
```

### Step 2: Create Package
```bash
# Create app bundle
python package.py

# Create app bundle + DMG installer
python package.py --dmg
```

### Or: Build and Package Together
```bash
# Build + Package
python build.py --package

# Build + Package + DMG
python build.py --package --dmg
```

## Output Files

All files are in the `dist/` folder:

1. **`Terminal Browser`** - Standalone executable
2. **`Terminal Browser.app`** - macOS app bundle (ready to distribute)
3. **`TerminalBrowser-1.0.0.dmg`** - DMG installer (if created)

## Distribution

### Option 1: Share App Bundle
- Share `Terminal Browser.app` (zip it first)
- Users drag to Applications folder

### Option 2: Share DMG (Recommended)
- Share `TerminalBrowser-1.0.0.dmg`
- Users double-click to mount and install

## File Sizes
- Executable: ~26 MB
- App Bundle: ~26 MB
- DMG: ~26 MB (compressed)

For detailed information, see `PACKAGING.md`.




