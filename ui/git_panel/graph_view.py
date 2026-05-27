"""Commit graph view — visual git log with colored branch lanes."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QScrollArea,
    QLabel, QLineEdit, QPushButton, QComboBox, QMenu, QAction,
    QAbstractItemView, QHeaderView, QFrame, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QInputDialog, QMessageBox,
    QTextEdit, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QPainterPath, QLinearGradient
)
from .git_backend import GitBackend, Commit, GitError

# Lane colors (cycling)
LANE_COLORS = [
    QColor("#4ec9b0"),  # teal
    QColor("#ce9178"),  # orange
    QColor("#569cd6"),  # blue
    QColor("#c586c0"),  # purple
    QColor("#4fc1ff"),  # light blue
    QColor("#dcdcaa"),  # yellow
    QColor("#f44747"),  # red
    QColor("#b5cea8"),  # green
]

ROW_H = 24
HEADER_H = 22
LANE_W = 14          # narrower lanes so graph doesn't dominate
NODE_R = 4
MAX_LANES = 16       # cap visible lanes; repos with more still draw, just squeezed
NUM_COL_W = 44
MSG_COL_W = 280
AUTHOR_COL_W = 130
DATE_COL_W = 125
HASH_COL_W = 70


class GraphCanvas(QWidget):
    """Custom-painted widget that draws the commit graph + rows."""

    commit_clicked = pyqtSignal(object)   # Commit
    commit_right_clicked = pyqtSignal(object, QPoint)
    columns_changed = pyqtSignal()        # emitted when column widths change

    # Column resize constants (used by GraphHeader too)
    _RESIZE_NONE   = 0
    _RESIZE_MSG    = 1
    _RESIZE_AUTHOR = 2
    _RESIZE_DATE   = 3
    _SEP_HIT = 4   # px either side of separator counts as a hit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commits: list = []
        self.selected_idx: int = -1
        self.compare_idx: int = -1
        self._font = QFont("Menlo", 11)
        self._bold_font = QFont("Menlo", 11)
        self._bold_font.setBold(True)
        self._fm = QFontMetrics(self._font)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._hover_idx = -1
        self._gw = LANE_W * 4
        # Mutable column widths (dragged via GraphHeader)
        self.num_w    = NUM_COL_W
        self.msg_w    = MSG_COL_W
        self.author_w = AUTHOR_COL_W
        self.date_w   = DATE_COL_W
        self.hash_w   = HASH_COL_W
        # Multi-click tracking
        self._click_count = 0
        self._click_row   = -1
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(400)
        self._click_timer.timeout.connect(self._reset_clicks)
        # Search highlight
        self._highlight_query = ""

    def set_commits(self, commits: list):
        self.commits = commits
        self.selected_idx = -1
        self.compare_idx = -1
        max_lane = max((c.lane for c in commits), default=0)
        visible_lanes = min(max_lane + 2, MAX_LANES + 1)
        self._gw = visible_lanes * LANE_W
        self._update_size()
        self.update()

    def _update_size(self):
        total_w = self.num_w + self._gw + self.msg_w + self.author_w + self.date_w + self.hash_w
        total_h = ROW_H * max(len(self.commits), 1)
        self.setMinimumSize(total_w, total_h)
        self.columns_changed.emit()

    def _sep_x(self):
        """Return x positions of the column separators (canvas coords)."""
        x1 = self.num_w + self._gw + self.msg_w
        x2 = x1 + self.author_w
        x3 = x2 + self.date_w
        return x1, x2, x3

    def _row_y(self, idx: int) -> int:
        return idx * ROW_H

    def _lane_x(self, lane: int) -> int:
        effective = min(lane, MAX_LANES)
        return self.num_w + effective * LANE_W + LANE_W // 2

    def _graph_width(self) -> int:
        return getattr(self, '_gw', LANE_W * 4)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self._font)
        painter.setRenderHint(QPainter.Antialiasing)

        gw = self._graph_width()
        x1, x2, x3 = self._sep_x()

        clip = event.rect()
        start_row = max(0, clip.top() // ROW_H - 1)
        end_row = min(len(self.commits), clip.bottom() // ROW_H + 2)

        # Draw rows
        for i in range(start_row, end_row):
            c = self.commits[i]
            y = self._row_y(i)
            row_rect = QRect(0, y, self.width(), ROW_H)

            # Background
            if i == self.selected_idx:
                painter.fillRect(row_rect, QColor("#264f78"))
            elif i == self.compare_idx:
                painter.fillRect(row_rect, QColor("#3a3a00"))
            elif i == self._hover_idx:
                painter.fillRect(row_rect, QColor("#2a2d2e"))
            else:
                bg = QColor("#1e1e1e") if i % 2 == 0 else QColor("#252526")
                painter.fillRect(row_rect, bg)

            # Draw graph lines to parents
            node_x = self._lane_x(c.lane)
            node_y = y + ROW_H // 2
            color = LANE_COLORS[c.color_idx % len(LANE_COLORS)]

            # Lines to children (draw line from this commit down to next in same lane)
            if i + 1 < len(self.commits):
                next_c = self.commits[i + 1]
                # Continuous lane lines
                for lane_idx in range(max(c.lane, next_c.lane) + 1):
                    lx = self._lane_x(lane_idx)
                    if lane_idx <= min(c.lane, next_c.lane):
                        lcolor = LANE_COLORS[lane_idx % len(LANE_COLORS)]
                        pen = QPen(lcolor, 2)
                        painter.setPen(pen)
                        painter.drawLine(lx, node_y, lx, node_y + ROW_H)

            # Lines to parents
            for pi, parent_hash in enumerate(c.parents):
                parent_idx = next(
                    (j for j, pc in enumerate(self.commits) if pc.hash == parent_hash),
                    None
                )
                if parent_idx is not None:
                    parent_c = self.commits[parent_idx]
                    px = self._lane_x(parent_c.lane)
                    py = self._row_y(parent_idx) + ROW_H // 2
                    p_color = LANE_COLORS[parent_c.color_idx % len(LANE_COLORS)]
                    pen = QPen(p_color if pi > 0 else color, 2)
                    painter.setPen(pen)
                    if node_x == px:
                        painter.drawLine(node_x, node_y, px, py)
                    else:
                        path = QPainterPath()
                        path.moveTo(node_x, node_y)
                        mid_y = (node_y + py) // 2
                        path.cubicTo(node_x, mid_y, px, mid_y, px, py)
                        painter.drawPath(path)

            # Draw node circle
            painter.setPen(QPen(color.darker(130), 1))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPoint(node_x, node_y), NODE_R, NODE_R)

            # ── Number column ──────────────────────────────────────────────────
            painter.save()
            painter.setClipRect(QRect(0, y, self.num_w, ROW_H), Qt.IntersectClip)
            num = len(self.commits) - i
            painter.setFont(self._font)
            painter.setPen(QColor("#555555"))
            painter.drawText(2, y, self.num_w - 6, ROW_H,
                             Qt.AlignVCenter | Qt.AlignRight, str(num))
            painter.restore()

            # ── Message column: badges + subject, hard-clipped to x1 ──────────
            painter.save()
            painter.setClipRect(QRect(self.num_w, y, x1 - self.num_w, ROW_H), Qt.IntersectClip)

            label_x = self.num_w + gw + 4
            for ref in c.refs:
                if not ref:
                    continue
                is_remote = "/" in ref and not ref.startswith("tag:")
                is_tag = ref.startswith("tag:")
                display = ref.replace("tag:", "").replace("HEAD -> ", "")
                badge_color = (
                    QColor("#b04040") if is_tag
                    else QColor("#2d5a8e") if is_remote
                    else QColor("#0e6027")
                )
                tw = self._fm.horizontalAdvance(display) + 8
                badge_rect = QRect(label_x, y + 4, tw, ROW_H - 8)
                painter.setBrush(QBrush(badge_color))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(badge_rect, 3, 3)
                painter.setPen(QColor("#ffffff"))
                painter.setFont(self._font)
                painter.drawText(badge_rect, Qt.AlignCenter, display)
                label_x += tw + 4

            available_w = x1 - label_x - 4
            if available_w > 20:
                self._draw_with_highlight(painter, c.subject, self._highlight_query,
                                          label_x, y, available_w, ROW_H, QColor("#cccccc"))
            painter.restore()

            # ── Author column, hard-clipped to [x1, x2] ────────────────────
            painter.save()
            painter.setClipRect(QRect(x1, y, self.author_w, ROW_H), Qt.IntersectClip)
            self._draw_with_highlight(painter, c.author, self._highlight_query,
                                      x1 + 4, y, self.author_w - 8, ROW_H, QColor("#9cdcfe"))
            painter.restore()

            # ── Date column, hard-clipped to [x2, x3] ──────────────────────
            painter.save()
            painter.setClipRect(QRect(x2, y, self.date_w, ROW_H), Qt.IntersectClip)
            self._draw_with_highlight(painter, c.date, self._highlight_query,
                                      x2 + 4, y, self.date_w - 8, ROW_H, QColor("#808080"))
            painter.restore()

            # ── Hash column, hard-clipped to [x3, x3+hash_w] ───────────────
            painter.save()
            painter.setClipRect(QRect(x3, y, self.hash_w, ROW_H), Qt.IntersectClip)
            self._draw_with_highlight(painter, c.short_hash, self._highlight_query,
                                      x3 + 4, y, self.hash_w - 4, ROW_H, QColor("#f1e05a"),
                                      bold=True)
            painter.restore()

            # ── Column separator lines (drawn after, no clip) ───────────────
            painter.setFont(self._font)
            painter.setPen(QPen(QColor("#3c3c3c"), 1))
            for sx in (self.num_w, x1, x2, x3):
                painter.drawLine(sx, y, sx, y + ROW_H - 1)

    def _draw_with_highlight(self, painter, text, q, rx, ry, rw, rh, base_color, bold=False):
        font = self._bold_font if bold else self._font
        fm = QFontMetrics(font)
        painter.setFont(font)
        display = fm.elidedText(text, Qt.ElideRight, rw)
        painter.setPen(base_color)
        painter.drawText(rx, ry, rw, rh, Qt.AlignVCenter | Qt.AlignLeft, display)
        if not q:
            return
        idx = display.lower().find(q.lower())
        if idx == -1:
            return
        pre_w = fm.horizontalAdvance(display[:idx])
        match_w = fm.horizontalAdvance(display[idx:idx + len(q)])
        painter.fillRect(QRect(rx + pre_w, ry + 3, match_w, rh - 6), QColor("#c5a000"))
        painter.setPen(QColor("#1a1a1a"))
        painter.drawText(rx + pre_w, ry, match_w, rh, Qt.AlignVCenter | Qt.AlignLeft,
                         display[idx:idx + len(q)])

    def _reset_clicks(self):
        self._click_count = 0
        self._click_row   = -1

    def _cell_value(self, commit, x: int) -> str:
        """Return the value of whichever column x falls in."""
        x1, x2, x3 = self._sep_x()
        if x >= x3:
            return commit.hash
        if x >= x2:
            return commit.date
        if x >= x1:
            return commit.author
        return commit.subject

    def _row_text(self, commit) -> str:
        return f"{commit.hash}\t{commit.subject}\t{commit.author}\t{commit.date}"

    def mousePressEvent(self, event):
        idx = event.y() // ROW_H
        if 0 <= idx < len(self.commits):
            if event.button() == Qt.LeftButton:
                # Track click sequence on the same row
                if idx == self._click_row and self._click_timer.isActive():
                    self._click_count += 1
                else:
                    self._click_count = 1
                    self._click_row = idx
                self._click_timer.start()

                if self._click_count == 1:
                    # Single click: select row
                    if event.modifiers() & Qt.ControlModifier:
                        self.compare_idx = idx
                    else:
                        self.selected_idx = idx
                        self.compare_idx = -1
                    self.commit_clicked.emit(self.commits[idx])
                    self.update()
                elif self._click_count == 3:
                    # Triple click: copy full row
                    QApplication.clipboard().setText(self._row_text(self.commits[idx]))
                    self._click_count = 0
                # 2nd click (double) is handled by mouseDoubleClickEvent

            elif event.button() == Qt.RightButton:
                self.selected_idx = idx
                self.update()
                self.commit_right_clicked.emit(self.commits[idx], event.globalPos())

    def mouseDoubleClickEvent(self, event):
        idx = event.y() // ROW_H
        if 0 <= idx < len(self.commits) and event.button() == Qt.LeftButton:
            text = self._cell_value(self.commits[idx], event.x())
            QApplication.clipboard().setText(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            if 0 <= self.selected_idx < len(self.commits):
                QApplication.clipboard().setText(
                    self._row_text(self.commits[self.selected_idx])
                )
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        idx = event.y() // ROW_H
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()

    def leaveEvent(self, event):
        self._hover_idx = -1
        self.update()


class GraphHeader(QWidget):
    """Fixed column-header bar that stays pinned above the scrollable canvas.

    Syncs with the horizontal scroll position so labels always line up with
    the canvas columns. Also owns the column drag-to-resize interaction.
    """

    def __init__(self, canvas: "GraphCanvas", scroll_area, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.scroll_area = scroll_area
        self.setFixedHeight(HEADER_H)
        self.setMouseTracking(True)
        self._font = QFont("Menlo", 10)
        self._resize_col   = GraphCanvas._RESIZE_NONE
        self._resize_start_x = 0
        self._resize_start_w = 0
        scroll_area.horizontalScrollBar().valueChanged.connect(self.update)
        canvas.columns_changed.connect(self.update)

    def _sep_x(self):
        """Separator x positions in *widget* (screen) coordinates."""
        c = self.canvas
        offset = self.scroll_area.horizontalScrollBar().value()
        x0 = c.num_w - offset
        x1 = x0 + c._gw + c.msg_w
        x2 = x1 + c.author_w
        x3 = x2 + c.date_w
        return x0, x1, x2, x3

    def _col_at(self, x):
        _, x1, x2, x3 = self._sep_x()
        for col, sx in zip(
            (GraphCanvas._RESIZE_MSG, GraphCanvas._RESIZE_AUTHOR, GraphCanvas._RESIZE_DATE),
            (x1, x2, x3)
        ):
            if abs(x - sx) <= GraphCanvas._SEP_HIT:
                return col
        return GraphCanvas._RESIZE_NONE

    def paintEvent(self, event):
        painter = QPainter(self)
        c = self.canvas
        offset = self.scroll_area.horizontalScrollBar().value()
        x0, x1, x2, x3 = self._sep_x()

        painter.fillRect(self.rect(), QColor("#252526"))
        painter.setFont(self._font)

        for text, sx, w in [
            ("#",              -offset,       c.num_w),
            ("Graph / Message", x0,           c.msg_w),
            ("Author",          x1,           c.author_w),
            ("Date",            x2,           c.date_w),
            ("Hash",            x3,           c.hash_w),
        ]:
            draw_x = max(sx, 0)
            draw_w = max(w - (draw_x - sx) - 4, 0)
            painter.setPen(QColor("#888888"))
            painter.drawText(draw_x + 4, 0, draw_w, HEADER_H,
                             Qt.AlignVCenter | Qt.AlignLeft, text)

        painter.setPen(QPen(QColor("#555555"), 1))
        for sx in (x0, x1, x2, x3):
            if 0 <= sx <= self.width():
                painter.drawLine(sx, 2, sx, HEADER_H - 2)

        painter.setPen(QPen(QColor("#3c3c3c"), 1))
        painter.drawLine(0, HEADER_H - 1, self.width(), HEADER_H - 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            col = self._col_at(event.x())
            if col != GraphCanvas._RESIZE_NONE:
                self._resize_col = col
                self._resize_start_x = event.x()
                c = self.canvas
                self._resize_start_w = {
                    GraphCanvas._RESIZE_MSG:    c.msg_w,
                    GraphCanvas._RESIZE_AUTHOR: c.author_w,
                    GraphCanvas._RESIZE_DATE:   c.date_w,
                }[col]

    def mouseReleaseEvent(self, event):
        self._resize_col = GraphCanvas._RESIZE_NONE

    def mouseMoveEvent(self, event):
        if self._resize_col != GraphCanvas._RESIZE_NONE and (event.buttons() & Qt.LeftButton):
            delta = event.x() - self._resize_start_x
            new_w = max(60, self._resize_start_w + delta)
            c = self.canvas
            if self._resize_col == GraphCanvas._RESIZE_MSG:
                c.msg_w = new_w
            elif self._resize_col == GraphCanvas._RESIZE_AUTHOR:
                c.author_w = new_w
            elif self._resize_col == GraphCanvas._RESIZE_DATE:
                c.date_w = new_w
            c._update_size()
            c.update()
            return
        if self._col_at(event.x()) != GraphCanvas._RESIZE_NONE:
            self.setCursor(Qt.SplitHCursor)
        else:
            self.setCursor(Qt.ArrowCursor)


class CommitDetailPanel(QWidget):
    """Right panel showing commit details and file diffs."""

    def __init__(self, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Commit info — read-only QTextEdit so text is fully selectable
        # (single click = cursor, double = word, triple = line, Ctrl+A/C work natively)
        self.info_edit = QTextEdit()
        self.info_edit.setReadOnly(True)
        self.info_edit.setMaximumHeight(80)
        self.info_edit.setFont(QFont("Menlo", 10))
        self.info_edit.setStyleSheet(
            "QTextEdit { background:#252526; color:#cccccc; border:none; padding:4px; }"
            "QScrollBar:vertical { width:0; border:none; }"
        )
        layout.addWidget(self.info_edit)

        # File list
        _tree_ss = (
            "QTreeWidget { background:#1e1e1e; color:#cccccc; border:1px solid #3c3c3c; }"
            "QTreeWidget::item:selected { background:#094771; }"
            "QScrollBar:vertical { background:#2d2d2d; width:10px; }"
            "QScrollBar::handle:vertical { background:#555; border-radius:5px; min-height:20px; }"
            "QScrollBar::handle:vertical:hover { background:#777; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
        )
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Status", "File"])
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.file_tree.setStyleSheet(_tree_ss)
        self.file_tree.itemClicked.connect(self._on_file_clicked)
        self.file_tree.setMaximumHeight(180)
        # Right-click to copy file path
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._file_tree_menu)
        layout.addWidget(self.file_tree)

        # Diff view
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Menlo", 11))
        self.diff_view.setStyleSheet(
            "QTextEdit { background:#1e1e1e; color:#cccccc; border:1px solid #3c3c3c; }"
            "QScrollBar:vertical { background:#2d2d2d; width:10px; }"
            "QScrollBar::handle:vertical { background:#555; border-radius:5px; min-height:20px; }"
            "QScrollBar::handle:vertical:hover { background:#777; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
            "QScrollBar:horizontal { background:#2d2d2d; height:10px; }"
            "QScrollBar::handle:horizontal { background:#555; border-radius:5px; min-width:20px; }"
            "QScrollBar::handle:horizontal:hover { background:#777; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }"
        )
        layout.addWidget(self.diff_view)

        self._current_hash = ""

    def show_commit(self, commit: Commit):
        self._current_hash = commit.hash
        detail = self.backend.get_commit_detail(commit.hash)
        text = (f"<b>{detail['subject']}</b><br>"
                f"<span style='color:#9cdcfe'>{detail['author']}</span> "
                f"<span style='color:#808080'>{detail['date']}</span><br>"
                f"<span style='color:#f1e05a'>{commit.hash}</span>")
        self.info_edit.setHtml(text)

        self.file_tree.clear()
        STATUS_ICONS = {"M": ("M", "#dcdcaa"), "A": ("A", "#4ec9b0"),
                        "D": ("D", "#f44747"), "R": ("R", "#569cd6"),
                        "C": ("C", "#c586c0")}
        for fs in self.backend.get_commit_files(commit.hash):
            icon, color = STATUS_ICONS.get(fs.status, (fs.status, "#cccccc"))
            item = QTreeWidgetItem([icon, fs.path])
            item.setForeground(0, QColor(color))
            item.setData(0, Qt.UserRole, fs)
            self.file_tree.addTopLevelItem(item)

        self.diff_view.clear()

    def _file_tree_menu(self, pos):
        item = self.file_tree.itemAt(pos)
        if not item:
            return
        fs = item.data(0, Qt.UserRole)
        if not fs:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#2d2d2d;color:#cccccc;border:1px solid #555;}"
            "QMenu::item:selected{background:#094771;}"
        )
        menu.addAction("Copy path",   lambda: QApplication.clipboard().setText(fs.path))
        menu.addAction("Copy status", lambda: QApplication.clipboard().setText(fs.status))
        menu.addAction("Copy both",   lambda: QApplication.clipboard().setText(f"{fs.status}\t{fs.path}"))
        menu.exec_(self.file_tree.mapToGlobal(pos))

    def _on_file_clicked(self, item, col):
        fs = item.data(0, Qt.UserRole)
        if fs and self._current_hash:
            diff = self.backend.get_diff_between(
                f"{self._current_hash}^", self._current_hash, fs.path
            )
            self._render_diff(diff)

    def _render_diff(self, diff: str):
        self.diff_view.clear()
        cursor = self.diff_view.textCursor()
        from PyQt5.QtGui import QTextCharFormat
        fmt_normal = QTextCharFormat()
        fmt_normal.setForeground(QColor("#cccccc"))
        fmt_add = QTextCharFormat()
        fmt_add.setForeground(QColor("#4ec9b0"))
        fmt_add.setBackground(QColor("#0d2b1a"))
        fmt_del = QTextCharFormat()
        fmt_del.setForeground(QColor("#f44747"))
        fmt_del.setBackground(QColor("#2b0d0d"))
        fmt_hunk = QTextCharFormat()
        fmt_hunk.setForeground(QColor("#569cd6"))

        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                cursor.setCharFormat(fmt_add)
            elif line.startswith("-") and not line.startswith("---"):
                cursor.setCharFormat(fmt_del)
            elif line.startswith("@@"):
                cursor.setCharFormat(fmt_hunk)
            else:
                cursor.setCharFormat(fmt_normal)
            cursor.insertText(line + "\n")
        self.diff_view.setTextCursor(cursor)


class GraphView(QWidget):
    """Full commit graph view: toolbar + graph + detail panel."""

    def __init__(self, backend: GitBackend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self._build_ui()
        self._load_commits()

    # Shared scrollbar + splitter stylesheet applied to the whole view
    _SCROLL_STYLE = """
        QScrollBar:vertical {
            background: #2d2d2d; width: 10px; margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #555; min-height: 24px; border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover { background: #777; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal {
            background: #2d2d2d; height: 10px; margin: 0;
        }
        QScrollBar::handle:horizontal {
            background: #555; min-width: 24px; border-radius: 5px;
        }
        QScrollBar::handle:horizontal:hover { background: #777; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QSplitter::handle { background: #3c3c3c; }
        QSplitter::handle:horizontal { width: 3px; }
        QSplitter::handle:vertical   { height: 3px; }
        QSplitter::handle:hover { background: #569cd6; }
    """

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setStyleSheet(self._SCROLL_STYLE)

        # search_box and branch_filter are created as attributes but NOT placed
        # into any layout here — GitPanel owns and places them in its graph
        # toolbar row (between the tab buttons and the content stack).
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search commits (message, author, hash)…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setStyleSheet(
            "QLineEdit { background:#3c3c3c; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:3px 6px; }"
        )
        self.search_box.textChanged.connect(lambda _: self._search())

        self.branch_filter = QComboBox()
        self.branch_filter.setFixedWidth(160)
        self.branch_filter.setStyleSheet(
            "QComboBox { background:#3c3c3c; color:#cccccc; border:1px solid #555; "
            "border-radius:3px; padding:2px 4px; }"
        )
        self.branch_filter.addItem("All branches")

        # Splitter: [header + graph scroll] | detail
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)

        # Left pane: fixed header + scrollable canvas
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.graph_scroll = QScrollArea()
        self.graph_scroll.setWidgetResizable(False)
        self.graph_scroll.setStyleSheet("background:#1e1e1e; border:none;")
        self.graph_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.graph_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.canvas = GraphCanvas()
        self.canvas.commit_clicked.connect(self._on_commit_clicked)
        self.canvas.commit_right_clicked.connect(self._on_commit_right_click)
        self.graph_scroll.setWidget(self.canvas)

        # Fixed header that mirrors horizontal scroll and owns column resize
        self.graph_header = GraphHeader(self.canvas, self.graph_scroll)

        left_layout.addWidget(self.graph_header)
        left_layout.addWidget(self.graph_scroll)

        splitter.addWidget(left_pane)

        # Detail panel
        self.detail = CommitDetailPanel(self.backend)
        self.detail.setMinimumWidth(320)
        splitter.addWidget(self.detail)
        splitter.setSizes([900, 320])

        layout.addWidget(splitter)

    def _load_commits(self):
        try:
            self._all_commits = self.backend.get_commits()
            self.canvas.set_commits(self._all_commits)
            # Populate branch filter
            self.branch_filter.clear()
            self.branch_filter.addItem("All branches")
            for b in self.backend.get_branches():
                self.branch_filter.addItem(b["name"])
        except GitError:
            self._all_commits = []
            self.canvas.set_commits([])

    def _search(self):
        q = self.search_box.text().strip()
        ql = q.lower()
        all_commits = getattr(self, "_all_commits", [])
        self.canvas._highlight_query = ql
        if not ql:
            self.canvas.set_commits(all_commits)
            return
        filtered = [
            c for c in all_commits
            if ql in c.subject.lower()
            or ql in c.author.lower()
            or ql in c.hash.lower()
        ]
        self.canvas.set_commits(filtered)

    def _on_commit_clicked(self, commit: Commit):
        self.detail.show_commit(commit)

    def _on_commit_right_click(self, commit: Commit, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#2d2d2d;color:#cccccc;border:1px solid #555;}"
            "QMenu::item:selected{background:#094771;}"
        )

        def action(text, slot):
            a = menu.addAction(text)
            a.triggered.connect(lambda: slot(commit))
            return a

        action("Checkout commit", self._checkout_commit)
        action("Cherry-pick", self._cherry_pick)
        action("Revert commit", self._revert_commit)
        menu.addSeparator()
        action("Create branch here", self._create_branch)
        action("Create tag here", self._create_tag)
        menu.addSeparator()
        action("Copy message",    lambda c: self._copy(c.subject))
        action("Copy author",     lambda c: self._copy(c.author))
        action("Copy date",       lambda c: self._copy(c.date))
        action("Copy short hash", lambda c: self._copy(c.short_hash))
        action("Copy full hash",  lambda c: self._copy(c.hash))
        action("Copy row",        lambda c: self._copy(self.canvas._row_text(c)))

        menu.exec_(pos)

    def _checkout_commit(self, commit):
        self._run_op(lambda: self.backend.checkout(commit.hash))

    def _cherry_pick(self, commit):
        self._run_op(lambda: self.backend.cherry_pick(commit.hash))

    def _revert_commit(self, commit):
        self._run_op(lambda: self.backend.revert_commit(commit.hash, no_commit=True))

    def _create_branch(self, commit):
        name, ok = QInputDialog.getText(self, "Create Branch", "Branch name:")
        if ok and name:
            self._run_op(lambda: self.backend.create_branch(name, commit.hash))

    def _create_tag(self, commit):
        name, ok = QInputDialog.getText(self, "Create Tag", "Tag name:")
        if ok and name:
            self._run_op(lambda: self.backend.create_tag(name, commit.hash))

    def _copy(self, text: str):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _run_op(self, op):
        try:
            op()
            self._load_commits()
        except GitError as e:
            QMessageBox.warning(self, "Git Error", str(e))
