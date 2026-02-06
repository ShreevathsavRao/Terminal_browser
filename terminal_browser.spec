# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Terminal Browser
Creates a standalone executable with all dependencies bundled
"""

block_cipher = None

# Collect all data files to include
datas = [
    ('assets', 'assets'),  # Include entire assets folder
]

# Hidden imports for PyQt5 modules
hiddenimports = [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtSvg',
    'pyte',
    'qasync',
    'aiofiles',
    # UI modules
    'ui',
    'ui.main_window',
    'ui.terminal_group_panel',
    'ui.button_panel',
    'ui.terminal_tabs',
    'ui.terminal_widget',
    'ui.pyte_terminal_widget',
    'ui.pty_terminal_widget',
    'ui.preferences_dialog',
    'ui.help_dialog',
    'ui.dialogs',
    'ui.command_history_dialog',
    'ui.command_book_widget',
    'ui.session_recorder_widget',
    'ui.suggestion_widget',
    # Core modules
    'core',
    'core.state_manager',
    'core.preferences_manager',
    'core.command_history_manager',
    'core.command_queue',
    'core.command_library',
    'core.platform_manager',
    'core.session_recorder',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Key change: creates onedir instead of onefile
    name='Terminal Browser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Can add .icns file here if available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Terminal Browser',
)

