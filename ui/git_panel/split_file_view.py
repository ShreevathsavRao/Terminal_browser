"""Split file view — Local ↔ Remote/Branch side-by-side with git status."""

import os
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMenu, QAction, QInputDialog, QMessageBox,
    QFileDialog, QTextEdit, QDialog, QDialogButtonBox, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont, QIcon
from .git_backend import GitBackend, FileStatus, GitError

# Status display config: (label, color)
STATUS_DISPLAY = {
    "M":  ("M  Modified",    "#dcdcaa"),
    "A":  ("A  Added",       "#4ec9b0"),
    "D":  ("D  Deleted",     "#f44747"),
    "R":  ("R  Renamed",     "#569cd6"),
    "C":  ("C  Copied",      "#c586c0"),
    "U":  ("!! Conflict",    "#ff0000"),
    "?":  ("?  Untracked",   "#cccccc"),
    "!":  ("I  Ignored",     "#555555"),
    "S":  ("S  Staged",      "#4ec9b0"),
    "DS": ("DS Del.Staged",  "#f47474"),
    "≠":  ("≠  Differs",     "#dcdcaa"),
    "↓":  ("↓  Behind",      "#569cd6"),
    "✓":  ("✓  In sync",     "#4ec9b0"),
    "NEW":("NEW Local only", "#4ec9b0"),
    "MISSING": ("MISSING",   "#f44747"),
}


class FileDiffDialog(QDialog):
    """Popup showing unified diff between two versions of a file."""

    def __init__(self, title: str, diff_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setFont(QFont("Menlo", 11))
        view.setStyleSheet("background:#1e1e1e; color:#cccccc;")
        self._render_diff(view, diff_text)
        layout.addWidget(view)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _render_diff(self, view, diff):
        from PyQt5.QtGui import QTextCharFormat
        cursor = view.textCursor()
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
        view.setTextCursor(cursor)


class FilePanel(QWidget):
    """Single side of the split panel (local or remote)."""

    file_selected = pyqtSignal(str, bool)   # path, is_local

    def __init__(self, title: str, is_local: bool, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.is_local = is_local
        self.backend = backend
        self._files: dict = {}       # path → (status_label, color)
        self._ref = ""
        self._build_ui(title)

    def _build_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QHBoxLayout()
        header.setContentsMargins(6, 4, 6, 4)
        lbl = QLabel(title)
        lbl.setStyleSheet("color:#ffffff; font-weight:bold; font-size:12px;")
        header.addWidget(lbl)

        self.ref_combo = QComboBox()
        self.ref_combo.setFixedWidth(180)
        self.ref_combo.setStyleSheet(
            "background:#3c3c3c; color:#cccccc; border:1px solid #555; border-radius:3px;"
        )
        self.ref_combo.currentTextChanged.connect(self._on_ref_changed)
        header.addWidget(self.ref_combo)
        header.addStretch()

        hdr_widget = QWidget()
        hdr_widget.setLayout(header)
        hdr_widget.setStyleSheet("background:#252526; border-bottom:1px solid #3c3c3c;")
        layout.addWidget(hdr_widget)

        # File tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Status", "File Path"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tree.header().setDefaultSectionSize(110)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.setStyleSheet(
            "QTreeWidget{background:#1e1e1e; color:#cccccc; border:none;}"
            "QTreeWidget::item:selected{background:#094771;}"
            "QTreeWidget::item:hover{background:#2a2d2e;}"
        )
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # Status bar
        self.status_bar = QLabel("")
        self.status_bar.setStyleSheet(
            "background:#252526; color:#888; padding:2px 6px; font-size:10px; "
            "border-top:1px solid #3c3c3c;"
        )
        layout.addWidget(self.status_bar)

    def populate_branches(self, branches: list):
        self.ref_combo.blockSignals(True)
        self.ref_combo.clear()
        for b in branches:
            self.ref_combo.addItem(b)
        self.ref_combo.blockSignals(False)
        if self.ref_combo.count():
            self._ref = self.ref_combo.currentText()

    def _on_ref_changed(self, ref: str):
        self._ref = ref
        self.refresh()

    def populate_local(self, status_map: dict, all_paths: list):
        """Show local files with git status."""
        self.tree.clear()
        self._files.clear()
        # Keep strong Python refs to all items so PyQt5 can't GC them
        self._item_refs = []

        counts = {"M": 0, "?": 0, "D": 0, "U": 0, "A": 0}

        dirs: dict = {}
        for path in sorted(all_paths):
            parts = path.replace("\\", "/").split("/")
            fs = status_map.get(path)
            status = "✓"
            color = "#4ec9b0"
            if fs:
                staged_map = {"M": "S", "A": "A", "D": "DS"}
                if fs.staged:
                    status = staged_map.get(fs.status, fs.status)
                else:
                    status = fs.status
                _, color = STATUS_DISPLAY.get(status, (status, "#cccccc"))
                counts[fs.status] = counts.get(fs.status, 0) + 1

            self._files[path] = (status, color)

            if len(parts) == 1:
                item = QTreeWidgetItem([status, parts[0]])
                item.setForeground(0, QColor(color))
                item.setForeground(1, QColor("#cccccc") if status == "✓" else QColor(color))
                item.setData(0, Qt.UserRole, path)
                self._item_refs.append(item)
                self.tree.addTopLevelItem(item)
            else:
                dir_path = "/".join(parts[:-1])
                if dir_path not in dirs:
                    dir_item = QTreeWidgetItem([" ", dir_path + "/"])
                    dir_item.setForeground(0, QColor("#888"))
                    dir_item.setForeground(1, QColor("#569cd6"))
                    self._item_refs.append(dir_item)
                    self.tree.addTopLevelItem(dir_item)
                    dirs[dir_path] = dir_item
                    dir_item.setExpanded(True)
                child = QTreeWidgetItem([status, parts[-1]])
                child.setForeground(0, QColor(color))
                child.setForeground(1, QColor("#cccccc") if status == "✓" else QColor(color))
                child.setData(0, Qt.UserRole, path)
                self._item_refs.append(child)
                dirs[dir_path].addChild(child)

        parts_list = []
        if counts.get("M", 0) or counts.get("S", 0):
            parts_list.append(f"{counts.get('M', 0) + counts.get('S', 0)}M")
        if counts.get("A", 0):
            parts_list.append(f"{counts['A']}A")
        if counts.get("D", 0):
            parts_list.append(f"{counts['D']}D")
        if counts.get("?", 0):
            parts_list.append(f"{counts['?']}?")
        if counts.get("U", 0):
            parts_list.append(f"{counts['U']} conflicts")
        self.status_bar.setText("  ".join(parts_list) if parts_list else "Clean")

    def populate_remote(self, local_files: set, remote_files: set):
        """Show remote files with comparison status."""
        self.tree.clear()
        self._files.clear()

        all_paths = sorted(remote_files | local_files)
        dirs: dict = {}

        for path in all_paths:
            if path in remote_files and path in local_files:
                status, color = "✓", "#4ec9b0"
            elif path in remote_files:
                status, color = "MISSING", "#f44747"   # on remote, not local
            else:
                continue  # local-only handled in local panel

            self._files[path] = (status, color)
            parts = path.replace("\\", "/").split("/")

            if len(parts) == 1:
                item = QTreeWidgetItem([status, parts[0]])
                item.setForeground(0, QColor(color))
                item.setForeground(1, QColor("#cccccc"))
                item.setData(0, Qt.UserRole, path)
                self.tree.addTopLevelItem(item)
            else:
                dir_path = "/".join(parts[:-1])
                if dir_path not in dirs:
                    dir_item = QTreeWidgetItem([" ", dir_path + "/"])
                    dir_item.setForeground(1, QColor("#569cd6"))
                    self.tree.addTopLevelItem(dir_item)
                    dirs[dir_path] = dir_item
                    dir_item.setExpanded(True)
                child = QTreeWidgetItem([status, parts[-1]])
                child.setForeground(0, QColor(color))
                child.setForeground(1, QColor("#cccccc"))
                child.setData(0, Qt.UserRole, path)
                dirs[dir_path].addChild(child)

    def refresh(self):
        """Reload data for this panel."""
        pass  # called externally by SplitFileView

    def _on_item_clicked(self, item, col):
        path = item.data(0, Qt.UserRole)
        if path:
            self.file_selected.emit(path, self.is_local)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        if not path:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#2d2d2d;color:#cccccc;border:1px solid #555;}"
            "QMenu::item:selected{background:#094771;}"
        )

        if self.is_local:
            self._build_local_menu(menu, path, item)
        else:
            self._build_remote_menu(menu, path)

        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _build_local_menu(self, menu: QMenu, path: str, item):
        status = item.text(0).strip()

        menu.addAction("Open File", lambda: self._open_file(path))
        menu.addAction("View Diff vs HEAD", lambda: self._diff_vs_head(path))
        menu.addSeparator()

        if status in ("M", "S", "A"):
            menu.addAction("Stage (git add)", lambda: self._stage(path))
            menu.addAction("Unstage", lambda: self._unstage(path))
            menu.addAction("Discard Changes", lambda: self._discard(path))
            menu.addAction("Revert to HEAD", lambda: self._revert_to_head(path))
        if status == "?":
            menu.addAction("Stage (git add)", lambda: self._stage(path))
            menu.addAction("Add to .gitignore", lambda: self._add_to_gitignore(path))
            menu.addAction("Delete File", lambda: self._delete_local(path))
        if status in ("D", "DS"):
            menu.addAction("Restore Deleted File", lambda: self._revert_to_head(path))
            menu.addAction("Stage Deletion", lambda: self._stage(path))
        if status == "U":
            menu.addAction("Open Conflict Resolver", lambda: self._open_conflict(path))
            menu.addAction("Accept Ours", lambda: self._resolve(path, "ours"))
            menu.addAction("Accept Theirs", lambda: self._resolve(path, "theirs"))
            menu.addAction("Mark Resolved", lambda: self._stage(path))

        menu.addSeparator()
        menu.addAction("Replace from Remote Branch", lambda: self._replace_from_remote(path))
        menu.addAction("Replace from Local Folder…", lambda: self._replace_from_folder(path))
        menu.addSeparator()
        menu.addAction("Rename / Move (git mv)…", lambda: self._rename_file(path))
        menu.addAction("Delete (git rm)…", lambda: self._git_rm(path))

    def _build_remote_menu(self, menu: QMenu, path: str):
        menu.addAction("View File Content", lambda: self._view_remote_file(path))
        menu.addAction("Download to Local", lambda: self._download_to_local(path))
        menu.addAction("Diff vs Local", lambda: self._diff_remote_vs_local(path))

    # ── Local operations ──────────────────────────────────────────────────────

    def _open_file(self, path: str):
        full = os.path.join(self.backend.repo_path, path)
        os.startfile(full) if os.name == "nt" else os.system(f'open "{full}"')

    def _diff_vs_head(self, path: str):
        diff = self.backend.get_file_unstaged_diff(path)
        if not diff:
            diff = self.backend.get_file_staged_diff(path)
        dlg = FileDiffDialog(f"Diff: {path}", diff, self)
        dlg.exec_()

    def _stage(self, path: str):
        try:
            self.backend.stage([path])
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _unstage(self, path: str):
        try:
            self.backend.unstage([path])
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _discard(self, path: str):
        if QMessageBox.question(self, "Discard", f"Discard changes to {path}?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                self.backend.discard([path])
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _revert_to_head(self, path: str):
        try:
            self.backend.revert_file(path, "HEAD")
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _add_to_gitignore(self, path: str):
        gi = os.path.join(self.backend.repo_path, ".gitignore")
        with open(gi, "a") as f:
            f.write(f"\n{path}")

    def _delete_local(self, path: str):
        full = os.path.join(self.backend.repo_path, path)
        if QMessageBox.question(self, "Delete", f"Permanently delete {path}?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                os.remove(full)
            except OSError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _resolve(self, path: str, side: str):
        try:
            self.backend.resolve_file(path, side)
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))

    def _open_conflict(self, path: str):
        # Will be connected externally
        pass

    def _replace_from_remote(self, path: str):
        ref = self._ref or "HEAD"
        try:
            content = self.backend.get_remote_file_content(ref, path)
            full = os.path.join(self.backend.repo_path, path)
            with open(full, "w") as f:
                f.write(content)
            QMessageBox.information(self, "Done", f"{path} replaced from {ref}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _replace_from_folder(self, path: str):
        src, _ = QFileDialog.getOpenFileName(self, "Select replacement file")
        if src:
            dst = os.path.join(self.backend.repo_path, path)
            try:
                shutil.copy2(src, dst)
                QMessageBox.information(self, "Done", f"Replaced {path} from {src}")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _rename_file(self, path: str):
        new_name, ok = QInputDialog.getText(self, "Rename", "New path:", text=path)
        if ok and new_name and new_name != path:
            try:
                self.backend.mv_file(path, new_name)
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    def _git_rm(self, path: str):
        if QMessageBox.question(self, "Delete", f"git rm {path}?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                self.backend.rm_file(path)
            except GitError as e:
                QMessageBox.warning(self, "Git Error", str(e))

    # ── Remote operations ─────────────────────────────────────────────────────

    def _view_remote_file(self, path: str):
        ref = self._ref or "HEAD"
        content = self.backend.get_remote_file_content(ref, path)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{ref}:{path}")
        dlg.resize(700, 500)
        layout = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setFont(QFont("Menlo", 11))
        view.setStyleSheet("background:#1e1e1e; color:#cccccc;")
        view.setPlainText(content)
        layout.addWidget(view)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        layout.addWidget(bb)
        dlg.exec_()

    def _download_to_local(self, path: str):
        ref = self._ref or "HEAD"
        try:
            content = self.backend.get_remote_file_content(ref, path)
            full = os.path.join(self.backend.repo_path, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(content)
            QMessageBox.information(self, "Done", f"Downloaded {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _diff_remote_vs_local(self, path: str):
        ref = self._ref or "HEAD"
        diff = self.backend.get_diff_between("HEAD", ref, path)
        dlg = FileDiffDialog(f"Local vs {ref}: {path}", diff, self)
        dlg.exec_()


class SplitFileView(QWidget):
    """Two-panel local ↔ remote file view with sync toolbar."""

    open_conflict_resolver = pyqtSignal(str)   # path

    def __init__(self, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._build_ui()
        QTimer.singleShot(200, self.refresh)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Conflict indicator bar (only shown when conflicts exist)
        conflict_bar = QHBoxLayout()
        conflict_bar.setContentsMargins(6, 4, 6, 4)
        conflict_bar.addStretch()

        self.conflict_label = QLabel("")
        self.conflict_label.setStyleSheet("color:#f44747; font-weight:bold;")
        conflict_bar.addWidget(self.conflict_label)

        resolve_btn = QPushButton("Resolve Conflicts")
        resolve_btn.setStyleSheet(
            "QPushButton { background:#f44747; color:#fff; border:none; padding:4px 10px; border-radius:3px; }"
            "QPushButton:hover { background:#ff6b6b; }"
            "QPushButton:pressed { background:#c0392b; }"
        )
        resolve_btn.clicked.connect(self._open_first_conflict)
        resolve_btn.setVisible(False)
        self.resolve_btn = resolve_btn
        conflict_bar.addWidget(resolve_btn)

        cb_widget = QWidget()
        cb_widget.setLayout(conflict_bar)
        cb_widget.setStyleSheet("background:#252526; border-bottom:1px solid #3c3c3c;")
        cb_widget.setFixedHeight(32)
        layout.addWidget(cb_widget)

        # Status summary
        self.summary_bar = QLabel("")
        self.summary_bar.setStyleSheet(
            "background:#1e1e1e; color:#888; padding:2px 8px; font-size:10px;"
        )
        layout.addWidget(self.summary_bar)

        # Split panels
        splitter = QSplitter(Qt.Horizontal)
        self.local_panel = FilePanel("LOCAL", True, self.backend)
        self.remote_panel = FilePanel("REMOTE / BRANCH", False, self.backend)
        splitter.addWidget(self.local_panel)
        splitter.addWidget(self.remote_panel)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter)

    def refresh(self):
        try:
            root = self.backend.repo_root()
            self.backend.repo_path = root

            # Populate branch dropdowns
            branches = [b["name"] for b in self.backend.get_branches()]
            remotes = [b["name"] for b in self.backend.get_branches() if b["is_remote"]]
            self.local_panel.populate_branches([b for b in branches if not b.startswith("remotes/")])
            self.remote_panel.populate_branches(remotes or branches)

            # Collect local files via git — tracked files + untracked from status
            import subprocess as _sp
            local_files = set()
            try:
                out = _sp.check_output(
                    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                    cwd=root, stderr=_sp.DEVNULL, text=True
                )
                for line in out.splitlines():
                    line = line.strip()
                    if line:
                        local_files.add(line.replace("\\", "/"))
            except Exception:
                # Fallback: walk but skip .git and node_modules
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames
                                   if d not in (".git", "node_modules", "__pycache__", ".venv", "venv")]
                    for fname in filenames:
                        rel = os.path.relpath(os.path.join(dirpath, fname), root)
                        local_files.add(rel.replace("\\", "/"))

            # Git status
            status_map = self.backend.get_status_map()

            # Conflicts
            conflicts = self.backend.get_conflicts()
            if conflicts:
                self.conflict_label.setText(f"⚠ {len(conflicts)} conflict(s)")
                self.resolve_btn.setVisible(True)
            else:
                self.conflict_label.setText("")
                self.resolve_btn.setVisible(False)

            # Populate local panel
            self.local_panel.populate_local(status_map, sorted(local_files))

            # Remote files from current remote ref
            remote_ref = self.remote_panel._ref or "origin/HEAD"
            remote_files = {f["path"] for f in self.backend.get_remote_tree(remote_ref)}
            self.remote_panel.populate_remote(local_files, remote_files)

            # Summary
            ahead, behind = 0, 0
            try:
                cur = self.backend.current_branch()
                remote_ref_b = f"origin/{cur}"
                ahead, behind = self.backend.get_ahead_behind(cur, remote_ref_b)
            except Exception:
                pass
            modified = sum(1 for f in status_map.values() if f.status == "M")
            untracked = sum(1 for f in status_map.values() if f.status == "?")
            self.summary_bar.setText(
                f"↑{ahead} unpushed  ↓{behind} behind  "
                f"{modified} modified  {untracked} untracked  "
                f"{len(conflicts)} conflicts"
            )
        except GitError:
            pass

    def _fetch(self):
        try:
            self.backend.fetch()
            self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Fetch Failed", str(e))

    def _pull(self):
        try:
            self.backend.pull()
            self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Pull Failed", str(e))

    def _push(self):
        try:
            self.backend.push()
            self.refresh()
        except GitError as e:
            QMessageBox.warning(self, "Push Failed", str(e))

    def _open_first_conflict(self):
        conflicts = self.backend.get_conflicts()
        if conflicts:
            self.open_conflict_resolver.emit(conflicts[0])
