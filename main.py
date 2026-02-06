#!/usr/bin/env python3
"""
Terminal Browser Application
A desktop application with browser-like tabs, terminal groups, and command execution
"""

import sys
import os
import asyncio
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QMovie
import qasync

from ui.main_window import MainWindow

# Initialize debug logging system
from core.debug_logger import (
    set_debug_enabled, 
    set_category_enabled, 
    print_debug_config,
    enable_all_categories,
    debug_log
)

def init_debug_logging():
    """Initialize debug logging based on configuration"""
    try:
        import debug_config
        
        if debug_config.ENABLE_DEBUG:
            set_debug_enabled(True)
            
            if debug_config.ENABLE_ALL:
                enable_all_categories()
            else:
                # Enable specific categories
                for category in debug_config.ENABLED_CATEGORIES:
                    set_category_enabled(category, True)
    except:
        pass


def get_logo_path():
    """Get the path to the logo file"""
    # Get the directory where this script is located
    if getattr(sys, 'frozen', False):
        # Running as a compiled executable
        # In macOS .app bundle, assets are in Contents/Resources
        executable_path = Path(sys.executable)
        # Check if we're in a .app bundle
        if '.app/Contents/MacOS' in str(executable_path):
            # Navigate to Resources folder
            base_path = executable_path.parent.parent / 'Resources'
        else:
            base_path = executable_path.parent
    else:
        # Running as a script
        base_path = Path(__file__).parent
    
    logo_path = base_path / 'assets' / 'logo_tb_terminal.png'
    return str(logo_path)

def create_splash_screen():
    """Create and return a splash screen with animated GIF"""
    # Use animated GIF instead of PNG
    gif_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo_cursor_blink_fade.gif')
    
    # Create label to hold the animated GIF
    splash_label = QLabel()
    splash_label.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.SplashScreen)
    splash_label.setAttribute(Qt.WA_TranslucentBackground)
    
    # Load and set the animated GIF
    movie = QMovie(gif_path)
    splash_label.setMovie(movie)
    
    # Get the actual size from the first frame
    movie.jumpToFrame(0)
    size = movie.currentPixmap().size()
    
    # Set size before starting animation
    if size.width() > 0 and size.height() > 0:
        splash_label.setFixedSize(size)
    else:
        # Fallback size if movie dimensions unavailable
        splash_label.setFixedSize(400, 400)
    
    splash_label.setScaledContents(True)
    movie.start()
    
    return splash_label

def main():
    """Main entry point for the application"""
    # Initialize debug logging first
    init_debug_logging()
    
    # Enable High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    debug_log('ui', 'Creating QApplication...')
    app = QApplication(sys.argv)
    app.setApplicationName("Terminal Browser")
    app.setOrganizationName("TerminalBrowser")
    
    # Set up async event loop with qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Set application icon
    logo_path = get_logo_path()
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))
        debug_log('ui', 'Application icon set', path=logo_path)
    
    # Set application style
    app.setStyle('Fusion')
    debug_log('ui', 'Application style set to Fusion')
    
    # Show splash screen
    splash = create_splash_screen()
    splash.show()
    app.processEvents()
    debug_log('ui', 'Splash screen displayed')
    
    # Create main window asynchronously
    async def create_window():
        debug_log('ui', 'Creating main window...')
        window = MainWindow()
        
        # Initialize async components
        await window.initialize_async()
        
        # Close splash screen after a short delay or when window is ready
        def close_splash():
            splash.close()
            debug_log('ui', 'Splash screen closed')
        
        QTimer.singleShot(1500, close_splash)  # Show splash for 1.5 seconds
        
        window.show()
        splash.raise_()
        debug_log('ui', 'Main window displayed, entering event loop')
    
    # Run the async window creation
    with loop:
        loop.run_until_complete(create_window())
        loop.run_forever()

if __name__ == '__main__':
    main()

