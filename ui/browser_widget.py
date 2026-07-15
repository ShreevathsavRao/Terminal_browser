"""Integrated web browser tool widget.

A lightweight browser panel built on QWebEngineView with a navigation
toolbar (back / forward / reload / home), an editable address bar, and a
progress indicator. Designed to be embedded as a "tool" tab alongside the
terminal tabs.
"""

from qtpy.QtCore import Qt, QUrl, Signal, QPoint, QTimer, QSize
from qtpy.QtGui import QColor, QPixmap, QPainter, QPen, QPolygon, QIcon
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QToolButton, QProgressBar, QSizePolicy, QSplitter,
                             QSlider)

try:
    from qtpy.QtMultimedia import QMediaPlayer, QAudioOutput
    from qtpy.QtMultimediaWidgets import QVideoWidget, QGraphicsVideoItem
    MULTIMEDIA_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    QMediaPlayer = QAudioOutput = QVideoWidget = QGraphicsVideoItem = None
    MULTIMEDIA_AVAILABLE = False

try:
    from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    WEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    QWebEngineView = None
    QWebEnginePage = None
    WEBENGINE_AVAILABLE = False

# Qt6 bundles Chromium 118+ which natively supports CSS cascade layers
# (@layer) and :has()/:is()/:where(), so the legacy CSS-downgrade shim is only
# needed on the old Qt5/Chromium 87 engine.
try:
    from qtpy import QtCore as _qtcore
    _MODERN_ENGINE = int(_qtcore.__version__.split(".")[0]) >= 6
except Exception:
    _MODERN_ENGINE = False


DEFAULT_HOME = "https://www.google.com"


class _BrowserWebPage(QWebEnginePage if WEBENGINE_AVAILABLE else object):
    """Page that keeps direct-media navigations inline (YouTube-style).

    Many sites (e.g. tube sites) wire their play button to *navigate* the
    whole tab to the raw ``.mp4``/``.m3u8`` file, throwing away the page you
    were on. Here we catch that main-frame navigation, cancel it, and instead
    tell the owner to pop the video up in an in-page overlay player so the
    original page stays put — just like clicking play on YouTube.
    """

    def __init__(self, profile, owner):
        super().__init__(profile, owner)
        self._owner = owner

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        try:
            if is_main_frame and self._owner is not None:
                media = QWebEnginePage.NavigationTypeTyped
                back_fwd = QWebEnginePage.NavigationTypeBackForward
                reload_t = QWebEnginePage.NavigationTypeReload
                # Only hijack link/JS-driven jumps to a media file, never the
                # user typing a URL, reloading, or using back/forward.
                if nav_type not in (media, back_fwd, reload_t) \
                        and self._owner._url_is_media(url):
                    self._owner._play_inline(url.toString())
                    return False
        except Exception:
            pass
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class _FullScreenHost(QWidget):
    """Top-level black window that hosts the web view during HTML5 fullscreen.

    Reparenting into a dedicated container (rather than turning the web view
    itself into a window) keeps Chromium's render surface intact, so returning
    from fullscreen no longer leaves a blank page. Also catches Esc to exit.
    """

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setWindowFlags(Qt.Window)
        self.setStyleSheet("background:#000;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._layout = lay

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._owner._request_exit_fullscreen()
        else:
            super().keyPressEvent(event)


class _ClickSlider(QSlider):
    """QSlider that seeks to the clicked position (YouTube-style).

    A plain QSlider only moves when you drag the handle or page-steps on a
    groove click, so a single click on the seek bar wouldn't jump to that
    time. This maps a click (and drag) straight to the position under the
    cursor and emits ``sliderMoved`` so the player seeks there.
    """

    def _value_at(self, event):
        from qtpy.QtWidgets import QStyle
        try:
            pt = event.position().toPoint()
        except Exception:
            pt = event.pos()
        if self.orientation() == Qt.Horizontal:
            return QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), pt.x(), self.width())
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), pt.y(), self.height(), True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.maximum() > self.minimum():
            val = self._value_at(event)
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.setSliderDown(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown() and (event.buttons() & Qt.LeftButton):
            val = self._value_at(event)
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.isSliderDown():
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _VideoCanvas(QWidget):
    """Paints QMediaPlayer frames via a QVideoSink (no native video layer).

    On macOS a native video surface (QVideoWidget / QGraphicsVideoItem) is
    composited *above* the Qt widget layer and swallows mouse input, so the
    player's own buttons/seek bar can't be clicked and clicks fall through to
    the web view underneath. By pulling frames from a QVideoSink and painting
    them ourselves, the video becomes ordinary Qt-painted content: it respects
    z-order and receives mouse events like any other widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from qtpy.QtMultimedia import QVideoSink
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._image = None
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._on_frame)

    def _on_frame(self, frame):
        try:
            img = frame.toImage()
        except Exception:
            img = None
        if img is not None and not img.isNull() and self._image is None:
            print("PLAYER: first frame", img.width(), "x", img.height(), flush=True)
        self._image = img if (img is not None and not img.isNull()) else None
        self.update()

    def mousePressEvent(self, event):
        owner = self.parent()
        if event.button() == Qt.LeftButton and hasattr(owner, '_on_video_click'):
            owner._on_video_click()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        owner = self.parent()
        if event.button() == Qt.LeftButton and hasattr(owner, '_on_video_double_click'):
            owner._on_video_double_click()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        owner = self.parent()
        if hasattr(owner, '_show_controls'):
            owner._show_controls()
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        from qtpy.QtGui import QPainter
        from qtpy.QtCore import QRect
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)
        img = self._image
        if img is not None and not img.isNull():
            target = self.rect()
            scaled = img.size().scaled(target.size(), Qt.KeepAspectRatio)
            x = (target.width() - scaled.width()) // 2
            y = (target.height() - scaled.height()) // 2
            painter.drawImage(QRect(x, y, scaled.width(), scaled.height()), img)
        painter.end()


class NativeVideoOverlay(QWidget):
    """A Chrome-style video player that plays with Qt Multimedia.

    The bundled QtWebEngine has no H.264/AAC codecs, so most ``.mp4`` streams
    (e.g. tube sites) won't play in-page. This overlay decodes them through
    Qt Multimedia — on macOS that's AVFoundation, which supports H.264/AAC —
    so the video actually plays. Shown on top of the web view when a media
    link is opened.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from qtpy.QtWidgets import QPushButton, QLabel
        # Embedded child overlay: the player is drawn ON TOP of the web view
        # *inside* the tab, so it never floats as a separate window and is
        # hidden automatically when the user switches tabs (no orphan players
        # from background tabs). On macOS the web view is a native surface, so
        # the overlay must itself be a native widget to composite above it.
        self._embed_parent = parent
        self._is_fullscreen = False
        self._reparenting = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background:#000;")
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)

        # Paint frames ourselves via a QVideoSink instead of a native video
        # surface. On macOS a native video layer renders above Qt widgets and
        # swallows mouse input; a sink we paint keeps the player fully in-tab
        # and clickable (buttons, seek bar) with no click-through.
        self._view = _VideoCanvas(self)
        self._view.setStyleSheet("background:#000;")
        self._view.setFocusPolicy(Qt.NoFocus)
        self._player.setVideoSink(self._view.sink)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar: close button.
        top = QHBoxLayout()
        top.setContentsMargins(8, 6, 8, 6)
        top.addStretch(1)
        self._close_btn = QPushButton("\u2715 Close")
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(
            "QPushButton{background:#e84393;color:#fff;border:none;"
            "border-radius:6px;padding:6px 12px;font-weight:600;}"
            "QPushButton:hover{background:#d63384;}")
        self._close_btn.clicked.connect(self.stop_and_hide)
        top.addWidget(self._close_btn)
        root.addLayout(top)

        root.addWidget(self._view, 1)

        # Bottom control bar: play/pause, seek slider, time.
        bar = QHBoxLayout()
        bar.setContentsMargins(10, 8, 10, 10)
        bar.setSpacing(8)
        self._control_bar = bar
        _btn_css = (
            "QPushButton{background:#2a2a2a;color:#fff;border:none;"
            "border-radius:6px;padding:6px;font-size:15px;}"
            "QPushButton:hover{background:#3a3a3a;}")

        self._play_btn = QPushButton("\u23f8")
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setFixedWidth(40)
        self._play_btn.setStyleSheet(_btn_css)
        self._play_btn.setToolTip("Play/Pause (k)")
        self._play_btn.clicked.connect(self._toggle_play)
        bar.addWidget(self._play_btn)

        # Skip back / forward 10s (YouTube j / l).
        self._back_btn = QPushButton("\u23ea")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFixedWidth(36)
        self._back_btn.setStyleSheet(_btn_css)
        self._back_btn.setToolTip("Back 10s (j)")
        self._back_btn.clicked.connect(lambda: self._seek_relative(-10000))
        bar.addWidget(self._back_btn)

        self._fwd_btn = QPushButton("\u23e9")
        self._fwd_btn.setCursor(Qt.PointingHandCursor)
        self._fwd_btn.setFixedWidth(36)
        self._fwd_btn.setStyleSheet(_btn_css)
        self._fwd_btn.setToolTip("Forward 10s (l)")
        self._fwd_btn.clicked.connect(lambda: self._seek_relative(10000))
        bar.addWidget(self._fwd_btn)

        self._slider = _ClickSlider(Qt.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.sliderMoved.connect(self._player.setPosition)
        bar.addWidget(self._slider, 1)

        self._time = QLabel("0:00 / 0:00")
        self._time.setStyleSheet("color:#ddd;font-size:12px;")
        bar.addWidget(self._time)

        # Volume (mute toggle + slider).
        self._vol_btn = QPushButton("\U0001f50a")
        self._vol_btn.setCursor(Qt.PointingHandCursor)
        self._vol_btn.setFixedWidth(36)
        self._vol_btn.setStyleSheet(
            "QPushButton{background:#2a2a2a;color:#fff;border:none;"
            "border-radius:6px;padding:6px;font-size:14px;}"
            "QPushButton:hover{background:#3a3a3a;}")
        self._vol_btn.clicked.connect(self._toggle_mute)
        bar.addWidget(self._vol_btn)

        self._vol_slider = _ClickSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(100)
        self._vol_slider.setFixedWidth(90)
        self._vol_slider.valueChanged.connect(self._on_volume)
        bar.addWidget(self._vol_slider)

        # Settings menu (quality / speed / loop) — mirrors the site player.
        self._settings_btn = QPushButton("\u2699")
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setFixedWidth(36)
        self._settings_btn.setStyleSheet(_btn_css)
        self._settings_btn.setToolTip("Settings (quality / speed / loop)")
        self._settings_btn.clicked.connect(self._show_settings_menu)
        bar.addWidget(self._settings_btn)

        # Fullscreen toggle.
        self._fs_btn = QPushButton("\u26f6")
        self._fs_btn.setCursor(Qt.PointingHandCursor)
        self._fs_btn.setFixedWidth(36)
        self._fs_btn.setStyleSheet(_btn_css)
        self._fs_btn.setToolTip("Fullscreen (f)")
        self._fs_btn.clicked.connect(self._toggle_fullscreen)
        bar.addWidget(self._fs_btn)
        root.addLayout(bar)

        self._top_bar = top
        self._audio.setVolume(1.0)
        self._normal_geom = None
        self._referer = None
        self._sources = {}          # {'Low':url, 'High':url, 'HLS':url}
        self._quality = None        # current quality key
        self._loop = False
        self._rate = 1.0
        self._player.durationChanged.connect(self._on_duration)
        self._player.positionChanged.connect(self._on_position)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        try:
            self._player.errorOccurred.connect(self._on_player_error)
        except Exception:
            pass
        self._tried_qualities = set()

        # Centered status/error message shown over the video area.
        self._msg_label = QLabel("", self._view)
        self._msg_label.setAlignment(Qt.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.setStyleSheet(
            "color:#eee;background:transparent;font-size:14px;padding:20px;")
        self._msg_label.hide()

        # Auto-hide the controls after inactivity (YouTube-style).
        self.setMouseTracking(True)
        self._view.setMouseTracking(True)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(2600)
        self._hide_timer.timeout.connect(self._hide_controls)

        # Distinguish a single click on the video (play/pause) from a
        # double click (fullscreen): a lone click fires after a short delay
        # unless a double click cancels it first.
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self._toggle_play)

    def _on_video_click(self):
        """A single click on the video toggles play/pause (after a delay)."""
        self._show_controls()
        self._click_timer.start()

    def _on_video_double_click(self):
        """A double click on the video toggles fullscreen (not play/pause)."""
        self._click_timer.stop()
        self._toggle_fullscreen()

    def _show_settings_menu(self):
        from qtpy.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1e1e1e;color:#eee;border:1px solid #333;}"
            "QMenu::item:selected{background:#0d47a1;}")

        # Quality submenu (only qualities we actually have URLs for).
        if self._sources:
            qmenu = menu.addMenu("Quality")
            order = [('High', 'HD (High)'), ('Low', 'SD (Low)'), ('HLS', 'Auto (HLS)')]
            for key, label in order:
                if self._sources.get(key):
                    act = qmenu.addAction(
                        ("\u2713 " if key == self._quality else "   ") + label)
                    act.triggered.connect(lambda _c, k=key: self._switch_quality(k))

        # Speed submenu.
        smenu = menu.addMenu("Speed")
        for rate in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            act = smenu.addAction(
                ("\u2713 " if abs(rate - self._rate) < 1e-3 else "   ")
                + ("%gx" % rate))
            act.triggered.connect(lambda _c, r=rate: self._set_rate(r))

        # Loop toggle.
        loop_act = menu.addAction(("\u2713 " if self._loop else "   ") + "Loop")
        loop_act.triggered.connect(self._toggle_loop)

        menu.exec_(self._settings_btn.mapToGlobal(
            self._settings_btn.rect().topRight()))

    def _set_rate(self, rate):
        self._rate = rate
        try:
            self._player.setPlaybackRate(rate)
        except Exception:
            pass

    def _toggle_loop(self):
        self._loop = not self._loop

    def _switch_quality(self, key):
        url = self._sources.get(key)
        if not url or key == self._quality:
            return
        pos = self._player.position()
        was_playing = self._player.playbackState() == QMediaPlayer.PlayingState
        self._quality = key
        self._settings_btn.setToolTip("Quality: " + key)
        self._resume_pos = pos
        self._resume_play = was_playing
        self._load_media(url)

    def _on_media_status(self, status):
        try:
            print("PLAYER: status", int(status), flush=True)
        except Exception:
            pass
        if status == QMediaPlayer.EndOfMedia and self._loop:
            self._player.setPosition(0)
            self._player.play()
        elif status == QMediaPlayer.LoadedMedia:
            self._set_message("")
            # After a quality switch, restore position and play state.
            rp = getattr(self, '_resume_pos', None)
            if rp:
                self._player.setPosition(rp)
                self._resume_pos = None
            if getattr(self, '_resume_play', False):
                self._player.play()
                self._resume_play = False
            self._player.setPlaybackRate(self._rate)
        elif status == QMediaPlayer.BufferedMedia:
            self._set_message("")

    def _on_player_error(self, error, msg=""):
        try:
            print("VIDEO ERROR:", int(error), repr(msg), flush=True)
        except Exception:
            pass
        # A source that won't open: fall back to the next quality we haven't
        # tried yet (HD \u2192 SD \u2192 HLS) before giving up.
        for key in ('High', 'Low', 'HLS'):
            url = self._sources.get(key)
            if url and key not in self._tried_qualities:
                self._tried_qualities.add(key)
                self._quality = key
                self._settings_btn.setToolTip("Quality: " + key)
                self._set_message("Trying %s\u2026" % key)
                self._load_media(url)
                return
        self._set_message("Couldn't play this video.\n%s" % (msg or ""))

    def _set_message(self, text):
        try:
            self._msg_label.setText(text or "")
            self._msg_label.setVisible(bool(text))
            if text:
                self._msg_label.setGeometry(self._view.rect())
                self._msg_label.raise_()
        except Exception:
            pass

    def play_url(self, url, referer=None):
        self._referer = referer
        self._sources = {}
        self._quality = None
        self._tried_qualities = set()
        self._set_message("Loading\u2026")
        self.show()
        self.raise_()
        self._load_media(url)

    def play_sources(self, sources, referer=None):
        """Play from a set of quality URLs (High/Low/HLS), preferring HD."""
        self._referer = referer
        self._sources = {k: v for k, v in (sources or {}).items() if v}
        self._tried_qualities = set()
        self._set_message("Loading\u2026")
        self.show()
        self.raise_()
        for key in ('High', 'Low', 'HLS'):
            if self._sources.get(key):
                self._quality = key
                self._tried_qualities.add(key)
                self._settings_btn.setToolTip("Quality: " + key)
                self._load_media(self._sources[key])
                return

    def _load_media(self, url):
        # Qt6 QMediaPlayer takes a QUrl directly; QMediaContent and per-request
        # headers were removed, so custom Referer headers are no longer applied.
        print("PLAYER: load_media", (url or "")[:90], flush=True)
        self._player.setSource(QUrl(url))
        self._player.setPlaybackRate(self._rate)
        self._player.play()

    def stop_and_hide(self):
        try:
            self._player.stop()
            self._player.setSource(QUrl())
        except Exception:
            pass
        if self._is_fullscreen:
            self._exit_fullscreen()
        self.hide()
        # Bring the web page back now that the player is gone.
        parent = self._embed_parent
        if parent is not None:
            try:
                parent._on_overlay_closed()
            except Exception:
                pass

    def _fit_video(self, *args):
        """Repaint the video canvas (frames are scaled in paintEvent)."""
        try:
            self._view.update()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_video()
        try:
            if self._msg_label.isVisible():
                self._msg_label.setGeometry(self._view.rect())
        except Exception:
            pass

    def hideEvent(self, event):
        super().hideEvent(event)
        # Pause when the tab is switched away (the parent tab hides its
        # children) so an inactive tab never keeps playing audio. Guarded so
        # the fullscreen reparent (which briefly hides us) doesn't pause.
        if self._reparenting:
            return
        try:
            if self._player.playbackState() == QMediaPlayer.PlayingState:
                self._player.pause()
        except Exception:
            pass

    def _toggle_play(self):
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_volume(self, value):
        self._audio.setVolume(value / 100.0)
        self._audio.setMuted(value == 0)
        self._vol_btn.setText("\U0001f507" if value == 0 else "\U0001f50a")

    def _toggle_mute(self):
        if self._audio.isMuted() or self._vol_slider.value() == 0:
            vol = self._last_volume if getattr(self, '_last_volume', 0) else 100
            self._vol_slider.setValue(vol)
        else:
            self._last_volume = self._vol_slider.value()
            self._vol_slider.setValue(0)

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        # True fullscreen requires a top-level window, so briefly detach from
        # the tab, go fullscreen, and re-embed on exit.
        self._reparenting = True
        self.setParent(None)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self._is_fullscreen = True
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._reparenting = False
        self._fit_video()

    def _exit_fullscreen(self):
        self._reparenting = True
        self._is_fullscreen = False
        self.setWindowFlags(Qt.Widget)
        parent = self._embed_parent
        if parent is not None:
            try:
                parent._embed_overlay()
            except Exception:
                self.setParent(parent)
                self.show()
        else:
            self.show()
        self.raise_()
        self.setFocus()
        self._reparenting = False
        self._fit_video()

    def _on_state(self, state):
        self._play_btn.setText(
            "\u23f8" if state == QMediaPlayer.PlayingState else "\u25b6")
        if state == QMediaPlayer.PlayingState:
            self._hide_timer.start()
        else:
            # Keep controls visible whenever not actively playing.
            self._show_controls()
            self._hide_timer.stop()

    def _on_duration(self, dur):
        self._slider.setRange(0, dur)
        self._update_time()

    def _on_position(self, pos):
        if not self._slider.isSliderDown():
            self._slider.setValue(pos)
        self._update_time()

    @staticmethod
    def _fmt(ms):
        s = int(ms // 1000)
        return "%d:%02d" % (s // 60, s % 60)

    def _update_time(self):
        self._time.setText("%s / %s" % (
            self._fmt(self._player.position()),
            self._fmt(self._player.duration())))

    def _seek_relative(self, delta_ms):
        pos = max(0, self._player.position() + delta_ms)
        dur = self._player.duration()
        if dur:
            pos = min(pos, dur)
        self._player.setPosition(pos)
        self._show_controls()

    def _seek_percent(self, frac):
        dur = self._player.duration()
        if dur:
            self._player.setPosition(int(dur * frac))
        self._show_controls()

    def _bump_rate(self, step):
        rates = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        try:
            i = min(range(len(rates)), key=lambda k: abs(rates[k] - self._rate))
        except ValueError:
            i = 3
        i = max(0, min(len(rates) - 1, i + step))
        self._set_rate(rates[i])

    def _nudge_volume(self, delta):
        self._vol_slider.setValue(
            max(0, min(100, self._vol_slider.value() + delta)))
        self._show_controls()

    def _show_controls(self):
        self._top_bar_widgets(True)
        self._control_bar_widgets(True)
        self.unsetCursor()
        self._view.unsetCursor()
        self._hide_timer.start()

    def _hide_controls(self):
        # Only auto-hide while actually playing AND a real frame is on screen.
        # On a black/"source error" screen we keep the cursor and controls
        # visible so the pointer never vanishes over an unplayable video.
        if self._player.playbackState() != QMediaPlayer.PlayingState:
            return
        if getattr(self._view, '_image', None) is None:
            return
        self._top_bar_widgets(False)
        self._control_bar_widgets(False)
        self.setCursor(Qt.BlankCursor)
        self._view.setCursor(Qt.BlankCursor)

    def _top_bar_widgets(self, visible):
        for i in range(self._top_bar.count()):
            w = self._top_bar.itemAt(i).widget()
            if w is not None:
                w.setVisible(visible)

    def _control_bar_widgets(self, visible):
        for i in range(self._control_bar.count()):
            w = self._control_bar.itemAt(i).widget()
            if w is not None:
                w.setVisible(visible)

    def mouseMoveEvent(self, event):
        self._show_controls()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        text = event.text()
        if key == Qt.Key_Escape:
            if self._is_fullscreen:
                self._exit_fullscreen()
            else:
                self.stop_and_hide()
        elif key in (Qt.Key_Space, Qt.Key_K):
            self._toggle_play()
        elif key in (Qt.Key_F,):
            self._toggle_fullscreen()
        elif key == Qt.Key_M:
            self._toggle_mute()
        elif key == Qt.Key_J:
            self._seek_relative(-10000)
        elif key == Qt.Key_L:
            self._seek_relative(10000)
        elif key == Qt.Key_Left:
            self._seek_relative(-5000)
        elif key == Qt.Key_Right:
            self._seek_relative(5000)
        elif key == Qt.Key_Up:
            self._nudge_volume(5)
        elif key == Qt.Key_Down:
            self._nudge_volume(-5)
        elif key == Qt.Key_Home:
            self._player.setPosition(0)
        elif key == Qt.Key_End:
            self._player.setPosition(self._player.duration())
        elif text == ">":
            self._bump_rate(1)
        elif text == "<":
            self._bump_rate(-1)
        elif text.isdigit():
            self._seek_percent(int(text) / 10.0)
        else:
            super().keyPressEvent(event)
        self._show_controls()


class _BrowserWebView(QWebEngineView if WEBENGINE_AVAILABLE else object):
    """A web view that routes "open in new tab/window" through the owner.
    Chromium requests a new view via :meth:`createWindow` (e.g. the context
    menu's *Open link in new tab*, ``target="_blank"`` links, ``window.open``).
    Returning a view here lets it load the link; returning ``None`` — the
    default — is why those actions appear to do nothing.
    """

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self._owner = owner

    def createWindow(self, _window_type):
        return self._owner._create_linked_view()



def make_audio_pulse_pixmap(intensity, size=16):
    """Draw a small speaker with pulsing sound waves (a "heartbeat" effect).

    ``intensity`` (0.0-1.0) drives the opacity of the sound waves so animating
    it over time produces the pulse. Returns a transparent ``QPixmap``.
    Shared by the browser tab bar and the terminal-group panel.
    """
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color = QColor(76, 222, 128)  # green

    # Speaker body (static)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRect(2, 6, 2, 4)
    p.drawPolygon(QPolygon([
        QPoint(4, 6), QPoint(8, 3), QPoint(8, 13), QPoint(4, 10)
    ]))

    # Pulsing sound waves (opacity driven by intensity)
    pen = QPen(color)
    pen.setWidthF(1.4)
    p.setBrush(Qt.NoBrush)
    for i, radius in enumerate((3, 6)):
        wave_alpha = max(0.0, min(1.0, intensity - i * 0.25))
        c = QColor(color)
        c.setAlphaF(wave_alpha)
        pen.setColor(c)
        p.setPen(pen)
        p.drawArc(6 - radius + 4, 8 - radius, radius * 2, radius * 2, -60 * 16, 120 * 16)
    p.end()
    return pm



class BrowserWidget(QWidget):
    """A simple embedded web browser with a navigation toolbar."""

    # Emitted whenever the page starts/stops producing audible sound.
    audioStateChanged = Signal(bool)
    # Emitted when a fresh page load starts and capture stores are cleared.
    captureReset = Signal()
    # Text to show on the owning tab: the site name, or the live u.../d... rate
    # while data is flowing.
    tabLabelChanged = Signal(str)
    # Favicon (or a null QIcon to fall back to the default logo) for the tab.
    tabFaviconChanged = Signal(QIcon)

    # One ad blocker shared by every browser tab (the default profile is
    # process-wide, so a single interceptor covers all views).
    _shared_ad_blocker = None

    def __init__(self, home_url=DEFAULT_HOME, parent=None):
        super().__init__(parent)
        self.home_url = home_url
        # Scraper capture stores (populated by injected instrumentation)
        self.captured_requests = []          # list of request dicts
        self.captured_ws = []                # list of websocket frame dicts
        self.media_sessions = []             # list of session/file dicts
        self._session_by_id = {}             # MediaSource id -> logical session
        # Per-tab network meter state
        self._site_name = "Browser"          # short name derived from the URL
        self._net_loaded = False             # True once a page loads OK
        self._net_last = None                # last (up_bytes, down_bytes) sample
        # Per-tab network privacy (Tor / proxy) route manager.
        try:
            from core.network_privacy import NetworkPrivacyManager
            self.privacy = NetworkPrivacyManager(self)
        except Exception:
            self.privacy = None
        self._init_ui()
        if WEBENGINE_AVAILABLE:
            self._attach_scraper()
            self.navigate_to(home_url)

    def _attach_scraper(self):
        """Install page instrumentation for the scraping toolkit."""
        try:
            from ui.browser_scraper import attach_scraper
            attach_scraper(self)
        except Exception:
            pass

    def _on_scrape_report(self, obj):
        """Handle a captured event reported by the page instrumentation."""
        t = obj.get('t')
        if t == 'req':
            self.captured_requests.append(obj)
            if len(self.captured_requests) > 500:
                self.captured_requests = self.captured_requests[-500:]
        elif t == 'ws':
            self.captured_ws.append(obj)
            if len(self.captured_ws) > 1000:
                self.captured_ws = self.captured_ws[-1000:]
        elif t == 'msession':
            self._get_or_create_session(obj.get('id'), obj.get('title'), obj.get('url'))
        elif t == 'mtitle':
            # A newly played video reports its now-current title.
            sess = self._get_or_create_session(obj.get('session'), obj.get('title'))
            title = obj.get('title')
            if title:
                sess['title'] = title
        elif t == 'media':
            import base64
            mime = obj.get('mime', 'application/octet-stream')
            try:
                data = base64.b64decode(obj.get('b64', ''))
            except Exception:
                return
            sess = self._get_or_create_session(obj.get('session'), obj.get('title'))
            sess['tracks'].setdefault(mime, []).append(data)
            # Preserve the global append order across all tracks so adaptive
            # (ABR) quality switches can be stitched back into one timeline.
            sess.setdefault('stream', []).append((mime, data))
        elif t == 'mediafile':
            url = obj.get('url')
            if url and not any(s.get('url') == url for s in self.media_sessions):
                self._add_file_session(url, self._basename(url), obj.get('kind', 'file'))

    def _now(self):
        from datetime import datetime
        return datetime.now().strftime('%H:%M:%S')

    def _basename(self, url):
        from urllib.parse import urlparse, unquote
        import os
        try:
            return unquote(os.path.basename(urlparse(url).path)) or 'file'
        except Exception:
            return 'file'

    def _session_key(self, url):
        """A stable identifier for the video currently playing at ``url``.

        For YouTube this is the ``v`` id, so ABR quality switches / seeks
        (which each spin up a new MediaSource) fold into one session.
        """
        from urllib.parse import urlparse, parse_qs
        try:
            u = urlparse(url or '')
            if 'youtube' in u.netloc or 'youtu.be' in u.netloc:
                v = parse_qs(u.query).get('v', [None])[0]
                if v:
                    return 'yt:' + v
            return (u.netloc + u.path + u.query) or (url or '')
        except Exception:
            return url or ''

    def _get_or_create_session(self, sid, title, url=None):
        """Return (creating if needed) the MSE media session for ``sid``.

        Consecutive MediaSources for the same video (same URL key) are merged
        into a single logical session instead of creating a new one each time.
        """
        existing = self._session_by_id.get(sid)
        if existing is not None:
            if title and not existing.get('title'):
                existing['title'] = title
            return existing

        key = self._session_key(url) if url else None
        # Merge with the most recent session if it's the same video.
        if key and self.media_sessions:
            last = self.media_sessions[-1]
            if last.get('kind') == 'mse' and last.get('key') == key:
                self._session_by_id[sid] = last
                if title and not last.get('title'):
                    last['title'] = title
                return last

        sess = {'kind': 'mse', 'id': sid, 'key': key, 'title': title or '',
                'time': self._now(), 'tracks': {}, 'stream': []}
        self.media_sessions.append(sess)
        self._session_by_id[sid] = sess
        return sess

    def _add_file_session(self, url, name, kind):
        real_kind = 'pdf' if (name or '').lower().endswith('.pdf') else kind
        self.media_sessions.append({'kind': real_kind, 'url': url,
                                    'name': name, 'time': self._now(),
                                    'title': name})

    def _on_file_caught(self, url, name):
        """Called by the profile request interceptor for downloadable files."""
        if url and not any(s.get('url') == url for s in self.media_sessions):
            self._add_file_session(url, name, 'file')


    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not WEBENGINE_AVAILABLE:
            from qtpy.QtWidgets import QLabel
            msg = QLabel(
                "Web browser is unavailable.\n\n"
                "Install the web engine module with:\n"
                "    pip install PyQtWebEngine"
            )
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet("color:#cccccc; font-size:13px; padding:20px;")
            layout.addWidget(msg)
            return

        # ── Navigation toolbar ────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(40)
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setStyleSheet("background:#252526;")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(6, 4, 6, 4)
        tb.setSpacing(4)

        self.back_btn = self._make_button("‹", "Back")
        self.forward_btn = self._make_button("›", "Forward")
        self.reload_btn = self._make_button("⟳", "Reload")
        self.home_btn = self._make_button("⌂", "Home")

        self.back_btn.clicked.connect(lambda: (self._teardown_inline_player(), self.web_view.back()))
        self.forward_btn.clicked.connect(lambda: (self._teardown_inline_player(), self.web_view.forward()))
        self.reload_btn.clicked.connect(lambda: (self._teardown_inline_player(), self.web_view.reload()))
        self.home_btn.clicked.connect(lambda: self.navigate_to(self.home_url))

        tb.addWidget(self.back_btn)
        tb.addWidget(self.forward_btn)
        tb.addWidget(self.reload_btn)
        tb.addWidget(self.home_btn)

        # Ad-blocker toggle (sits just before the address bar).
        self.adblock_btn = QToolButton()
        self.adblock_btn.setCheckable(True)
        self.adblock_btn.setCursor(Qt.PointingHandCursor)
        self.adblock_btn.setIconSize(QSize(20, 20))
        self.adblock_btn.clicked.connect(self._toggle_adblock)
        tb.addWidget(self.adblock_btn)

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Search Google or type a URL")
        self._address_base_style = (
            "QLineEdit { background:#3c3c3c; color:#e0e0e0; border:1px solid #555; "
            "border-radius:12px; padding:5px 12px; selection-background-color:#094771; }"
            "QLineEdit:focus { border:1px solid #007acc; }"
        )
        self.address_bar.setStyleSheet(self._address_base_style)
        self.address_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.address_bar.returnPressed.connect(self._on_address_entered)
        tb.addWidget(self.address_bar)

        # Inspect Element / DevTools toggle
        self.inspect_btn = self._make_button("⧉", "Inspect Element (DevTools)")
        self.inspect_btn.setCheckable(True)
        self.inspect_btn.clicked.connect(self.toggle_devtools)
        tb.addWidget(self.inspect_btn)

        self.nav_toolbar = toolbar
        layout.addWidget(toolbar)

        # ── Progress bar ──────────────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setMaximumHeight(2)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar { background:#252526; border:none; }"
            "QProgressBar::chunk { background:#007acc; }"
        )
        self.progress.hide()
        layout.addWidget(self.progress)

        # ── Web view (+ collapsible DevTools pane in a splitter) ───────────
        self.web_view = _BrowserWebView(self)
        self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Swap in a page that keeps direct-media links playing inline instead
        # of navigating the whole tab to a bare .mp4 file. Reuse the default
        # profile so the ad blocker / user-agent still apply.
        if WEBENGINE_AVAILABLE:
            try:
                _profile = self.web_view.page().profile()
                self._page = _BrowserWebPage(_profile, self)
                self.web_view.setPage(self._page)
            except Exception:
                pass

        self.devtools_view = None  # created lazily when first toggled on
        self.split = QSplitter(Qt.Vertical)
        self.split.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.split.setChildrenCollapsible(False)
        self.split.addWidget(self.web_view)
        layout.addWidget(self.split, 1)

        # Allow media (incl. audio) to play without a prior user gesture and
        # make sure the page is not muted.
        try:
            from qtpy.QtWebEngineWidgets import QWebEngineSettings
            self.web_view.settings().setAttribute(
                QWebEngineSettings.PlaybackRequiresUserGesture, False)
            # Let pages (YouTube etc.) enter HTML5 fullscreen.
            self.web_view.settings().setAttribute(
                QWebEngineSettings.FullScreenSupportEnabled, True)
        except Exception:
            pass
        self.web_view.page().setAudioMuted(False)

        # Honour HTML5 fullscreen requests from the page.
        self._fs_prev_index = None
        self._fs_host = None
        try:
            self.web_view.page().fullScreenRequested.connect(
                self._on_fullscreen_requested)
        except Exception:
            pass

        # Present a plain desktop-Chrome user agent (drop the "QtWebEngine"
        # token that some sites use to flag automated browsers).
        self._set_user_agent()

        # Install the shared ad/tracker blocker on this view's profile.
        self._install_ad_blocker()

        # Notify listeners (e.g. the tab bar) when audio starts/stops so an
        # indicator can be shown on the tab.
        self.web_view.page().recentlyAudibleChanged.connect(self.audioStateChanged)

        # Signals
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.loadStarted.connect(self._on_load_started)
        self.web_view.loadProgress.connect(self._on_load_progress)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.iconChanged.connect(self._on_icon_changed)

        # Per-tab network meter: sample bytes up/down once a second so the tab
        # can show the live transfer rate.
        self._install_net_meter()
        self._net_timer = QTimer(self)
        self._net_timer.setInterval(1000)
        self._net_timer.timeout.connect(self._sample_net)
        self._net_timer.start()

    def _make_button(self, text, tooltip):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QToolButton { background:transparent; color:#cccccc; border:none; "
            "border-radius:4px; font-size:18px; min-width:28px; min-height:26px; }"
            "QToolButton:hover { background:#3c3c3c; }"
            "QToolButton:pressed { background:#094771; }"
            "QToolButton:disabled { color:#555; }"
        )
        return btn

    # ── Ad blocker ────────────────────────────────────────────────────────
    def _install_ad_blocker(self):
        """Attach the shared ad blocker to this view's profile and sync the UI."""
        try:
            from core.ad_blocker import AdBlocker
        except Exception:
            self._ad_blocker = None
            self.adblock_btn.setEnabled(False)
            return
        blocker = BrowserWidget._shared_ad_blocker
        if blocker is None:
            blocker = AdBlocker()
            BrowserWidget._shared_ad_blocker = blocker
        self._ad_blocker = blocker
        try:
            profile = self.web_view.page().profile()
            if hasattr(profile, 'setUrlRequestInterceptor'):
                profile.setUrlRequestInterceptor(blocker)
            else:  # older Qt fallback
                profile.setRequestInterceptor(blocker)
        except Exception:
            pass
        self._update_adblock_button()

    def _toggle_adblock(self):
        if self._ad_blocker is None:
            return
        self._ad_blocker.enabled = not self._ad_blocker.enabled
        self._update_adblock_button()
        # Reload so the new blocking state takes effect immediately.
        try:
            self.web_view.reload()
        except Exception:
            pass

    def _update_adblock_button(self):
        on = bool(self._ad_blocker and self._ad_blocker.enabled)
        self.adblock_btn.setChecked(on)
        # Green octagon when on, pink when off (a painted icon so it actually
        # recolors — unlike the multicolor 🛡 emoji glyph).
        self.adblock_btn.setIcon(QIcon(self._make_adblock_pixmap(on)))
        self.adblock_btn.setStyleSheet(
            "QToolButton { background:transparent; border:none; "
            "border-radius:4px; min-width:28px; min-height:26px; }"
            "QToolButton:hover { background:#3c3c3c; }"
            "QToolButton:pressed { background:#094771; }"
        )
        self.adblock_btn.setToolTip(
            "Ad blocker: ON — click to disable" if on
            else "Ad blocker: OFF — click to enable")

    @staticmethod
    def _make_adblock_pixmap(on, size=20):
        """Draw a stop-sign octagon with 'AD' — green when on, pink when off."""
        if on:
            fill, edge = QColor('#1db954'), QColor('#0f8a3c')
        else:
            fill, edge = QColor('#e84393'), QColor('#b52c6f')
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        # Octagon vertices inset within the pixmap.
        import math
        cx = cy = size / 2.0
        r = size / 2.0 - 1
        pts = []
        for i in range(8):
            ang = math.pi / 8 + i * math.pi / 4  # rotate so flats are top/bottom
            pts.append(QPoint(int(round(cx + r * math.cos(ang))),
                              int(round(cy + r * math.sin(ang)))))
        pen = QPen(edge)
        pen.setWidthF(1.4)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawPolygon(QPolygon(pts))
        # "AD" letters.
        from qtpy.QtGui import QFont
        f = QFont()
        f.setBold(True)
        f.setPixelSize(int(size * 0.42))
        p.setFont(f)
        p.setPen(QPen(QColor('white')))
        p.drawText(pm.rect(), Qt.AlignCenter, "AD")
        p.end()
        return pm

    def _inject_cosmetic_css(self):
        """Hide the empty slots ad networks leave behind (cosmetic filtering)."""
        if not (self._ad_blocker and self._ad_blocker.enabled):
            return
        try:
            from core.ad_blocker import COSMETIC_CSS
        except Exception:
            return
        css = COSMETIC_CSS.replace('\\', '\\\\').replace('`', '\\`')
        js = (
            "(function(){var s=document.getElementById('__tb_adblock');"
            "if(!s){s=document.createElement('style');s.id='__tb_adblock';"
            "document.documentElement.appendChild(s);}"
            "s.textContent=`" + css + "`;})();"
        )
        try:
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    def _downgrade_modern_css(self):
        """Flatten CSS ``@layer`` blocks so the old engine can style the page.

        QtWebEngine 5.15 bundles Chromium 87, which predates CSS cascade
        layers. Modern (e.g. Tailwind v4) sites wrap *all* their rules in
        ``@layer`` blocks, so the whole stylesheet is discarded and the page
        renders unstyled. We fetch each same-origin stylesheet, strip the
        ``@layer`` wrappers (keeping the rules inside), and re-inject the
        flattened CSS so the theme, component and utility rules apply again.
        """
        if not WEBENGINE_AVAILABLE or _MODERN_ENGINE:
            return
        js = r"""
(function(){
  function flatten(css){
    if(css.indexOf('@layer')===-1) return null;
    css = css.replace(/@layer[^{;]*;/g, '');          // drop "@layer a,b;"
    var out='', i=0, n=css.length, stack=[];
    while(i<n){
      if(css.charCodeAt(i)===64 && css.substr(i,6)==='@layer'){
        var j=i+6;
        while(j<n && css[j]!=='{' && css[j]!==';') j++;
        if(j<n && css[j]==='{'){ stack.push(1); i=j+1; continue; } // unwrap
      }
      var c=css[i];
      if(c==='{'){ stack.push(0); out+=c; i++; continue; }
      if(c==='}'){ var t=stack.pop(); if(!t) out+=c; i++; continue; }
      out+=c; i++;
    }
    return out;
  }
  try{
    document.querySelectorAll('style').forEach(function(s){
      var f=flatten(s.textContent||''); if(f!==null) s.textContent=f;
    });
  }catch(e){}
  try{
    document.querySelectorAll('link[rel~="stylesheet"]').forEach(function(l){
      if(!l.href || l.href.indexOf(location.origin)!==0) return;   // same-origin only
      if(l.dataset.tbFlat) return;
      fetch(l.href).then(function(r){return r.text();}).then(function(t){
        var f=flatten(t); if(f===null) return;
        var st=document.createElement('style');
        st.setAttribute('data-tb-flattened','1');
        st.textContent=f;
        l.parentNode.insertBefore(st, l.nextSibling);
        l.dataset.tbFlat='1';
        l.disabled=true;
      }).catch(function(){});
    });
  }catch(e){}
})();
"""
        try:
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    # ── Network meter (per-tab transfer rate) ─────────────────────────────
    def _set_user_agent(self):
        """Use a clean desktop-Chrome UA to look less like an automated view."""
        ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0.0.0 Safari/537.36")
        try:
            self.web_view.page().profile().setHttpUserAgent(ua)
        except Exception:
            pass

    def _install_net_meter(self):
        """Inject a byte counter that runs on every page (download + upload)."""
        try:
            from qtpy.QtWebEngineWidgets import QWebEngineScript
        except Exception:
            return
        js = (
            "(function(){"
            "if(window.__tbNetReady)return;window.__tbNetReady=true;"
            "window.__tbNet={up:0,down:0};"
            "function mask(w,o){try{var s=(''+o);w.toString=function(){return s;};}catch(e){}return w;}"
            "try{var po=new PerformanceObserver(function(l){var es=l.getEntries();"
            "for(var i=0;i<es.length;i++){window.__tbNet.down+=(es[i].transferSize||0);}});"
            "po.observe({type:'resource',buffered:true});}catch(e){}"
            "try{var nav=performance.getEntriesByType('navigation');"
            "if(nav&&nav[0]){window.__tbNet.down+=(nav[0].transferSize||0);}}catch(e){}"
            "try{var of=window.fetch;if(of){window.fetch=mask(function(){try{var o=arguments[1];"
            "if(o&&o.body){var b=o.body;window.__tbNet.up+=(b.length||b.size||b.byteLength||0);}}catch(e){}"
            "return of.apply(this,arguments);},of);}}catch(e){}"
            "try{var os=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.send=mask(function(b){"
            "try{if(b){window.__tbNet.up+=(b.length||b.size||b.byteLength||0);}}catch(e){}"
            "return os.apply(this,arguments);},os);}catch(e){}"
            "try{var ob=navigator.sendBeacon;if(ob){navigator.sendBeacon=mask(function(u,d){"
            "try{if(d){window.__tbNet.up+=(d.length||d.size||0);}}catch(e){}"
            "return ob.apply(this,arguments);},ob);}}catch(e){}"
            "})();"
        )
        try:
            script = QWebEngineScript()
            script.setName('tb_net_meter')
            script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            script.setWorldId(QWebEngineScript.MainWorld)
            script.setRunsOnSubFrames(True)
            script.setSourceCode(js)
            self.web_view.page().scripts().insert(script)
        except Exception:
            pass

    def _sample_net(self):
        if not WEBENGINE_AVAILABLE:
            return
        try:
            self.web_view.page().runJavaScript(
                "JSON.stringify(window.__tbNet||{up:0,down:0})",
                self._on_net_sample)
        except Exception:
            pass

    def _on_net_sample(self, result):
        import json
        try:
            data = json.loads(result) if result else {}
        except Exception:
            data = {}
        up = float(data.get('up', 0) or 0)
        down = float(data.get('down', 0) or 0)
        prev = self._net_last
        self._net_last = (up, down)
        if prev is None or not self._net_loaded:
            return
        # Bytes since the previous sample (interval is ~1s, so this is B/s).
        up_rate = max(0.0, up - prev[0])
        down_rate = max(0.0, down - prev[1])
        if (up_rate + down_rate) > 1024:  # > ~1 KB/s: show the live rate
            self.tabLabelChanged.emit(
                "u%s/d%s" % (self._fmt_rate(up_rate), self._fmt_rate(down_rate)))
        else:  # idle: show the site name again
            self.tabLabelChanged.emit(self._site_name)

    @staticmethod
    def _fmt_rate(bps):
        kb = bps / 1024.0
        if kb < 1024:
            return "%.2fkb" % kb
        return "%.2fmb" % (kb / 1024.0)

    def _compute_site_name(self):
        """Short label from the URL host: ``1377x.to`` → ``1377``."""
        try:
            host = (self.web_view.url().host() or "").lower()
        except Exception:
            host = ""
        if not host:
            return "Browser"
        if host.startswith("www."):
            host = host[4:]
        label = host.split(".")[0]
        import re
        m = re.match(r'^(\d{2,})[a-z]{1,3}$', label)
        if m:
            label = m.group(1)
        return label or "Browser"

    def _on_icon_changed(self, icon):
        """Relay the page favicon to the tab (empty icon keeps the logo)."""
        if not self._net_loaded:
            return
        self.tabFaviconChanged.emit(icon if icon is not None else QIcon())

    # ── Media viewer (Chrome-style player for direct video/audio URLs) ────
    _MEDIA_EXTS = (".mp4", ".webm", ".ogg", ".ogv", ".mov", ".m4v", ".mkv",
                   ".avi", ".m3u8", ".mp3", ".m4a", ".wav", ".flac", ".aac",
                   ".opus")

    def _is_media_url(self):
        try:
            path = (self.web_view.url().path() or "").lower()
        except Exception:
            return False
        return any(path.endswith(ext) for ext in self._MEDIA_EXTS)

    def _url_is_media(self, url):
        """True when a QUrl points straight at a video/audio file."""
        try:
            path = (url.path() or "").lower()
        except Exception:
            return False
        return any(path.endswith(ext) for ext in self._MEDIA_EXTS)

    def _play_inline(self, media_url):
        """Play an intercepted media link over the current page.

        The bundled QtWebEngine can't decode H.264/AAC, so we play the stream
        with a native Qt Multimedia overlay (AVFoundation on macOS) instead of
        navigating the tab away to a bare — and unplayable — ``.mp4``. The page
        the user was browsing stays loaded underneath.
        """
        if not MULTIMEDIA_AVAILABLE:
            return
        # The page keeps re-firing the media navigation in a retry loop (each
        # reload mints a fresh signed URL). Restarting playback on every one
        # interrupts the previous still-opening stream (FFmpeg "partial file" /
        # "Immediate exit requested") and leaves a black screen. So once a
        # video is active, ignore further media navigations entirely — the
        # player keeps running. A new video only starts after the current
        # overlay is torn down by an explicit user navigation (back/forward/
        # reload/address bar), which clears ``_playing_url``.
        # NOTE: we gate on ``_playing_url`` rather than ``overlay.isVisible()``
        # because an inactive/background tab page reports isVisible()==False
        # even while its overlay is shown, which let the loop slip through.
        ov = getattr(self, '_video_overlay', None)
        if getattr(self, '_playing_url', None) is not None and ov is not None:
            return
        self._playing_url = media_url
        if ov is None:
            self._video_overlay = NativeVideoOverlay(self)
        overlay = self._video_overlay
        print("PLAYER: play_inline", (media_url or "")[:90], flush=True)
        # Swap the whole web area out for the player instead of overlaying it:
        # on macOS the web view is a native surface that steals all mouse input
        # and can't be reliably composited under, so we hide the web area and
        # put the player in its place in the layout. Restored on close/reload.
        self._embed_overlay()
        try:
            referer = self.web_view.url().toString()
        except Exception:
            referer = None
        # Prefer the site's own quality URLs (HD/SD/HLS) captured from the page
        # so the player offers the same choices as the in-site player; fall
        # back to the single intercepted URL when we couldn't parse them.
        sources = getattr(self, '_media_sources', None)
        if sources and any(sources.values()):
            overlay.play_sources(sources, referer=referer)
        else:
            overlay.play_url(media_url, referer=referer)
        overlay.show()
        overlay.raise_()
        overlay.setFocus()

    def _extract_media_sources(self):
        """Parse the page for the site player's quality URLs (HD/SD/HLS).

        Tube sites configure their HTML5 player with calls like
        ``html5player.setVideoUrlHigh('...')``. We read those (and the JSON-LD
        ``contentUrl``) so the native overlay can play — and switch between —
        the same streams the built-in player would use. We also detect a
        ``blob:``/MSE ``<video>`` so pages the bundled Chromium can't decode
        (which show a "Source error") can be auto-played in the overlay.
        """
        if not WEBENGINE_AVAILABLE:
            return
        js = r"""
        (function(){
          try{
            var h=document.documentElement.innerHTML;
            function g(re){var m=h.match(re);return m?m[1]:'';}
            var o={High:'',Low:'',HLS:''};
            o.High = g(/setVideoUrlHigh\('([^']+)'\)/) || g(/setVideoHLS\("([^"]+)"\)/);
            o.Low  = g(/setVideoUrlLow\('([^']+)'\)/);
            o.HLS  = g(/setVideoHLS\('([^']+)'\)/);
            // JSON-LD contentUrl: pick one that is a real stream file.
            if(!o.High && !o.Low && !o.HLS){
              var urls=[], re=/"contentUrl":\s*"([^"]+)"/g, m;
              while((m=re.exec(h))!==null){ urls.push(m[1].replace(/\\\//g,'/')); }
              for(var i=0;i<urls.length;i++){
                if(/\.m3u8(\?|$)/i.test(urls[i])){ o.HLS=urls[i]; break; }
              }
              if(!o.HLS){ for(var j=0;j<urls.length;j++){
                if(/\.mp4(\?|$)/i.test(urls[j])){ o.High=urls[j]; break; } } }
            }
            // Inspect real <video> elements for a stream we can hand to FFmpeg,
            // and flag blob/MSE playback the bundled Chromium can't decode.
            var blob=false, vids=document.getElementsByTagName('video');
            for(var k=0;k<vids.length;k++){
              var s=vids[k].currentSrc||vids[k].src||'';
              if(s.indexOf('blob:')===0) blob=true;
              if(/\.m3u8(\?|$)/i.test(s) && !o.HLS) o.HLS=s;
              else if(/\.mp4(\?|$)/i.test(s) && !o.High) o.High=s;
              var srcs=vids[k].getElementsByTagName('source');
              for(var p=0;p<srcs.length;p++){
                var ss=srcs[p].src||'';
                if(/\.m3u8(\?|$)/i.test(ss) && !o.HLS) o.HLS=ss;
                else if(/\.mp4(\?|$)/i.test(ss) && !o.High) o.High=ss;
              }
            }
            // Last resort: any HLS master playlist anywhere in the page markup
            // (covers sites whose player config we don't parse explicitly).
            if(!o.HLS && !o.High && !o.Low){
              var mm=h.match(/(https?:\/\/[^"'\\ )<>]+\.m3u8[^"'\\ )<>]*)/);
              if(mm) o.HLS=mm[1].replace(/\\\//g,'/');
            }
            o.hasVideo = vids.length>0;
            o.blob = blob;
            return JSON.stringify(o);
          }catch(e){ return '{}'; }
        })();
        """
        try:
            self.web_view.page().runJavaScript(js, self._on_media_sources)
        except Exception:
            pass

    def _on_media_sources(self, result):
        import json
        try:
            data = json.loads(result) if result else {}
        except Exception:
            data = {}
        self._media_sources = {
            'High': data.get('High') or '',
            'Low': data.get('Low') or '',
            'HLS': data.get('HLS') or '',
        }
        # Auto-launch the native overlay when the page plays through a
        # blob/MSE <video> the bundled Chromium can't decode (it shows a
        # "Source error"), but we extracted a real HLS/MP4 URL that our
        # FFmpeg-backed player can handle. Gated on an actual stream URL so it
        # only fires on genuine video pages, and once per page load.
        if getattr(self, '_media_autoplayed', False):
            return
        best = (self._media_sources['HLS'] or self._media_sources['High']
                or self._media_sources['Low'])
        if best and (data.get('blob') or data.get('hasVideo')):
            self._media_autoplayed = True
            self._play_inline(best)

    def _embed_overlay(self):
        """Put the player in the tab layout in place of the web view."""
        ov = getattr(self, '_video_overlay', None)
        if ov is None:
            return
        lay = self.layout()
        if lay is not None and lay.indexOf(ov) == -1:
            idx = lay.indexOf(self.split)
            lay.insertWidget(idx + 1 if idx >= 0 else lay.count(), ov, 1)
        try:
            self.web_view.hide()
            self.split.hide()
        except Exception:
            pass
        ov.show()
        ov.raise_()
        ov.setFocus()

    def _on_overlay_closed(self):
        """Restore the web view and tear down the player after it's closed.

        The overlay (and its QMediaPlayer / QVideoSink) is destroyed rather
        than reused, so the next play starts from a clean state — reusing a
        stopped player left it unable to open a new stream on replay.
        """
        ov = getattr(self, '_video_overlay', None)
        try:
            lay = self.layout()
            if ov is not None and lay is not None and lay.indexOf(ov) != -1:
                lay.removeWidget(ov)
            self.split.show()
            self.web_view.show()
        finally:
            if ov is not None:
                ov.setParent(None)
                ov.deleteLater()
            self._video_overlay = None
            self._playing_url = None

    def _position_video_overlay(self):
        # The layout now manages the player's geometry; kept as a no-op so the
        # existing resize / move handlers stay harmless.
        return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        ov = getattr(self, '_video_overlay', None)
        if ov is not None and ov.isVisible():
            self._position_video_overlay()

    def moveEvent(self, event):
        super().moveEvent(event)
        ov = getattr(self, '_video_overlay', None)
        if ov is not None and ov.isVisible():
            self._position_video_overlay()

    def _enhance_media_page(self):
        """Give bare media pages a full-window, dark, Chrome-style player.

        When a link points straight at a video/audio file, Chromium renders a
        tiny default player. We blow it up to fill the viewport, force the
        native controls on, and add a black backdrop so it looks and behaves
        like Chrome's built-in media viewer.
        """
        if not WEBENGINE_AVAILABLE or not self._is_media_url():
            return
        js = (
            "(function(){"
            "var v=document.querySelector('video')||document.querySelector('audio');"
            "if(!v)return;"
            "var isAudio=v.tagName==='AUDIO';"
            "document.documentElement.style.cssText='background:#0a0a0a;height:100%';"
            "document.body.style.cssText='background:#0a0a0a;margin:0;height:100%;"
            "display:flex;align-items:center;justify-content:center;overflow:hidden';"
            "v.setAttribute('controls','');v.controls=true;"
            "v.setAttribute('playsinline','');v.setAttribute('preload','auto');"
            "v.style.cssText=isAudio?'width:70vw;max-width:640px':"
            "'width:100vw;height:100vh;max-width:100vw;max-height:100vh;"
            "background:#000;object-fit:contain;outline:none';"
            "try{v.focus();}catch(e){}"
            "})();"
        )
        try:
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    # ── Fullscreen ────────────────────────────────────────────────────────
    def _on_fullscreen_requested(self, request):
        """Grant HTML5 fullscreen by hosting the web view in a full-screen window."""
        try:
            request.accept()
        except Exception:
            return
        if getattr(request, 'toggleOn', lambda: False)():
            # Enter: move the web view into a dedicated full-screen host.
            self._fs_prev_index = self.split.indexOf(self.web_view)
            if self._fs_host is None:
                self._fs_host = _FullScreenHost(self)
            self._fs_host._layout.addWidget(self.web_view)
            self._fs_host.showFullScreen()
            self.web_view.show()
            self.web_view.setFocus()
        else:
            # Exit: return the web view to its splitter slot.
            idx = self._fs_prev_index if self._fs_prev_index is not None else 0
            self.split.insertWidget(idx, self.web_view)
            self.web_view.show()
            self.web_view.setFocus()
            if self._fs_host is not None:
                self._fs_host.hide()
            self._fs_prev_index = None

    def _request_exit_fullscreen(self):
        """Ask the page to leave fullscreen (drives _on_fullscreen_requested)."""
        try:
            self.web_view.page().runJavaScript(
                "if(document.exitFullscreen){document.exitFullscreen();}"
                "else if(document.webkitExitFullscreen){"
                "document.webkitExitFullscreen();}")
        except Exception:
            pass

    # ── Navigation helpers ────────────────────────────────────────────────
    def set_chrome_visible(self, visible):
        """Show/hide the navigation toolbar (used when embedding a local app)."""
        tb = getattr(self, 'nav_toolbar', None)
        if tb is not None:
            tb.setVisible(visible)

    def navigate_to(self, text):
        """Load a URL, or run a Google search if the text isn't a URL."""
        self._teardown_inline_player()
        url = self._resolve_url(text)
        self.web_view.setUrl(QUrl(url))

    def _create_linked_view(self):
        """Return the web view a new tab/window link should load into.

        ``new_tab_factory`` is set by the tab container to spawn a sibling
        browser tab; its ``web_view`` is handed back to Chromium so the link
        loads there. Falls back to the current view when no factory is set.
        """
        factory = getattr(self, 'new_tab_factory', None)
        if factory is None:
            return self.web_view
        try:
            new_browser = factory()
        except Exception:
            new_browser = None
        if new_browser is not None and getattr(new_browser, 'web_view', None):
            return new_browser.web_view
        return self.web_view


    def current_url(self):
        """Return the currently-loaded URL as a string (for state saving)."""
        if not WEBENGINE_AVAILABLE:
            return self.home_url
        url = self.web_view.url().toString()
        return url or self.home_url

    def toggle_devtools(self, checked=None):
        """Show/hide an embedded DevTools (Inspect Element) pane."""
        if not WEBENGINE_AVAILABLE:
            return
        currently_open = self.devtools_view is not None
        want_open = checked if checked is not None else not currently_open

        if want_open and not currently_open:
            self.devtools_view = QWebEngineView()
            self.devtools_view.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.web_view.page().setDevToolsPage(self.devtools_view.page())
            self.split.addWidget(self.devtools_view)
            total = max(self.split.height(), 300)
            self.split.setSizes([total * 2 // 3, total // 3])
        elif not want_open and currently_open:
            # Fully tear down DevTools so the inspect-mode overlay and any
            # crosshair/resize cursor left behind get cleared.
            try:
                self.web_view.page().setDevToolsPage(None)
            except Exception:
                pass
            self.devtools_view.setParent(None)
            self.devtools_view.deleteLater()
            self.devtools_view = None
            # Reset any lingering override cursor from inspect mode / splitter.
            from qtpy.QtWidgets import QApplication
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            self.web_view.unsetCursor()
            self.unsetCursor()

        if hasattr(self, 'inspect_btn'):
            self.inspect_btn.setChecked(self.devtools_view is not None)

    @staticmethod
    def _resolve_url(text):
        text = text.strip()
        if not text:
            return DEFAULT_HOME
        # Already has a scheme
        if text.startswith(("http://", "https://", "file://", "about:")):
            return text
        # Looks like a domain (contains a dot and no spaces)
        if "." in text and " " not in text:
            return "https://" + text
        # Otherwise treat as a search query
        from qtpy.QtCore import QUrl as _QUrl
        query = _QUrl.toPercentEncoding(text).data().decode()
        return f"https://www.google.com/search?q={query}"

    def _on_address_entered(self):
        self.navigate_to(self.address_bar.text())

    # ── Signal handlers ───────────────────────────────────────────────────
    def _on_url_changed(self, qurl):
        self.address_bar.setText(qurl.toString())
        self.address_bar.setCursorPosition(0)
        self._update_nav_buttons()

    def _on_load_started(self):
        # A reload / navigation invalidates everything captured so far:
        # drop it and start grabbing fresh for the new page.
        self.captured_requests = []
        self.captured_ws = []
        self.media_sessions = []
        self._session_by_id = {}
        self.captureReset.emit()
        self.progress.setValue(0)
        self.progress.show()
        self._set_address_progress(0)
        # Page isn't up yet: reset the meter and show the default logo/name.
        self._net_loaded = False
        self._net_last = None
        self._media_sources = {}
        self._media_autoplayed = False
        self.tabFaviconChanged.emit(QIcon())
        self.tabLabelChanged.emit(self._compute_site_name())
        # NOTE: the inline player is intentionally NOT torn down here. Tube
        # sites auto-reload the page underneath (each reload feeding a new
        # media navigation); tearing the overlay down on every such reload
        # restarted playback in a loop that never opened. The overlay is now
        # closed only on explicit user navigation (see _teardown_inline_player).

    def _teardown_inline_player(self):
        """Close the inline video overlay in response to a user navigation."""
        ov = getattr(self, '_video_overlay', None)
        if ov is not None:
            ov.stop_and_hide()

    def _on_load_progress(self, value):
        self.progress.setValue(value)
        self._set_address_progress(value)

    def _on_load_finished(self, ok):
        self.progress.hide()
        self._set_address_progress(None)
        self._inject_cosmetic_css()
        self._downgrade_modern_css()
        self._enhance_media_page()
        self._extract_media_sources()
        self._update_nav_buttons()
        self._site_name = self._compute_site_name()
        if ok:
            self._net_loaded = True
            # Show the favicon if we already have one; otherwise the default
            # logo stays until iconChanged fires.
            icon = self.web_view.icon()
            if icon is not None and not icon.isNull():
                self.tabFaviconChanged.emit(icon)
        else:
            # Error / aborted load: fall back to the default logo.
            self._net_loaded = False
            self.tabFaviconChanged.emit(QIcon())
        self.tabLabelChanged.emit(self._site_name)

    def _set_address_progress(self, value):
        """Paint a loading fill behind the address bar text.

        ``value`` is 0-100 during a load, or ``None`` to clear the fill and
        restore the normal address-bar style.
        """
        if value is None or value >= 100:
            self.address_bar.setStyleSheet(self._address_base_style)
            return
        frac = max(0.0, min(1.0, value / 100.0))
        edge = min(frac + 0.001, 1.0)
        fill = (
            "QLineEdit { color:#e0e0e0; border:1px solid #555; "
            "border-radius:12px; padding:5px 12px; "
            "selection-background-color:#094771; "
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #0e5a8a, stop:{frac:.3f} #0e5a8a, "
            f"stop:{edge:.3f} #3c3c3c, stop:1 #3c3c3c); }}"
            "QLineEdit:focus { border:1px solid #007acc; }"
        )
        self.address_bar.setStyleSheet(fill)

    def _on_title_changed(self, title):
        self._page_title = title or "Browser"

    def _update_nav_buttons(self):
        history = self.web_view.history()
        self.back_btn.setEnabled(history.canGoBack())
        self.forward_btn.setEnabled(history.canGoForward())

    def current_title(self):
        return getattr(self, "_page_title", "Browser")
