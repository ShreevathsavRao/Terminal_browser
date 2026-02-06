# Packaging Guide for Terminal Browser

This guide explains how to create distributable packages for Terminal Browser.

## Quick Start

### Option 1: Build and Package Separately

```bash
# Step 1: Build the executable
python build.py

# Step 2: Create the app bundle
python package.py

# Step 3: Create DMG installer (optional)
python package.py --dmg
```

### Option 2: Build and Package Together

```bash
# Build executable and create package
python build.py --package

# Build executable, create package, and DMG
python build.py --package --dmg
```

## What Gets Created

### 1. Executable
- **Location**: `dist/Terminal Browser`
- **Type**: Standalone executable (40-50 MB)
- **Can run**: Directly by double-clicking or from terminal

### 2. App Bundle (macOS)
- **Location**: `dist/Terminal Browser.app`
- **Type**: macOS application bundle
- **Contains**:
  - Executable in `Contents/MacOS/`
  - Assets in `Contents/Resources/assets/`
  - Info.plist with app metadata
- **Can run**: Double-click to launch, or drag to Applications folder

### 3. DMG Installer (macOS)
- **Location**: `dist/TerminalBrowser-1.0.0.dmg`
- **Type**: Disk image for distribution
- **Contains**:
  - Terminal Browser.app
  - Applications folder symlink (for easy installation)
- **Can distribute**: Share the DMG file with users

## Distribution Methods

### Method 1: Share App Bundle Directly
1. Zip the `Terminal Browser.app` folder
2. Share the zip file
3. Users extract and drag to Applications folder

### Method 2: Share DMG Installer (Recommended)
1. Share the `TerminalBrowser-1.0.0.dmg` file
2. Users double-click DMG to mount
3. Users drag app to Applications folder
4. More professional and user-friendly

### Method 3: Direct Executable
1. Share the `Terminal Browser` executable
2. Users run it directly from terminal
3. Less user-friendly (no app bundle features)

## Package Contents

### App Bundle Structure
```
Terminal Browser.app/
├── Contents/
│   ├── Info.plist          # App metadata
│   ├── MacOS/
│   │   └── Terminal Browser # Main executable
│   └── Resources/
│       └── assets/          # Logo files (SVG)
│           ├── logo_tb_minimal.svg
│           ├── logo_tb_tab.svg
│           └── logo_tb_terminal.svg
```

### DMG Structure
```
Terminal Browser (DMG volume)
├── Terminal Browser.app
└── Applications -> (symlink to /Applications)
```

## App Bundle Metadata

The app bundle includes the following metadata in `Info.plist`:

- **Bundle Name**: Terminal Browser
- **Bundle Identifier**: com.terminalbrowser.app
- **Version**: 1.0.0
- **Category**: Developer Tools
- **Minimum macOS**: 10.13 (High Sierra)
- **High Resolution**: Supported

## Customization

### Changing Version Number

Edit `package.py` and update:
```python
'CFBundleVersion': '1.0.0',
'CFBundleShortVersionString': '1.0.0',
```

And update DMG name:
```python
dmg_name = "TerminalBrowser-1.0.0.dmg"
```

### Adding App Icon

1. Create an `.icns` file from your icon
2. Place it in `assets/` folder as `icon.icns`
3. Update `package.py`:
   ```python
   'CFBundleIconFile': 'icon.icns',
   ```
4. Copy icon to Resources:
   ```python
   shutil.copy2(assets_source / 'icon.icns', resources_path / 'icon.icns')
   ```

### Changing DMG Name

Edit `package.py`:
```python
dmg_name = "TerminalBrowser-1.0.0.dmg"  # Change version
```

## Code Signing (Optional)

For distribution outside the App Store, you may want to code sign:

```bash
# Sign the app bundle
codesign --sign "Developer ID Application: Your Name" \
         --options runtime \
         --deep \
         "dist/Terminal Browser.app"

# Sign the DMG
codesign --sign "Developer ID Application: Your Name" \
         "dist/TerminalBrowser-1.0.0.dmg"
```

## Notarization (Optional)

For macOS Gatekeeper compatibility:

```bash
# Notarize the app
xcrun notarytool submit \
    --apple-id "your@email.com" \
    --team-id "YOUR_TEAM_ID" \
    --password "app-specific-password" \
    "dist/Terminal Browser.app"

# Staple notarization
xcrun stapler staple "dist/Terminal Browser.app"
```

## Troubleshooting

### DMG Creation Fails

- Ensure you're on macOS (hdiutil is macOS-only)
- Check that the app bundle exists before creating DMG
- Verify disk space is available

### App Won't Launch

- Check executable permissions: `chmod +x "Terminal Browser.app/Contents/MacOS/Terminal Browser"`
- Verify all assets are included
- Check Console.app for error messages
- Try running from terminal to see error output

### File Size Concerns

The executable is ~40-50 MB because it includes:
- Python interpreter
- PyQt5 libraries (~30 MB)
- All dependencies
- Assets

This is normal for a standalone Python application.

## Distribution Checklist

- [ ] Build executable (`python build.py`)
- [ ] Create app bundle (`python package.py`)
- [ ] Create DMG installer (`python package.py --dmg`)
- [ ] Test app bundle on clean macOS system
- [ ] Verify assets are included
- [ ] Check app metadata (version, name, etc.)
- [ ] (Optional) Code sign the app
- [ ] (Optional) Notarize the app
- [ ] Test DMG on clean system
- [ ] Share DMG or app bundle

## File Sizes

Typical sizes:
- **Executable**: ~40-50 MB
- **App Bundle**: ~40-50 MB (same as executable)
- **DMG**: ~30-40 MB (compressed)

## Platform Support

- **macOS**: ✅ Full support (app bundle + DMG)
- **Linux**: ⚠️ Executable only (no app bundle)
- **Windows**: ⚠️ Executable only (no app bundle)

For Linux/Windows, users can run the executable directly or create platform-specific installers separately.




