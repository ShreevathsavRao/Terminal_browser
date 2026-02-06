"""Terminal search widget for finding text in terminal output"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QPushButton, 
                             QLabel, QCheckBox, QFrame, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent


class TerminalSearchWidget(QWidget):
    """Search widget for finding text in terminal"""
    
    # Signals
    search_requested = pyqtSignal(str, bool, bool)  # text, case_sensitive, whole_word
    next_requested = pyqtSignal()
    previous_requested = pyqtSignal()
    close_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Style the widget
        self.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-top: 1px solid #3c3c3c;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 3px;
                min-width: 200px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
            QPushButton:pressed {
                background-color: #555;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #0078d4;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
        
        # Search label
        search_label = QLabel("Find:")
        layout.addWidget(search_label)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in terminal...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._on_enter_pressed)
        layout.addWidget(self.search_input)
        
        # Match counter label
        self.match_label = QLabel("")
        self.match_label.setMinimumWidth(60)
        layout.addWidget(self.match_label)
        
        # Previous button
        self.prev_button = QPushButton("↑")
        self.prev_button.setToolTip("Previous match (Shift+Enter)")
        self.prev_button.clicked.connect(self.previous_requested.emit)
        self.prev_button.setEnabled(False)
        layout.addWidget(self.prev_button)
        
        # Next button
        self.next_button = QPushButton("↓")
        self.next_button.setToolTip("Next match (Enter)")
        self.next_button.clicked.connect(self.next_requested.emit)
        self.next_button.setEnabled(False)
        layout.addWidget(self.next_button)
        
        # Case sensitive checkbox
        self.case_checkbox = QCheckBox("Aa")
        self.case_checkbox.setToolTip("Match case")
        self.case_checkbox.stateChanged.connect(self._on_options_changed)
        layout.addWidget(self.case_checkbox)
        
        # Whole word checkbox
        self.whole_word_checkbox = QCheckBox("Ab")
        self.whole_word_checkbox.setToolTip("Match whole word")
        self.whole_word_checkbox.stateChanged.connect(self._on_options_changed)
        layout.addWidget(self.whole_word_checkbox)
        
        # Close button
        close_button = QPushButton("✕")
        close_button.setToolTip("Close (Esc)")
        close_button.clicked.connect(self.close_requested.emit)
        close_button.setMaximumWidth(30)
        layout.addWidget(close_button)
        
        # Add stretch to push everything to the left
        layout.addStretch()
        
        # Set fixed height
        self.setFixedHeight(45)
        
        # Hide by default
        self.hide()
    
    def _on_search_text_changed(self, text):
        """Handle search text change"""
        case_sensitive = self.case_checkbox.isChecked()
        whole_word = self.whole_word_checkbox.isChecked()
        
        # Enable/disable buttons based on text
        has_text = bool(text.strip())
        self.prev_button.setEnabled(has_text)
        self.next_button.setEnabled(has_text)
        
        # Emit search request
        self.search_requested.emit(text, case_sensitive, whole_word)
    
    def _on_options_changed(self):
        """Handle option checkbox changes"""
        text = self.search_input.text()
        case_sensitive = self.case_checkbox.isChecked()
        whole_word = self.whole_word_checkbox.isChecked()
        
        # Re-search with new options
        if text.strip():
            self.search_requested.emit(text, case_sensitive, whole_word)
    
    def _on_enter_pressed(self):
        """Handle Enter key in search input"""
        modifiers = QApplication.instance().keyboardModifiers()
        if modifiers & Qt.ShiftModifier:
            # Shift+Enter: Previous match
            self.previous_requested.emit()
        else:
            # Enter: Next match
            self.next_requested.emit()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            # Escape closes the search
            self.close_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def show_and_focus(self):
        """Show the widget and focus the search input"""
        self.show()
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def update_match_count(self, current, total):
        """Update the match counter label
        
        Args:
            current: Current match index (1-based)
            total: Total number of matches
        """
        if total == 0:
            self.match_label.setText("No matches")
        elif total == 1:
            self.match_label.setText("1 match")
        else:
            self.match_label.setText(f"{current}/{total}")
    
    def get_search_text(self):
        """Get the current search text"""
        return self.search_input.text()
    
    def is_case_sensitive(self):
        """Check if case sensitive search is enabled"""
        return self.case_checkbox.isChecked()
    
    def is_whole_word(self):
        """Check if whole word search is enabled"""
        return self.whole_word_checkbox.isChecked()
