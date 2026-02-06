# Terminal Browser Logo Assets

This directory contains SVG logo files for Terminal Browser.

## Available Logos

### 1. `logo_tb_terminal.svg` ⭐ **RECOMMENDED**
- **Style**: Terminal window frame with "tb" monogram
- **Features**: Window frame, title bar, tab indicator, cursor
- **Best For**: Application icon, professional branding
- **Colors**: Dark background (#0d1117) with green text (#00ff00)

### 2. `logo_tb_minimal.svg`
- **Style**: Minimal "tb" with cursor
- **Features**: Clean design, just letters and cursor
- **Best For**: Favicon, small icons, minimal aesthetic
- **Colors**: Dark background (#1e1e1e) with green text (#00ff00)

### 3. `logo_tb_tab.svg`
- **Style**: Browser tab with "tb" and terminal window
- **Features**: Tab design emphasizing browser-like nature
- **Best For**: Emphasizing tabbed interface feature
- **Colors**: Dark background (#0d1117) with green accents

## Converting SVG to Application Icons

### macOS (.icns)

1. **Using IconUtil** (built into macOS):
```bash
# Create iconset directory
mkdir logo.iconset

# Convert to PNG at different sizes
sips -z 16 16 logo_tb_terminal.svg --out logo.iconset/icon_16x16.png
sips -z 32 32 logo_tb_terminal.svg --out logo.iconset/icon_16x16@2x.png
sips -z 32 32 logo_tb_terminal.svg --out logo.iconset/icon_32x32.png
sips -z 64 64 logo_tb_terminal.svg --out logo.iconset/icon_32x32@2x.png
sips -z 128 128 logo_tb_terminal.svg --out logo.iconset/icon_128x128.png
sips -z 256 256 logo_tb_terminal.svg --out logo.iconset/icon_128x128@2x.png
sips -z 256 256 logo_tb_terminal.svg --out logo.iconset/icon_256x256.png
sips -z 512 512 logo_tb_terminal.svg --out logo.iconset/icon_256x256@2x.png
sips -z 512 512 logo_tb_terminal.svg --out logo.iconset/icon_512x512.png
sips -z 1024 1024 logo_tb_terminal.svg --out logo.iconset/icon_512x512@2x.png

# Convert to .icns
iconutil -c icns logo.iconset
```

2. **Using Online Tools**:
   - [CloudConvert](https://cloudconvert.com/svg-to-icns)
   - [Convertio](https://convertio.co/svg-icns/)

### Windows (.ico)

1. **Using ImageMagick**:
```bash
convert logo_tb_terminal.svg -define icon:auto-resize=256,128,64,48,32,16 logo.ico
```

2. **Using Online Tools**:
   - [CloudConvert](https://cloudconvert.com/svg-to-ico)
   - [Convertio](https://convertio.co/svg-ico/)

### Linux (.png)

1. **Using Inkscape** (recommended):
```bash
# Install Inkscape if needed: sudo apt install inkscape
inkscape logo_tb_terminal.svg --export-width=512 --export-height=512 --export-filename=logo_512.png
inkscape logo_tb_terminal.svg --export-width=256 --export-height=256 --export-filename=logo_256.png
inkscape logo_tb_terminal.svg --export-width=128 --export-height=128 --export-filename=logo_128.png
inkscape logo_tb_terminal.svg --export-width=64 --export-height=64 --export-filename=logo_64.png
inkscape logo_tb_terminal.svg --export-width=32 --export-height=32 --export-filename=logo_32.png
inkscape logo_tb_terminal.svg --export-width=16 --export-height=16 --export-filename=logo_16.png
```

2. **Using ImageMagick**:
```bash
convert logo_tb_terminal.svg -resize 512x512 logo_512.png
convert logo_tb_terminal.svg -resize 256x256 logo_256.png
convert logo_tb_terminal.svg -resize 128x128 logo_128.png
convert logo_tb_terminal.svg -resize 64x64 logo_64.png
convert logo_tb_terminal.svg -resize 32x32 logo_32.png
convert logo_tb_terminal.svg -resize 16x16 logo_16.png
```

## Customization

### Changing Colors

Edit the SVG files directly:
- **Background**: Change `fill="#0d1117"` or `fill="#1e1e1e"`
- **Text/Cursor**: Change `fill="#00ff00"` (green)
- **Accents**: Modify stroke colors

### Color Suggestions:
- **Classic Green**: `#00ff00` (bright green)
- **Material Green**: `#4CAF50` (softer green)
- **Cyan**: `#00d4ff` (modern cyan)
- **White**: `#ffffff` (monochrome)

### Font Changes

The SVGs use monospace fonts (`'Courier New', 'Monaco', monospace`). You can:
- Change font-family in the `<text>` elements
- Adjust font-size for different proportions
- Modify letter-spacing for tighter/looser spacing

## Using in Application

### Python/PyQt5

```python
from PyQt5.QtGui import QIcon

# Set application icon
app.setWindowIcon(QIcon('assets/logo_tb_terminal.svg'))
window.setWindowIcon(QIcon('assets/logo_tb_terminal.svg'))
```

### For macOS App Bundle

In `setup.py` (py2app), add:
```python
APP = ['main.py']
DATA_FILES = [
    ('assets', ['assets/logo_tb_terminal.svg']),
]
ICON = 'assets/logo_tb_terminal.icns'  # Convert SVG to ICNS first
```

## Next Steps

1. ✅ Choose your preferred logo variant
2. ✅ Customize colors if needed
3. ✅ Convert to required formats (.icns, .ico, .png)
4. ✅ Integrate into application
5. ✅ Test at different sizes (especially small icons)

## Tools for Editing

- **Figma** (free, web-based): Best for design adjustments
- **Inkscape** (free, open-source): Full SVG editing
- **Adobe Illustrator** (paid): Professional vector editing
- **VS Code** with SVG preview extension: Quick edits

---

**Need help?** Check `../LOGO_DESIGN_CONCEPTS.md` for design concepts and inspiration!




