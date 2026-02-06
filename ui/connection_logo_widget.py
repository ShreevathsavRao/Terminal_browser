from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QImage, qRed, qGreen, qBlue, qAlpha, qRgba
import os
import sys
try:
    from PyQt5.QtSvg import QSvgRenderer
except Exception:
    QSvgRenderer = None


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ConnectionLogoWidget(QWidget):
    """Clickable logo widget showing connection state.

    States:
      - connected (green)
      - probing (rotating ring)
      - offline (red)

    Emits `clicked` when user clicks the widget.
    """

    clicked = pyqtSignal()

    def __init__(self, parent=None, size: int = 48, svg_path: str = None):
        super().__init__(parent)
        self._base_state = 'offline'  # 'connected' or 'offline'
        self._probing = False
        self.setToolTip('Click to start probing')
        self._size = max(25, int(size))
        self.setFixedSize(QSize(self._size, max(20, int(self._size * 0.66))))
        # SVG paths for each state - use resource path resolver
        self._svg_green = get_resource_path('assets/network-connector-green.svg')
        self._svg_red = get_resource_path('assets/network-connector-red.svg')
        self._svg_probing = get_resource_path('assets/network-connector-probing.svg')
        self._svg_renderer = None
        self._update_svg_renderer()
        # Animation timer for rotating ring
        self._angle = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(80)
        self._anim_timer.timeout.connect(self._advance)

    def sizeHint(self):
        return QSize(self._size, max(20, int(self._size * 0.66)))

    def _advance(self):
        self._angle = (self._angle + 20) % 360
        self.update()

    def set_connected(self, val: bool):
        self._base_state = 'connected' if val else 'offline'
        if val:
            self.setToolTip('Connected — click to stop probing')
        else:
            self.setToolTip('Offline — click to start probing')
        self._update_svg_renderer()
        self.update()

    def set_svg(self, svg_path: str):
        """Load an SVG for the globe. Path may be absolute or relative."""
        if QSvgRenderer is None:
            self._svg_renderer = None
            return
        try:
            self._svg_renderer = QSvgRenderer(svg_path)
        except Exception:
            self._svg_renderer = None
            return

        # Prepare pixmaps for fast rendering and create tinted variants
        self._prepare_svg_pixmaps()
        self.update()

    def _prepare_svg_pixmaps(self):
        """Render the loaded SVG to a pixmap and create tinted connected/offline variants.

        Strategy:
        - Render SVG to square pixmap of size `self._size`.
        - Find the most common (dominant) non-transparent color — assumed to be the background circle.
        - Build a mask where pixels close to that color are selected.
        - Create two tinted images (connected/offline) by filling the mask with the desired color
          and compositing that onto the original SVG so other details remain intact.
        """
        if not self._svg_renderer or not self._svg_renderer.isValid():
            self._svg_pixmap = None
            self._svg_pixmap_connected = None
            self._svg_pixmap_offline = None
            return

        size_px = max(24, int(self._size))
        svg_pix = QPixmap(size_px, size_px)
        svg_pix.fill(Qt.transparent)
        p = QPainter(svg_pix)
        p.setRenderHint(QPainter.Antialiasing)
        try:
            self._svg_renderer.render(p, QRectF(0, 0, size_px, size_px))
        except Exception:
            pass
        p.end()

        img = svg_pix.toImage().convertToFormat(QImage.Format_ARGB32)

        # Build histogram of non-transparent colors
        color_count = {}
        w = img.width()
        h = img.height()
        for y in range(h):
            for x in range(w):
                px = img.pixel(x, y)
                a = qAlpha(px)
                if a < 16:
                    continue
                r = qRed(px); g = qGreen(px); b = qBlue(px)
                color_count[(r, g, b)] = color_count.get((r, g, b), 0) + 1

        if not color_count:
            self._svg_pixmap = QPixmap.fromImage(img)
            self._svg_pixmap_connected = self._svg_pixmap
            self._svg_pixmap_offline = self._svg_pixmap
            return

        # Most common color (assumed background)
        dominant = max(color_count.items(), key=lambda kv: kv[1])[0]
        dr, dg, db = dominant

        # Create mask image where pixels match dominant color within a tolerance
        mask = QImage(w, h, QImage.Format_ARGB32)
        mask.fill(0)
        tol = 40
        for y in range(h):
            for x in range(w):
                px = img.pixel(x, y)
                a = qAlpha(px)
                if a < 16:
                    continue
                r = qRed(px); g = qGreen(px); b = qBlue(px)
                if abs(r - dr) <= tol and abs(g - dg) <= tol and abs(b - db) <= tol:
                    mask.setPixel(x, y, qRgba(255, 255, 255, 255))

        def make_tinted(final_color: QColor):
            # color_img: solid color image
            color_img = QImage(w, h, QImage.Format_ARGB32)
            color_img.fill(qRgba(final_color.red(), final_color.green(), final_color.blue(), 255))

            # Apply mask by keeping only masked alpha
            # Use painter composition: DestinationIn with mask
            tmp = QImage(w, h, QImage.Format_ARGB32)
            tmp.fill(0)
            tp = QPainter(tmp)
            tp.drawImage(0, 0, color_img)
            tp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            tp.drawImage(0, 0, mask)
            tp.end()

            # Composite original SVG and colored mask
            final = QImage(w, h, QImage.Format_ARGB32)
            final.fill(0)
            fp = QPainter(final)
            fp.drawImage(0, 0, img)
            fp.drawImage(0, 0, tmp)
            fp.end()
            return QPixmap.fromImage(final)

        self._svg_pixmap = QPixmap.fromImage(img)
        self._svg_pixmap_connected = make_tinted(QColor('#4CAF50'))
        self._svg_pixmap_offline = make_tinted(QColor('#E53935'))

    def set_probing(self, val: bool):
        self._probing = bool(val)
        if self._probing:
            self.setToolTip('Probing network... click to stop')
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            if self._anim_timer.isActive():
                self._anim_timer.stop()
            if self._base_state == 'connected':
                self.setToolTip('Connected — click to stop probing')
            else:
                self.setToolTip('Offline — click to start probing')
        self._update_svg_renderer()
        self.update()

    def _update_svg_renderer(self):
        """Switch SVG based on state."""
        if QSvgRenderer is None:
            self._svg_renderer = None
            return
        if self._probing:
            path = self._svg_probing
        elif self._base_state == 'connected':
            path = self._svg_green
        else:
            path = self._svg_red
        try:
            # Check if file exists before loading
            if os.path.exists(path):
                self._svg_renderer = QSvgRenderer(path)
            else:
                self._svg_renderer = None
        except Exception:
            self._svg_renderer = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w // 2
        cy = h // 2 + 1

        # Draw the globe. If an SVG is provided, render it scaled into the
        # widget rect; otherwise draw a simple programmatic globe.
        pen = QPen(QColor('#222'))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        radius = min(w, h) * 0.34
        inner_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        if self._svg_renderer is not None and self._svg_renderer.isValid():
            svg_rect = QRectF(0, 0, inner_rect.width(), inner_rect.height())
            svg_rect.moveCenter(inner_rect.center())
            try:
                self._svg_renderer.render(painter, svg_rect)
            except Exception:
                painter.drawEllipse(inner_rect)
                painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
                painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        else:
            # Simple programmatic globe
            painter.drawEllipse(inner_rect)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawArc(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2), 0, 360 * 16)
            painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
            painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))

        # Draw colored outline according to base state (persistent)
        color = QColor('#4CAF50') if self._base_state == 'connected' else QColor('#E53935')
        pen = QPen(color)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(inner_rect)

        # If probing, draw a neutral (light) rotating ring overlay so it doesn't
        # obscure the base color. Use a light gray so it's visible on dark theme.
        if self._probing:
            ring_radius = radius + 6
            pen = QPen(QColor('#bdbdbd'))
            pen.setWidth(3)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            # draw several short arc segments rotated by angle
            for i in range(0, 360, 40):
                start = int((i + self._angle) * 16)
                span = int(18 * 16)
                painter.drawArc(int(cx - ring_radius), int(cy - ring_radius), int(ring_radius * 2), int(ring_radius * 2), start, span)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
