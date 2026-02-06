from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QPen, QColor


class NetworkStatusWidget(QWidget):
    """Small Wi‑Fi status indicator widget.

    Shows three arcs and a dot; green when online, red when offline.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._online = False
        self.setToolTip("Network: Unknown")
        self.setFixedSize(QSize(28, 28))

    def sizeHint(self):
        return QSize(28, 28)

    def set_status(self, online: bool):
        """Set current network status and refresh display."""
        self._online = bool(online)
        self.setToolTip("Online" if self._online else "Offline")
        self.update()

    # Provide compatibility alias for signal connection
    setOnline = set_status

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Determine color
        color = QColor('#4CAF50') if self._online else QColor('#E53935')

        # Background is transparent - draw arcs centered
        w = self.width()
        h = self.height()
        center_x = w / 2
        center_y = h / 2 + 2

        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)

        # Draw three arcs (representing wifi waves)
        # Use decreasing radii
        for i, radius in enumerate([10, 6, 2]):
            rect_side = radius * 2
            rect_x = center_x - radius
            rect_y = center_y - radius
            # drawArc expects QRect and angles in 1/16th degrees
            # Draw a semicircular arc (approx from 200 deg to -20 deg)
            start_angle = int(200 * 16)
            span_angle = int(140 * 16)
            painter.drawArc(int(rect_x), int(rect_y), int(rect_side), int(rect_side), start_angle, span_angle)

        # Draw small center dot
        dot_radius = 2
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(center_x - dot_radius), int(center_y - dot_radius), dot_radius * 2, dot_radius * 2)
