"""3-way merge conflict resolver."""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QScrollBar, QFrame, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextBlockFormat
from .git_backend import GitBackend, ConflictHunk, GitError


class HunkWidget(QWidget):
    """Single conflict hunk with accept buttons."""

    resolved = pyqtSignal(int, str, list)  # hunk_idx, resolution, lines

    def __init__(self, hunk: ConflictHunk, idx: int, parent=None):
        super().__init__(parent)
        self.hunk = hunk
        self.idx = idx
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        # Hunk header
        header = QHBoxLayout()
        lbl = QLabel(f"Conflict #{self.idx + 1}")
        lbl.setStyleSheet("color:#f44747; font-weight:bold; font-size:11px;")
        header.addWidget(lbl)
        header.addStretch()

        for text, color, res in [
            ("Accept Ours",         "#0e6027", "ours"),
            ("Accept Theirs",       "#6a0dad", "theirs"),
            ("Accept Both",         "#3a4a00", "both"),
            ("Accept Both (↕)",     "#4a3a00", "both_rev"),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"background:{color}; color:#fff; border:none; "
                f"padding:2px 8px; border-radius:3px; font-size:10px;"
            )
            btn.clicked.connect(lambda checked, r=res: self._accept(r))
            header.addWidget(btn)

        layout.addLayout(header)

        # Three-way diff display
        diff_row = QHBoxLayout()
        diff_row.setSpacing(4)

        self.ours_view = self._make_text_view("#0d2b1a", "#4ec9b0")
        self.ours_view.setPlainText("".join(self.hunk.ours_lines))
        self.base_view = self._make_text_view("#1e1e1e", "#888888")
        self.base_view.setPlainText("".join(self.hunk.base_lines) or "(no base)")
        self.theirs_view = self._make_text_view("#2b0d2b", "#c586c0")
        self.theirs_view.setPlainText("".join(self.hunk.theirs_lines))

        for view, label in [
            (self.ours_view, "OURS (current branch)"),
            (self.base_view, "BASE (common ancestor)"),
            (self.theirs_view, "THEIRS (incoming)"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(0)
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#888; font-size:10px; padding:2px 4px;")
            col.addWidget(lbl)
            col.addWidget(view)
            w = QWidget()
            w.setLayout(col)
            diff_row.addWidget(w)

        layout.addLayout(diff_row)

        # Resolution indicator
        self.resolved_label = QLabel("")
        self.resolved_label.setStyleSheet("color:#4ec9b0; font-size:10px; padding:2px 4px;")
        layout.addWidget(self.resolved_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#3c3c3c;")
        layout.addWidget(sep)

    def _make_text_view(self, bg: str, fg: str) -> QTextEdit:
        view = QTextEdit()
        view.setReadOnly(True)
        view.setFont(QFont("Menlo", 10))
        view.setMaximumHeight(120)
        view.setStyleSheet(f"background:{bg}; color:{fg}; border:1px solid #3c3c3c;")
        return view

    def _accept(self, resolution: str):
        if resolution == "ours":
            lines = self.hunk.ours_lines
        elif resolution == "theirs":
            lines = self.hunk.theirs_lines
        elif resolution == "both":
            lines = self.hunk.ours_lines + self.hunk.theirs_lines
        else:  # both_rev
            lines = self.hunk.theirs_lines + self.hunk.ours_lines

        self.hunk.resolved = True
        self.hunk.resolution = resolution
        res_text = {"ours": "✓ Accepted Ours", "theirs": "✓ Accepted Theirs",
                    "both": "✓ Accepted Both", "both_rev": "✓ Accepted Both (Theirs First)"}
        self.resolved_label.setText(res_text.get(resolution, "✓ Resolved"))
        self.resolved.emit(self.idx, resolution, lines)


class ConflictResolver(QWidget):
    """Full 3-way merge conflict resolver for a single file."""

    all_resolved = pyqtSignal(str)   # path — emitted when all hunks resolved

    def __init__(self, backend: GitBackend, path: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.path = path
        self._hunks: list = []
        self._result_lines: list = []
        self._hunk_widgets: list = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        title = QLabel(f"Conflict Resolver — {self.path}")
        title.setStyleSheet("color:#f44747; font-weight:bold; font-size:13px;")
        header.addWidget(title)
        header.addStretch()

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color:#888; font-size:11px;")
        header.addWidget(self.progress_label)

        layout.addLayout(header)

        # Navigation buttons
        nav = QHBoxLayout()
        prev_btn = QPushButton("← Prev Conflict")
        prev_btn.clicked.connect(self._prev_hunk)
        next_btn = QPushButton("Next Conflict →")
        next_btn.clicked.connect(self._next_hunk)
        for b in (prev_btn, next_btn):
            b.setStyleSheet(
                "background:#3c3c3c; color:#cccccc; border:none; "
                "padding:4px 10px; border-radius:3px;"
            )
            nav.addWidget(b)
        nav.addStretch()

        accept_all_ours = QPushButton("Accept All Ours")
        accept_all_ours.setStyleSheet(
            "background:#0e6027; color:#fff; border:none; padding:4px 10px; border-radius:3px;"
        )
        accept_all_ours.clicked.connect(lambda: self._accept_all("ours"))

        accept_all_theirs = QPushButton("Accept All Theirs")
        accept_all_theirs.setStyleSheet(
            "background:#6a0dad; color:#fff; border:none; padding:4px 10px; border-radius:3px;"
        )
        accept_all_theirs.clicked.connect(lambda: self._accept_all("theirs"))

        nav.addWidget(accept_all_ours)
        nav.addWidget(accept_all_theirs)
        layout.addLayout(nav)

        # Main splitter: hunks | result
        splitter = QSplitter(Qt.Vertical)

        # Hunk list scroll area
        from PyQt5.QtWidgets import QScrollArea
        self.hunk_scroll = QScrollArea()
        self.hunk_scroll.setWidgetResizable(True)
        self.hunk_scroll.setStyleSheet("background:#1e1e1e; border:none;")
        self.hunk_container = QWidget()
        self.hunk_layout = QVBoxLayout(self.hunk_container)
        self.hunk_layout.setContentsMargins(4, 4, 4, 4)
        self.hunk_layout.setSpacing(0)
        self.hunk_layout.addStretch()
        self.hunk_scroll.setWidget(self.hunk_container)
        splitter.addWidget(self.hunk_scroll)

        # Result editor
        result_frame = QWidget()
        rl = QVBoxLayout(result_frame)
        rl.setContentsMargins(0, 0, 0, 0)
        result_label = QLabel("RESULT (editable — this will be saved)")
        result_label.setStyleSheet("color:#cccccc; padding:4px; background:#252526;")
        rl.addWidget(result_label)
        self.result_view = QTextEdit()
        self.result_view.setFont(QFont("Menlo", 11))
        self.result_view.setStyleSheet("background:#1e1e1e; color:#cccccc; border:none;")
        rl.addWidget(self.result_view)
        splitter.addWidget(result_frame)

        splitter.setSizes([400, 200])
        layout.addWidget(splitter)

        # Action buttons
        actions = QHBoxLayout()
        actions.addStretch()

        for text, color, slot in [
            ("Abort Merge",     "#f44747", self._abort),
            ("Mark Resolved & Stage", "#0e6027", self._save_and_stage),
            ("Continue Merge", "#0e4d91", self._continue_merge),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(
                f"background:{color}; color:#fff; border:none; "
                f"padding:5px 14px; border-radius:3px;"
            )
            btn.clicked.connect(slot)
            actions.addWidget(btn)

        layout.addLayout(actions)

    def _load(self):
        ours, theirs, base, hunks = self.backend.get_conflict_hunks(self.path)
        self._hunks = hunks
        self._hunk_widgets = []

        # Clear hunk container
        while self.hunk_layout.count() > 1:
            item = self.hunk_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build result from file content
        full_path = os.path.join(self.backend.repo_path, self.path)
        try:
            with open(full_path, "r", errors="replace") as f:
                self._result_lines = f.readlines()
        except OSError:
            self._result_lines = []
        self.result_view.setPlainText("".join(self._result_lines))

        for i, hunk in enumerate(hunks):
            hw = HunkWidget(hunk, i)
            hw.resolved.connect(self._on_hunk_resolved)
            self._hunk_widgets.append(hw)
            self.hunk_layout.insertWidget(i, hw)

        self._update_progress()

    def _on_hunk_resolved(self, idx: int, resolution: str, lines: list):
        self._hunks[idx].resolved = True
        self._apply_resolution_to_result(idx, lines)
        self._update_progress()

        unresolved = [h for h in self._hunks if not h.resolved]
        if not unresolved:
            self.all_resolved.emit(self.path)

    def _apply_resolution_to_result(self, hunk_idx: int, resolved_lines: list):
        """Replace the conflict markers in result with resolved lines."""
        content = self.result_view.toPlainText()
        lines = content.splitlines(keepends=True)
        out = []
        i = 0
        conflicts_seen = 0
        while i < len(lines):
            if lines[i].startswith("<<<<<<<"):
                if conflicts_seen == hunk_idx:
                    # Replace this conflict block with resolved lines
                    out.extend(resolved_lines)
                    # Skip to >>>>>>>
                    while i < len(lines) and not lines[i].startswith(">>>>>>>"):
                        i += 1
                    i += 1  # skip >>>>>>>
                    conflicts_seen += 1
                else:
                    out.append(lines[i])
                    conflicts_seen += 1
                    i += 1
            else:
                out.append(lines[i])
                i += 1
        self.result_view.setPlainText("".join(out))

    def _update_progress(self):
        total = len(self._hunks)
        done = sum(1 for h in self._hunks if h.resolved)
        self.progress_label.setText(f"Resolved {done} / {total} conflicts")

    def _prev_hunk(self):
        # Scroll to previous unresolved hunk widget
        for i in range(len(self._hunk_widgets) - 1, -1, -1):
            if not self._hunks[i].resolved:
                self.hunk_scroll.ensureWidgetVisible(self._hunk_widgets[i])
                break

    def _next_hunk(self):
        for i, hw in enumerate(self._hunk_widgets):
            if not self._hunks[i].resolved:
                self.hunk_scroll.ensureWidgetVisible(hw)
                break

    def _accept_all(self, side: str):
        for i, hw in enumerate(self._hunk_widgets):
            if not self._hunks[i].resolved:
                hw._accept(side)

    def _save_and_stage(self):
        content = self.result_view.toPlainText()
        try:
            self.backend.write_resolved(self.path, content)
            QMessageBox.information(self, "Done", f"{self.path} saved and staged.")
            self.all_resolved.emit(self.path)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _abort(self):
        if QMessageBox.question(self, "Abort", "Abort the merge?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                self.backend.merge_abort()
            except GitError:
                try:
                    self.backend.rebase_abort()
                except GitError:
                    pass

    def _continue_merge(self):
        try:
            self.backend.merge_continue()
            QMessageBox.information(self, "Done", "Merge continued successfully.")
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))


class ConflictListPanel(QWidget):
    """Panel listing all conflicted files with resolution status."""

    open_file = pyqtSignal(str)

    def __init__(self, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("CONFLICTS")
        header.setStyleSheet(
            "color:#f44747; font-weight:bold; padding:6px; "
            "background:#252526; border-bottom:1px solid #3c3c3c;"
        )
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget{background:#1e1e1e; color:#cccccc; border:none;}"
            "QListWidget::item:selected{background:#094771;}"
        )
        self.list_widget.itemDoubleClicked.connect(
            lambda item: self.open_file.emit(item.data(Qt.UserRole))
        )
        layout.addWidget(self.list_widget)

        actions = QHBoxLayout()
        for text, color, slot in [
            ("Mark All Resolved", "#0e6027", self._mark_all),
            ("Abort Merge",       "#f44747", self._abort),
            ("Continue Merge",    "#0e4d91", self._continue),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(
                f"background:{color}; color:#fff; border:none; "
                f"padding:4px 8px; border-radius:3px; font-size:10px;"
            )
            btn.clicked.connect(slot)
            actions.addWidget(btn)
        layout.addLayout(actions)

    def refresh(self):
        self.list_widget.clear()
        conflicts = self.backend.get_conflicts()
        for path in conflicts:
            item = QListWidgetItem(f"!!  {path}")
            item.setForeground(QColor("#f44747"))
            item.setData(Qt.UserRole, path)
            self.list_widget.addItem(item)

    def _mark_all(self):
        conflicts = self.backend.get_conflicts()
        try:
            if conflicts:
                self.backend.stage(conflicts)
                self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _abort(self):
        try:
            self.backend.merge_abort()
            self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _continue(self):
        try:
            self.backend.merge_continue()
            self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Error", str(e))
