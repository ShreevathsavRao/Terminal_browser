"""Stage / unstage / commit dialog."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QTextEdit, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from .git_backend import GitBackend, GitError, FileStatus

STATUS_COLOR = {
    "M": "#dcdcaa", "A": "#4ec9b0", "D": "#f44747",
    "R": "#569cd6", "C": "#c586c0", "?": "#cccccc",
}

_SCROLL_STYLE = """
    QScrollBar:vertical { background:#2d2d2d; width:10px; margin:0; }
    QScrollBar::handle:vertical { background:#555; min-height:24px; border-radius:5px; }
    QScrollBar::handle:vertical:hover { background:#777; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
    QScrollBar:horizontal { background:#2d2d2d; height:10px; margin:0; }
    QScrollBar::handle:horizontal { background:#555; min-width:24px; border-radius:5px; }
    QScrollBar::handle:horizontal:hover { background:#777; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
"""

_SPLITTER_STYLE = """
    QSplitter::handle { background:#3c3c3c; }
    QSplitter::handle:horizontal { width:4px; }
    QSplitter::handle:vertical { height:4px; }
    QSplitter::handle:hover { background:#569cd6; }
"""

_BTN = (
    "QPushButton {{ background:{bg}; color:#fff; border:none; "
    "padding:3px 8px; border-radius:3px; font-size:11px; }}"
    "QPushButton:hover {{ background:{hover}; }}"
    "QPushButton:pressed {{ background:{press}; }}"
)


def _btn(text, bg, slot):
    b = QPushButton(text)
    hover = QColor(bg).lighter(130).name()
    press = QColor(bg).darker(120).name()
    b.setStyleSheet(_BTN.format(bg=bg, hover=hover, press=press))
    b.clicked.connect(slot)
    return b


class CommitPanel(QWidget):
    """Staging area and commit UI embedded in the Git panel."""

    committed = pyqtSignal()

    def __init__(self, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._build_ui()
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _build_ui(self):
        self.setStyleSheet(_SCROLL_STYLE + _SPLITTER_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 6, 4, 4)
        root.setSpacing(0)

        # ── Outer horizontal splitter: file lists | diff+commit ───────────────
        outer = QSplitter(Qt.Horizontal)
        outer.setHandleWidth(4)
        outer.setStyleSheet(_SPLITTER_STYLE)

        # ── LEFT: staged + unstaged (vertical splitter) ───────────────────────
        file_split = QSplitter(Qt.Vertical)
        file_split.setHandleWidth(4)
        file_split.setStyleSheet(_SPLITTER_STYLE)

        file_split.addWidget(self._build_staged_section())
        file_split.addWidget(self._build_unstaged_section())
        file_split.setSizes([200, 280])

        outer.addWidget(file_split)

        # ── RIGHT: diff | commit form (vertical splitter) ─────────────────────
        right_split = QSplitter(Qt.Vertical)
        right_split.setHandleWidth(4)
        right_split.setStyleSheet(_SPLITTER_STYLE)

        right_split.addWidget(self._build_diff_section())
        right_split.addWidget(self._build_commit_section())
        right_split.setSizes([320, 220])

        outer.addWidget(right_split)
        outer.setSizes([340, 520])

        root.addWidget(outer)

        # Wire diff-on-selection and gitignore button updates
        self.staged_tree.currentItemChanged.connect(self._show_staged_diff)
        self.unstaged_tree.currentItemChanged.connect(self._show_unstaged_diff)
        self.staged_tree.currentItemChanged.connect(
            lambda cur, prev: self._update_gi_btn(self.staged_tree, self.staged_gi_btn, cur)
        )
        self.unstaged_tree.currentItemChanged.connect(
            lambda cur, prev: self._update_gi_btn(self.unstaged_tree, self.unstaged_gi_btn, cur)
        )

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_staged_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 2)
        layout.setSpacing(3)

        hdr = QHBoxLayout()
        lbl = QLabel("⬆  Staged Changes")
        lbl.setStyleSheet("color:#4ec9b0; font-weight:bold; font-size:11px; padding:0 4px;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        self.staged_tree = self._make_tree()
        self.staged_tree.itemDoubleClicked.connect(
            lambda item, col: self._unstage_item(item)
        )
        layout.addWidget(self.staged_tree)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_row.addWidget(_btn("⬇ Unstage Selected", "#3a3a60", self._unstage_selected))
        btn_row.addWidget(_btn("⬇ Unstage All",      "#3a3a60", self._unstage_all))
        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(4)
        self.staged_gi_btn = self._make_gi_btn()
        btn_row2.addWidget(self.staged_gi_btn)
        layout.addLayout(btn_row2)

        return w

    def _build_unstaged_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 2)
        layout.setSpacing(3)

        lbl = QLabel("⬇  Unstaged / Untracked")
        lbl.setStyleSheet("color:#dcdcaa; font-weight:bold; font-size:11px; padding:0 4px;")
        layout.addWidget(lbl)

        self.unstaged_tree = self._make_tree()
        self.unstaged_tree.itemDoubleClicked.connect(
            lambda item, col: self._stage_item(item)
        )
        layout.addWidget(self.unstaged_tree)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_row.addWidget(_btn("⬆ Stage Selected",  "#0e6027", self._stage_selected))
        btn_row.addWidget(_btn("Stage All",          "#0e4d91", self._stage_all))
        layout.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(4)
        btn_row2.addWidget(_btn("Discard Selected",  "#6a1010", self._discard_selected))
        self.unstaged_gi_btn = self._make_gi_btn()
        btn_row2.addWidget(self.unstaged_gi_btn)
        layout.addLayout(btn_row2)

        return w

    def _build_diff_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        lbl = QLabel("Diff")
        lbl.setStyleSheet("color:#888; font-size:11px; padding:0 4px;")
        layout.addWidget(lbl)

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Menlo", 10))
        self.diff_view.setStyleSheet(
            "QTextEdit { background:#1e1e1e; color:#cccccc; border:1px solid #3c3c3c; }"
            + _SCROLL_STYLE
        )
        layout.addWidget(self.diff_view)
        return w

    def _build_commit_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        msg_lbl = QLabel("Commit Message")
        msg_lbl.setStyleSheet("color:#cccccc; font-weight:bold; font-size:11px; padding:0 4px;")
        layout.addWidget(msg_lbl)

        self.msg_box = QTextEdit()
        self.msg_box.setPlaceholderText("Summary (first line)\n\nDetailed description…")
        self.msg_box.setFont(QFont("Menlo", 11))
        self.msg_box.setStyleSheet(
            "QTextEdit { background:#2d2d2d; color:#cccccc; "
            "border:1px solid #555; border-radius:3px; }"
            + _SCROLL_STYLE
        )
        self.msg_box.textChanged.connect(self._update_char_count)
        layout.addWidget(self.msg_box)

        self.char_count = QLabel("0 chars")
        self.char_count.setStyleSheet("color:#888; font-size:10px; padding:0 4px;")
        layout.addWidget(self.char_count)

        options_row = QHBoxLayout()
        self.amend_check = QCheckBox("Amend last commit")
        self.amend_check.setStyleSheet("color:#cccccc;")
        self.signoff_check = QCheckBox("Sign-off")
        self.signoff_check.setStyleSheet("color:#cccccc;")
        options_row.addWidget(self.amend_check)
        options_row.addWidget(self.signoff_check)
        options_row.addStretch()
        layout.addLayout(options_row)

        commit_btn = QPushButton("✓  Commit")
        commit_btn.setStyleSheet(
            "QPushButton { background:#0e6027; color:#fff; border:none; "
            "padding:6px 20px; border-radius:3px; font-weight:bold; }"
            "QPushButton:hover { background:#13802f; }"
            "QPushButton:pressed { background:#09401a; }"
        )
        commit_btn.clicked.connect(self._commit)
        layout.addWidget(commit_btn)

        return w

    # ── Tree factory ──────────────────────────────────────────────────────────

    def _make_tree(self) -> QTreeWidget:
        t = QTreeWidget()
        t.setHeaderLabels(["St", "File"])
        # Status column: fixed, wide enough for the letter + padding
        t.header().setSectionResizeMode(0, QHeaderView.Fixed)
        t.header().resizeSection(0, 36)
        # File column: takes remaining space
        t.header().setSectionResizeMode(1, QHeaderView.Stretch)
        t.header().setMinimumSectionSize(24)
        t.header().setStretchLastSection(True)
        t.setStyleSheet(
            "QTreeWidget { background:#1e1e1e; color:#cccccc; border:1px solid #3c3c3c; }"
            "QTreeWidget::item { padding:2px 0; }"
            "QTreeWidget::item:selected { background:#094771; }"
            "QHeaderView::section { background:#252526; color:#9cdcfe; "
            "border:none; border-bottom:1px solid #3c3c3c; border-right:1px solid #3c3c3c; "
            "padding:3px 4px; font-size:11px; font-weight:bold; }"
            "QHeaderView { background:#252526; }"
            + _SCROLL_STYLE
        )
        return t

    def _make_gi_btn(self) -> QPushButton:
        b = QPushButton("+ Add to .gitignore")
        b.setStyleSheet(_BTN.format(bg="#555555",
                                    hover=QColor("#555555").lighter(130).name(),
                                    press=QColor("#555555").darker(120).name()))
        return b

    def _update_gi_btn(self, tree: QTreeWidget, btn: QPushButton, item=None):
        if item is None:
            item = tree.currentItem()
        path = None
        if item:
            fs = item.data(0, Qt.UserRole)
            if fs:
                path = fs.path
        ignored = self._read_gitignore()
        in_ignore = bool(path and path in ignored)
        try:
            btn.clicked.disconnect()
        except TypeError:
            pass
        if in_ignore:
            btn.setText("✕ Remove from .gitignore")
            btn.setStyleSheet(_BTN.format(bg="#6a3a10",
                                          hover=QColor("#6a3a10").lighter(130).name(),
                                          press=QColor("#6a3a10").darker(120).name()))
            btn.clicked.connect(lambda: self._remove_from_gitignore(tree))
        else:
            btn.setText("+ Add to .gitignore")
            btn.setStyleSheet(_BTN.format(bg="#555555",
                                          hover=QColor("#555555").lighter(130).name(),
                                          press=QColor("#555555").darker(120).name()))
            btn.clicked.connect(lambda: self._add_to_gitignore(tree))

    # ── Data ─────────────────────────────────────────────────────────────────

    def _read_gitignore(self) -> set:
        import os
        gitignore_path = os.path.join(self.backend.repo_path, ".gitignore")
        entries = set()
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, "r") as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if line and not line.startswith("#"):
                            entries.add(line)
            except OSError:
                pass
        return entries

    def refresh(self):
        # Remember selections so we can restore them after clear()
        staged_sel = None
        unstaged_sel = None
        if self.staged_tree.currentItem():
            fs = self.staged_tree.currentItem().data(0, Qt.UserRole)
            if fs:
                staged_sel = fs.path
        if self.unstaged_tree.currentItem():
            fs = self.unstaged_tree.currentItem().data(0, Qt.UserRole)
            if fs:
                unstaged_sel = fs.path

        self.staged_tree.clear()
        self.unstaged_tree.clear()
        ignored_paths = self._read_gitignore()
        staged_restored = None
        unstaged_restored = None
        try:
            for fs in self.backend.get_status():
                tree = self.staged_tree if fs.staged else self.unstaged_tree
                in_gitignore = fs.path in ignored_paths
                color = QColor("#666666") if in_gitignore else QColor(STATUS_COLOR.get(fs.status, "#cccccc"))
                file_label = f"{fs.path}  ⊘" if in_gitignore else fs.path
                item = QTreeWidgetItem([fs.status, file_label])
                item.setForeground(0, color)
                item.setForeground(1, color)
                item.setTextAlignment(0, Qt.AlignCenter | Qt.AlignVCenter)
                item.setData(0, Qt.UserRole, fs)
                if in_gitignore:
                    item.setToolTip(1, "Listed in .gitignore")
                    item.setBackground(0, QColor("#2a1f1f"))
                    item.setBackground(1, QColor("#2a1f1f"))
                tree.addTopLevelItem(item)
                # Restore previous selection
                if fs.staged and staged_sel == fs.path:
                    self.staged_tree.setCurrentItem(item)
                    staged_restored = item
                elif not fs.staged and unstaged_sel == fs.path:
                    self.unstaged_tree.setCurrentItem(item)
                    unstaged_restored = item
        except GitError:
            pass
        self._update_gi_btn(self.staged_tree, self.staged_gi_btn, staged_restored)
        self._update_gi_btn(self.unstaged_tree, self.unstaged_gi_btn, unstaged_restored)

    # ── Diff display ──────────────────────────────────────────────────────────

    def _show_staged_diff(self, item, prev):
        if item:
            fs = item.data(0, Qt.UserRole)
            if fs:
                self._render_diff(self.backend.get_file_staged_diff(fs.path))

    def _show_unstaged_diff(self, item, prev):
        if item:
            fs = item.data(0, Qt.UserRole)
            if fs:
                if fs.status == "?":
                    self._render_untracked(fs.path)
                else:
                    self._render_diff(self.backend.get_file_unstaged_diff(fs.path))

    def _render_untracked(self, path: str):
        import os
        full_path = os.path.join(self.backend.repo_path, path)
        try:
            with open(full_path, "r", errors="replace") as f:
                content = f.read()
        except OSError:
            self._render_diff("")
            return
        header = f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(content.splitlines())} @@\n"
        body = "\n".join("+" + line for line in content.splitlines())
        self._render_diff(header + body)

    def _render_diff(self, diff: str):
        from PyQt5.QtGui import QTextCharFormat
        self.diff_view.clear()
        cursor = self.diff_view.textCursor()
        for line in diff.splitlines():
            fmt = QTextCharFormat()
            if line.startswith("+") and not line.startswith("+++"):
                fmt.setForeground(QColor("#4ec9b0"))
                fmt.setBackground(QColor("#0d2b1a"))
            elif line.startswith("-") and not line.startswith("---"):
                fmt.setForeground(QColor("#f44747"))
                fmt.setBackground(QColor("#2b0d0d"))
            elif line.startswith("@@"):
                fmt.setForeground(QColor("#569cd6"))
            else:
                fmt.setForeground(QColor("#cccccc"))
            cursor.setCharFormat(fmt)
            cursor.insertText(line + "\n")
        self.diff_view.setTextCursor(cursor)

    # ── Selection helpers ─────────────────────────────────────────────────────

    def _get_selected_paths(self, tree: QTreeWidget):
        paths = []
        for item in tree.selectedItems():
            fs = item.data(0, Qt.UserRole)
            if fs:
                paths.append(fs.path)
        return paths

    # ── Stage / unstage ───────────────────────────────────────────────────────

    def _stage_item(self, item):
        fs = item.data(0, Qt.UserRole)
        if fs:
            try:
                self.backend.stage([fs.path])
                self.refresh()
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _unstage_item(self, item):
        fs = item.data(0, Qt.UserRole)
        if fs:
            try:
                self.backend.unstage([fs.path])
                self.refresh()
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _stage_selected(self):
        paths = self._get_selected_paths(self.unstaged_tree)
        if paths:
            try:
                self.backend.stage(paths)
                self.refresh()
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _unstage_selected(self):
        paths = self._get_selected_paths(self.staged_tree)
        if paths:
            try:
                self.backend.unstage(paths)
                self.refresh()
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _stage_all(self):
        try:
            self.backend.stage(["."])
            self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _unstage_all(self):
        try:
            staged = [
                item.data(0, Qt.UserRole).path
                for i in range(self.staged_tree.topLevelItemCount())
                for item in [self.staged_tree.topLevelItem(i)]
                if item.data(0, Qt.UserRole)
            ]
            if staged:
                self.backend.unstage(staged)
                self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _discard_selected(self):
        paths = self._get_selected_paths(self.unstaged_tree)
        if paths and QMessageBox.question(
            self, "Discard", f"Discard changes to {len(paths)} file(s)?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            try:
                self.backend.discard(paths)
                self.refresh()
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _add_to_gitignore(self, tree: QTreeWidget = None):
        if tree is None:
            tree = self.unstaged_tree
        paths = self._get_selected_paths(tree)
        if not paths:
            return
        import os
        gitignore_path = os.path.join(self.backend.repo_path, ".gitignore")
        try:
            existing = set()
            if os.path.exists(gitignore_path):
                with open(gitignore_path, "r") as f:
                    existing = {line.rstrip("\n") for line in f}
            with open(gitignore_path, "a") as f:
                for p in paths:
                    if p not in existing:
                        f.write(p + "\n")
            self.refresh()
        except OSError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _remove_from_gitignore(self, tree: QTreeWidget):
        paths = self._get_selected_paths(tree)
        if not paths:
            return
        import os
        gitignore_path = os.path.join(self.backend.repo_path, ".gitignore")
        if not os.path.exists(gitignore_path):
            QMessageBox.information(self, ".gitignore", ".gitignore does not exist.")
            return
        try:
            with open(gitignore_path, "r") as f:
                lines = f.readlines()
            to_remove = set(paths)
            new_lines = [l for l in lines if l.rstrip("\n") not in to_remove]
            if len(new_lines) == len(lines):
                QMessageBox.information(
                    self, ".gitignore",
                    "Selected file(s) not found as exact lines in .gitignore."
                )
                return
            with open(gitignore_path, "w") as f:
                f.writelines(new_lines)
            self.refresh()
        except OSError as e:
            QMessageBox.warning(self, "Error", str(e))

    # ── Commit ────────────────────────────────────────────────────────────────

    def _update_char_count(self):
        n = len(self.msg_box.toPlainText())
        self.char_count.setText(f"{n} chars")

    def _commit(self):
        msg = self.msg_box.toPlainText().strip()
        if not msg:
            QMessageBox.warning(self, "No Message", "Please enter a commit message.")
            return
        try:
            self.backend.commit(
                msg,
                amend=self.amend_check.isChecked(),
                signoff=self.signoff_check.isChecked(),
            )
            self.msg_box.clear()
            self.refresh()
            self.committed.emit()
        except GitError as e:
            QMessageBox.warning(self, "Commit Failed", str(e))
