#!/usr/bin/env python3
"""
Package script for Terminal Browser
Creates a distributable macOS .app bundle and DMG installer
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from plistlib import dump

def create_app_bundle():
    """Create a proper macOS .app bundle"""
    print("=" * 60)
    print("Terminal Browser - Package Creator")
    print("=" * 60)
    
    # Check if icon exists, create it if not
    icon_path = Path('assets/icon.icns')
    if not icon_path.exists():
        print("Icon not found. Creating icon from SVG...")
        try:
            import create_icon
            create_icon.create_icon()
        except Exception as e:
            print(f"⚠ Could not create icon: {e}")
            print("App will be created without custom icon.")
    
    # Paths
    dist_dir = Path('dist')
    app_name = "Terminal Browser.app"
    app_path = dist_dir / app_name
    contents_path = app_path / "Contents"
    macos_path = contents_path / "MacOS"
    resources_path = contents_path / "Resources"
    
    # Check if executable/folder exists (onedir creates a folder)
    executable_folder = dist_dir / "Terminal Browser"
    executable_path = executable_folder / "Terminal Browser"
    if not executable_path.exists():
        print("✗ Executable not found. Please run build.py first.")
        return 1
    
    # Remove existing app bundle if it exists
    if app_path.exists():
        print(f"Removing existing {app_name}...")
        shutil.rmtree(app_path)
    
    # Create app bundle structure
    print(f"\nCreating {app_name} bundle...")
    macos_path.mkdir(parents=True, exist_ok=True)
    resources_path.mkdir(parents=True, exist_ok=True)
    
    # Copy entire executable folder to MacOS folder (onedir mode)
    print("Copying executable and dependencies...")
    if (macos_path / "Terminal Browser").exists():
        shutil.rmtree(macos_path / "Terminal Browser")
    shutil.copytree(executable_folder, macos_path / "Terminal Browser")
    
    # Make main executable executable
    main_exec = macos_path / "Terminal Browser" / "Terminal Browser"
    os.chmod(main_exec, 0o755)
    
    # Create Info.plist
    print("Creating Info.plist...")
    info_plist = {
        'CFBundleName': 'Terminal Browser',
        'CFBundleDisplayName': 'Terminal Browser',
        'CFBundleIdentifier': 'com.terminalbrowser.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': '????',
        'CFBundleExecutable': 'Terminal Browser/Terminal Browser',  # Path to executable in onedir
        'CFBundleIconFile': 'icon.icns',
        'CFBundleInfoDictionaryVersion': '6.0',
        'CFBundleGetInfoString': 'A powerful desktop terminal application',
        'NSHumanReadableCopyright': 'Copyright © 2025',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13',
        'NSRequiresAquaSystemAppearance': False,
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True
        },
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
    }
    
    plist_path = contents_path / "Info.plist"
    with open(plist_path, 'wb') as f:
        dump(info_plist, f)
    
    # Copy icon to Resources if it exists
    icon_source = Path('assets/icon.icns')
    if icon_source.exists():
        print("Copying icon to Resources...")
        shutil.copy2(icon_source, resources_path / "icon.icns")
    
    # Copy assets to Resources if they exist
    assets_source = Path('assets')
    if assets_source.exists():
        print("Copying assets to Resources...")
        assets_dest = resources_path / "assets"
        shutil.copytree(assets_source, assets_dest)
    
    print(f"\n✓ {app_name} created successfully!")
    print(f"Location: {app_path.absolute()}")
    
    return 0

def create_dmg():
    """Create a DMG installer for distribution"""
    print("\n" + "=" * 60)
    print("Creating DMG installer...")
    print("=" * 60)
    
    app_name = "Terminal Browser.app"
    app_path = Path('dist') / app_name
    dmg_name = "TerminalBrowser-1.0.0.dmg"
    dmg_path = Path('dist') / dmg_name
    
    # Check if app bundle exists, if not, create it
    if not app_path.exists():
        print("App bundle not found. Creating it first...")
        result = create_app_bundle()
        if result != 0:
            print("✗ Failed to create app bundle.")
            return 1
    
    # Remove existing DMG
    if dmg_path.exists():
        print(f"Removing existing {dmg_name}...")
        dmg_path.unlink()
    
    # Create a temporary folder for DMG contents
    temp_dmg_dir = Path('dist') / "dmg_temp"
    if temp_dmg_dir.exists():
        shutil.rmtree(temp_dmg_dir)
    temp_dmg_dir.mkdir()
    
    # Copy app to temp directory
    print("Preparing DMG contents...")
    shutil.copytree(app_path, temp_dmg_dir / app_name)
    
    # Create Applications symlink
    applications_link = temp_dmg_dir / "Applications"
    os.symlink("/Applications", applications_link)
    
    # Create DMG using hdiutil (UDRO = read-only, uncompressed - much faster)
    print(f"Creating DMG: {dmg_name}...")
    try:
        cmd = [
            'hdiutil', 'create',
            '-volname', 'Terminal Browser',
            '-srcfolder', str(temp_dmg_dir),
            '-ov', '-format', 'UDRO',
            str(dmg_path)
        ]
        subprocess.run(cmd, check=True)
        
        print(f"\n✓ DMG created successfully!")
        print(f"Location: {dmg_path.absolute()}")
        
        # Clean up temp directory
        shutil.rmtree(temp_dmg_dir)
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Failed to create DMG: {e}")
        print("Note: DMG creation requires hdiutil (macOS built-in tool)")
        return 1
    except FileNotFoundError:
        print("\n✗ hdiutil not found. This is a macOS-only tool.")
        print("DMG creation skipped. App bundle is ready for distribution.")
        return 1

def main():
    """Main packaging function"""
    # Create app bundle
    result = create_app_bundle()
    if result != 0:
        return result
    
    # Create DMG if --dmg flag is provided, otherwise skip
    if '--dmg' in sys.argv:
        create_dmg()
    else:
        print("\nSkipping DMG creation. To create DMG, run:")
        print("  python package.py --dmg")
    
    print("\n" + "=" * 60)
    print("✓ Packaging completed!")
    print("=" * 60)
    print(f"\nApp bundle: dist/Terminal Browser.app")
    print("\nTo distribute:")
    print("  1. Share the .app bundle directly (drag to Applications folder)")
    print("  2. Or create a DMG: python package.py --dmg")
    
    return 0

if __name__ == '__main__':
    # Check for --dmg flag
    if '--dmg' in sys.argv:
        sys.exit(create_dmg())
    else:
        sys.exit(main())

