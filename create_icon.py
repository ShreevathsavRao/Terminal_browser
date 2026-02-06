#!/usr/bin/env python3
"""
Create macOS icon (.icns) from SVG logo
"""

import os
import sys
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

def create_icon():
    """Create .icns file from SVG"""
    print("Creating macOS icon...")
    
    # Initialize QApplication (required for QPixmap)
    app = QApplication(sys.argv)
    
    # Paths
    svg_path = Path('assets/logo_tb_terminal.svg')
    iconset_dir = Path('assets/icon.iconset')
    icns_path = Path('assets/icon.icns')
    
    if not svg_path.exists():
        print(f"✗ SVG file not found: {svg_path}")
        return 1
    
    # Create iconset directory
    if iconset_dir.exists():
        import shutil
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir(parents=True)
    
    # Required icon sizes for macOS
    sizes = [
        (16, 'icon_16x16.png'),
        (32, 'icon_16x16@2x.png'),
        (32, 'icon_32x32.png'),
        (64, 'icon_32x32@2x.png'),
        (128, 'icon_128x128.png'),
        (256, 'icon_128x128@2x.png'),
        (256, 'icon_256x256.png'),
        (512, 'icon_256x256@2x.png'),
        (512, 'icon_512x512.png'),
        (1024, 'icon_512x512@2x.png'),
    ]
    
    print("Converting SVG to PNG at multiple sizes...")
    renderer = QSvgRenderer(str(svg_path))
    
    if not renderer.isValid():
        print("✗ Failed to load SVG file")
        return 1
    
    for size, filename in sizes:
        pixmap = QPixmap(size, size)
        pixmap.fill()  # Transparent background
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        output_path = iconset_dir / filename
        if not pixmap.save(str(output_path), 'PNG'):
            print(f"✗ Failed to save {filename}")
            return 1
    
    print("✓ PNG files created")
    
    # Convert iconset to .icns using iconutil
    print("Converting to .icns format...")
    try:
        cmd = [
            'iconutil',
            '-c', 'icns',
            str(iconset_dir),
            '-o', str(icns_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Clean up iconset directory
        import shutil
        shutil.rmtree(iconset_dir)
        
        print(f"✓ Icon created: {icns_path}")
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create .icns: {e}")
        print("Note: iconutil is a macOS-only tool")
        return 1
    except FileNotFoundError:
        print("✗ iconutil not found. This is a macOS-only tool.")
        return 1

if __name__ == '__main__':
    sys.exit(create_icon())

