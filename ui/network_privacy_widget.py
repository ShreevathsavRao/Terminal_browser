"""VPN / Tor control page for the browser tools panel.

Renders the per-tab network-privacy controls (bound to a
:class:`core.network_privacy.NetworkPrivacyManager`) with both a one-click
auto setup and a fully configurable manual setup.
"""

from qtpy.QtCore import Qt
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QListWidget, QScrollArea, QFrame, QApplication, QMessageBox)


_BTN = ("QPushButton {{ background:{c}; color:white; border:none; "
        "border-radius:4px; padding:6px 10px; font-weight:bold; }}"
        "QPushButton:hover {{ background:{h}; }}"
        "QPushButton:disabled {{ background:#555; color:#999; }}")


def _section(title):
    lbl = QLabel(title)
    lbl.setStyleSheet("color:#4FC3F7; font-size:12px; font-weight:bold; "
                      "padding:6px 2px 2px 2px;")
    return lbl


def _divider():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Plain)
    line.setStyleSheet("color:#3a3a3a; background:#3a3a3a; max-height:1px;")
    return line


class NetworkPrivacyPage(QWidget):
    """One tab's VPN/Tor controls. Rebound via :meth:`set_manager`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mgr = None
        self._browser = None
        self._auto_after_install = False
        self._build_ui()

    # ── construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(4)

        # Status banner
        self.status_lbl = QLabel("Direct connection")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(
            "color:#ddd; font-size:12px; font-weight:bold; padding:8px; "
            "background:#333; border-radius:4px;")
        outer.addWidget(self.status_lbl)

        note = QLabel(
            "ℹ Scope is per-tab: each tab remembers its own route and it is "
            "applied when the tab is active. Note — Chromium applies one proxy "
            "app-wide, so only the active tab's route is live at a time. "
            "⚠ Free public proxies are untrusted: never use them for logins.")
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#D7A100; font-size:10px; padding:6px; background:#332b00; "
            "border:1px solid #5a4a00; border-radius:4px;")
        outer.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(4)
        v.setAlignment(Qt.AlignTop)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # ── Quick (auto) setup ────────────────────────────────────────────
        v.addWidget(_section("⚡ Auto setup (one click)"))
        row = QHBoxLayout()
        self.btn_auto_tor = QPushButton("🧅 Auto Tor")
        self.btn_auto_tor.setStyleSheet(_BTN.format(c='#7E57C2', h='#673AB7'))
        self.btn_auto_tor.setCursor(Qt.PointingHandCursor)
        self.btn_auto_tor.clicked.connect(lambda: self._auto_tor())
        row.addWidget(self.btn_auto_tor)
        self.btn_auto_vpn = QPushButton("🛡 Auto VPN")
        self.btn_auto_vpn.setStyleSheet(_BTN.format(c='#26A69A', h='#00897B'))
        self.btn_auto_vpn.setCursor(Qt.PointingHandCursor)
        self.btn_auto_vpn.clicked.connect(lambda: self._auto_vpn())
        row.addWidget(self.btn_auto_vpn)
        v.addLayout(row)

        # ── Mode ──────────────────────────────────────────────────────────
        v.addWidget(_divider())
        v.addWidget(_section("Mode"))
        mrow = QHBoxLayout()
        self.btn_direct = QPushButton("Direct")
        self.btn_direct.setStyleSheet(_BTN.format(c='#607D8B', h='#455A64'))
        self.btn_direct.setCursor(Qt.PointingHandCursor)
        self.btn_direct.clicked.connect(lambda: self._set_direct())
        mrow.addWidget(self.btn_direct)
        v.addLayout(mrow)

        # ── Tor (configurable) ────────────────────────────────────────────
        v.addWidget(_divider())
        v.addWidget(_section("🧅 Tor"))
        self.tor_status = QLabel("Idle")
        self.tor_status.setStyleSheet("color:#aaa; font-size:11px; padding:0 2px;")
        v.addWidget(self.tor_status)
        trow = QHBoxLayout()
        self.btn_tor_connect = QPushButton("Connect")
        self.btn_tor_connect.setStyleSheet(_BTN.format(c='#7E57C2', h='#673AB7'))
        self.btn_tor_connect.setCursor(Qt.PointingHandCursor)
        self.btn_tor_connect.clicked.connect(lambda: self._tor_connect())
        trow.addWidget(self.btn_tor_connect)
        self.btn_new_id = QPushButton("New Identity")
        self.btn_new_id.setStyleSheet(_BTN.format(c='#5C6BC0', h='#3949AB'))
        self.btn_new_id.setCursor(Qt.PointingHandCursor)
        self.btn_new_id.clicked.connect(lambda: self._new_identity())
        trow.addWidget(self.btn_new_id)
        v.addLayout(trow)
        self.btn_install_tor = QPushButton("Install Tor (Homebrew)")
        self.btn_install_tor.setStyleSheet(_BTN.format(c='#EF6C00', h='#E65100'))
        self.btn_install_tor.setCursor(Qt.PointingHandCursor)
        self.btn_install_tor.clicked.connect(lambda: self._install_tor())
        v.addWidget(self.btn_install_tor)

        # ── Proxy / VPN (configurable) ────────────────────────────────────
        v.addWidget(_divider())
        v.addWidget(_section("🛡 Proxy / VPN"))
        prow = QHBoxLayout()
        self.proto = QComboBox()
        self.proto.addItems(["http", "socks5"])
        self.proto.setStyleSheet(
            "QComboBox{background:#3c3c3c;color:#e0e0e0;border:1px solid #555;"
            "border-radius:4px;padding:4px;}")
        prow.addWidget(self.proto)
        self.btn_refresh = QPushButton("↻ Refresh list")
        self.btn_refresh.setStyleSheet(_BTN.format(c='#455A64', h='#37474F'))
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(lambda: self._refresh_proxies())
        prow.addWidget(self.btn_refresh)
        v.addLayout(prow)

        self.proxy_list = QListWidget()
        self.proxy_list.setStyleSheet(
            "QListWidget{background:#1e1e1e;color:#ddd;border:1px solid #555;"
            "border-radius:4px;} QListWidget::item:selected{background:#094771;}")
        self.proxy_list.setMinimumHeight(120)
        self.proxy_list.itemDoubleClicked.connect(lambda _i: self._connect_selected())
        v.addWidget(self.proxy_list)

        self.btn_connect_sel = QPushButton("Connect via selected country")
        self.btn_connect_sel.setStyleSheet(_BTN.format(c='#26A69A', h='#00897B'))
        self.btn_connect_sel.setCursor(Qt.PointingHandCursor)
        self.btn_connect_sel.clicked.connect(lambda: self._connect_selected())
        v.addWidget(self.btn_connect_sel)

        # Manual entry
        mline = QHBoxLayout()
        self.host_in = QLineEdit()
        self.host_in.setPlaceholderText("host / IP")
        self.port_in = QLineEdit()
        self.port_in.setPlaceholderText("port")
        self.port_in.setFixedWidth(70)
        for w in (self.host_in, self.port_in):
            w.setStyleSheet(
                "QLineEdit{background:#3c3c3c;color:#e0e0e0;border:1px solid #555;"
                "border-radius:4px;padding:4px;}")
        mline.addWidget(self.host_in, 1)
        mline.addWidget(self.port_in)
        v.addLayout(mline)
        self.btn_connect_manual = QPushButton("Connect to manual proxy")
        self.btn_connect_manual.setStyleSheet(_BTN.format(c='#00897B', h='#00695C'))
        self.btn_connect_manual.setCursor(Qt.PointingHandCursor)
        self.btn_connect_manual.clicked.connect(lambda: self._connect_manual())
        v.addWidget(self.btn_connect_manual)

        # ── Verify ────────────────────────────────────────────────────────
        v.addWidget(_divider())
        v.addWidget(_section("Verify"))
        self.btn_check_ip = QPushButton("🌐 Check my IP / Tor status")
        self.btn_check_ip.setStyleSheet(_BTN.format(c='#3F51B5', h='#303F9F'))
        self.btn_check_ip.setCursor(Qt.PointingHandCursor)
        self.btn_check_ip.clicked.connect(lambda: self._check_ip())
        v.addWidget(self.btn_check_ip)

        # ── Persistent Stop (bottom) ──────────────────────────────────────
        self.btn_tor_stop = QPushButton("⏹ Stop (disconnect)")
        self.btn_tor_stop.setStyleSheet(_BTN.format(c='#8D6E63', h='#6D4C41'))
        self.btn_tor_stop.setCursor(Qt.PointingHandCursor)
        self.btn_tor_stop.clicked.connect(lambda: self._set_direct())
        outer.addWidget(self.btn_tor_stop)

    # ── binding ───────────────────────────────────────────────────────────
    def set_manager(self, manager, browser):
        """Bind the page to the active tab's manager (and its browser)."""
        if self._mgr is not None:
            for sig, slot in (
                    (self._mgr.statusChanged, self._on_status),
                    (self._mgr.proxyListReady, self._fill_list),
                    (self._mgr.proxyListFailed, self._on_list_failed),
                    (self._mgr.torInstallProgress, self._on_install_progress),
                    (self._mgr.torInstallDone, self._on_install_done)):
                try:
                    sig.disconnect(slot)
                except Exception:
                    pass
        self._mgr = manager
        self._browser = browser
        if manager is not None:
            manager.statusChanged.connect(self._on_status)
            manager.proxyListReady.connect(self._fill_list)
            manager.proxyListFailed.connect(self._on_list_failed)
            manager.torInstallProgress.connect(self._on_install_progress)
            manager.torInstallDone.connect(self._on_install_done)
            self._on_status(manager.mode, manager.state, manager.detail)
        self._refresh_availability()

    def _refresh_availability(self):
        from core.network_privacy import NetworkPrivacyManager
        has_tor = NetworkPrivacyManager.tor_available()
        self.btn_install_tor.setVisible(not has_tor)
        enabled = self._mgr is not None
        # Proxy/VPN + general controls: available whenever a tab is bound.
        for b in (self.btn_auto_vpn, self.btn_direct, self.btn_connect_sel,
                  self.btn_connect_manual, self.btn_refresh, self.btn_check_ip,
                  self.btn_tor_stop):
            b.setEnabled(enabled)
        # Tor controls also require the tor binary to be installed.
        for b in (self.btn_auto_tor, self.btn_tor_connect, self.btn_new_id):
            b.setEnabled(enabled and has_tor)
        self.btn_install_tor.setEnabled(enabled)

    # ── status ────────────────────────────────────────────────────────────
    def _on_status(self, mode, state, detail):
        colors = {'on': '#1B5E20', 'starting': '#5D4037',
                  'error': '#7f1d1d', 'off': '#333'}
        self.status_lbl.setStyleSheet(
            f"color:#fff; font-size:12px; font-weight:bold; padding:8px; "
            f"background:{colors.get(state, '#333')}; border-radius:4px;")
        icon = {'tor': '🧅', 'proxy': '🛡', 'direct': '🔓'}.get(mode, '')
        self.status_lbl.setText(f"{icon} {detail}")
        if mode == 'tor':
            self.tor_status.setText(detail)
        # When the route changes to a live one *or back to direct*, reload so
        # the page actually reconnects over the new route (pressing Stop must
        # restore connectivity immediately).
        if state in ('on', 'off') and self._browser is not None:
            try:
                self._browser.web_view.reload()
            except Exception:
                pass

    # ── actions ───────────────────────────────────────────────────────────
    def _guard(self):
        if self._mgr is None:
            QMessageBox.information(self, "No browser",
                                    "Open a browser tab first.")
            return False
        return True

    def _set_direct(self):
        if self._guard():
            self._mgr.set_direct()

    def _tor_connect(self):
        if self._guard():
            self._start_tor_with_choice()

    def _auto_tor(self):
        if not self._guard():
            return
        from core.network_privacy import NetworkPrivacyManager
        if not NetworkPrivacyManager.tor_available():
            self._auto_after_install = True
            self._start_install()
            return
        self._start_tor_with_choice()

    def _start_tor_with_choice(self):
        """Start Tor, asking whether to reuse another tab's live network.

        When another tab already has a connected Tor circuit, prompt the user
        to either share that same network or spin up a fresh, independent Tor
        network for this tab.
        """
        if not self._mgr.has_live_tor_elsewhere():
            self._mgr.start_tor()
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Tor network")
        box.setText("Another tab is already connected to Tor.")
        box.setInformativeText(
            "Use the same Tor network as the other tab, or start a new, "
            "independent Tor network for this tab?")
        same_btn = box.addButton("Same network", QMessageBox.AcceptRole)
        new_btn = box.addButton("New network", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(same_btn)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is same_btn:
            self._mgr.start_tor(force_new=False)
        elif clicked is new_btn:
            self._mgr.start_tor(force_new=True)
        # Cancel: leave the route unchanged.

    def _auto_vpn(self):
        if self._guard():
            self._mgr.auto_proxy(self.proto.currentText())

    def _new_identity(self):
        if not self._guard():
            return
        ok, msg = self._mgr.tor_new_identity()
        if ok and self._browser is not None:
            self._browser.web_view.reload()
        elif not ok:
            QMessageBox.warning(self, "New Identity", msg)

    def _install_tor(self):
        self._auto_after_install = False
        self._start_install()

    def _start_install(self):
        """Kick off the async Homebrew install with immediate button feedback."""
        if not self._guard():
            return False
        self.btn_install_tor.setEnabled(False)
        self.btn_install_tor.setText("⏳ Installing Tor…")
        self.btn_auto_tor.setEnabled(False)
        self.tor_status.setText("Starting Homebrew install of Tor…")
        self._mgr.install_tor_async()
        return True

    def _on_install_progress(self, line):
        self.tor_status.setText(f"Installing: {line}")

    def _on_install_done(self, ok, msg):
        self.btn_install_tor.setText("Install Tor (Homebrew)")
        self.btn_install_tor.setEnabled(True)
        self.btn_auto_tor.setEnabled(True)
        self.tor_status.setText(msg)
        self._refresh_availability()
        if ok:
            if self._auto_after_install:
                self._auto_after_install = False
                self._start_tor_with_choice()
            else:
                QMessageBox.information(self, "Install Tor", msg)
        else:
            self._auto_after_install = False
            QMessageBox.warning(self, "Install Tor", msg)

    def _refresh_proxies(self):
        if not self._guard():
            return
        self.proxy_list.clear()
        self.proxy_list.addItem("Fetching…")
        self._mgr.refresh_proxies(self.proto.currentText())

    def _fill_list(self, proxies):
        """Show one row per country; connecting picks a working proxy there."""
        from qtpy.QtWidgets import QListWidgetItem
        self.proxy_list.clear()
        # Group all proxies by country name.
        by_country = {}
        for entry in proxies:
            host, port = entry[0], int(entry[1])
            country = (entry[2] if len(entry) > 2 else '') or 'Unknown'
            by_country.setdefault(country, []).append((host, port))
        self._proxies_by_country = by_country
        if not by_country:
            self.proxy_list.addItem("(no proxies found)")
            return
        # Sort countries by proxy count (most first), ties broken by name.
        for country in sorted(by_country, key=lambda c: (-len(by_country[c]), c)):
            hosts = by_country[country]
            item = QListWidgetItem(f"{country}   ·  {len(hosts)} proxies")
            item.setData(Qt.UserRole, country)
            self.proxy_list.addItem(item)

    def _on_list_failed(self, msg):
        self.proxy_list.clear()
        self.proxy_list.addItem("(failed to fetch proxies)")

    def _connect_selected(self):
        if not self._guard():
            return
        item = self.proxy_list.currentItem()
        if not item:
            return
        country = item.data(Qt.UserRole)
        if not country:
            return
        candidates = getattr(self, '_proxies_by_country', {}).get(country, [])
        self._mgr.connect_country(self.proto.currentText(), country, candidates)

    def _connect_manual(self):
        if not self._guard():
            return
        host = self.host_in.text().strip()
        port = self.port_in.text().strip()
        if not host or not port.isdigit():
            QMessageBox.information(self, "Proxy",
                                    "Enter a valid host and numeric port.")
            return
        self._mgr.connect_proxy(self.proto.currentText(), host, int(port))

    def _check_ip(self):
        if self._browser is not None:
            try:
                from qtpy.QtCore import QUrl
                self._browser.web_view.setUrl(QUrl("https://check.torproject.org/"))
            except Exception:
                pass
