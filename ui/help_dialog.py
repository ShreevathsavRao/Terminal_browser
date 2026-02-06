"""Help Dialog with comprehensive documentation and navigation"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QTextBrowser, QListWidget, QListWidgetItem, 
                             QSplitter, QPushButton, QLabel, QWidget)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont, QTextCursor, QDesktopServices, QIcon, QPixmap, QPainter
import os
import sys
from pathlib import Path

# Try to import SVG support
try:
    from PyQt5.QtSvg import QSvgRenderer
    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False
    QSvgRenderer = None

class HelpDialog(QDialog):
    """Comprehensive help dialog with tabbed sections and navigation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Terminal Browser - Help & Documentation")
        self.setMinimumSize(1000, 700)
        self.init_ui()
    
    def get_logo_path(self):
        """Get the path to the logo file"""
        # Get the directory where this script is located
        if getattr(sys, 'frozen', False):
            # Running as a compiled executable
            base_path = Path(sys.executable).parent
        else:
            # Running as a script
            base_path = Path(__file__).parent.parent
        
        logo_path = base_path / 'assets' / 'logo_tb_terminal.svg'
        return str(logo_path)
    
    def create_logo_icon(self, size=48):
        """Create a logo icon from the SVG file"""
        logo_path = self.get_logo_path()
        
        if SVG_AVAILABLE and os.path.exists(logo_path):
            try:
                renderer = QSvgRenderer(logo_path)
                if renderer.isValid():
                    pixmap = QPixmap(size, size)
                    pixmap.fill(Qt.transparent)
                    painter = QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()
                    return QIcon(pixmap)
            except Exception:
                pass
        
        # Fallback: create a simple icon
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.green)
        painter.drawRect(0, 0, size, size)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Monaco", size // 2, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "tb")
        painter.end()
        return QIcon(pixmap)
        
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Header with logo and title
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-radius: 5px;
                padding: 15px;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setAlignment(Qt.AlignCenter)
        header_layout.setSpacing(15)
        
        # Logo icon
        logo_label = QLabel()
        logo_icon = self.create_logo_icon(48)
        logo_label.setPixmap(logo_icon.pixmap(48, 48))
        logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(logo_label)
        
        # Title text
        title_label = QLabel("Terminal Browser Help")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #4CAF50;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        
        layout.addWidget(header_widget)
        
        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 2px solid #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: #3d3d3d;
            }
        """)
        
        # Add tabs
        self.add_feature_index_tab()  # Feature index first
        self.add_getting_started_tab()
        self.add_features_tab()
        self.add_shortcuts_tab()
        self.add_terminal_groups_tab()
        self.add_command_buttons_tab()
        self.add_session_recorder_tab()
        self.add_troubleshooting_tab()
        self.add_about_tab()
        
        layout.addWidget(self.tab_widget)
        
        # Close button at bottom
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QTextBrowser {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 15px;
                selection-background-color: #0d47a1;
            }
            QListWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #0d47a1;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
    
    def create_navigable_tab(self, sections):
        """Create a tab with navigation sidebar and content area"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for navigation and content
        splitter = QSplitter(Qt.Horizontal)
        
        # Navigation list
        nav_list = QListWidget()
        nav_list.setMaximumWidth(250)
        
        # Content browser
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        content.setFont(QFont("Courier", 11))
        
        # Build content HTML
        html = """
        <html>
        <head>
            <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; }
                h2 { color: #4CAF50; border-bottom: 2px solid #4CAF50; padding-bottom: 5px; margin-top: 20px; }
                h3 { color: #64B5F6; margin-top: 15px; }
                code { background-color: #3d3d3d; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }
                pre { background-color: #3d3d3d; padding: 10px; border-radius: 5px; overflow-x: auto; }
                ul { margin-left: 20px; }
                li { margin: 5px 0; }
                .shortcut { color: #FFB74D; font-weight: bold; }
                .note { background-color: #2d3a4d; padding: 10px; border-left: 4px solid #2196F3; margin: 10px 0; }
                .tip { background-color: #2d4a2d; padding: 10px; border-left: 4px solid #4CAF50; margin: 10px 0; }
                a { color: #64B5F6; text-decoration: none; border-bottom: 1px solid transparent; transition: border-bottom 0.2s; }
                a:hover { color: #90CAF9; border-bottom: 1px solid #90CAF9; cursor: pointer; }
                .feature-link { color: #4CAF50; font-weight: 500; text-decoration: none; border-bottom: 2px solid transparent; padding-bottom: 2px; transition: all 0.2s; display: inline-block; }
                .feature-link:hover { color: #66BB6A; border-bottom: 2px solid #66BB6A; }
            </style>
        </head>
        <body>
        """
        
        # Add sections
        for section_name, section_content in sections.items():
            html += f'<h2 id="{self.slugify(section_name)}">{section_name}</h2>'
            html += section_content
            
            # Add to navigation
            item = QListWidgetItem(section_name)
            item.setData(Qt.UserRole, self.slugify(section_name))
            nav_list.addItem(item)
        
        html += "</body></html>"
        content.setHtml(html)
        
        # Connect navigation
        def navigate_to_section(item):
            anchor = item.data(Qt.UserRole)
            content.scrollToAnchor(anchor)
        
        nav_list.itemClicked.connect(navigate_to_section)
        
        # Enable link navigation within content
        def handle_anchor_click(url):
            if url.scheme() == "help" or url.scheme() == "":
                # Internal anchor link - navigate to section
                fragment = url.fragment()
                if fragment:
                    content.scrollToAnchor(fragment)
                    return True
            return False
        
        # Connect anchor clicks to navigation
        content.setOpenExternalLinks(False)
        content.anchorClicked.connect(handle_anchor_click)
        
        # Add to splitter
        splitter.addWidget(nav_list)
        splitter.addWidget(content)
        splitter.setSizes([200, 800])
        
        layout.addWidget(splitter)
        return widget
    
    def slugify(self, text):
        """Convert text to URL-friendly slug"""
        return text.lower().replace(' ', '-').replace('&', 'and')
    
    def add_feature_index_tab(self):
        """Feature Index tab with clickable links to detailed explanations"""
        content = QTextBrowser()
        content.setOpenExternalLinks(False)
        content.setFont(QFont("Courier", 11))
        
        # Store reference to tabs widget for navigation
        def navigate_to_tab(tab_name):
            """Navigate to a specific tab"""
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == tab_name:
                    self.tab_widget.setCurrentIndex(i)
                    break
        
        # Create click handler for feature links
        def handle_feature_click(url):
            """Handle clicks on feature index links"""
            if url.scheme() == "help":
                # Format: "help://TabName#section"
                # For help:// URLs, the tab name is in the host/authority, not the path
                path = url.host() or url.authority() or url.path().strip("/")
                fragment = url.fragment()
                
                
                # Map URL path to actual tab names (case-insensitive, handle emojis)
                tab_name_mapping = {
                    "features": "Features",
                    "shortcuts": "Shortcuts",
                    "terminal-groups": "Terminal Groups",
                    "command-buttons": "Command Buttons",
                    "session-recorder": "Session Recorder",
                    "getting-started": "Getting Started",
                    "troubleshooting": "Troubleshooting",
                    "about": "About"
                }
                
                # Try direct mapping first (normalize path to lowercase for lookup)
                path_lower = path.lower() if path else ""
                target_tab_name = tab_name_mapping.get(path_lower, path if path else "Features")
                
                # Find tab by name (try exact match, then partial match, then case-insensitive)
                found_tab_index = -1
                for i in range(self.tab_widget.count()):
                    tab_text = self.tab_widget.tabText(i)
                    # Remove emojis and normalize for comparison
                    tab_clean = ''.join(char for char in tab_text if char.isalnum() or char in (' ', '-', '_')).strip()
                    target_clean = ''.join(char for char in target_tab_name if char.isalnum() or char in (' ', '-', '_')).strip()
                    
                    
                    # Check if tab matches (case-insensitive, partial match OK)
                    if (tab_clean.lower() == target_clean.lower() or 
                        target_clean.lower() in tab_clean.lower() or
                        tab_clean.lower() in target_clean.lower()):
                        found_tab_index = i
                        break
                
                if found_tab_index >= 0:
                    # Switch to the tab
                    self.tab_widget.setCurrentIndex(found_tab_index)
                    
                    # Scroll to section after tab switch (with delay to allow rendering)
                    if fragment:
                        from PyQt5.QtCore import QTimer
                        def scroll_to_section():
                            current_widget = self.tab_widget.currentWidget()
                            if current_widget:
                                # Find all QTextBrowser widgets in the current tab
                                from PyQt5.QtWidgets import QTextBrowser
                                browsers = current_widget.findChildren(QTextBrowser)
                                
                                # If no browsers found, maybe the widget itself is a QTextBrowser
                                if len(browsers) == 0 and isinstance(current_widget, QTextBrowser):
                                    browsers = [current_widget]
                                
                                scroll_success = False
                                for browser in browsers:
                                    
                                    # Method 1: Try scrollToAnchor first (primary method)
                                    try:
                                        browser.scrollToAnchor(fragment)
                                        # Verify it worked by checking scroll position
                                        scrollbar = browser.verticalScrollBar()
                                        if scrollbar:
                                            scroll_value = scrollbar.value()
                                            # If scroll value changed, it likely worked
                                            if scroll_value > 0:
                                                scroll_success = True
                                                break  # Success, don't try other methods or other browsers
                                    except Exception as e:
                                        pass
                                    
                                    # Only try Method 2 if Method 1 didn't work
                                    if not scroll_success:
                                        # Method 2: Find anchor in HTML and scroll to its position using cursor
                                        try:
                                            document = browser.document()
                                            if document:
                                                # Search HTML content for the anchor
                                                html_content = browser.toHtml()
                                                anchor_pattern = f'id="{fragment}"'
                                                if anchor_pattern in html_content:
                                                    # Find the anchor tag position in HTML
                                                    anchor_start = html_content.find(anchor_pattern)
                                                    if anchor_start >= 0:
                                                        # Find the opening tag
                                                        tag_start = html_content.rfind('<', 0, anchor_start)
                                                        tag_end = html_content.find('>', anchor_start)
                                                        
                                                        # Extract tag name and content
                                                        if tag_start >= 0 and tag_end >= 0:
                                                            tag_content = html_content[tag_start:tag_end + 1]
                                                            
                                                            # Try to find this in the document
                                                            # First try to find by the id value itself
                                                            cursor = browser.textCursor()
                                                            cursor.movePosition(QTextCursor.Start)
                                                            
                                                            # Search for text that appears after the anchor
                                                            # Look for the heading text or section content
                                                            found = False
                                                            # Try finding by the fragment text as it might appear in the heading
                                                            search_text = fragment.replace('-', ' ').title()
                                                            cursor = document.find(search_text, 0)
                                                            if not cursor.isNull():
                                                                browser.setTextCursor(cursor)
                                                                browser.ensureCursorVisible()
                                                                found = True
                                                                scroll_success = True
                                                            
                                                            # If that didn't work, try finding by tag content
                                                            if not found:
                                                                cursor = document.find(tag_content, 0)
                                                                if not cursor.isNull():
                                                                    browser.setTextCursor(cursor)
                                                                    browser.ensureCursorVisible()
                                                                    scroll_success = True
                                        except Exception as e:
                                            pass
                                    
                                    if scroll_success:
                                        break  # Stop trying other browsers
                                else:
                                    pass
                            else:
                                pass
                        QTimer.singleShot(300, scroll_to_section)  # Increased delay to 300ms for better reliability
                    return True
                else:
                    pass
                
                return True
            return False
        
        content.anchorClicked.connect(handle_feature_click)
        
        html = """
        <html>
        <head>
            <style>
                body { 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    line-height: 1.8; 
                    padding: 20px;
                }
                h1 { 
                    color: #4CAF50; 
                    text-align: center; 
                    margin-bottom: 30px; 
                    border-bottom: 3px solid #4CAF50;
                    padding-bottom: 15px;
                }
                h2 { 
                    color: #64B5F6; 
                    margin-top: 25px; 
                    border-bottom: 2px solid #64B5F6; 
                    padding-bottom: 5px; 
                }
                .feature-category {
                    background-color: #2b2b2b;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 15px 0;
                }
                .feature-list {
                    list-style: none;
                    padding-left: 0;
                }
                .feature-list li {
                    margin: 10px 0;
                    padding: 8px;
                    background-color: #3d3d3d;
                    border-radius: 3px;
                }
                a.feature-link { 
                    color: #4CAF50; 
                    font-weight: 500; 
                    text-decoration: none; 
                    border-bottom: 2px solid transparent; 
                    padding-bottom: 2px; 
                    transition: all 0.2s; 
                    display: inline-block;
                    font-size: 16px;
                }
                a.feature-link:hover { 
                    color: #66BB6A; 
                    border-bottom: 2px solid #66BB6A; 
                }
                .new-badge {
                    background-color: #4CAF50;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-size: 11px;
                    font-weight: bold;
                    margin-left: 8px;
                }
            </style>
        </head>
        <body>
            <h1>📚 Feature Index</h1>
            <p style="text-align: center; font-size: 18px; color: #e0e0e0; margin-bottom: 30px;">
                Click on any feature below to jump to its detailed explanation
            </p>
            
            <h2>🖥️ Terminal Management</h2>
            <div class="feature-category">
                <ul class="feature-list">
                    <li><a href="help://Features#terminal-management" class="feature-link">Browser-Like Tabs</a> - Horizontal scrollable tabs with drag & drop</li>
                    <li><a href="help://Features#terminal-groups" class="feature-link">Terminal Groups</a> - Organize terminals by project or task</li>
                    <li><a href="help://Features#full-terminal-emulation" class="feature-link">Full Terminal Emulation</a> - Complete VT100/ANSI support with htop, vim, nano</li>
                    <li><a href="help://Features#command-history-search" class="feature-link">Command History Search</a> <span class="new-badge">NEW</span> - Fuzzy search with Ctrl+R</li>
                    <li><a href="help://Features#ctrl-click-files" class="feature-link">Ctrl+Click to Open Files</a> - Click files to open in default app</li>
                    <li><a href="help://Features#hover-underline" class="feature-link">Hover Underline for Files</a> - Visual feedback for clickable files</li>
                </ul>
            </div>
            
            <h2>🎯 Command Management</h2>
            <div class="feature-category">
                <ul class="feature-list">
                    <li><a href="help://Features#command-buttons" class="feature-link">Command Buttons</a> - One-click execution of frequently used commands</li>
                    <li><a href="help://Features#command-queue" class="feature-link">Command Queue</a> - FIFO queue system for batch processing</li>
                    <li><a href="help://Features#session-recording" class="feature-link">Session Recording & Playback</a> - Record and replay command sequences</li>
                </ul>
            </div>
            
            <h2>📁 File & Data Management</h2>
            <div class="feature-category">
                <ul class="feature-list">
                    <li><a href="help://Features#file-attachments" class="feature-link">File Attachments</a> - Attach PEM keys, configs, scripts as environment variables</li>
                    <li><a href="help://Features#tab-notes" class="feature-link">Tab Notes</a> <span class="new-badge">NEW</span> - Rich text notes with clickable links</li>
                </ul>
            </div>
            
            <h2>🎨 Customization</h2>
            <div class="feature-category">
                <ul class="feature-list">
                    <li><a href="help://Features#preferences" class="feature-link">Preferences</a> - Customize fonts, colors, cursor styles</li>
                    <li><a href="help://Shortcuts#keyboard-shortcuts" class="feature-link">Keyboard Shortcuts</a> - Quick access to all features</li>
                </ul>
            </div>
            
            <div class="tip" style="background-color: #2d4a2d; padding: 15px; border-left: 4px solid #4CAF50; margin: 20px 0; border-radius: 3px;">
                <strong>💡 Tip:</strong> Use the navigation sidebar in each help tab to quickly find specific sections!
            </div>
        </body>
        </html>
        """
        
        content.setHtml(html)
        
        # Store the HTML content and browser reference to restore it later if needed
        self.feature_index_html = html
        self.feature_index_browser = content
        
        # Handle sourceChanged signal to prevent QTextBrowser from trying to load help:// URLs
        def handle_source_changed(new_url):
            """Prevent QTextBrowser from navigating to help:// URLs"""
            url_str = new_url.toString()
            if url_str.startswith("help://"):
                # If it tries to load a help:// URL, restore the original HTML
                content.setHtml(self.feature_index_html)
        
        content.sourceChanged.connect(handle_source_changed)
        
        # Handle tab changes to restore content if it gets cleared
        def handle_tab_change(index):
            """Restore Feature Index content when switching back to it"""
            current_widget = self.tab_widget.widget(index)
            if current_widget == self.feature_index_browser:
                # Check if content is empty or cleared (look for key marker from original HTML)
                current_html = self.feature_index_browser.toHtml()
                if not current_html or "📚 Feature Index" not in current_html:
                    # Use QTimer to restore after a short delay to ensure tab is fully visible
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(50, lambda: self.feature_index_browser.setHtml(self.feature_index_html))
        
        # Connect to tab changed signal if not already connected
        if not hasattr(self, '_tab_change_connected'):
            self.tab_widget.currentChanged.connect(handle_tab_change)
            self._tab_change_connected = True
        
        self.tab_widget.addTab(content, "📚 Feature Index")
    
    def add_getting_started_tab(self):
        """Getting Started tab"""
        sections = {
            "Welcome": """
                <p>Welcome to <strong>Terminal Browser</strong> - a powerful desktop terminal application 
                with browser-like tabs, terminal groups, and command execution management.</p>
                
                <div class="tip">
                    <strong>💡 Tip:</strong> Terminal Browser lets you manage multiple terminal sessions 
                    simultaneously with an intuitive tab-based interface, just like a web browser!
                </div>
            """,
            
            "Quick Start": """
                <h3>Starting the Application</h3>
                <pre>python main.py</pre>
                
                <h3>First Steps</h3>
                <ol>
                    <li><strong>Create a Terminal Group:</strong> Click "+ Add Group" in the left panel</li>
                    <li><strong>Add Terminal Tabs:</strong> Click the "+" button in the tab bar</li>
                    <li><strong>Execute Commands:</strong> Type commands or use the button panel on the right</li>
                    <li><strong>Organize Your Workflow:</strong> Create groups for different projects or tasks</li>
                </ol>
            """,
            
            "Installation": """
                <h3>Prerequisites</h3>
                <ul>
                    <li>Python 3.7 or higher</li>
                    <li>pip (Python package installer)</li>
                </ul>
                
                <h3>Setup Steps</h3>
                <ol>
                    <li>Navigate to the project directory</li>
                    <li>Install dependencies: <code>pip install -r requirements.txt</code></li>
                    <li>Run the application: <code>python main.py</code></li>
                </ol>
                
                <div class="note">
                    <strong>📝 Note:</strong> On macOS, you can build a standalone app using 
                    <code>python setup.py py2app</code>
                </div>
            """,
            
            "Interface Overview": """
                <h3>Left Panel - Terminal Groups</h3>
                <p>Organize terminals into logical groups (e.g., Frontend, Backend, DevOps)</p>
                
                <h3>Center Area - Terminal Tabs</h3>
                <p>Browser-like tabs for multiple terminal sessions within each group</p>
                
                <h3>Right Panel - Command Buttons & Files</h3>
                <p>Quick-access buttons for frequently used commands and file attachments</p>
                
                <h3>Toolbar</h3>
                <p>Toggle panels, access preferences, and access help documentation</p>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "🚀 Getting Started")
    
    def add_features_tab(self):
        """Features tab"""
        sections = {
            "Terminal Management": """
                <h3 id="terminal-management">Browser-Like Tabs</h3>
                <ul>
                    <li>Horizontal scrollable tabs for easy navigation</li>
                    <li>Drag and drop to reorder tabs</li>
                    <li>Quick close buttons on each tab</li>
                    <li>Right-click to rename tabs</li>
                    <li>Tab navigation buttons with hidden tab counts</li>
                    <li>Shell selection for each tab (bash, zsh, fish, etc.)</li>
                </ul>
                
                <h3 id="terminal-groups">Terminal Groups</h3>
                <ul>
                    <li>Organize terminals into logical groups</li>
                    <li>Each group has its own set of tabs and buttons</li>
                    <li>Rename and delete groups as needed</li>
                    <li>Groups are saved between sessions</li>
                    <li>Quick switching between groups with a single click</li>
                </ul>
                
                <h3 id="full-terminal-emulation">Full Terminal Emulation</h3>
                <ul>
                    <li>Complete VT100/ANSI support</li>
                    <li>Works with htop, vim, nano, less, tmux</li>
                    <li>All ncurses-based applications supported</li>
                    <li>Proper color and formatting support</li>
                    <li>256-color palette support</li>
                    <li>Unicode character support</li>
                </ul>
                
                <h3 id="command-history-search">Command History Search <span style="background-color: #4CAF50; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">NEW</span></h3>
                <p>Powerful fuzzy search for your command history, inspired by Warp terminal.</p>
                <ul>
                    <li><strong>Quick Access:</strong> Press <code>Ctrl+R</code> to instantly search</li>
                    <li><strong>Fuzzy Search:</strong> Find commands with partial matches</li>
                    <li><strong>Cross-Group Search:</strong> Search history across ALL terminal groups</li>
                    <li><strong>Smart Ranking:</strong> Results sorted by relevance and recency</li>
                    <li><strong>Rich Context:</strong> See when, where, and in which group commands were run</li>
                    <li><strong>Persistent History:</strong> Commands saved across sessions (up to 10,000 commands)</li>
                    <li><strong>Execute or Insert:</strong> Choose to insert for review or execute immediately</li>
                </ul>
                
                <div class="tip">
                    <strong>💡 Tip:</strong> Type part of a command in the search box to find it instantly!
                </div>
                
                <h3 id="ctrl-click-files">Ctrl+Click to Open Files</h3>
                <p>Quickly open files and folders in their default applications directly from the terminal.</p>
                <ul>
                    <li><strong>How to Use:</strong> Hold <code>Ctrl</code> (or <code>Cmd</code> on macOS) and click on any file or folder name</li>
                    <li><strong>Opens With:</strong> Files open in their default application (Finder on macOS, Explorer on Windows)</li>
                    <li><strong>Smart Detection:</strong> Automatically detects files and folders from <code>ls</code> output</li>
                    <li><strong>Path Resolution:</strong> Works with absolute paths, relative paths, and filenames</li>
                    <li><strong>Handles Spaces:</strong> Properly extracts filenames with spaces like "My Document.pdf"</li>
                </ul>
                
                <div class="tip">
                    <strong>💡 Example:</strong> Type <code>ls</code>, then Ctrl+Click on any file or folder to open it!
                </div>
                
                <h3 id="hover-underline">Hover Underline for Files</h3>
                <p>Visual feedback when hovering over clickable files and folders.</p>
                <ul>
                    <li><strong>Visual Indicator:</strong> Files and folders show an underline when you hover over them</li>
                    <li><strong>Interactive Feedback:</strong> Makes it clear which items can be clicked</li>
                    <li><strong>Smart Detection:</strong> Only shows underline for valid file/folder paths</li>
                </ul>
                
                <div class="note">
                    <strong>📝 Note:</strong> Hover over any file or folder name in the terminal to see the underline effect!
                </div>
            """,
            
            "Command Buttons": """
                <h3 id="command-buttons">Custom Command Buttons</h3>
                <ul>
                    <li>Create buttons with custom shell commands</li>
                    <li>One-click execution of complex commands</li>
                    <li>Edit and delete custom buttons</li>
                    <li>Buttons are saved per group</li>
                </ul>
                
                <h3>Default Commands</h3>
                <ul>
                    <li><strong>Clear:</strong> Clear the terminal screen</li>
                    <li><strong>List Files:</strong> Show directory contents</li>
                    <li><strong>Show Path:</strong> Display current directory</li>
                    <li><strong>Disk Usage:</strong> Show disk space</li>
                </ul>
                
                <div class="tip">
                    <strong>💡 Pro Tip:</strong> Right-click on custom buttons to edit or delete them!
                </div>
            """,
            
            "Command Queue": """
                <h3 id="command-queue">FIFO Queue System</h3>
                <ul>
                    <li>Commands execute in First-In-First-Out order</li>
                    <li>Queue multiple commands for batch execution</li>
                    <li>Visual feedback for queued commands</li>
                </ul>
                
                <h3>Queue Controls</h3>
                <ul>
                    <li><strong>Start Queue:</strong> Begin processing queued commands</li>
                    <li><strong>Stop Queue:</strong> Pause queue processing</li>
                    <li><strong>Kill Queue:</strong> Clear all queued commands</li>
                </ul>
            """,
            
            "Session Recording & Playback": """
                <h3 id="session-recording">Record Command Sequences</h3>
                <ul>
                    <li>Record sequences of commands for automation</li>
                    <li>Replay recordings with one click</li>
                    <li>Perfect for repetitive tasks and deployments</li>
                    <li>Import/Export recordings as JSON files</li>
                </ul>
                
                <h3>Key Features</h3>
                <ul>
                    <li><strong>Recording:</strong> Capture commands from buttons or command book</li>
                    <li><strong>Playback:</strong> Automatic execution with play/pause/stop controls</li>
                    <li><strong>Management:</strong> Edit, duplicate, delete recordings</li>
                    <li><strong>Sharing:</strong> Export recordings to share with team</li>
                    <li><strong>Usage Tracking:</strong> See how many times each recording has been played</li>
                </ul>
                
                <div class="note">
                    <strong>📝 Note:</strong> See the <strong>🎬 Session Recorder</strong> tab for detailed usage instructions
                </div>
            """,
            
            "File Attachments": """
                <h3 id="file-attachments">Attach Supporting Files</h3>
                <ul>
                    <li>Attach PEM keys, config files, scripts</li>
                    <li>Files available as environment variables</li>
                    <li>Easy to add and remove files</li>
                    <li>Files are saved per group</li>
                </ul>
                
                <h3>Usage in Commands</h3>
                <p>Attached files are automatically set as environment variables that can be 
                referenced in your commands.</p>
            """,
            
            "Tab Notes": """
                <h3 id="tab-notes">Tab-Specific Notes <span style="background-color: #4CAF50; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">NEW</span></h3>
                <p>Rich text notes for each terminal tab with advanced formatting and clickable links.</p>
                <ul>
                    <li><strong>Rich Text Editing:</strong> Bold, italic, underline, strikethrough, colors</li>
                    <li><strong>Multiple Notes per Tab:</strong> Create and organize multiple notes for each terminal</li>
                    <li><strong>Formatting Toolbar:</strong> Font selection, sizes, text/background colors</li>
                    <li><strong>Automatic Title:</strong> First line becomes the note title (underlined)</li>
                    <li><strong>Auto-Save:</strong> Notes are automatically saved as you type</li>
                    <li><strong>Persistent Storage:</strong> All notes saved across sessions</li>
                </ul>
                
                <h3 id="clickable-links">Clickable Links in Notes <span style="background-color: #4CAF50; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">NEW</span></h3>
                <p>Open URLs and file paths directly from your notes with Cmd/Ctrl+Click.</p>
                <ul>
                    <li><strong>Web URLs:</strong> <code>Cmd+Click</code> (macOS) or <code>Ctrl+Click</code> (Windows/Linux) on any URL to open in browser</li>
                    <li><strong>Supports:</strong> http://, https://, www. URLs</li>
                    <li><strong>File Paths:</strong> <code>Cmd+Click</code> or <code>Ctrl+Click</code> on file/folder paths to open</li>
                    <li><strong>Path Types:</strong> Unix paths (/Users/..., ~/...) and Windows paths (C:\\...)</li>
                    <li><strong>Smart Opening:</strong> Files open in default app, folders in Finder/Explorer</li>
                </ul>
                
                <div class="tip">
                    <strong>💡 Example:</strong> Type <code>/Users/john/Documents</code> or <code>https://github.com</code> in your notes, then Cmd+Click to open!
                </div>
                
                <h3>How to Access Notes</h3>
                <ul>
                    <li>Right-click on any terminal tab</li>
                    <li>Select "Notes" from the context menu</li>
                    <li>Or use the menu: <strong>Edit → Notes</strong></li>
                </ul>
                
                <div class="note">
                    <strong>📝 Note:</strong> Notes are automatically saved per tab, so you can have different notes for different terminals!
                </div>
            """,
            
            "Preferences": """
                <h3 id="preferences">Customizable Settings</h3>
                <ul>
                    <li><strong>Font Family:</strong> Choose from monospace fonts</li>
                    <li><strong>Font Size:</strong> Adjust terminal text size</li>
                    <li><strong>Colors:</strong> Customize foreground and background colors</li>
                    <li><strong>Cursor Style:</strong> Block, underline, or bar cursor</li>
                </ul>
                
                <div class="note">
                    <strong>📝 Note:</strong> Access preferences via Edit menu or toolbar button
                </div>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "✨ Features")
    
    def add_shortcuts_tab(self):
        """Keyboard Shortcuts tab"""
        sections = {
            "File Operations": """
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #2d2d2d;">
                        <td style="padding: 8px; border: 1px solid #555;"><strong>Action</strong></td>
                        <td style="padding: 8px; border: 1px solid #555;"><strong>macOS</strong></td>
                        <td style="padding: 8px; border: 1px solid #555;"><strong>Windows/Linux</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">New Tab</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+T</code> or <code>Cmd+N</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+T</code> or <code>Ctrl+N</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Close Tab</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+W</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+Shift+W</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Quit Application</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+Q</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+Q</code></td>
                    </tr>
                </table>
            """,
            
            "Editing & Clipboard": """
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #2d2d2d;">
                        <td style="padding: 8px; border: 1px solid #555;"><strong>Action</strong></td>
                        <td style="padding: 8px; border: 1px solid #555;"><strong>macOS</strong></td>
                        <td style="padding: 8px; border: 1px solid #555;"><strong>Windows/Linux</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Copy</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+C</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+Shift+C</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Paste</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+V</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+Shift+V</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Select All</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+A</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+Shift+A</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Cut</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd+X</code></td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+X</code></td>
                    </tr>
                </table>
            """,
            
            "View & Zoom": """
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #2d2d2d;">
                        <td style="padding: 8px; border: 1px solid #555;"><strong>Action</strong></td>
                        <td style="padding: 8px; border: 1px solid #555;"><strong>Shortcut</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Zoom In</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd/Ctrl + Plus</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Zoom Out</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd/Ctrl + Minus</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Reset Zoom</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl + 0</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Preferences</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Cmd/Ctrl + Comma</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #555;">Command History Search</td>
                        <td style="padding: 8px; border: 1px solid #555;"><code>Ctrl+R</code></td>
                    </tr>
                </table>
            """,
            
            "Terminal Control": """
                <h3 id="keyboard-shortcuts">Command History</h3>
                <ul>
                    <li><strong>Up Arrow:</strong> Previous command</li>
                    <li><strong>Down Arrow:</strong> Next command</li>
                </ul>
                
                <h3>Navigation</h3>
                <ul>
                    <li><strong>Home:</strong> Move to beginning of line</li>
                    <li><strong>End:</strong> Move to end of line</li>
                    <li><strong>Left/Right Arrow:</strong> Move cursor</li>
                </ul>
                
                <h3>Control Sequences</h3>
                <ul>
                    <li><strong>Ctrl+C:</strong> Interrupt/Cancel command</li>
                    <li><strong>Ctrl+D:</strong> Exit/EOF signal</li>
                    <li><strong>Ctrl+L:</strong> Clear screen</li>
                    <li><strong>Tab:</strong> Auto-complete</li>
                </ul>
            """,
            
            "Scrolling": """
                <ul>
                    <li><strong>Mouse Wheel:</strong> Scroll through output</li>
                    <li><strong>Shift+PageUp:</strong> Scroll up one page</li>
                    <li><strong>Shift+PageDown:</strong> Scroll down one page</li>
                    <li><strong>Two-finger scroll:</strong> Trackpad scrolling (macOS)</li>
                </ul>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "⌨️ Shortcuts")
    
    def add_terminal_groups_tab(self):
        """Terminal Groups guide"""
        sections = {
            "What are Terminal Groups?": """
                <p>Terminal Groups allow you to organize your terminal sessions into logical collections. 
                Each group maintains its own set of tabs, command buttons, and file attachments.</p>
                
                <div class="tip">
                    <strong>💡 Example Use Cases:</strong>
                    <ul>
                        <li><strong>Project-based:</strong> Frontend, Backend, Database, DevOps</li>
                        <li><strong>Environment-based:</strong> Development, Staging, Production</li>
                        <li><strong>Task-based:</strong> Monitoring, Deployment, Testing</li>
                    </ul>
                </div>
            """,
            
            "Creating Groups": """
                <h3>Step-by-Step</h3>
                <ol>
                    <li>Click <strong>"+ Add Group"</strong> button in the left panel</li>
                    <li>Enter a descriptive name for your group</li>
                    <li>The new group appears in the list</li>
                    <li>Select the group to start adding terminals</li>
                </ol>
                
                <div class="note">
                    <strong>📝 Note:</strong> Groups are automatically saved and restored between sessions
                </div>
            """,
            
            "Managing Groups": """
                <h3>Rename a Group</h3>
                <ol>
                    <li>Right-click on the group name</li>
                    <li>Select "Rename"</li>
                    <li>Enter the new name</li>
                </ol>
                
                <h3>Delete a Group</h3>
                <ol>
                    <li>Right-click on the group name</li>
                    <li>Select "Delete"</li>
                    <li>Confirm deletion</li>
                </ol>
                
                <div class="note">
                    <strong>⚠️ Warning:</strong> Deleting a group removes all its terminals, 
                    buttons, and file attachments
                </div>
            """,
            
            "Switching Between Groups": """
                <p>Simply click on any group name in the left panel to switch to it. The application 
                will automatically:</p>
                <ul>
                    <li>Load the group's terminal tabs</li>
                    <li>Restore command buttons</li>
                    <li>Load file attachments</li>
                    <li>Preserve terminal states</li>
                </ul>
            """,
            
            "Best Practices": """
                <ul>
                    <li><strong>Use descriptive names:</strong> "AWS Production" instead of "Group 1"</li>
                    <li><strong>Keep groups focused:</strong> One project or environment per group</li>
                    <li><strong>Organize by workflow:</strong> Group related tasks together</li>
                    <li><strong>Regular cleanup:</strong> Delete unused groups to stay organized</li>
                </ul>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "📁 Terminal Groups")
    
    def add_command_buttons_tab(self):
        """Command Buttons guide"""
        sections = {
            "Creating Command Buttons": """
                <h3>Step-by-Step</h3>
                <ol>
                    <li>Click <strong>"+ Add Button"</strong> in the right panel</li>
                    <li>Fill in the button details:
                        <ul>
                            <li><strong>Button Name:</strong> Display name (e.g., "Deploy")</li>
                            <li><strong>Command:</strong> Shell command to execute</li>
                            <li><strong>Description:</strong> Optional notes about the command</li>
                        </ul>
                    </li>
                    <li>Click <strong>"Save"</strong></li>
                </ol>
                
                <div class="tip">
                    <strong>💡 Tip:</strong> Use descriptive names that indicate what the command does!
                </div>
            """,
            
            "Command Examples": """
                <h3>Development</h3>
                <ul>
                    <li><code>npm start</code> - Start development server</li>
                    <li><code>npm test</code> - Run tests</li>
                    <li><code>npm run build</code> - Build for production</li>
                </ul>
                
                <h3>Git Operations</h3>
                <ul>
                    <li><code>git status</code> - Check repository status</li>
                    <li><code>git pull origin main</code> - Pull latest changes</li>
                    <li><code>git log --oneline -10</code> - Show recent commits</li>
                </ul>
                
                <h3>Server Management</h3>
                <ul>
                    <li><code>ssh user@server.com</code> - Connect to server</li>
                    <li><code>systemctl status nginx</code> - Check service status</li>
                    <li><code>docker ps</code> - List running containers</li>
                </ul>
                
                <h3>Database</h3>
                <ul>
                    <li><code>mysql -u root -p</code> - Connect to MySQL</li>
                    <li><code>psql -U postgres</code> - Connect to PostgreSQL</li>
                    <li><code>redis-cli</code> - Connect to Redis</li>
                </ul>
            """,
            
            "Using Environment Variables": """
                <p>If you have attached files, they're available as environment variables in your commands:</p>
                
                <h3>Example with SSH Key</h3>
                <p>If you attached <code>mykey.pem</code>, use it in commands:</p>
                <pre>ssh -i $MYKEY_PEM user@server.com</pre>
                
                <div class="note">
                    <strong>📝 Note:</strong> File names are converted to uppercase and dots become underscores
                </div>
            """,
            
            "Editing & Deleting Buttons": """
                <h3>Edit a Button</h3>
                <ol>
                    <li>Click the <strong>"Edit"</strong> button next to the command button</li>
                    <li>Modify the details</li>
                    <li>Click <strong>"Save"</strong></li>
                </ol>
                
                <h3>Delete a Button</h3>
                <ol>
                    <li>Click the <strong>"Delete"</strong> button next to the command button</li>
                    <li>Confirm deletion</li>
                </ol>
                
                <div class="note">
                    <strong>📝 Note:</strong> Default buttons (Clear, List Files, etc.) cannot be deleted
                </div>
            """,
            
            "Command Queue": """
                <h3>Queue Multiple Commands</h3>
                <p>Click multiple command buttons rapidly to add them to the queue. They'll execute 
                in order (FIFO - First In, First Out).</p>
                
                <h3>Queue Controls</h3>
                <ul>
                    <li><strong>Start:</strong> Begin executing queued commands</li>
                    <li><strong>Stop:</strong> Pause queue processing</li>
                    <li><strong>Kill:</strong> Clear all queued commands</li>
                </ul>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "🎯 Command Buttons")
    
    def add_session_recorder_tab(self):
        """Session Recorder guide"""
        sections = {
            "What is Session Recording?": """
                <p>The <strong>Session Recorder</strong> allows you to record sequences of commands and 
                replay them automatically. Perfect for repetitive tasks like deployments, setups, and testing.</p>
                
                <div class="tip">
                    <strong>💡 Perfect For:</strong>
                    <ul>
                        <li>Development environment setup</li>
                        <li>Deployment workflows</li>
                        <li>Testing sequences</li>
                        <li>Database operations</li>
                        <li>Batch processing tasks</li>
                    </ul>
                </div>
            """,
            
            "How to Record": """
                <h3>Step-by-Step Recording</h3>
                <ol>
                    <li>Go to <strong>🎬 Recorder</strong> tab in the right panel</li>
                    <li>Click <strong>⏺ Start Recording</strong></li>
                    <li>Execute commands using any method:
                        <ul>
                            <li><strong>Type directly</strong> in the terminal and press Enter</li>
                            <li><strong>Command Buttons</strong> (Command Buttons tab)</li>
                            <li><strong>Command Book</strong> (📚 Book tab)</li>
                            <li><strong>Command Queue</strong> (add and run commands)</li>
                        </ul>
                    </li>
                    <li>Click <strong>⏹ Stop Recording</strong></li>
                    <li>Review and edit commands if needed</li>
                    <li>Name your recording and save</li>
                </ol>

                <div class="tip" style="background-color: #2d4a2d; border-left: 4px solid #4CAF50;">
                    <strong>✨ NEW:</strong> Commands typed directly in the terminal are now captured automatically!
                    Type your commands naturally and they'll be recorded for later editing and playback.
                </div>
            """,
            
            "Playing Recordings": """
                <h3>Playback Controls</h3>
                <ul>
                    <li><strong>▶ Play:</strong> Execute the entire sequence automatically</li>
                    <li><strong>⏸ Pause:</strong> Temporarily halt execution</li>
                    <li><strong>⏹ Stop:</strong> Cancel playback immediately</li>
                </ul>
                
                <h3>Playback Features</h3>
                <ul>
                    <li>Commands execute sequentially with 1-second delay</li>
                    <li>Visual feedback shows playback status</li>
                    <li>Completion notification when done</li>
                    <li>Usage statistics tracked (play count)</li>
                </ul>
                
                <div class="tip">
                    <strong>💡 Tip:</strong> Watch the terminal output during playback to monitor command execution.
                </div>
            """,
            
            "Managing Recordings": """
                <h3>Edit Recording</h3>
                <p>Click the <strong>✏️</strong> button to modify:</p>
                <ul>
                    <li>Recording name</li>
                    <li>Description</li>
                    <li>Command list (add, remove, reorder)</li>
                </ul>
                
                <h3>More Options (⋮ Menu)</h3>
                <ul>
                    <li><strong>📋 Duplicate:</strong> Create a copy for variations</li>
                    <li><strong>💾 Export:</strong> Save as JSON file to share</li>
                    <li><strong>🗑️ Delete:</strong> Remove recording permanently</li>
                </ul>
                
                <h3>Import Recording</h3>
                <p>Click <strong>📥 Import</strong> to load recordings from JSON files.</p>
            """,
            
            "Correct Workflow Example": """
                <h3>✅ Method 1: Natural Typing (RECOMMENDED)</h3>
                <pre>
1. Go to "🎬 Recorder" tab
2. Click "⏺ Start Recording"
3. Click on terminal
4. Type: git pull
5. Press Enter              ← Command captured! ✓
6. Type: npm install
7. Press Enter              ← Command captured! ✓
8. Type: npm run build
9. Press Enter              ← Command captured! ✓
10. Go to "🎬 Recorder" tab
11. Click "⏹ Stop Recording"
12. Review and edit commands
13. Name it "Deploy Setup" and save

✅ Result: Recording saved with 3 commands!
                </pre>
                
                <h3>✅ Method 2: Using Command Buttons</h3>
                <pre>
1. Go to "Command Buttons" tab
2. Click "+ Add Button" to create commands:
   • Name: "Pull Code" → Command: git pull
   • Name: "Install Deps" → Command: npm install
   • Name: "Build" → Command: npm run build

3. Go to "🎬 Recorder" tab
4. Click "⏺ Start Recording"
5. Go back to "Command Buttons" tab
6. Click "Pull Code" button       ← Captured! ✓
7. Click "Install Deps" button    ← Captured! ✓
8. Click "Build" button          ← Captured! ✓
9. Go to "🎬 Recorder" tab
10. Click "⏹ Stop Recording"
11. Name and save

✅ Result: Recording saved with 3 commands!
                </pre>

                <div class="tip">
                    <strong>💡 Mix & Match:</strong> You can combine both methods! Type some commands,
                    click some buttons - all will be recorded.
                </div>
            """,
            
            "Alternative: Using Command Book": """
                <h3>Recording from Command Book</h3>
                <ol>
                    <li>Go to <strong>📚 Book</strong> tab</li>
                    <li>Find or add commands you want to record</li>
                    <li>Go to <strong>🎬 Recorder</strong> tab</li>
                    <li>Click <strong>⏺ Start Recording</strong></li>
                    <li>Go back to <strong>📚 Book</strong> tab</li>
                    <li>Double-click commands to execute them</li>
                    <li>Return to <strong>🎬 Recorder</strong> tab</li>
                    <li>Click <strong>⏹ Stop Recording</strong></li>
                </ol>
                
                <div class="tip">
                    <strong>💡 Pro Tip:</strong> The Command Book has hundreds of pre-built commands. 
                    Use it to quickly build recordings without typing!
                </div>
            """,
            
            "Best Practices": """
                <h3>Do's</h3>
                <ul>
                    <li>✅ Use descriptive names for recordings</li>
                    <li>✅ Add descriptions to explain what the recording does</li>
                    <li>✅ Test recordings in safe environments first</li>
                    <li>✅ Keep recordings focused on single tasks</li>
                    <li>✅ Export important recordings as backups</li>
                    <li>✅ Review and edit commands before saving recordings</li>
                    <li>✅ Press Enter after typing each command to capture it</li>
                </ul>
                
                <h3>Don'ts</h3>
                <ul>
                    <li>❌ Don't record commands requiring user input</li>
                    <li>❌ Don't record destructive commands without caution</li>
                    <li>❌ Don't record commands needing decision-making</li>
                    <li>❌ Avoid very long sequences - break them up</li>
                    <li>❌ Don't forget to press Enter to capture typed commands</li>
                </ul>
            """,
            
            "Troubleshooting": """
                <h3>"No Commands Recorded" Error</h3>
                <p><strong>Cause:</strong> Recording was stopped before any commands were executed.</p>
                <p><strong>Solution:</strong></p>
                <ol>
                    <li>Click "⏺ Start Recording"</li>
                    <li>Type commands in terminal and press Enter (or use buttons)</li>
                    <li>Wait for each command to appear in the terminal</li>
                    <li>Click "⏹ Stop Recording"</li>
                </ol>

                <h3>Commands Not Being Captured</h3>
                <p>Make sure you press <strong>Enter</strong> after typing each command.
                Commands are captured when you press Enter, not while typing.</p>

                <h3>Recording Won't Play</h3>
                <ul>
                    <li>Ensure no other recording is currently playing</li>
                    <li>Check that recording has commands in it</li>
                    <li>Verify terminal tab is active</li>
                </ul>
                
                <h3>Commands Executing Too Fast/Slow</h3>
                <p>Commands execute with a fixed 1-second delay. This is intentional to allow 
                each command to complete.</p>
            """,
            
            "Example Recordings": """
                <h3>Development Setup</h3>
                <pre>
Name: "Setup Dev Environment"
Commands:
  cd ~/projects/myapp
  git pull
  npm install
  npm run build
  npm start
                </pre>
                
                <h3>Database Backup</h3>
                <pre>
Name: "Daily DB Backup"
Commands:
  cd /var/backups
  pg_dump mydb > backup.sql
  gzip backup.sql
  ls -lh backup.sql.gz
                </pre>
                
                <h3>Deployment</h3>
                <pre>
Name: "Deploy to Production"
Commands:
  cd /app
  git checkout main
  git pull origin main
  npm run build
  pm2 restart app
  pm2 logs --lines 20
                </pre>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "🎬 Session Recorder")
    
    def add_troubleshooting_tab(self):
        """Troubleshooting guide"""
        sections = {
            "Application Won't Start": """
                <h3>Check Python Version</h3>
                <pre>python --version</pre>
                <p>Ensure Python 3.7 or higher is installed.</p>
                
                <h3>Verify Dependencies</h3>
                <pre>pip list | grep PyQt5</pre>
                <p>Make sure PyQt5 and pyte are installed.</p>
                
                <h3>Reinstall Dependencies</h3>
                <pre>pip install -r requirements.txt --force-reinstall</pre>
            """,
            
            "Commands Not Executing": """
                <ul>
                    <li><strong>Check Terminal:</strong> Ensure a terminal tab is selected</li>
                    <li><strong>Verify Command:</strong> Test the command in a regular terminal first</li>
                    <li><strong>Check Permissions:</strong> Ensure you have necessary permissions</li>
                    <li><strong>View Output:</strong> Look for error messages in the terminal</li>
                </ul>
            """,
            
            "Terminal Display Issues": """
                <h3>Text Not Visible</h3>
                <ul>
                    <li>Check color settings in Preferences</li>
                    <li>Ensure foreground and background colors contrast</li>
                    <li>Try resetting colors to defaults</li>
                </ul>
                
                <h3>Font Too Small/Large</h3>
                <ul>
                    <li>Use Zoom In/Out shortcuts: <code>Cmd/Ctrl + Plus/Minus</code></li>
                    <li>Adjust font size in Preferences</li>
                    <li>Reset to default: <code>Ctrl + 0</code></li>
                </ul>
            """,
            
            "Interactive Apps Not Working": """
                <p>Terminal Browser supports htop, vim, nano, and other ncurses applications. 
                If they're not working properly:</p>
                
                <ul>
                    <li>Ensure <code>pyte</code> is installed: <code>pip install pyte</code></li>
                    <li>Check that the app works in a regular terminal</li>
                    <li>Try resizing the terminal window</li>
                    <li>Restart the terminal tab</li>
                </ul>
            """,
            
            "File Attachments Not Working": """
                <ul>
                    <li><strong>Check Path:</strong> Ensure file exists at the specified path</li>
                    <li><strong>Permissions:</strong> Verify you have read permissions</li>
                    <li><strong>Environment Variable:</strong> Use the correct variable name (uppercase, underscores)</li>
                    <li><strong>Test:</strong> Try <code>echo $VARIABLE_NAME</code> to verify</li>
                </ul>
            """,
            
            "Performance Issues": """
                <h3>Slow Performance</h3>
                <ul>
                    <li>Close unused terminal tabs and groups</li>
                    <li>Clear terminal output regularly (use Clear button)</li>
                    <li>Reduce font size if necessary</li>
                    <li>Close other resource-intensive applications</li>
                </ul>
                
                <h3>High Memory Usage</h3>
                <ul>
                    <li>Terminal Browser caches terminal sessions for quick switching</li>
                    <li>Consider closing groups you're not actively using</li>
                    <li>Restart the application periodically</li>
                </ul>
            """,
            
            "Settings Not Saving": """
                <h3>Check Settings Location</h3>
                <ul>
                    <li><strong>macOS:</strong> ~/Library/Preferences/com.TerminalBrowser.plist</li>
                    <li><strong>Linux:</strong> ~/.config/TerminalBrowser/</li>
                    <li><strong>Windows:</strong> Registry (HKEY_CURRENT_USER\\Software\\TerminalBrowser)</li>
                </ul>
                
                <h3>Reset Settings</h3>
                <p>Delete the settings file/directory and restart the application to reset to defaults.</p>
            """
        }
        
        tab = self.create_navigable_tab(sections)
        self.tab_widget.addTab(tab, "🔧 Troubleshooting")
    
    def add_about_tab(self):
        """About tab"""
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        
        html = """
        <html>
        <head>
            <style>
                body { 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    line-height: 1.8; 
                    padding: 20px;
                }
                h1 { color: #4CAF50; text-align: center; margin-bottom: 30px; }
                h2 { color: #64B5F6; margin-top: 25px; border-bottom: 2px solid #64B5F6; padding-bottom: 5px; }
                .center { text-align: center; margin: 20px 0; }
                .version { font-size: 18px; color: #FFB74D; font-weight: bold; }
                ul { margin-left: 20px; }
                li { margin: 8px 0; }
                .highlight { background-color: #2d3a4d; padding: 15px; border-radius: 5px; margin: 15px 0; }
            </style>
        </head>
        <body>
            <h1>🚀 Terminal Browser</h1>
            
            <div class="center">
                <p class="version">Version 1.0.0</p>
                <p>A powerful desktop terminal application with browser-like tabs,<br>
                terminal groups, and command execution management.</p>
            </div>
            
            <h2>👨‍💻 Developer</h2>
            <div class="highlight" style="background-color: #2d3a4d; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <p style="font-size: 18px; font-weight: bold; color: #4CAF50; margin-bottom: 15px;">Shreevathsav Rao</p>
                <p style="margin: 10px 0;"><strong>📞 Phone:</strong> <a href="tel:8105142706" style="color: #64B5F6; text-decoration: none;">8105142706</a></p>
                <p style="margin: 10px 0;"><strong>📧 Email:</strong> <a href="mailto:shreevathsavraokh@gmail.com" style="color: #64B5F6; text-decoration: none;">shreevathsavraokh@gmail.com</a></p>
            </div>
            
            <h2>✨ Key Features</h2>
            <ul>
                <li><strong>Browser-Like Tabs:</strong> Manage multiple terminal sessions with ease</li>
                <li><strong>Terminal Groups:</strong> Organize terminals by project or task</li>
                <li><strong>Command Buttons:</strong> One-click execution of frequently used commands</li>
                <li><strong>Command Book:</strong> Library of pre-built and custom commands</li>
                <li><strong>Command Queue:</strong> Batch execution with FIFO processing</li>
                <li><strong>Session Recording:</strong> Record and replay command sequences automatically</li>
                <li><strong>File Attachments:</strong> Easy access to keys, configs, and scripts</li>
                <li><strong>Full Terminal Emulation:</strong> Support for vim, htop, nano, and more</li>
                <li><strong>Customizable:</strong> Fonts, colors, and preferences</li>
                <li><strong>Persistent State:</strong> Everything saves between sessions</li>
            </ul>
            
            <h2>🛠️ Built With</h2>
            <ul>
                <li><strong>PyQt5:</strong> Modern GUI framework</li>
                <li><strong>pyte:</strong> Terminal emulator in Python</li>
                <li><strong>Python 3.7+:</strong> Powerful and flexible</li>
            </ul>
            
            <h2>📚 Documentation</h2>
            <div class="highlight">
                <p>Explore the tabs above for comprehensive guides on:</p>
                <ul>
                    <li>Getting Started & Installation</li>
                    <li>Features & Capabilities</li>
                    <li>Keyboard Shortcuts</li>
                    <li>Terminal Groups Management</li>
                    <li>Command Buttons & Queue</li>
                    <li>Session Recording & Playback</li>
                    <li>Troubleshooting & Support</li>
                </ul>
            </div>
            
            <h2>💡 Use Cases</h2>
            <ul>
                <li><strong>DevOps:</strong> Manage multiple servers and deployments</li>
                <li><strong>Development:</strong> Run builds, tests, and development servers</li>
                <li><strong>System Administration:</strong> Monitor and manage systems</li>
                <li><strong>Database Management:</strong> Connect to multiple databases</li>
            </ul>
            
            <h2>📄 License</h2>
            <p>This project is open source and available under the MIT License.</p>
            
            <div class="center" style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #555;">
                <p><strong>© 2025 Terminal Browser</strong></p>
                <p>Created for efficient terminal workflow management</p>
            </div>
        </body>
        </html>
        """
        
        content.setHtml(html)
        self.tab_widget.addTab(content, "ℹ️ About")

