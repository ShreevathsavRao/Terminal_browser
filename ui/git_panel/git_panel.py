"""Main Git panel — tab container wiring all sub-components."""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel,
    QPushButton, QComboBox, QFileDialog, QMessageBox, QInputDialog,
    QMenu, QAction, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont

from .git_backend import GitBackend, GitError
from .graph_view import GraphView
from .split_file_view import SplitFileView
from .conflict_resolver import ConflictResolver, ConflictListPanel
from .commit_dialog import CommitPanel
from .clone_dialog import CloneDialog, RemoteManagerDialog


class RepoPicker(QWidget):
    """Shown when no repo is open yet."""

    repo_opened = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icon = QLabel("⎇")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size:64px; color:#3c3c3c;")
        layout.addWidget(icon)

        hint = QLabel("Open a git repository or clone one to get started.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#888; font-size:13px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(12)

        open_btn = QPushButton("Open Repository…")
        open_btn.setFixedWidth(180)
        open_btn.setStyleSheet(
            "background:#0e4d91; color:#fff; border:none; "
            "padding:8px 16px; border-radius:4px; font-size:13px;"
        )
        open_btn.clicked.connect(self._open_repo)
        btn_row.addWidget(open_btn)

        clone_btn = QPushButton("Clone Repository…")
        clone_btn.setFixedWidth(180)
        clone_btn.setStyleSheet(
            "background:#0e6027; color:#fff; border:none; "
            "padding:8px 16px; border-radius:4px; font-size:13px;"
        )
        clone_btn.clicked.connect(self._clone_repo)
        btn_row.addWidget(clone_btn)

        layout.addLayout(btn_row)

    def _open_repo(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Git Repository")
        if folder:
            self.repo_opened.emit(folder)

    def _clone_repo(self):
        dlg = CloneDialog(self)
        dlg.clone_done.connect(self.repo_opened.emit)
        dlg.exec_()


class GitPanel(QWidget):
    """Top-level Git panel with toolbar + sub-tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend = GitBackend()
        self._repo_open = False
        self._build_ui()
        self._try_auto_detect()

    def _build_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Top toolbar
        self._toolbar = self._build_toolbar()
        self._main_layout.addWidget(self._toolbar)
        self._toolbar.setVisible(False)

        # Stack: picker or tabs
        self._picker = RepoPicker()
        self._picker.repo_opened.connect(self._open_repo)
        self._main_layout.addWidget(self._picker)

        # Custom tab area — replaces QTabWidget so the graph toolbar row can be
        # placed explicitly between the tab buttons and the content stack.
        self._tab_area = QWidget()
        _ta_layout = QVBoxLayout(self._tab_area)
        _ta_layout.setContentsMargins(0, 0, 0, 0)
        _ta_layout.setSpacing(0)

        # ── Tab button bar ────────────────────────────────────────────────────
        self._tab_bar_widget = QWidget()
        self._tab_bar_widget.setFixedHeight(32)
        self._tab_bar_widget.setStyleSheet(
            "background:#252526; border-bottom:1px solid #3c3c3c;"
        )
        self._tab_bar_layout = QHBoxLayout(self._tab_bar_widget)
        self._tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_bar_layout.setSpacing(0)

        self._tab_buttons = []
        for i, label in enumerate(["⎇  Graph", "⇄  Files", "✓  Commit", "!!  Conflicts"]):
            btn = self._make_tab_button(label, i)
            self._tab_bar_layout.addWidget(btn)
            self._tab_buttons.append(btn)
        self._tab_bar_layout.addStretch()
        _ta_layout.addWidget(self._tab_bar_widget)

        # ── Graph-specific toolbar row (visible only for the Graph tab) ───────
        self._graph_toolbar_row = QWidget()
        self._graph_toolbar_row.setFixedHeight(34)
        self._graph_toolbar_row.setStyleSheet(
            "background:#252526; border-bottom:1px solid #3c3c3c;"
        )
        self._graph_toolbar_layout = QHBoxLayout(self._graph_toolbar_row)
        self._graph_toolbar_layout.setContentsMargins(6, 3, 6, 3)
        self._graph_toolbar_layout.setSpacing(6)
        self._graph_toolbar_row.setVisible(False)
        _ta_layout.addWidget(self._graph_toolbar_row)

        # ── Content stack ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(
            "QStackedWidget{background:#1e1e1e;}"
            "QScrollBar:vertical{background:#2d2d2d;width:10px;margin:0;}"
            "QScrollBar::handle:vertical{background:#555;min-height:24px;border-radius:5px;}"
            "QScrollBar::handle:vertical:hover{background:#777;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            "QScrollBar:horizontal{background:#2d2d2d;height:10px;margin:0;}"
            "QScrollBar::handle:horizontal{background:#555;min-width:24px;border-radius:5px;}"
            "QScrollBar::handle:horizontal:hover{background:#777;}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;}"
            "QSplitter::handle{background:#3c3c3c;}"
            "QSplitter::handle:horizontal{width:3px;}"
            "QSplitter::handle:vertical{height:3px;}"
            "QSplitter::handle:hover{background:#569cd6;}"
        )
        _ta_layout.addWidget(self._stack)

        self._tab_area.setVisible(False)
        self._main_layout.addWidget(self._tab_area)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(38)
        bar.setStyleSheet("background:#252526; border-bottom:1px solid #3c3c3c;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        # Repo label
        self.repo_label = QLabel("")
        self.repo_label.setStyleSheet("color:#9cdcfe; font-size:11px; font-weight:bold;")
        layout.addWidget(self.repo_label)

        # Branch selector
        self.branch_combo = QComboBox()
        self.branch_combo.setFixedWidth(160)
        self.branch_combo.setStyleSheet(
            "background:#3c3c3c; color:#cccccc; border:1px solid #555; border-radius:3px;"
        )
        self.branch_combo.currentTextChanged.connect(self._checkout_branch)
        layout.addWidget(self.branch_combo)

        layout.addStretch()

        # Action buttons
        for text, color, slot in [
            ("⬇ Fetch",   "#3a3a60", self._fetch),
            ("⬇ Pull",    "#0e4d91", self._pull),
            ("⬆ Push",    "#6a0dad", self._push),
            ("+ Branch",  "#0e6027", self._new_branch),
            ("⟳ Refresh", "#3c3c3c", self.refresh_all),
        ]:
            btn = QPushButton(text)
            from PyQt5.QtGui import QColor as _QC
            hover  = _QC(color).lighter(130).name()
            press  = _QC(color).darker(120).name()
            btn.setStyleSheet(
                f"QPushButton {{ background:{color}; color:#fff; border:none; "
                f"padding:4px 10px; border-radius:3px; font-size:11px; }}"
                f"QPushButton:hover {{ background:{hover}; }}"
                f"QPushButton:pressed {{ background:{press}; padding-top:5px; padding-bottom:3px; }}"
            )
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        # Hamburger menu
        menu_btn = QPushButton("⋮")
        menu_btn.setFixedWidth(28)
        menu_btn.setStyleSheet(
            "QPushButton { background:#3c3c3c; color:#cccccc; border:none; "
            "padding:4px; border-radius:3px; font-size:14px; }"
            "QPushButton:hover { background:#555555; color:#ffffff; }"
            "QPushButton:pressed { background:#222222; padding-top:5px; }"
        )
        menu_btn.clicked.connect(self._show_menu)
        layout.addWidget(menu_btn)

        return bar

    def _make_tab_button(self, label: str, idx: int) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFixedHeight(32)
        btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
        btn.setStyleSheet(
            "QPushButton { background:#2d2d2d; color:#888888; border:none; "
            "border-right:1px solid #3c3c3c; padding:0 14px; font-size:12px; }"
            "QPushButton:checked { background:#1e1e1e; color:#cccccc; "
            "border-bottom:2px solid #4ec9b0; }"
            "QPushButton:hover:!checked { background:#3c3c3c; color:#cccccc; }"
        )
        return btn

    def _switch_tab(self, idx: int):
        for i, btn in enumerate(self._tab_buttons):
            btn.setChecked(i == idx)
        self._graph_toolbar_row.setVisible(idx == 0)
        if 0 <= idx < self._stack.count():
            self._stack.setCurrentIndex(idx)

    def _populate_graph_toolbar(self):
        while self._graph_toolbar_layout.count():
            item = self._graph_toolbar_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._graph_toolbar_layout.addWidget(self._graph_view.search_box)
        self._graph_toolbar_layout.addWidget(self._graph_view.branch_filter)
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.setStyleSheet(
            "QPushButton { background:#0e6027; color:#fff; border:none; "
            "padding:4px 10px; border-radius:3px; }"
            "QPushButton:hover { background:#13802f; }"
            "QPushButton:pressed { background:#09401a; padding-top:5px; padding-bottom:3px; }"
        )
        refresh_btn.clicked.connect(self._graph_view._load_commits)
        self._graph_toolbar_layout.addWidget(refresh_btn)

    def _try_auto_detect(self):
        """Try to detect if cwd is a git repo and auto-open it."""
        cwd = os.getcwd()
        backend = GitBackend(cwd)
        if backend.is_git_repo():
            self._open_repo(cwd)

    def _open_repo(self, path: str):
        self.backend = GitBackend(path)
        if not self.backend.is_git_repo():
            QMessageBox.warning(self, "Not a Git repo",
                                f"{path} is not a git repository.")
            return

        self.backend.repo_path = self.backend.repo_root()
        self._repo_open = True

        # Switch from picker to custom tab area
        self._picker.setVisible(False)
        self._toolbar.setVisible(True)
        self._tab_area.setVisible(True)

        # Release old graph-view widgets from toolbar before deleting old views
        while self._graph_toolbar_layout.count():
            item = self._graph_toolbar_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Clear stack and remove any dynamically added conflict-resolver tabs
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
            w.deleteLater()
        while len(self._tab_buttons) > 4:
            btn = self._tab_buttons.pop()
            self._tab_bar_layout.removeWidget(btn)
            btn.deleteLater()

        # Build views
        self._graph_view = GraphView(self.backend)
        self._split_view = SplitFileView(self.backend)
        self._commit_panel = CommitPanel(self.backend)
        self._conflict_list = ConflictListPanel(self.backend)

        self._split_view.open_conflict_resolver.connect(self._open_conflict_resolver)
        self._conflict_list.open_file.connect(self._open_conflict_resolver)
        self._commit_panel.committed.connect(self.refresh_all)
        self._graph_view.canvas.commit_clicked.connect(lambda _: None)

        self._stack.addWidget(self._graph_view)
        self._stack.addWidget(self._split_view)
        self._stack.addWidget(self._commit_panel)
        self._stack.addWidget(self._conflict_list)

        # Populate graph toolbar row with the new view's search/filter widgets
        self._populate_graph_toolbar()

        # Switch to Graph tab
        self._switch_tab(0)
        self._refresh_toolbar()
        self.repo_label.setText(os.path.basename(self.backend.repo_path))

    def _refresh_toolbar(self):
        try:
            self.branch_combo.blockSignals(True)
            self.branch_combo.clear()
            cur = self.backend.current_branch()
            branches = [b["name"] for b in self.backend.get_branches()
                        if not b["is_remote"]]
            for b in branches:
                self.branch_combo.addItem(b)
            idx = self.branch_combo.findText(cur)
            if idx >= 0:
                self.branch_combo.setCurrentIndex(idx)
            self.branch_combo.blockSignals(False)
        except GitError:
            pass

    def refresh_all(self):
        if not self._repo_open:
            return
        self._refresh_toolbar()
        self._graph_view._load_commits()
        self._split_view.refresh()
        self._commit_panel.refresh()
        self._conflict_list.refresh()

    def _open_conflict_resolver(self, path: str):
        resolver = ConflictResolver(self.backend, path, self)
        resolver.all_resolved.connect(lambda p: self.refresh_all())
        tab_title = f"!! {os.path.basename(path)}"
        for i, btn in enumerate(self._tab_buttons):
            if btn.text() == tab_title:
                self._switch_tab(i)
                return
        idx = self._stack.count()
        self._stack.addWidget(resolver)
        btn = self._make_tab_button(tab_title, idx)
        self._tab_bar_layout.insertWidget(len(self._tab_buttons), btn)
        self._tab_buttons.append(btn)
        self._switch_tab(idx)

    # ── Toolbar actions ───────────────────────────────────────────────────────

    def _checkout_branch(self, branch: str):
        if not branch or not self._repo_open:
            return
        try:
            current = self.backend.current_branch()
            if branch != current:
                self.backend.checkout(branch)
                self.refresh_all()
        except GitError as e:
            QMessageBox.warning(self, "Checkout Failed", str(e))

    def _fetch(self):
        try:
            self.backend.fetch()
            self.refresh_all()
        except GitError as e:
            QMessageBox.warning(self, "Fetch Failed", str(e))

    def _pull(self):
        try:
            self.backend.pull()
            self.refresh_all()
        except GitError as e:
            QMessageBox.warning(self, "Pull Failed", str(e))

    def _push(self):
        try:
            self.backend.push()
            self.refresh_all()
        except GitError as e:
            QMessageBox.warning(self, "Push Failed", str(e))

    def _new_branch(self):
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if ok and name:
            try:
                self.backend.create_branch(name)
                self.backend.checkout(name)
                self.refresh_all()
            except GitError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#2d2d2d; color:#cccccc; border:1px solid #555;}"
            "QMenu::item:selected{background:#094771;}"
        )
        menu.addAction("Clone Repository…", self._clone)
        menu.addAction("Open Repository…",  self._pick_repo)
        menu.addSeparator()
        menu.addAction("Manage Remotes…",   self._manage_remotes)
        menu.addAction("Stash Changes…",    self._stash)
        menu.addAction("Pop Stash",         self._pop_stash)
        menu.addSeparator()
        menu.addAction("Merge Branch…",     self._merge)
        menu.addAction("Rebase onto…",      self._rebase)
        menu.addAction("Create Tag…",       self._tag)
        menu.exec_(self.mapToGlobal(self.sender().pos()))

    def _clone(self):
        dlg = CloneDialog(self)
        dlg.clone_done.connect(self._open_repo)
        dlg.exec_()

    def _pick_repo(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Git Repository")
        if folder:
            self._open_repo(folder)

    def _manage_remotes(self):
        dlg = RemoteManagerDialog(self.backend, self)
        dlg.exec_()

    def _stash(self):
        msg, ok = QInputDialog.getText(self, "Stash", "Stash message (optional):")
        if ok:
            try:
                self.backend.stash_push(message=msg)
                self.refresh_all()
            except GitError as e:
                QMessageBox.warning(self, "Stash Failed", str(e))

    def _pop_stash(self):
        try:
            self.backend.stash_pop()
            self.refresh_all()
        except GitError as e:
            QMessageBox.warning(self, "Pop Failed", str(e))

    def _merge(self):
        branches = [b["name"] for b in self.backend.get_branches()]
        branch, ok = QInputDialog.getItem(self, "Merge", "Merge branch into current:", branches)
        if ok and branch:
            try:
                self.backend.merge(branch)
                self.refresh_all()
            except GitError as e:
                QMessageBox.warning(self, "Merge Failed", str(e))

    def _rebase(self):
        branches = [b["name"] for b in self.backend.get_branches()]
        branch, ok = QInputDialog.getItem(self, "Rebase", "Rebase current onto:", branches)
        if ok and branch:
            try:
                self.backend.rebase(branch)
                self.refresh_all()
            except GitError as e:
                QMessageBox.warning(self, "Rebase Failed", str(e))

    def _tag(self):
        name, ok = QInputDialog.getText(self, "Create Tag", "Tag name:")
        if ok and name:
            msg, ok2 = QInputDialog.getText(self, "Tag Message",
                                            "Message (blank = lightweight):")
            try:
                self.backend.create_tag(name, message=msg, annotated=bool(msg))
                self.refresh_all()
            except GitError as e:
                QMessageBox.warning(self, "Tag Failed", str(e))
