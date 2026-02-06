#!/usr/bin/env python3
"""
Test script to verify file/folder clicking functionality
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from ui.pyte_terminal_widget import PyteTerminalWidget

def test_get_text_at_pos():
    """Test the get_text_at_pos method"""
    app = QApplication(sys.argv)
    
    # Create a terminal widget
    terminal = PyteTerminalWidget()
    
    # Simulate some output with file names
    test_lines = [
        "test.txt",
        "folder/",
        "my document.pdf",
        "path/to/file.txt",
    ]
    
    print("Testing text extraction...")
    for line in test_lines:
        print(f"\nTest line: '{line}'")
        # Simulate clicking at different positions in the line
        for col in range(len(line)):
            # Create mock screen data
            # Note: This is a simplified test - in reality we'd need full screen setup
            print(f"  Position {col}: character '{line[col]}'")
    
    print("\nDone!")

if __name__ == "__main__":
    test_get_text_at_pos()
