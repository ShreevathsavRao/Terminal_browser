#!/usr/bin/env python3
"""
Build script for Terminal Browser
Creates a standalone executable using PyInstaller
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    """Main build function"""
    print("=" * 60)
    print("Terminal Browser - Build Script")
    print("=" * 60)
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"✓ PyInstaller found: {PyInstaller.__version__}")
    except ImportError:
        print("✗ PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller installed")
    
    # Clean previous builds
    build_dirs = ['build', 'dist']
    for dir_name in build_dirs:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)
    
    # Remove previous spec file if it exists
    spec_file = Path('terminal_browser.spec')
    if spec_file.exists():
        print(f"Using existing spec file: {spec_file}")
    else:
        print("✗ Spec file not found. Please create terminal_browser.spec first.")
        return 1
    
    # Build the executable
    print("\nBuilding executable...")
    print("-" * 60)
    
    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            "terminal_browser.spec"
        ]
        
        result = subprocess.run(cmd, check=True)
        print("\n" + "=" * 60)
        print("✓ Build completed successfully!")
        print("=" * 60)
        print(f"\nExecutable location: {Path('dist').absolute()}")
        
        # Ask if user wants to create package
        if '--package' in sys.argv or '--pkg' in sys.argv:
            print("\nCreating distributable package...")
            try:
                import package
                package_result = package.create_app_bundle()
                if package_result == 0:
                    if '--dmg' in sys.argv:
                        package.create_dmg()
                    print("\n✓ Package created successfully!")
                else:
                    print("\n⚠ Package creation had issues. Executable is still available.")
            except Exception as e:
                print(f"\n⚠ Package creation failed: {e}")
                print("Executable is still available in dist/ folder.")
        else:
            print("\nTo create a distributable package, run:")
            print("  python package.py")
            print("  python package.py --dmg  # With DMG installer")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 60)
        print("✗ Build failed!")
        print("=" * 60)
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n\nBuild interrupted by user.")
        return 1

if __name__ == '__main__':
    sys.exit(main())

