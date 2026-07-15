"""Top tab bar for terminals (browser-like)"""

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QTabBar,
                             QPushButton, QHBoxLayout, QInputDialog, QMenu, QAction,
                             QDialog, QLabel, QComboBox, QLineEdit, QFormLayout,
                             QDialogButtonBox, QListWidget, QListWidgetItem)
from qtpy.QtCore import Qt, Signal, QSize, QTimer, QEvent, QThread
from qtpy.QtGui import QIcon, QPixmap, QPainter, QColor
from ui.pyte_terminal_widget import PyteTerminalWidget as TerminalWidget
import os

# Module-level cache shared across all dialogs opened in the session
_shell_cache = []  # List of "name (path)" strings
_shell_cache_ready = False


class ShellScanWorker(QThread):
    """Background thread that scans for available shells once at startup."""
    finished = Signal(list)  # emits list of "name (path)" strings

    def run(self):
        results = NewTerminalDialog.detect_shells_static()
        global _shell_cache, _shell_cache_ready
        _shell_cache = results
        _shell_cache_ready = True
        self.finished.emit(results)


class RenameableTabBar(QTabBar):
    """Custom tab bar that allows renaming tabs with right-click and supports drag-and-drop"""
    
    def __init__(self, parent=None, terminal_tabs_widget=None):
        super().__init__(parent)
        self.terminal_tabs_widget = terminal_tabs_widget
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # Explicitly enable movable tabs
        self.setMovable(True)

    def tabSizeHint(self, index):
        """Keep browser tabs a fixed width.

        A browser tab's label changes every second (site name ⇄ live u.../d…
        transfer rate) and its favicon pops in mid-load. If the tab resized to
        fit, the tab bar's total width would cross the overflow threshold and
        make the scroll arrows flicker on/off. A fixed width avoids that.
        """
        hint = super().tabSizeHint(index)
        try:
            ttw = self.terminal_tabs_widget
            if ttw is not None:
                widget = ttw.tab_widget.widget(index)
                from ui.browser_widget import BrowserWidget
                if isinstance(widget, BrowserWidget):
                    hint.setWidth(170)
        except Exception:
            pass
        return hint
        
    def mousePressEvent(self, event):
        """Handle right-click to show context menu, allow left-click drag"""
        if event.button() == Qt.RightButton:
            index = self.tabAt(event.pos())
            if index >= 0:
                # Use stored reference to TerminalTabs widget
                if self.terminal_tabs_widget and hasattr(self.terminal_tabs_widget, 'show_tab_context_menu'):
                    self.terminal_tabs_widget.show_tab_context_menu(index, event.globalPos())
                return
        # Always call super() to allow drag functionality to work
        super().mousePressEvent(event)


class TabMinimapStrip(QWidget):
    """Slim horizontal strip above the tab bar: one icon per tab.

    Works like the editor minimap — each tab is shown as a small favicon
    (browser) or a logo (git / terminal). Clicking or dragging across the strip
    selects that tab (which auto-scrolls the tab bar to it). Replaces the old
    ◀ / ▶ end scroll buttons.
    """

    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self._tabs = tab_widget
        self._cells = []            # list of (index, QRect)
        self._sig = None            # last rendered state signature
        self.setFixedHeight(20)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def refresh(self):
        # Only repaint when the tab set / current index / icons actually
        # changed, so unrelated app activity doesn't make the strip flicker.
        parts = [str(self._tabs.count()), str(self._tabs.currentIndex())]
        for i in range(self._tabs.count()):
            ic = self._tabs.tabIcon(i)
            parts.append(str(ic.cacheKey()) if ic is not None else '0')
        sig = '|'.join(parts)
        if sig == self._sig:
            return
        self._sig = sig
        self.update()


    def _pixmap_for(self, index, size):
        """Favicon / logo pixmap for a tab, or None to draw a text glyph."""
        icon = self._tabs.tabIcon(index)
        if icon is not None and not icon.isNull():
            pm = icon.pixmap(size, size)
            if pm is not None and not pm.isNull():
                return pm
        return None

    def _glyph_for(self, index):
        """Fallback glyph + colour when a tab has no usable icon."""
        widget = self._tabs.widget(index)
        try:
            from ui.git_panel import GitPanel
            from ui.browser_widget import BrowserWidget
        except Exception:
            GitPanel = BrowserWidget = ()
        if GitPanel and isinstance(widget, GitPanel):
            return "⎇", QColor('#f0803c')
        if BrowserWidget and isinstance(widget, BrowserWidget):
            return "🌐", QColor('#6cb2ff')
        return "❯", QColor('#4ec9b0')     # terminal

    def paintEvent(self, event):
        from qtpy.QtCore import QRect
        from qtpy.QtGui import QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#232323'))
        n = self._tabs.count()
        self._cells = []
        if n == 0:
            p.end()
            return
        cur = self._tabs.currentIndex()
        cell = max(14, min(30, (self.width() - 4) // n))
        icon_sz = min(14, cell - 2)
        cy = self.height() // 2
        x = 2
        gfont = QFont()
        gfont.setPixelSize(11)
        for i in range(n):
            rect = QRect(x, 1, cell, self.height() - 2)
            self._cells.append((i, rect))
            if i == cur:
                p.fillRect(rect, QColor('#0d47a1'))
                p.fillRect(QRect(rect.x(), rect.bottom() - 1, rect.width(), 2),
                           QColor('#4d9bff'))
            pm = self._pixmap_for(i, icon_sz)
            if pm is not None:
                scaled = pm.scaled(icon_sz, icon_sz, Qt.KeepAspectRatio,
                                   Qt.SmoothTransformation)
                p.drawPixmap(rect.center().x() - scaled.width() // 2,
                             cy - scaled.height() // 2, scaled)
            else:
                glyph, color = self._glyph_for(i)
                p.setFont(gfont)
                p.setPen(color)
                p.drawText(rect, Qt.AlignCenter, glyph)
            x += cell
        p.end()

    def _select_at(self, pos):
        for i, rect in self._cells:
            if rect.contains(pos):
                if i != self._tabs.currentIndex():
                    self._tabs.setCurrentIndex(i)
                return

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._select_at(event.pos())

    def mouseMoveEvent(self, event):
        # Drag across the strip to scrub through tabs (minimap-style).
        if event.buttons() & Qt.LeftButton:
            self._select_at(event.pos())

class NewTerminalDialog(QDialog):
    """Dialog to configure a new terminal or tool tab."""

    def __init__(self, parent=None, tab_number=1, cached_shells=None):
        super().__init__(parent)
        self.setWindowTitle("New Tab")
        self.setMinimumWidth(420)
        self._type = 'shell'   # 'shell' or 'tool'
        self._tool = None      # e.g. 'git'
        self._cached_shells = cached_shells  # pre-scanned list from startup
        self._init_ui(tab_number)

    def _init_ui(self, tab_number):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Tab name row
        name_row = QHBoxLayout()
        name_lbl = QLabel("Tab Name:")
        name_lbl.setStyleSheet("color:#cccccc;")
        self.name_input = QLineEdit(f"Tab {tab_number}")
        self.name_input.setStyleSheet(
            "background:#2d2d2d; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:4px;"
        )
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        # Tab switcher: Shells | Tools
        self.type_tabs = QTabWidget()
        self.type_tabs.setStyleSheet("""
            QTabWidget::pane { background:#1e1e1e; border:1px solid #3c3c3c; }
            QTabBar::tab { background:#2d2d2d; color:#888; padding:6px 18px;
                           border:none; margin-right:2px; }
            QTabBar::tab:selected { background:#1e1e1e; color:#cccccc;
                                    border-bottom:2px solid #4ec9b0; }
            QTabBar::tab:hover { background:#3c3c3c; color:#cccccc; }
        """)

        # ── Shells tab ────────────────────────────────────────────────────────
        shells_widget = QWidget()
        sl = QVBoxLayout(shells_widget)
        sl.setContentsMargins(8, 8, 8, 8)
        self.shell_list = QListWidget()
        self.shell_list.setStyleSheet(
            "QListWidget { background:#1e1e1e; color:#cccccc; border:none; }"
            "QListWidget::item:selected { background:#094771; }"
            "QListWidget::item:hover { background:#2a2d2e; }"
        )
        self.shell_list.setSpacing(2)
        available_shells = self._cached_shells if self._cached_shells else self.detect_shells()
        self._populate_shell_list(available_shells)
        self.shell_list.itemDoubleClicked.connect(self._accept_shell)
        sl.addWidget(self.shell_list)
        self.type_tabs.addTab(shells_widget, "🖥  Shells")

        # ── Tools tab ─────────────────────────────────────────────────────────
        tools_widget = QWidget()
        tl = QVBoxLayout(tools_widget)
        tl.setContentsMargins(8, 8, 8, 8)
        self.tool_list = QListWidget()
        self.tool_list.setStyleSheet(
            "QListWidget { background:#1e1e1e; color:#cccccc; border:none; }"
            "QListWidget::item:selected { background:#094771; }"
            "QListWidget::item:hover { background:#2a2d2e; }"
        )
        self.tool_list.setSpacing(2)
        # Each entry: (display text, tool key)
        self._tools = [("⎇  Git", "git"), ("🌐  Browser", "browser"),
                       ("🛰  API Studio", "api")]
        for display, _ in self._tools:
            item = QListWidgetItem(display)
            item.setForeground(QColor("#4ec9b0"))
            self.tool_list.addItem(item)
        if self.tool_list.count():
            self.tool_list.setCurrentRow(0)
        self.tool_list.itemDoubleClicked.connect(self._accept_tool)
        tl.addWidget(self.tool_list)
        self.type_tabs.addTab(tools_widget, "🔧  Tools")

        layout.addWidget(self.type_tabs)

        # Bottom row: [Scan for Shells]  ----stretch----  [Cancel] [OK]
        bottom_row = QHBoxLayout()

        self._scan_btn = QPushButton("⟳  Scan for Shells")
        self._scan_btn.setStyleSheet(
            "QPushButton { background:#2d2d2d; color:#4ec9b0; border:1px solid #555; "
            "border-radius:3px; padding:6px 10px; }"
            "QPushButton:hover { background:#3c3c3c; }"
            "QPushButton:disabled { color:#555; }"
        )
        self._scan_btn.clicked.connect(self._rescan_shells)
        bottom_row.addWidget(self._scan_btn)

        bottom_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; border: none;
                padding: 6px 15px; border-radius: 3px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        bottom_row.addWidget(buttons)

        layout.addLayout(bottom_row)

    def _populate_shell_list(self, shells):
        """Fill the shell list widget and pre-select the user's default shell."""
        self.shell_list.clear()
        for s in shells:
            self.shell_list.addItem(s)
        default_shell = os.environ.get('SHELL', '/bin/bash')
        shell_name = os.path.basename(default_shell)
        matches = self.shell_list.findItems(shell_name, Qt.MatchContains)
        if matches:
            self.shell_list.setCurrentItem(matches[0])
        elif self.shell_list.count():
            self.shell_list.setCurrentRow(0)

    def _rescan_shells(self):
        """Re-scan for shells on demand and refresh the list + global cache."""
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("Scanning…")
        from qtpy.QtWidgets import QApplication
        QApplication.processEvents()

        shells = NewTerminalDialog.detect_shells_static()

        global _shell_cache, _shell_cache_ready
        _shell_cache = shells
        _shell_cache_ready = True

        self._cached_shells = shells
        self._populate_shell_list(shells)
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("⟳  Scan for Shells")

    def _accept_shell(self):
        self._type = 'shell'
        self.accept()

    def _accept_tool(self):
        self._type = 'tool'
        idx = self.tool_list.currentRow()
        self._tool = self._tools[idx][1] if idx >= 0 else None
        self.accept()

    def _on_ok(self):
        if self.type_tabs.currentIndex() == 0:
            self._accept_shell()
        else:
            self._accept_tool()

    @staticmethod
    def detect_shells_static():
        """Detect available shells dynamically — no hardcoded name or path list.

        Sources:
          1. /etc/shells — OS-maintained authoritative registry (trusted as-is).
          2. Every executable in PATH dirs + common extra locations that passes
             `<binary> -c 'exit 42'` within 1 s — the definitive test that something
             is an interactive shell, filtering out ssh, hash, chsh, jshell, etc.
        """
        import subprocess, re

        found = []
        seen_paths = set()
        CANDIDATE_RE = re.compile(
            r'sh$|shell|^fish$|^nu$|^ion$|^xonsh$|^elvish$', re.IGNORECASE
        )

        def is_real_shell(path):
            try:
                r = subprocess.run(
                    [path, '-c', 'exit 42'],
                    timeout=1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return r.returncode == 42
            except (OSError, subprocess.TimeoutExpired):
                return False

        def add(path, verify=False):
            real = os.path.realpath(path)
            if real in seen_paths or not os.access(real, os.X_OK):
                return
            if verify and not is_real_shell(real):
                return
            seen_paths.add(real)
            found.append((os.path.basename(path), real))

        try:
            with open('/etc/shells') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and os.path.isfile(line):
                        add(line)
        except OSError:
            pass

        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        extra_dirs = [
            '/bin', '/usr/bin', '/usr/local/bin',
            '/opt/homebrew/bin', '/opt/local/bin',
            '/usr/pkg/bin', '/snap/bin',
        ]
        for d in list(dict.fromkeys(path_dirs + extra_dirs)):
            if not os.path.isdir(d):
                continue
            try:
                for entry in os.scandir(d):
                    if entry.is_file(follow_symlinks=True) and CANDIDATE_RE.search(entry.name):
                        add(entry.path, verify=True)
            except OSError:
                pass

        if not found:
            found = [('bash', '/bin/bash'), ('sh', '/bin/sh')]

        return [f"{name} ({path})" for name, path in found]

    def detect_shells(self):
        return NewTerminalDialog.detect_shells_static()
    
    def get_data(self):
        """Return dialog data. 'type' is 'shell' or 'tool'."""
        name = self.name_input.text()
        if self._type == 'tool':
            return {'name': name, 'type': 'tool', 'tool': self._tool, 'shell': None}
        # Shell path extracted from "name (path)" format
        item = self.shell_list.currentItem()
        shell_text = item.text() if item else '/bin/bash'
        if '(' in shell_text and ')' in shell_text:
            shell_path = shell_text.split('(')[1].rstrip(')')
        else:
            shell_path = '/bin/bash'
        return {'name': name, 'type': 'shell', 'shell': shell_path, 'tool': None}

class TerminalTabs(QWidget):
    """Browser-like terminal tabs"""

    # Emitted when any browser tab in a group starts/stops playing audio.
    group_audio_changed = Signal(str, bool)  # group_name, playing

    def __init__(self):
        super().__init__()
        self.tab_counter = 0
        self.current_group = None
        self.tabs_per_group = {}  # Store tabs per group: {group_name: [tab_data]}
        self.terminal_widgets_cache = {}  # Cache terminal widgets: {group_name: [(name, shell, widget)]}
        self._active_tab_per_group = {}  # Remember last-selected tab index per group
        self.is_switching = False  # Flag to track if a group switch is in progress
        self.tabs_changed_callback = None  # Callback for when tabs structure changes
        self.init_ui()
        self._start_shell_scan()
    
    def _start_shell_scan(self):
        """Kick off a background shell scan at startup so the cache is warm."""
        global _shell_cache_ready
        if _shell_cache_ready:
            return  # already scanned (e.g. multiple TerminalTabs instances)
        self._shell_scan_worker = ShellScanWorker()
        self._shell_scan_worker.start()

    def create_close_icon(self):
        """Create a custom close icon"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw X
        painter.setPen(QColor(200, 200, 200))
        painter.drawLine(4, 4, 12, 12)
        painter.drawLine(12, 4, 4, 12)
        
        painter.end()
        return QIcon(pixmap)
        
    def init_ui(self):
        """Initialize the UI"""
        from qtpy.QtWidgets import QSizePolicy
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create custom tab bar container
        tab_bar_container = QWidget()
        tab_bar_container.setStyleSheet("background-color: #2b2b2b;")
        tab_bar_container.setFixedHeight(32)
        tab_bar_layout = QHBoxLayout(tab_bar_container)
        tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        tab_bar_layout.setSpacing(0)
        
        # Left navigation button
        self.left_nav_btn = QPushButton("◀")
        self.left_nav_btn.setFixedWidth(35)
        self.left_nav_btn.setFixedHeight(28)
        self.left_nav_btn.setEnabled(False)
        self.left_nav_btn.clicked.connect(self.scroll_tabs_left)
        self.left_nav_btn.setMouseTracking(True)
        self.left_nav_btn.installEventFilter(self)
        self.left_nav_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: none;
                border-right: 1px solid #555;
                padding: 2px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #424242;
            }
            QPushButton:pressed:enabled {
                background-color: #555;
            }
            QPushButton:disabled {
                background-color: #1e1e1e;
                color: #666;
            }
        """)
        tab_bar_layout.addWidget(self.left_nav_btn)
        
        # Tab widget with custom styling
        self.tab_widget = QTabWidget()
        
        # Set custom tab bar FIRST before setting properties
        custom_tab_bar = RenameableTabBar(terminal_tabs_widget=self)
        self.tab_widget.setTabBar(custom_tab_bar)
        
        # Now set tab widget properties (after custom tab bar is installed)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        
        # Enable Qt's built-in scroll buttons but we'll hide them visually
        # This allows Qt to manage tab scrolling natively when currentIndex changes
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setElideMode(Qt.ElideNone)
        
        # Set icon size for close buttons
        custom_tab_bar.setIconSize(QSize(16, 16))
        
        # Make tab bar expand to fill available space
        custom_tab_bar.setExpanding(False)  # We'll control spacing ourselves
        custom_tab_bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        
        # Install event filter to detect tab bar resizes
        custom_tab_bar.installEventFilter(self)
        
        # Style the tabs
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #1e1e1e;
                top: -32px;
                margin-top: 0px;
                padding-top: 0px;
            }
            QTabWidget::tab-bar {
                alignment: left;
                height: 32px;
            }
            QTabBar {
                background-color: transparent;
                margin-left: 8px;
                margin-top: 0px;
                margin-bottom: 0px;
                height: 32px;
                max-height: 32px;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 6px 25px 6px 10px;
                margin-right: 2px;
                margin-left: 2px;
                margin-top: 0px;
                margin-bottom: 0px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                min-width: 80px;
                max-width: 200px;
            }
            QTabBar::tab:first {
                margin-left: 0px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: 2px solid #0d47a1;
            }
            QTabBar::tab:hover {
                background-color: #424242;
            }
            QTabBar::close-button {
                subcontrol-position: right;
                subcontrol-origin: padding;
                margin: 4px 6px 4px 4px;
                image: none;
                width: 16px;
                height: 16px;
                border: none;
            }
            QTabBar::close-button:hover {
                background-color: #f44336;
                border-radius: 2px;
            }
            /* Completely hide Qt's default scroll buttons */
            QTabBar::scroller {
                width: 0px;
                height: 0px;
            }
            QTabBar QToolButton {
                background: transparent;
                border: none;
                width: 0px;
                height: 0px;
                max-width: 0px;
                max-height: 0px;
                min-width: 0px;
                min-height: 0px;
            }
            QTabBar QToolButton::right-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QTabBar QToolButton::left-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QTabBar QToolButton:disabled {
                width: 0px;
                height: 0px;
            }
        """)
        
        # Hide any Qt default scroll buttons that might appear
        # This is done by finding all QToolButton children and hiding them
        QTimer.singleShot(0, lambda: self.hide_qt_scroll_buttons())
        
        # Store reference to tab bar for later use
        self.custom_tab_bar = custom_tab_bar
        
        # Add the tab bar to layout (after left nav button, position 1)
        tab_bar_layout.addWidget(self.tab_widget.tabBar())
        
        # Add "+" button (appears right after tabs)
        self.add_tab_btn = QPushButton("+")
        self.add_tab_btn.setFixedWidth(28)
        self.add_tab_btn.setFixedHeight(28)
        self.add_tab_btn.clicked.connect(lambda: self.add_tab())
        self.add_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: none;
                border-left: 1px solid #555;
                padding: 2px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #424242;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        tab_bar_layout.addWidget(self.add_tab_btn)
        
        # Add flexible space between + and ▶ (shrinks as tabs are added)
        tab_bar_layout.addStretch(1)
        
        # Right navigation button
        self.right_nav_btn = QPushButton("▶")
        self.right_nav_btn.setFixedWidth(35)
        self.right_nav_btn.setFixedHeight(28)
        self.right_nav_btn.setEnabled(False)
        self.right_nav_btn.clicked.connect(self.scroll_tabs_right)
        self.right_nav_btn.setMouseTracking(True)
        self.right_nav_btn.installEventFilter(self)
        self.right_nav_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: none;
                border-left: 1px solid #555;
                padding: 2px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #424242;
            }
            QPushButton:pressed:enabled {
                background-color: #555;
            }
            QPushButton:disabled {
                background-color: #1e1e1e;
                color: #666;
            }
        """)
        tab_bar_layout.addWidget(self.right_nav_btn)
        # The old ◀ / ▶ end scroll buttons are replaced by the minimap strip.
        self.left_nav_btn.hide()
        self.right_nav_btn.hide()

        # Minimap-style overview strip above the tabs: an icon per tab
        # (favicon for browsers, logo for git / terminal). Click or drag to
        # jump to a tab.
        self.tab_minimap = TabMinimapStrip(self.tab_widget)
        main_layout.addWidget(self.tab_minimap)

        # Add the custom tab bar container to main layout
        main_layout.addWidget(tab_bar_container)
        
        # Add the tab widget's content pane (just the pane, tab bar is already positioned above)
        self.tab_widget.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.tab_widget)
        
        # Timer to update navigation buttons
        self.nav_update_timer = QTimer()
        self.nav_update_timer.setSingleShot(True)
        self.nav_update_timer.timeout.connect(self.update_navigation_buttons)
        
        # Connect tab changes to update navigation
        self.tab_widget.currentChanged.connect(lambda: self.nav_update_timer.start(100))
        self.tab_widget.currentChanged.connect(self._reapply_active_browser_route)
        self.tab_widget.tabBar().tabMoved.connect(self.on_tab_moved)

    def _reapply_active_browser_route(self, *args):
        """Make the active browser tab's own network route the live one.

        Qt's proxy is app-wide, so switching to a tab must re-assert that
        tab's route — otherwise a tab that never enabled Tor/VPN would keep
        using whatever route another tab set (e.g. reaching a Tor-only site
        without Tor). Non-browser tabs leave the route untouched.
        """
        try:
            widget = self.tab_widget.currentWidget()
            mgr = getattr(widget, 'privacy', None)
            if mgr is not None:
                mgr.reapply()
        except Exception:
            pass
    
    def hide_qt_scroll_buttons(self):
        """Hide Qt's default scroll buttons completely"""
        from qtpy.QtWidgets import QToolButton
        
        # Find all QToolButton children of the tab bar and hide them
        tab_bar = self.tab_widget.tabBar()
        for child in tab_bar.findChildren(QToolButton):
            child.hide()
            child.setFixedSize(0, 0)
            child.setEnabled(False)
    
    def on_tab_moved(self, from_index, to_index):
        """Handle tab reordering - sync internal data structures"""
        # Update navigation buttons
        self.nav_update_timer.start(100)
        
        # Sync the tabs_per_group and terminal_widgets_cache to match new order
        if self.current_group:
            # Get the current order from the visible tabs
            tabs_info = []
            widgets_cache = []
            
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if widget:
                    tab_text = self.tab_widget.tabText(i)

                    # Preserve tool tabs (git / browser) instead of flattening to terminals
                    from ui.git_panel import GitPanel
                    from ui.browser_widget import BrowserWidget
                    if isinstance(widget, GitPanel):
                        clean = tab_text.strip().lstrip("⎇").strip()
                        tabs_info.append({'name': clean or 'Git', 'tab_type': 'git'})
                        widgets_cache.append((clean or 'Git', None, widget))
                        continue
                    if isinstance(widget, BrowserWidget):
                        if getattr(widget, 'is_api_studio', False):
                            clean = tab_text.strip().lstrip("🛰").strip()
                            tabs_info.append({'name': clean or 'API Studio',
                                              'tab_type': 'api'})
                            widgets_cache.append((tab_text, None, widget))
                            continue
                        clean = tab_text.strip().lstrip("🌐").strip()
                        tabs_info.append({
                            'name': clean or 'Browser',
                            'tab_type': 'browser',
                            'url': widget.current_url(),
                        })
                        widgets_cache.append((tab_text, None, widget))
                        continue

                    shell = widget.shell if hasattr(widget, 'shell') else '/bin/bash'
                    
                    # Strip shell indicator from name
                    base_name = tab_text
                    if '[' in tab_text and ']' in tab_text:
                        base_name = tab_text.rsplit('[', 1)[0].strip()
                    
                    tabs_info.append({
                        'name': base_name,
                        'shell': shell
                    })
                    widgets_cache.append((base_name, shell, widget))
            
            # Update the data structures with the new order
            self.tabs_per_group[self.current_group] = tabs_info
            self.terminal_widgets_cache[self.current_group] = widgets_cache
            
            # Notify about tab structure change
            if self.tabs_changed_callback:
                self.tabs_changed_callback()
    
    def showEvent(self, event):
        """Update navigation buttons when widget is shown"""
        super().showEvent(event)
        # Force tab bar geometry update to ensure proper spacing at startup
        if hasattr(self, 'tab_widget') and self.tab_widget.count() > 0:
            QTimer.singleShot(50, lambda: self.tab_widget.tabBar().updateGeometry())
            QTimer.singleShot(100, lambda: self.tab_widget.tabBar().update())
        # Trigger navigation button update after the widget is fully shown
        if hasattr(self, 'update_navigation_buttons'):
            QTimer.singleShot(200, self.update_navigation_buttons)
        # Hide Qt scroll buttons
        QTimer.singleShot(50, self.hide_qt_scroll_buttons)
    
    def resizeEvent(self, event):
        """Update navigation buttons when widget is resized"""
        super().resizeEvent(event)
        if hasattr(self, 'nav_update_timer'):
            self.nav_update_timer.start(150)
        # Ensure Qt scroll buttons stay hidden
        if hasattr(self, 'hide_qt_scroll_buttons'):
            QTimer.singleShot(100, self.hide_qt_scroll_buttons)
        
    def _open_tool_tab(self, name: str, tool: str, url: str = None):
        """Open a tool (non-terminal) as a tab in the tab widget."""
        if tool == 'git':
            from ui.git_panel import GitPanel
            # Reuse existing git tab if already open
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i).startswith("⎇"):
                    self.tab_widget.setCurrentIndex(i)
                    return self.tab_widget.widget(i)
            git_panel = GitPanel()
            idx = self.tab_widget.addTab(git_panel, f"⎇  {name}")
            self.tab_widget.setCurrentIndex(idx)
            self.tab_widget.tabBar().setTabButton(idx, QTabBar.RightSide, self.create_close_button())
            git_panel.refresh_all()
            return git_panel
        if tool == 'browser':
            from ui.browser_widget import BrowserWidget
            browser = BrowserWidget()
            idx = self.tab_widget.addTab(browser, name)
            self.tab_widget.setTabIcon(idx, self._make_globe_icon())
            self.tab_widget.setCurrentIndex(idx)
            self.tab_widget.tabBar().setTabButton(idx, QTabBar.RightSide, self.create_close_button())
            # Let "open link in new tab / window" spawn a sibling browser tab
            # that inherits this tab's VPN/Tor route.
            browser.new_tab_factory = lambda parent=browser: self._new_browser_from(parent)
            # Restore the previously-open page, if provided
            if url:
                browser.navigate_to(url)
            # Show a pulsing "heartbeat" indicator on the tab while audio/video plays
            browser.audioStateChanged.connect(
                lambda playing, b=browser: self._on_browser_audio(b, playing))
            # Tab title tracks the site name / live transfer rate; the tab icon
            # tracks the page favicon (default logo while loading or on error).
            browser.tabLabelChanged.connect(
                lambda text, b=browser: self._on_browser_label(b, text))
            browser.tabFaviconChanged.connect(
                lambda icon, b=browser: self._on_browser_favicon(b, icon))
            # Tint the tab by network route: lavender = Tor, yellow = VPN/proxy.
            if getattr(browser, 'privacy', None) is not None:
                browser.privacy.statusChanged.connect(
                    lambda mode, state, detail, b=browser:
                    self._on_browser_privacy(b, mode, state))
            return browser
        if tool == 'api':
            # Postman-style API Studio: a local JS app served by a stdlib
            # backend, displayed inside an embedded browser view.
            from ui.browser_widget import BrowserWidget
            try:
                from ui.api_studio import ensure_server
                url = ensure_server()
            except Exception as exc:
                print(f"API Studio backend failed to start: {exc}")
                return None
            browser = BrowserWidget()
            browser.is_api_studio = True
            browser.set_chrome_visible(False)
            idx = self.tab_widget.addTab(browser, name or "API Studio")
            self.tab_widget.setTabIcon(idx, self._make_api_icon())
            self.tab_widget.setCurrentIndex(idx)
            self.tab_widget.tabBar().setTabButton(idx, QTabBar.RightSide, self.create_close_button())
            browser.navigate_to(url)
            return browser
        return None

    def _new_browser_from(self, parent):
        """Open a new browser tab that inherits ``parent``'s VPN/Tor route."""
        child = self._open_tool_tab("Browser", 'browser')
        try:
            p_priv = getattr(parent, 'privacy', None)
            c_priv = getattr(child, 'privacy', None)
            if p_priv is not None and c_priv is not None:
                c_priv.inherit_from(p_priv)
        except Exception:
            pass
        return child

    # ── Browser network-privacy tab tint ──────────────────────────────────
    def _on_browser_privacy(self, browser, mode, state):
        """Record a browser tab's active route and recolor its tab."""
        kind = mode if (state == 'on' and mode in ('tor', 'proxy')) else None
        if not hasattr(self, '_privacy_kind'):
            self._privacy_kind = {}
        self._privacy_kind[browser] = kind
        self._apply_tab_privacy(browser)

    def _apply_tab_privacy(self, browser):
        idx = self.tab_widget.indexOf(browser)
        if idx < 0:
            return
        from qtpy.QtGui import QColor
        kind = getattr(self, '_privacy_kind', {}).get(browser)
        colors = {'tor': QColor('#B57EDC'), 'proxy': QColor('#FFD400')}
        self.tab_widget.tabBar().setTabTextColor(
            idx, colors.get(kind, QColor('#e0e0e0')))
        # The favicon owns the tab icon; the route dot is only a fallback.
        self._refresh_browser_icon(browser)

    # ── Browser tab label / favicon ───────────────────────────────────────
    def _on_browser_label(self, browser, text):
        idx = self.tab_widget.indexOf(browser)
        if idx < 0:
            return
        # Skip no-op updates: the net meter fires once a second even when the
        # label is unchanged, and repainting the tab bar each time makes the
        # tabs look like they are "jumping".
        if not hasattr(self, '_browser_label'):
            self._browser_label = {}
        if self._browser_label.get(browser) == text:
            return
        self._browser_label[browser] = text
        self.tab_widget.setTabText(idx, text)

    def _on_browser_favicon(self, browser, icon):
        if not hasattr(self, '_browser_favicon'):
            self._browser_favicon = {}
        self._browser_favicon[browser] = icon
        self._refresh_browser_icon(browser)

    def _refresh_browser_icon(self, browser):
        """Pick the tab icon: audio pulse > favicon > route dot > logo."""
        idx = self.tab_widget.indexOf(browser)
        if idx < 0:
            return
        # The audio pulse animation owns the icon while it runs.
        if hasattr(self, '_audio_pulses') and browser in self._audio_pulses:
            return
        icon = getattr(self, '_browser_favicon', {}).get(browser)
        if icon is not None and not icon.isNull():
            new_icon, sig = icon, 'fav:%s' % icon.cacheKey()
        else:
            kind = getattr(self, '_privacy_kind', {}).get(browser)
            if kind:
                new_icon, sig = self._make_privacy_icon(kind), 'route:%s' % kind
            else:
                new_icon, sig = self._make_globe_icon(), 'globe'
        # Only touch the tab bar / minimap when the icon actually changed, so
        # unrelated updates don't trigger a full re-render.
        if not hasattr(self, '_browser_icon_sig'):
            self._browser_icon_sig = {}
        if self._browser_icon_sig.get(browser) == sig:
            return
        self._browser_icon_sig[browser] = sig
        self.tab_widget.setTabIcon(idx, new_icon)
        if hasattr(self, 'tab_minimap'):
            self.tab_minimap.refresh()

    def _make_globe_icon(self):
        """Default browser tab logo: a small globe."""
        from qtpy.QtGui import QColor, QPixmap, QPainter, QPen
        pm = QPixmap(14, 14)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor('#6cb2ff'))
        pen.setWidthF(1.2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(1, 1, 11, 11)
        p.drawEllipse(4, 1, 5, 11)   # vertical meridian
        p.drawLine(1, 6, 12, 6)       # equator
        p.end()
        return QIcon(pm)

    def _make_api_icon(self):
        """API Studio tab logo: a small orbiting-satellite glyph."""
        from qtpy.QtGui import QColor, QPixmap, QPainter, QPen
        pm = QPixmap(14, 14)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        # Orbit ring
        pen = QPen(QColor('#4ec9b0'))
        pen.setWidthF(1.1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(1, 3, 12, 8)
        # Central node
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#4ec9b0'))
        p.drawEllipse(5, 5, 4, 4)
        # Orbiting satellite dot
        p.setBrush(QColor('#6cb2ff'))
        p.drawEllipse(11, 5, 3, 3)
        p.end()
        return QIcon(pm)

    def _make_privacy_icon(self, kind):
        """Return a small filled dot QIcon (lavender=Tor, yellow=VPN)."""
        from qtpy.QtGui import QColor, QPixmap, QPainter
        color = {'tor': QColor('#B57EDC'), 'proxy': QColor('#FFD400')}.get(kind)
        if color is None:
            return QIcon()
        pm = QPixmap(12, 12)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(1, 1, 10, 10)
        p.end()
        return QIcon(pm)

    # ── Browser audio "heartbeat" indicator ───────────────────────────────
    def _on_browser_audio(self, browser, playing):
        """Start/stop the pulsing tab indicator when a browser tab plays sound."""
        if playing:
            self._start_audio_pulse(browser)
        else:
            self._stop_audio_pulse(browser)
        # Track for the per-group indicator too
        if not hasattr(self, '_audible_browsers'):
            self._audible_browsers = set()
        if playing:
            self._audible_browsers.add(browser)
        else:
            self._audible_browsers.discard(browser)
        self._recompute_group_audio()

    def _group_of_browser(self, browser):
        """Return the group name that owns the given browser widget."""
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) is browser:
                return self.current_group
        for group, cache in self.terminal_widgets_cache.items():
            for _, _, w in cache:
                if w is browser:
                    return group
        return self.current_group

    def _recompute_group_audio(self):
        """Emit group_audio_changed for groups whose audio state changed."""
        if not hasattr(self, '_audio_groups'):
            self._audio_groups = set()
        active = set()
        for b in list(getattr(self, '_audible_browsers', ())):
            g = self._group_of_browser(b)
            if g:
                active.add(g)
        for g in active - self._audio_groups:
            self.group_audio_changed.emit(g, True)
        for g in self._audio_groups - active:
            self.group_audio_changed.emit(g, False)
        self._audio_groups = active

    def _cleanup_browser_audio(self, widget):
        """Remove a browser from audio tracking when its tab is closed."""
        self._stop_audio_pulse(widget)
        if hasattr(self, '_audible_browsers'):
            self._audible_browsers.discard(widget)
        self._recompute_group_audio()

    def _start_audio_pulse(self, browser):
        if not hasattr(self, '_audio_pulses'):
            self._audio_pulses = {}
        if browser in self._audio_pulses:
            return
        state = {'phase': 0.0}
        timer = QTimer(self)

        def tick():
            idx = self.tab_widget.indexOf(browser)
            if idx < 0:
                # Tab is off-screen (e.g. another group is showing). Keep the
                # timer alive so the pulse resumes when this group is reopened.
                return
            import math
            state['phase'] += 0.14
            # Heartbeat: intensity oscillates smoothly between 0.35 and 1.0
            intensity = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(state['phase'] * math.pi * 2))
            self.tab_widget.setIconSize(QSize(16, 16))
            self.tab_widget.setTabIcon(idx, self._make_audio_icon(intensity))

        timer.timeout.connect(tick)
        timer.start(60)
        self._audio_pulses[browser] = timer
        tick()

    def _stop_audio_pulse(self, browser):
        if hasattr(self, '_audio_pulses') and browser in self._audio_pulses:
            self._audio_pulses[browser].stop()
            del self._audio_pulses[browser]
        # Restore the favicon / route dot / logo once audio stops.
        self._refresh_browser_icon(browser)

    def _make_audio_icon(self, intensity):
        """Return a pulsing speaker QIcon for the given intensity (0-1)."""
        from ui.browser_widget import make_audio_pulse_pixmap
        return QIcon(make_audio_pulse_pixmap(intensity))

    def add_tab(self, name=None, shell=None, skip_save=False):
        """Add a new terminal tab"""
        if not self.current_group:
            return None  # No group selected
            
        # Handle the case where a boolean is passed from button click
        if isinstance(name, bool):
            name = None
            
        # If called from button, show dialog
        if name is None:
            self.tab_counter += 1
            dialog = NewTerminalDialog(self, self.tab_counter,
                                       cached_shells=_shell_cache if _shell_cache_ready else None)
            if dialog.exec_():
                data = dialog.get_data()
                name = data['name']
                shell = data['shell']
                # Handle tool tabs
                if data.get('type') == 'tool':
                    return self._open_tool_tab(name, data.get('tool'))
            else:
                return None  # User cancelled
        else:
            self.tab_counter += 1

        if name is None:
            name = f"Tab {self.tab_counter}"

        # Create terminal with specified shell and preferences
        from core.preferences_manager import PreferencesManager
        prefs_manager = PreferencesManager()
        terminal = TerminalWidget(shell=shell, prefs_manager=prefs_manager)
        
        # Connect to session recorder for command capture (if available)
        # This will capture commands typed directly in the terminal
        if hasattr(self, 'command_executed_callback'):
            terminal.command_executed.connect(self.command_executed_callback)
        
        # Connect viewport scroll signal to update minimap (if available)
        if hasattr(self, 'viewport_scrolled_callback') and hasattr(terminal, 'viewport_scrolled'):
            terminal.viewport_scrolled.connect(self.viewport_scrolled_callback)
        
        # Add shell indicator to tab name
        shell_name = os.path.basename(shell) if shell else "bash"
        tab_label = f"{name} [{shell_name}]"
        
        index = self.tab_widget.addTab(terminal, tab_label)
        self.tab_widget.setCurrentIndex(index)
        
        # Set close button icon for this tab
        self.tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, self.create_close_button())
        
        # Add to cache
        if self.current_group:
            if self.current_group not in self.terminal_widgets_cache:
                self.terminal_widgets_cache[self.current_group] = []
            self.terminal_widgets_cache[self.current_group].append((name, shell, terminal))
        
        # Save to current group's tabs
        if not skip_save:
            self.save_and_notify_tab_change()
        
        # Update navigation buttons
        self.nav_update_timer.start(100)
        
        return terminal
    
    def create_close_button(self):
        """Create a custom close button for tabs"""
        close_btn = QPushButton("×")
        close_btn.setMaximumSize(16, 16)
        close_btn.setMinimumSize(16, 16)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #f44336;
                color: white;
                border-radius: 2px;
            }
        """)
        close_btn.clicked.connect(lambda: self.close_current_button_tab(close_btn))
        return close_btn
    
    def close_current_button_tab(self, button):
        """Close the tab associated with a close button"""
        # Find which tab this button belongs to
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabBar().tabButton(i, QTabBar.RightSide) == button:
                self.close_tab(i)
                break
    
    def show_tab_context_menu(self, index, position):
        """Show context menu for tab"""
        menu = QMenu(self)
        
        # Add actions
        rename_action = QAction("Rename", self)
        close_action = QAction("Close", self)
        
        rename_action.triggered.connect(lambda: self.rename_tab(index))
        close_action.triggered.connect(lambda: self.close_tab(index))
        
        menu.addAction(rename_action)
        menu.addSeparator()
        menu.addAction(close_action)
        
        # Style the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
            QMenu::item:disabled {
                color: #666;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0px;
            }
        """)
        
        menu.exec_(position)
    
    def close_tab(self, index):
        """Close a tab"""
        widget = self.tab_widget.widget(index)
        
        # Notify about tab closure (for queue cleanup) before actually closing
        if widget and hasattr(self, 'tab_closing_callback'):
            self.tab_closing_callback(widget)
        
        # Check if tab has history file and prompt for cleanup
        if widget and hasattr(widget, 'history_file_path') and widget.history_file_path:
            from qtpy.QtWidgets import QMessageBox
            file_size = widget.get_history_file_size() if hasattr(widget, 'get_history_file_size') else "Unknown"
            
            reply = QMessageBox.question(
                self,
                'Close Tab',
                f'This tab has {file_size} of archived history.\n\n'
                f'Do you want to delete the history file?',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                return  # Don't close tab
            elif reply == QMessageBox.Yes:
                # Delete history file
                if hasattr(widget, 'history_manager') and hasattr(widget, 'tab_id'):
                    widget.history_manager.delete_history_file(widget.tab_id)
        
        # Check if this is the last tab
        is_last_tab = self.tab_widget.count() == 1
        
        self.tab_widget.removeTab(index)
        
        # Clean up browser audio tracking if this was a browser tab
        from ui.browser_widget import BrowserWidget
        if isinstance(widget, BrowserWidget):
            self._cleanup_browser_audio(widget)
        
        # Remove from cache
        if self.current_group and self.current_group in self.terminal_widgets_cache:
            self.terminal_widgets_cache[self.current_group] = [
                (name, shell, w) for name, shell, w in self.terminal_widgets_cache[self.current_group]
                if w != widget
            ]
        
        widget.deleteLater()
        
        # If we just closed the last tab, create a new one with default settings
        if is_last_tab:
            self.tab_counter += 1
            default_shell = os.environ.get('SHELL', '/bin/bash')
            self.add_tab(name=f"Tab {self.tab_counter}", shell=default_shell)
        else:
            # Save updated tabs for current group
            self.save_and_notify_tab_change()
        
        # Update navigation buttons
        self.nav_update_timer.start(100)
    
    def rename_tab(self, index):
        """Rename a tab"""
        if 0 <= index < self.tab_widget.count():
            old_name = self.tab_widget.tabText(index)
            widget = self.tab_widget.widget(index)
            
            # Extract base name without shell indicator
            base_name = old_name
            if '[' in old_name and ']' in old_name:
                base_name = old_name.rsplit('[', 1)[0].strip()
            
            new_name, ok = QInputDialog.getText(self, "Rename Tab", 
                                               "Enter new name:", 
                                               text=base_name)
            if ok and new_name:
                # Re-add shell indicator
                if widget and hasattr(widget, 'shell'):
                    shell_name = os.path.basename(widget.shell)
                    tab_label = f"{new_name} [{shell_name}]"
                    self.tab_widget.setTabText(index, tab_label)
                    
                    # Update in cache
                    if self.current_group and self.current_group in self.terminal_widgets_cache:
                        for i, (name, shell, w) in enumerate(self.terminal_widgets_cache[self.current_group]):
                            if w == widget:
                                self.terminal_widgets_cache[self.current_group][i] = (new_name, shell, w)
                                break
                else:
                    self.tab_widget.setTabText(index, new_name)
                
                # Save updated tabs
                self.save_and_notify_tab_change()
    
    def set_current_tab(self, index):
        """Set the current tab by index"""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
    
    def get_current_terminal(self):
        """Get the current terminal widget"""
        return self.tab_widget.currentWidget()
    
    def get_current_tab_name(self):
        """Get the name of the current tab"""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            return self.tab_widget.tabText(current_index)
        return None
    
    def set_all_terminals_resize_enabled(self, enabled):
        """Enable or disable PTY resizing for all terminal widgets across all groups"""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"set_all_terminals_resize_enabled: Setting resize_enabled={enabled}")
        
        # Set for currently visible widgets
        count = 0
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget and hasattr(widget, 'resize_enabled'):
                widget.resize_enabled = enabled
                count += 1
        
        # Set for cached widgets
        for group_name, cached_widgets in self.terminal_widgets_cache.items():
            for name, shell, widget in cached_widgets:
                if widget and hasattr(widget, 'resize_enabled'):
                    widget.resize_enabled = enabled
                    count += 1
        
        logger.debug(f"set_all_terminals_resize_enabled: Updated {count} widgets")
    
    def is_switching_groups(self):
        """Check if a group switch is currently in progress"""
        return self.is_switching
    
    # ===== Group Management Methods =====
    
    def load_group_tabs(self, group_name):
        """Load tabs for a specific group"""
        # Mark that we're switching groups
        self.is_switching = True
        
        # Save current group's tab info and cache widgets
        if self.current_group:
            self._active_tab_per_group[self.current_group] = self.tab_widget.currentIndex()
            self.save_and_cache_current_group()
        
        # Update current group
        self.current_group = group_name
        
        # Block signals and updates to prevent focus changes and redraws while switching tabs
        self.tab_widget.blockSignals(True)
        self.tab_widget.setUpdatesEnabled(False)
        
        # Store widgets being removed and disable their resize/focus handlers
        widgets_being_removed = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget:
                widgets_being_removed.append(widget)
                # Temporarily disable focus for widgets being removed
                widget.setFocusPolicy(Qt.NoFocus)
                # Disable PTY resize to prevent prompt redraws
                if hasattr(widget, 'resize_enabled'):
                    widget.resize_enabled = False
        
        # Clear all current tabs from display (but don't delete widgets)
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)
        
        # Initialize group if not exists
        if group_name not in self.tabs_per_group:
            self.tabs_per_group[group_name] = []
            self.terminal_widgets_cache[group_name] = []
            self.add_default_tabs_for_group(group_name)
        
        # Check if we have cached widgets for this group
        if group_name in self.terminal_widgets_cache and self.terminal_widgets_cache[group_name]:
            # Restore from cache
            for tab_name, shell, terminal_widget in self.terminal_widgets_cache[group_name]:
                # Temporarily disable focus and resize for widgets being added
                terminal_widget.setFocusPolicy(Qt.NoFocus)
                if hasattr(terminal_widget, 'resize_enabled'):
                    terminal_widget.resize_enabled = False

                from ui.git_panel import GitPanel
                from ui.browser_widget import BrowserWidget
                if isinstance(terminal_widget, (GitPanel, BrowserWidget)):
                    tab_label = tab_name
                else:
                    # Connect to session recorder for command capture (if not already connected)
                    if hasattr(self, 'command_executed_callback'):
                        try:
                            terminal_widget.command_executed.disconnect()
                        except:
                            pass
                        terminal_widget.command_executed.connect(self.command_executed_callback)
                    shell_name = os.path.basename(shell) if shell else "bash"
                    tab_label = f"{tab_name} [{shell_name}]"

                index = self.tab_widget.addTab(terminal_widget, tab_label)
                self.tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, self.create_close_button())
        else:
            # Create new tabs
            for tab_data in self.tabs_per_group[group_name]:
                if tab_data.get('tab_type') == 'git':
                    self._open_tool_tab(tab_data.get('name', 'Git'), 'git')
                elif tab_data.get('tab_type') == 'browser':
                    self._open_tool_tab(tab_data.get('name', 'Browser'), 'browser',
                                        url=tab_data.get('url'))
                elif tab_data.get('tab_type') == 'api':
                    self._open_tool_tab(tab_data.get('name', 'API Studio'), 'api')
                else:
                    self.add_tab(tab_data['name'], tab_data.get('shell', '/bin/bash'), skip_save=True)
        
        # Re-enable signals and updates
        self.tab_widget.blockSignals(False)
        self.tab_widget.setUpdatesEnabled(True)
        
        # Force tab bar geometry update to prevent overlap after group switch
        if self.tab_widget.count() > 0:
            QTimer.singleShot(50, lambda: self.tab_widget.tabBar().updateGeometry())
            QTimer.singleShot(100, lambda: self.tab_widget.tabBar().update())
        
        # Restore focus policy and resize handling for all widgets after a short delay
        # This prevents race conditions with Qt's event processing
        QTimer.singleShot(100, lambda: self.restore_widget_capabilities(widgets_being_removed))
        if group_name in self.terminal_widgets_cache and self.terminal_widgets_cache[group_name]:
            restored_widgets = [w for _, _, w in self.terminal_widgets_cache[group_name]]
            QTimer.singleShot(100, lambda: self.restore_widget_capabilities(restored_widgets))
        
        # Restore the previously-active tab for this group (fallback to first)
        if self.tab_widget.count() > 0:
            target = self._active_tab_per_group.get(group_name, 0)
            if target < 0 or target >= self.tab_widget.count():
                target = 0
            self.tab_widget.setCurrentIndex(target)
        
        # Update navigation buttons after loading group
        self.nav_update_timer.start(200)
    
    def restore_widget_focus_policy(self, widgets):
        """Restore normal focus policy for widgets after group switch"""
        for widget in widgets:
            if widget:
                widget.setFocusPolicy(Qt.StrongFocus)
    
    def restore_widget_capabilities(self, widgets):
        """Restore focus policy and resize handling for widgets after group switch"""
        for widget in widgets:
            if widget:
                # Restore focus policy
                widget.setFocusPolicy(Qt.StrongFocus)
                # Re-enable PTY resize handling
                if hasattr(widget, 'resize_enabled'):
                    widget.resize_enabled = True
        
        # Mark that group switch is complete
        self.is_switching = False
    
    def add_default_tabs_for_group(self, group_name):
        """Add default tabs for a new group"""
        default_shell = os.environ.get('SHELL', '/bin/bash')
        self.tabs_per_group[group_name] = [
            {'name': 'Tab 1', 'shell': default_shell}
        ]
    
    def save_and_cache_current_group(self):
        """Save tab info and cache terminal widgets for current group"""
        if not self.current_group:
            return
        
        tabs_info = []
        widgets_cache = []
        
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget:
                tab_text = self.tab_widget.tabText(i)

                # Detect git panel tabs
                from ui.git_panel import GitPanel
                if isinstance(widget, GitPanel):
                    clean = tab_text.strip().lstrip("⎇").strip()
                    tabs_info.append({'name': clean or 'Git', 'tab_type': 'git'})
                    widgets_cache.append((clean or 'Git', None, widget))
                    continue

                # Detect browser tabs
                from ui.browser_widget import BrowserWidget
                if isinstance(widget, BrowserWidget):
                    if getattr(widget, 'is_api_studio', False):
                        clean = tab_text.strip().lstrip("🛰").strip()
                        tabs_info.append({'name': clean or 'API Studio',
                                          'tab_type': 'api'})
                        widgets_cache.append((tab_text, None, widget))
                        continue
                    clean = tab_text.strip().lstrip("🌐").strip()
                    tabs_info.append({
                        'name': clean or 'Browser',
                        'tab_type': 'browser',
                        'url': widget.current_url(),
                    })
                    widgets_cache.append((tab_text, None, widget))
                    continue

                shell = widget.shell if hasattr(widget, 'shell') else '/bin/bash'
                
                # Strip shell indicator from name
                base_name = tab_text
                if '[' in tab_text and ']' in tab_text:
                    base_name = tab_text.rsplit('[', 1)[0].strip()
                
                # Save tab info
                tabs_info.append({
                    'name': base_name,
                    'shell': shell
                })
                
                # Cache the widget
                widgets_cache.append((base_name, shell, widget))
        
        self.tabs_per_group[self.current_group] = tabs_info
        self.terminal_widgets_cache[self.current_group] = widgets_cache
    
    def save_current_group_tabs(self):
        """Save current tabs to current group storage"""
        if not self.current_group:
            return
        
        tabs_info = []
        widgets_cache = []
        
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget:
                tab_text = self.tab_widget.tabText(i)

                # Detect git panel tabs
                from ui.git_panel import GitPanel
                if isinstance(widget, GitPanel):
                    # Strip the "⎇  " prefix so _open_tool_tab doesn't double-add it
                    clean = tab_text.strip().lstrip("⎇").strip()
                    tabs_info.append({'name': clean or 'Git', 'tab_type': 'git'})
                    widgets_cache.append((clean or 'Git', None, widget))
                    continue

                # Detect browser tabs
                from ui.browser_widget import BrowserWidget
                if isinstance(widget, BrowserWidget):
                    clean = tab_text.strip().lstrip("🌐").strip()
                    tabs_info.append({
                        'name': clean or 'Browser',
                        'tab_type': 'browser',
                        'url': widget.current_url(),
                    })
                    widgets_cache.append((tab_text, None, widget))
                    continue

                shell = widget.shell if hasattr(widget, 'shell') else '/bin/bash'

                # Strip shell indicator from name (e.g., "Tab 1 [zsh]" -> "Tab 1")
                base_name = tab_text
                if '[' in tab_text and ']' in tab_text:
                    base_name = tab_text.rsplit('[', 1)[0].strip()

                tabs_info.append({
                    'name': base_name,
                    'shell': shell
                })
                
                # Also update the widget cache to keep it in sync
                widgets_cache.append((base_name, shell, widget))
        
        self.tabs_per_group[self.current_group] = tabs_info
        self.terminal_widgets_cache[self.current_group] = widgets_cache
    
    def save_and_notify_tab_change(self):
        """Save current group tabs AND notify about the change - use only when tabs are modified"""
        self.save_current_group_tabs()
        if self.tabs_changed_callback:
            self.tabs_changed_callback()
    
    def rename_group(self, old_name, new_name):
        """Handle group rename - update all internal references"""
        # Update cache key
        if old_name in self.terminal_widgets_cache:
            self.terminal_widgets_cache[new_name] = self.terminal_widgets_cache.pop(old_name)
        
        # Update tabs_per_group key
        if old_name in self.tabs_per_group:
            self.tabs_per_group[new_name] = self.tabs_per_group.pop(old_name)
        
        # Update current_group if it's the one being renamed
        if self.current_group == old_name:
            self.current_group = new_name
    
    def delete_group(self, group_name):
        """Handle group deletion - clean up all associated tabs and widgets"""
        # If this is the current group, close all visible tabs
        if self.current_group == group_name:
            # Close all tabs in the current view
            while self.tab_widget.count() > 0:
                widget = self.tab_widget.widget(0)
                self.tab_widget.removeTab(0)
                if widget:
                    widget.deleteLater()
            
            # Clear current group reference
            self.current_group = None
        
        # Clean up cached widgets for this group
        if group_name in self.terminal_widgets_cache:
            # Delete all cached terminal widgets
            for name, shell, widget in self.terminal_widgets_cache[group_name]:
                if widget and widget != self.tab_widget.currentWidget():
                    widget.deleteLater()
            del self.terminal_widgets_cache[group_name]
        
        # Clean up tabs data for this group
        if group_name in self.tabs_per_group:
            del self.tabs_per_group[group_name]
    
    # ===== State Persistence Methods =====
    
    def get_all_tabs_info(self):
        """Get all tabs organized by group for state saving"""
        # Save current group first
        self.save_current_group_tabs()
        return self.tabs_per_group.copy()
    
    def restore_tabs(self, tabs_per_group):
        """Restore all tabs from saved state"""
        self.tabs_per_group = tabs_per_group or {}
        # Tabs will be loaded when groups are selected
    
    def apply_preferences(self, prefs_manager):
        """Apply preferences to all existing terminals"""
        # Update each terminal's viewport highlight color
        for i in range(self.tab_widget.count()):
            terminal = self.tab_widget.widget(i)
            if terminal and hasattr(terminal, 'canvas'):
                if hasattr(terminal.canvas, 'refresh_viewport_highlight_color'):
                    terminal.canvas.refresh_viewport_highlight_color()
    
    # ===== Tab Navigation Methods =====
    
    def eventFilter(self, obj, event):
        """Filter events to detect tab bar resizes and button right-clicks"""
        from qtpy.QtCore import QEvent, Qt
        
        # Safety check: ensure widgets are initialized
        if not hasattr(self, 'tab_widget') or not hasattr(self, 'left_nav_btn') or not hasattr(self, 'right_nav_btn'):
            return super().eventFilter(obj, event)
        
        # Handle tab bar resize events
        if obj == self.tab_widget.tabBar() and event.type() in [QEvent.Resize, QEvent.Show]:
            # Update navigation buttons when tab bar resizes
            if hasattr(self, 'nav_update_timer'):
                self.nav_update_timer.start(100)
        
        # Handle right-click on left navigation button
        elif obj == self.left_nav_btn and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self.show_left_nav_menu(event.pos())
                return True
        
        # Handle right-click on right navigation button
        elif obj == self.right_nav_btn and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self.show_right_nav_menu(event.pos())
                return True
        
        return super().eventFilter(obj, event)
    
    def scroll_tabs_left(self):
        """Scroll tabs to the left (show earlier tabs)"""
        tab_bar = self.tab_widget.tabBar()
        current_index = self.tab_widget.currentIndex()
        
        # Find the first visible tab
        first_visible = self.find_first_visible_tab()
        
        if first_visible > 0:
            # Move to the previous tab - Qt will auto-scroll
            target_index = first_visible - 1
            self.tab_widget.setCurrentIndex(target_index)
        elif current_index > 0:
            # If we can't detect visibility, just move one tab left
            target_index = current_index - 1
            self.tab_widget.setCurrentIndex(target_index)
        
        QTimer.singleShot(150, self.update_navigation_buttons)
    
    def scroll_tabs_right(self):
        """Scroll tabs to the right (show later tabs)"""
        tab_bar = self.tab_widget.tabBar()
        current_index = self.tab_widget.currentIndex()
        
        # Find the last visible tab
        last_visible = self.find_last_visible_tab()
        
        if last_visible < self.tab_widget.count() - 1:
            # Move to the next tab - Qt will auto-scroll
            target_index = last_visible + 1
            self.tab_widget.setCurrentIndex(target_index)
        elif current_index < self.tab_widget.count() - 1:
            # If we can't detect visibility, just move one tab right
            target_index = current_index + 1
            self.tab_widget.setCurrentIndex(target_index)
        
        QTimer.singleShot(150, self.update_navigation_buttons)
    
    def find_first_visible_tab(self):
        """Find the index of the first visible tab"""
        tab_bar = self.tab_widget.tabBar()
        # Get the visible area of the tab bar (excluding our custom buttons)
        tab_bar_x = tab_bar.x()
        
        for i in range(self.tab_widget.count()):
            tab_rect = tab_bar.tabRect(i)
            # Check if tab's left edge is visible within the tab bar's viewport
            if tab_rect.x() >= 0 and tab_rect.left() >= tab_bar_x:
                return i
        return 0
    
    def find_last_visible_tab(self):
        """Find the index of the last visible tab"""
        tab_bar = self.tab_widget.tabBar()
        # Get the visible width of the tab bar
        tab_bar_width = tab_bar.width()
        tab_bar_x = tab_bar.x()
        visible_width = tab_bar_x + tab_bar_width
        
        for i in range(self.tab_widget.count() - 1, -1, -1):
            tab_rect = tab_bar.tabRect(i)
            # Check if tab's right edge is fully visible
            if tab_rect.right() <= visible_width and tab_rect.x() >= 0:
                return i
        return self.tab_widget.count() - 1
    
    def count_hidden_tabs_left(self):
        """Count how many tabs are hidden to the left"""
        first_visible = self.find_first_visible_tab()
        return first_visible
    
    def count_hidden_tabs_right(self):
        """Count how many tabs are hidden to the right"""
        last_visible = self.find_last_visible_tab()
        return self.tab_widget.count() - 1 - last_visible
    
    def update_navigation_buttons(self):
        """Update navigation button enabled state and labels - buttons always visible"""
        # Always hide Qt's default scroll buttons
        self.hide_qt_scroll_buttons()

        # Keep the minimap overview strip in sync with the tabs.
        if hasattr(self, 'tab_minimap'):
            self.tab_minimap.refresh()
        
        if self.tab_widget.count() <= 1:
            # No navigation needed for 0 or 1 tabs - disable buttons
            self.left_nav_btn.setEnabled(False)
            self.left_nav_btn.setText("◀")
            self.right_nav_btn.setEnabled(False)
            self.right_nav_btn.setText("▶")
            return
        
        tab_bar = self.tab_widget.tabBar()
        
        # Force immediate update of tab bar geometry
        tab_bar.updateGeometry()
        
        # Check if any tabs are hidden by looking at their positions
        tabs_overflow = False
        first_visible_idx = -1
        last_visible_idx = -1
        
        for i in range(self.tab_widget.count()):
            tab_rect = tab_bar.tabRect(i)
            # Check if tab is visible (x position is within tab bar width)
            if tab_rect.x() >= 0 and tab_rect.right() <= tab_bar.width():
                if first_visible_idx == -1:
                    first_visible_idx = i
                last_visible_idx = i
            elif tab_rect.x() < 0 or tab_rect.right() > tab_bar.width():
                tabs_overflow = True
        
        # Enable/disable navigation buttons based on overflow
        if tabs_overflow or first_visible_idx > 0 or last_visible_idx < self.tab_widget.count() - 1:
            # Count hidden tabs
            hidden_left = self.count_hidden_tabs_left()
            hidden_right = self.count_hidden_tabs_right()
            
            # Update left button
            if hidden_left > 0:
                self.left_nav_btn.setText(f"◀{hidden_left}")  # Compact format
                self.left_nav_btn.setEnabled(True)
            else:
                self.left_nav_btn.setText("◀")
                self.left_nav_btn.setEnabled(False)
            
            # Update right button
            if hidden_right > 0:
                self.right_nav_btn.setText(f"{hidden_right}▶")  # Compact format
                self.right_nav_btn.setEnabled(True)
            else:
                self.right_nav_btn.setText("▶")
                self.right_nav_btn.setEnabled(False)
        else:
            # All tabs fit - disable navigation buttons
            self.left_nav_btn.setText("◀")
            self.left_nav_btn.setEnabled(False)
            self.right_nav_btn.setText("▶")
            self.right_nav_btn.setEnabled(False)
    
    def get_hidden_tabs_left(self):
        """Get list of (index, name) tuples for tabs hidden on the left"""
        first_visible = self.find_first_visible_tab()
        hidden_tabs = []
        
        for i in range(first_visible):
            tab_name = self.tab_widget.tabText(i)
            hidden_tabs.append((i, tab_name))
        
        return hidden_tabs
    
    def get_hidden_tabs_right(self):
        """Get list of (index, name) tuples for tabs hidden on the right"""
        last_visible = self.find_last_visible_tab()
        hidden_tabs = []
        
        for i in range(last_visible + 1, self.tab_widget.count()):
            tab_name = self.tab_widget.tabText(i)
            hidden_tabs.append((i, tab_name))
        
        return hidden_tabs
    
    def show_left_nav_menu(self, position):
        """Show context menu with hidden tabs on the left"""
        # Only show menu if button is enabled
        if not self.left_nav_btn.isEnabled():
            return
            
        hidden_tabs = self.get_hidden_tabs_left()
        
        if not hidden_tabs:
            return
        
        menu = QMenu(self)
        
        # Add a header
        header_action = QAction("Hidden Tabs (Left)", self)
        header_action.setEnabled(False)
        menu.addAction(header_action)
        menu.addSeparator()
        
        # Add each hidden tab
        for index, tab_name in hidden_tabs:
            action = QAction(tab_name, self)
            # Use lambda with default argument to capture index correctly
            action.triggered.connect(lambda checked=False, idx=index: self.navigate_to_tab(idx))
            menu.addAction(action)
        
        # Style the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 8px 25px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
            QMenu::item:disabled {
                color: #888;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0px;
            }
        """)
        
        # Show menu at button position
        menu.exec_(self.left_nav_btn.mapToGlobal(position))
    
    def show_right_nav_menu(self, position):
        """Show context menu with hidden tabs on the right"""
        # Only show menu if button is enabled
        if not self.right_nav_btn.isEnabled():
            return
            
        hidden_tabs = self.get_hidden_tabs_right()
        
        if not hidden_tabs:
            return
        
        menu = QMenu(self)
        
        # Add a header
        header_action = QAction("Hidden Tabs (Right)", self)
        header_action.setEnabled(False)
        menu.addAction(header_action)
        menu.addSeparator()
        
        # Add each hidden tab
        for index, tab_name in hidden_tabs:
            action = QAction(tab_name, self)
            # Use lambda with default argument to capture index correctly
            action.triggered.connect(lambda checked=False, idx=index: self.navigate_to_tab(idx))
            menu.addAction(action)
        
        # Style the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                color: #e0e0e0;
                padding: 8px 25px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0d47a1;
            }
            QMenu::item:disabled {
                color: #888;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0px;
            }
        """)
        
        # Show menu at button position
        menu.exec_(self.right_nav_btn.mapToGlobal(position))
    
    def navigate_to_tab(self, index):
        """Navigate to a specific tab by index"""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
            # Update navigation buttons after navigation
            self.nav_update_timer.start(100)

