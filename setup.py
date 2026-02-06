"""
py2app setup file for Terminal Browser
Run: python setup.py py2app
"""

from setuptools import setup

APP = ['main.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,  # You can add an .icns file here later
    'plist': {
        'CFBundleName': 'Terminal Browser',
        'CFBundleDisplayName': 'Terminal Browser',
        'CFBundleGetInfoString': 'A powerful desktop terminal application',
        'CFBundleIdentifier': 'com.terminalbrowser.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'Copyright © 2025',
        'NSHighResolutionCapable': True,
    },
    'packages': ['PyQt5', 'pyte', 'ui', 'core'],
    'includes': [
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'pyte',
    ],
    'excludes': ['tkinter', 'matplotlib', 'numpy', 'scipy'],
    'arch': 'universal2',  # Support both Intel and Apple Silicon
}

setup(
    name='Terminal Browser',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=['PyQt5>=5.15.0', 'pyte>=0.8.0'],
)

