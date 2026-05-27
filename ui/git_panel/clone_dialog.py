"""Clone repository dialog and remote manager."""

import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar, QFileDialog,
    QDialogButtonBox, QMessageBox, QWidget, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
from .git_backend import GitBackend, GitError


class CloneWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, url: str, dest: str, branch: str, depth: int):
        super().__init__()
        self.url = url
        self.dest = dest
        self.branch = branch
        self.depth = depth

    def run(self):
        args = ["git", "clone", "--progress"]
        if self.branch:
            args += ["-b", self.branch]
        if self.depth:
            args += ["--depth", str(self.depth)]
        args += [self.url, self.dest]

        try:
            proc = subprocess.Popen(
                args, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                text=True, bufsize=1
            )
            for line in proc.stderr:
                self.progress.emit(line.strip())
            proc.wait()
            if proc.returncode == 0:
                self.finished.emit(True, self.dest)
            else:
                self.finished.emit(False, f"git clone failed (code {proc.returncode})")
        except Exception as e:
            self.finished.emit(False, str(e))


class CloneDialog(QDialog):
    """Clone a repository with progress indicator."""

    clone_done = pyqtSignal(str)   # repo path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clone Repository")
        self.setMinimumWidth(520)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/user/repo.git")
        self.url_edit.setStyleSheet(
            "background:#2d2d2d; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:4px;"
        )
        self.url_edit.textChanged.connect(self._auto_fill_dest)
        form.addRow("Repository URL:", self.url_edit)

        dest_row = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Destination folder")
        self.dest_edit.setStyleSheet(
            "background:#2d2d2d; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:4px;"
        )
        dest_row.addWidget(self.dest_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        browse_btn.setStyleSheet(
            "background:#3c3c3c; color:#cccccc; border:none; padding:4px 8px; border-radius:3px;"
        )
        dest_row.addWidget(browse_btn)
        form.addRow("Destination:", dest_row)

        self.branch_edit = QLineEdit()
        self.branch_edit.setPlaceholderText("Default branch (leave blank for default)")
        self.branch_edit.setStyleSheet(
            "background:#2d2d2d; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:4px;"
        )
        form.addRow("Branch:", self.branch_edit)

        self.depth_edit = QLineEdit()
        self.depth_edit.setPlaceholderText("0 = full history")
        self.depth_edit.setStyleSheet(
            "background:#2d2d2d; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:4px;"
        )
        form.addRow("Depth:", self.depth_edit)

        layout.addLayout(form)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar{background:#1e1e1e; border:1px solid #555; border-radius:3px;}"
            "QProgressBar::chunk{background:#0e6027;}"
        )
        layout.addWidget(self.progress_bar)

        self.log_label = QLabel("")
        self.log_label.setWordWrap(True)
        self.log_label.setStyleSheet("color:#888; font-size:10px;")
        layout.addWidget(self.log_label)

        bb = QDialogButtonBox()
        self.clone_btn = bb.addButton("Clone", QDialogButtonBox.AcceptRole)
        self.clone_btn.setStyleSheet(
            "background:#0e6027; color:#fff; border:none; padding:5px 14px; border-radius:3px;"
        )
        self.clone_btn.clicked.connect(self._start_clone)
        cancel_btn = bb.addButton(QDialogButtonBox.Cancel)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(bb)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if folder:
            url_name = os.path.splitext(os.path.basename(self.url_edit.text()))[0]
            self.dest_edit.setText(os.path.join(folder, url_name) if url_name else folder)

    def _auto_fill_dest(self, url: str):
        if not self.dest_edit.text():
            name = os.path.splitext(os.path.basename(url))[0]
            home = os.path.expanduser("~")
            self.dest_edit.setText(os.path.join(home, name))

    def _start_clone(self):
        url = self.url_edit.text().strip()
        dest = self.dest_edit.text().strip()
        if not url or not dest:
            QMessageBox.warning(self, "Missing fields", "URL and destination are required.")
            return

        branch = self.branch_edit.text().strip()
        depth_str = self.depth_edit.text().strip()
        depth = int(depth_str) if depth_str.isdigit() else 0

        self.clone_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_label.setText("Cloning…")

        self._worker = CloneWorker(url, dest, branch, depth)
        self._worker.progress.connect(lambda msg: self.log_label.setText(msg))
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, success: bool, info: str):
        self.progress_bar.setVisible(False)
        self.clone_btn.setEnabled(True)
        if success:
            self.log_label.setText(f"✓ Cloned to {info}")
            self.clone_done.emit(info)
            QTimer.singleShot(1000, self.accept)
        else:
            self.log_label.setText(f"✗ {info}")
            QMessageBox.critical(self, "Clone Failed", info)


class RemoteManagerDialog(QDialog):
    """Add, edit, delete, fetch remotes."""

    def __init__(self, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setWindowTitle("Remote Manager")
        self.setMinimumSize(600, 400)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Fetch URL", "Push URL"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tree.setStyleSheet(
            "QTreeWidget{background:#1e1e1e; color:#cccccc;}"
            "QTreeWidget::item:selected{background:#094771;}"
        )
        layout.addWidget(self.tree)

        actions = QHBoxLayout()
        for text, color, slot in [
            ("Add Remote",    "#0e6027", self._add),
            ("Edit URL",      "#0e4d91", self._edit),
            ("Delete Remote", "#6a1010", self._delete),
            ("Fetch All",     "#3a3a60", self._fetch_all),
            ("Fetch & Prune", "#3a3a60", self._fetch_prune),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(
                f"background:{color}; color:#fff; border:none; "
                f"padding:4px 10px; border-radius:3px;"
            )
            btn.clicked.connect(slot)
            actions.addWidget(btn)

        layout.addLayout(actions)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.accept)
        layout.addWidget(bb)

    def _load(self):
        self.tree.clear()
        try:
            for remote in self.backend.get_remotes():
                item = QTreeWidgetItem([remote.name, remote.fetch_url, remote.push_url])
                item.setForeground(0, QColor("#4ec9b0"))
                self.tree.addTopLevelItem(item)
        except GitError:
            pass

    def _selected_name(self) -> str:
        item = self.tree.currentItem()
        return item.text(0) if item else ""

    def _add(self):
        name, ok = QInputDialog.getText(self, "Add Remote", "Remote name:")
        if not ok or not name:
            return
        url, ok = QInputDialog.getText(self, "Add Remote", "URL:")
        if not ok or not url:
            return
        try:
            self.backend.add_remote(name, url)
            self._load()
        except GitError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _edit(self):
        name = self._selected_name()
        if not name:
            return
        url, ok = QInputDialog.getText(self, "Edit URL", "New URL:")
        if ok and url:
            try:
                self.backend.set_remote_url(name, url)
                self._load()
            except GitError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _delete(self):
        name = self._selected_name()
        if name and QMessageBox.question(
            self, "Delete", f"Remove remote '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            try:
                self.backend.remove_remote(name)
                self._load()
            except GitError as e:
                QMessageBox.warning(self, "Error", str(e))

    def _fetch_all(self):
        try:
            self.backend.fetch()
            QMessageBox.information(self, "Done", "Fetched all remotes.")
        except GitError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _fetch_prune(self):
        try:
            self.backend.fetch(prune=True)
            QMessageBox.information(self, "Done", "Fetched and pruned.")
        except GitError as e:
            QMessageBox.warning(self, "Error", str(e))
