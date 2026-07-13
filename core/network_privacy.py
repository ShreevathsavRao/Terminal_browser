"""Network privacy for the embedded browser: Tor and free-proxy routing.

This module centralises how the QtWebEngine browser reaches the network. Three
modes are supported:

* ``direct``  – no proxy, traffic goes out on the real connection.
* ``tor``     – a local ``tor`` daemon is launched and the browser is pointed at
  its SOCKS5 port (``127.0.0.1:9050``); a "New Identity" command is available.
* ``proxy``   – the browser is routed through a single free public SOCKS5/HTTP
  proxy chosen from a refreshable list.

Routing is applied with :func:`QNetworkProxy.setApplicationProxy`, which
QtWebEngine honours for subsequent requests (callers should reload the page
after switching so every request uses the new route).

SECURITY NOTE: free public proxies are operated by unknown third parties and can
log or tamper with traffic. They must never be used for logins or anything
sensitive. Tor is far safer for anonymity but slower.
"""

import os
import re
import json
import shutil
import socket
import weakref
import tempfile
import subprocess
from urllib.request import urlopen, Request

from qtpy.QtCore import QObject, Signal, QProcess, QThread
from qtpy.QtNetwork import QNetworkProxy


# Free, community-maintained proxy lists (ip:port per line). Multiple sources
# are tried so a single one being down does not break the feature.
_PROXY_SOURCES = {
    'socks5': [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
    ],
    'http': [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000",
        "https://www.proxy-list.download/api/v1/get?type=http",
    ],
}

_IPPORT_RE = re.compile(r'^\s*(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})\s*$')


def _free_port():
    """Return an available TCP port on localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
    finally:
        s.close()


class _ProxyFetcher(QThread):
    """Fetches, de-duplicates and geolocates a proxy list off the UI thread."""

    done = Signal(list)          # list[(host, port, country_code)]
    failed = Signal(str)

    def __init__(self, protocol, parent=None):
        super().__init__(parent)
        self._protocol = protocol

    def run(self):
        seen, out = set(), []
        errors = []
        for url in _PROXY_SOURCES.get(self._protocol, []):
            try:
                req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urlopen(req, timeout=12) as resp:
                    text = resp.read().decode('utf-8', 'ignore')
            except Exception as exc:  # try the next source
                errors.append(str(exc))
                continue
            for line in text.splitlines():
                m = _IPPORT_RE.match(line)
                if not m:
                    continue
                host, port = m.group(1), int(m.group(2))
                if 0 < port < 65536 and (host, port) not in seen:
                    seen.add((host, port))
                    out.append((host, port))
            if out:
                break
        if not out:
            self.failed.emit("; ".join(errors) or "no proxies returned")
            return
        out = out[:100]  # cap (also the ip-api batch limit)
        countries = self._geolocate([h for h, _ in out])
        self.done.emit([(h, p, countries.get(h, '')) for h, p in out])

    @staticmethod
    def _geolocate(ips):
        """Return {ip: country_name} using ip-api.com's free batch endpoint."""
        if not ips:
            return {}
        try:
            body = json.dumps(list(ips)).encode()
            req = Request("http://ip-api.com/batch?fields=country,query",
                          data=body, headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=12) as resp:
                rows = json.loads(resp.read().decode('utf-8', 'ignore'))
            return {r.get('query'): r.get('country', '')
                    for r in rows if isinstance(r, dict)}
        except Exception:
            return {}


class _ProxyTester(QThread):
    """Finds the first proxy that can actually tunnel HTTPS traffic.

    A plain TCP-connect check is not enough: many free proxies accept the
    connection but never forward anything (or forward plain HTTP only), which
    silently breaks browsing. Since real sites are HTTPS, each candidate is
    validated by opening a CONNECT tunnel to a known host on port 443.
    """

    found = Signal(str, int)     # host, port
    failed = Signal(str)

    _TEST_HOST = 'www.google.com'
    _TEST_PORT = 443                 # HTTPS — what the browser really needs

    def __init__(self, proxies, protocol='http', parent=None):
        super().__init__(parent)
        self._proxies = list(proxies)[:40]
        self._protocol = protocol

    def run(self):
        for entry in self._proxies:
            host, port = entry[0], int(entry[1])
            if self._works(host, port):
                self.found.emit(host, port)
                return
        self.failed.emit(
            "No working proxy found in the list. Free proxies are unreliable — "
            "try 'Refresh list' for a fresh set or use a proxy you trust.")

    def _works(self, host, port):
        try:
            if self._protocol == 'socks5':
                return self._check_socks5(host, port)
            return self._check_http(host, port)
        except Exception:
            return False

    def _check_http(self, host, port):
        # An HTTP proxy must honour CONNECT to tunnel HTTPS for the browser.
        sock = socket.create_connection((host, port), timeout=6)
        try:
            sock.settimeout(6)
            req = (f"CONNECT {self._TEST_HOST}:{self._TEST_PORT} HTTP/1.1\r\n"
                   f"Host: {self._TEST_HOST}:{self._TEST_PORT}\r\n"
                   f"Connection: close\r\n\r\n")
            sock.sendall(req.encode())
            resp = sock.recv(64)
            # A successful tunnel replies "HTTP/1.x 200 …".
            return resp.startswith(b'HTTP/') and b' 200' in resp
        finally:
            sock.close()

    def _check_socks5(self, host, port):
        sock = socket.create_connection((host, port), timeout=6)
        try:
            sock.settimeout(6)
            # Greeting: version 5, one method, "no authentication".
            sock.sendall(b'\x05\x01\x00')
            if sock.recv(2) != b'\x05\x00':
                return False
            # CONNECT to the test host:443 by domain name.
            dst = self._TEST_HOST.encode()
            req = (b'\x05\x01\x00\x03' + bytes([len(dst)]) + dst +
                   self._TEST_PORT.to_bytes(2, 'big'))
            sock.sendall(req)
            reply = sock.recv(4)
            # rep == 0x00 means the tunnel to :443 was established.
            return len(reply) >= 2 and reply[0] == 0x05 and reply[1] == 0x00
        finally:
            sock.close()



class _TorCircuit:
    """A running Tor daemon shared between tabs via reference counting.

    The ``QProcess`` is created without a Qt parent so it outlives the tab
    that launched it — a child tab can keep the circuit alive after its parent
    closes. ``users`` tracks every manager routing through it; the daemon is
    only terminated once the last user detaches.
    """

    __slots__ = ('proc', 'socks_port', 'control_port', 'tor_dir', 'users')

    def __init__(self, proc, socks_port, control_port, tor_dir):
        self.proc = proc
        self.socks_port = socks_port
        self.control_port = control_port
        self.tor_dir = tor_dir
        self.users = set()           # NetworkPrivacyManager instances


class NetworkPrivacyManager(QObject):
    """Owns the browser's network route (direct / Tor / proxy)."""

    # mode, state, human-readable detail
    statusChanged = Signal(str, str, str)
    proxyListReady = Signal(list)
    proxyListFailed = Signal(str)
    torInstallProgress = Signal(str)
    torInstallDone = Signal(bool, str)

    # Every live manager (one per browser tab). Lets a tab reuse a Tor
    # circuit another tab already has running instead of starting a second
    # daemon, the same way a child tab adopts its parent's route.
    _instances = weakref.WeakSet()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = 'direct'
        self.state = 'off'
        self.detail = 'Direct connection'
        self._circuit = None             # _TorCircuit (owned or borrowed)
        self._borrowed_tor = False       # True when sharing another tab's Tor
        self._tor_dir = None             # temp DataDirectory
        self._socks_port = None          # chosen per instance (multi-tab safe)
        self._control_port = None
        self._fetcher = None
        self._tester = None
        self._installer = None           # QProcess for brew install
        self._current_proxy = None       # (protocol, host, port, country)
        NetworkPrivacyManager._instances.add(self)

    # ── status helpers ────────────────────────────────────────────────────
    def _emit(self, state, detail):
        self.state, self.detail = state, detail
        self.statusChanged.emit(self.mode, state, detail)

    def reapply(self):
        """Re-assert this tab's route as the (app-wide) active proxy.

        Called when this manager's tab becomes the active one, so switching
        tabs switches the effective network route.
        """
        if self.mode == 'direct':
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.NoProxy))
        elif self.mode == 'proxy' and self._current_proxy:
            self.use_proxy(*self._current_proxy)
        elif self.mode == 'tor' and self.state == 'on' and self._socks_port:
            self._apply_socks('127.0.0.1', self._socks_port)

    def _apply_socks(self, host, port):
        proxy = QNetworkProxy(QNetworkProxy.Socks5Proxy, host, int(port))
        proxy.setCapabilities(
            proxy.capabilities() | QNetworkProxy.HostNameLookupCapability)
        QNetworkProxy.setApplicationProxy(proxy)

    # ── INHERITANCE (child tab adopts the parent tab's route) ──────────────
    def inherit_from(self, other):
        """Adopt ``other``'s active route so a new tab opens on the same VPN/Tor.

        VPN/proxy is copied independently (stopping the parent never stops the
        child). Tor is *shared* via reference counting, so the child keeps
        working after the parent stops until the last user detaches.
        """
        if other is None or other is self:
            return
        if other.mode == 'proxy':
            if other.state == 'on' and other._current_proxy:
                self.use_proxy(*other._current_proxy)
            elif other.state == 'starting':
                self._defer_inherit(other)
        elif other.mode == 'tor':
            if other.state == 'on' and other._circuit is not None:
                self._borrow_tor(other._circuit)
            elif other.state == 'starting':
                self._defer_inherit(other)
        # 'direct' / 'error': nothing worth inheriting.

    def _borrow_tor(self, circuit):
        """Route through an already-running shared Tor circuit."""
        self.stop_tor()                  # detach from any prior circuit first
        self._circuit = circuit
        self._borrowed_tor = True
        circuit.users.add(self)
        self._socks_port = circuit.socks_port
        self._control_port = circuit.control_port
        self._tor_dir = circuit.tor_dir
        self.mode = 'tor'
        self._apply_socks('127.0.0.1', circuit.socks_port)
        self._emit('on', "Tor connected · same network as other tab")

    def _find_live_tor_circuit(self):
        """Return a Tor circuit from another tab that's already connected.

        Lets a fresh Tor request adopt the same Tor network another tab is on
        (like a child tab inheriting its parent's route) instead of spinning
        up a second daemon.
        """
        for mgr in list(NetworkPrivacyManager._instances):
            if mgr is self:
                continue
            circuit = mgr._circuit
            if (circuit is not None and mgr.mode == 'tor'
                    and mgr.state == 'on' and circuit.socks_port):
                return circuit
        return None

    def has_live_tor_elsewhere(self):
        """True if another tab already has a connected Tor circuit to reuse."""
        return self._find_live_tor_circuit() is not None

    def _defer_inherit(self, other):
        """Inherit once ``other`` finishes connecting (it's still starting)."""
        def _later(_mode, state, _detail, o=other):
            if state == 'on':
                _disconnect()
                self.inherit_from(o)
            elif state in ('off', 'error'):
                _disconnect()

        def _disconnect():
            try:
                other.statusChanged.disconnect(_later)
            except Exception:
                pass

        other.statusChanged.connect(_later)

    # ── DIRECT ────────────────────────────────────────────────────────────
    def set_direct(self):
        self.stop_tor()
        self._current_proxy = None
        QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.NoProxy))
        self.mode = 'direct'
        self._emit('off', 'Direct connection (no proxy)')

    # ── PROXY ─────────────────────────────────────────────────────────────
    def refresh_proxies(self, protocol='http'):
        """Kick off an async fetch of a fresh free-proxy list."""
        if self._fetcher and self._fetcher.isRunning():
            return
        self._fetcher = _ProxyFetcher(protocol, self)
        self._fetcher.done.connect(self.proxyListReady)
        self._fetcher.failed.connect(self.proxyListFailed)
        self._fetcher.start()

    def use_proxy(self, protocol, host, port, country=''):
        """Route the browser through the given proxy (also stops Tor)."""
        self.stop_tor()
        ptype = (QNetworkProxy.Socks5Proxy if protocol == 'socks5'
                 else QNetworkProxy.HttpProxy)
        proxy = QNetworkProxy(ptype, host, int(port))
        # Let DNS resolve through the proxy too (avoids DNS leaks on SOCKS5).
        proxy.setCapabilities(proxy.capabilities() | QNetworkProxy.HostNameLookupCapability)
        QNetworkProxy.setApplicationProxy(proxy)
        self._current_proxy = (protocol, host, int(port), country)
        self.mode = 'proxy'
        loc = f" · {country}" if country else ""
        self._emit('on', f"Proxy · {protocol.upper()} {host}:{port}{loc}")

    def connect_proxy(self, protocol, host, port, country=''):
        """Validate a single proxy, then route through it if it truly works.

        Free proxies often accept a connection but never relay traffic, which
        would leave the browser unable to load anything. Testing first avoids
        silently breaking browsing.
        """
        host, port = host.strip(), int(port)
        self.mode = 'proxy'
        self._emit('starting', f"Testing {host}:{port}…")
        tester = _ProxyTester([(host, port)], protocol, self)
        tester.found.connect(
            lambda h, p, pr=protocol, cc=country: self.use_proxy(pr, h, p, cc))
        tester.failed.connect(
            lambda _msg, hp=f"{host}:{port}": self._emit(
                'error', f"{hp} is not relaying traffic — pick another proxy."))
        self._tester = tester
        tester.start()

    def connect_country(self, protocol, country, candidates):
        """Find the first working proxy in ``candidates`` and route through it.

        ``candidates`` is a list of ``(host, port)`` in one country; each is
        validated with a real proxied request and the first that relays is
        used. This backs the country-based proxy picker.
        """
        if not candidates:
            self.mode = 'proxy'
            self._emit('error', f"No proxies available for {country}.")
            return
        self.mode = 'proxy'
        self._emit('starting', f"Finding an active proxy in {country}…")
        tester = _ProxyTester(candidates, protocol, self)
        tester.found.connect(
            lambda h, p, pr=protocol, cc=country: self.use_proxy(pr, h, p, cc))
        tester.failed.connect(
            lambda _msg, cc=country: self._emit(
                'error', f"No active proxy found in {cc} — try another country."))
        self._tester = tester
        tester.start()


    def auto_proxy(self, protocol='http'):
        """Fetch a list, pick the first reachable proxy, and connect."""
        self.mode = 'proxy'
        self._emit('starting', 'Finding a working proxy…')
        fetch = _ProxyFetcher(protocol, self)

        def _on_list(proxies):
            self.proxyListReady.emit(proxies)
            # Remember each proxy's country so the banner can show it.
            countries = {p[0]: (p[2] if len(p) > 2 else '') for p in proxies}
            self._tester = _ProxyTester(proxies, protocol, self)
            self._tester.found.connect(
                lambda h, p, pr=protocol, cc=countries:
                self.use_proxy(pr, h, p, cc.get(h, '')))
            self._tester.failed.connect(lambda msg: self._emit('error', msg))
            self._tester.start()

        fetch.done.connect(_on_list)
        fetch.failed.connect(lambda msg: self._emit('error', msg))
        self._fetcher = fetch
        fetch.start()

    # ── TOR ───────────────────────────────────────────────────────────────
    @staticmethod
    def tor_available():
        return shutil.which('tor') is not None
    @staticmethod
    def brew_available():
        return shutil.which('brew') is not None

    def install_tor(self):
        """Install Tor via Homebrew (blocking). Returns (ok, message)."""
        brew = shutil.which('brew')
        if not brew:
            return False, "Homebrew not found. Install it from https://brew.sh"
        try:
            r = subprocess.run([brew, 'install', 'tor'],
                               capture_output=True, text=True, timeout=600)
            if r.returncode == 0 and shutil.which('tor'):
                return True, "Tor installed."
            return False, (r.stderr or r.stdout or "brew install failed")[-800:]
        except Exception as exc:
            return False, str(exc)

    def install_tor_async(self):
        """Install Tor via Homebrew without blocking the UI.

        Emits :attr:`torInstallProgress` (live output lines) and
        :attr:`torInstallDone` (ok, message) when finished.
        """
        if self._installer is not None:
            return  # already installing
        brew = shutil.which('brew')
        if not brew:
            self.torInstallDone.emit(
                False, "Homebrew not found. Install it from https://brew.sh")
            return
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_install_output)
        proc.finished.connect(self._on_install_finished)
        self._installer = proc
        self.torInstallProgress.emit("Installing Tor via Homebrew…")
        proc.start(brew, ['install', 'tor'])

    def _on_install_output(self):
        if not self._installer:
            return
        try:
            txt = bytes(self._installer.readAllStandardOutput()).decode(
                'utf-8', 'ignore')
        except Exception:
            return
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if lines:
            self.torInstallProgress.emit(lines[-1][:90])

    def _on_install_finished(self, code, status):
        ok = (code == 0) and (shutil.which('tor') is not None)
        self._installer = None
        self.torInstallDone.emit(
            ok, "Tor installed." if ok
            else "Homebrew could not install Tor (see the launch terminal).")

    def start_tor(self, force_new=False):
        """Launch the local Tor daemon and route the browser through it.

        When ``force_new`` is False and another tab already has a connected
        Tor circuit, this tab reuses that same circuit instead of starting a
        second daemon. Pass ``force_new=True`` to always spin up a fresh,
        independent Tor network for this tab.
        """
        tor = shutil.which('tor')
        if not tor:
            self.mode = 'tor'
            self._emit('error', "Tor is not installed.")
            return
        if self._circuit is not None:
            return  # already running / starting / sharing
        # If another tab already has Tor connected, reuse its circuit (same
        # Tor network) instead of starting a second daemon — unless the caller
        # explicitly asked for a brand-new, independent Tor network.
        if not force_new:
            existing = self._find_live_tor_circuit()
            if existing is not None:
                self._borrow_tor(existing)
                return
        self.mode = 'tor'
        self._emit('starting', "Starting Tor…")

        self._socks_port = _free_port()
        self._control_port = _free_port()
        self._tor_dir = tempfile.mkdtemp(prefix='tbtor_')
        # No Qt parent: the process must outlive this tab so a child tab that
        # borrows the circuit keeps working after the parent tab closes.
        proc = QProcess()
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_tor_output)
        proc.finished.connect(self._on_tor_finished)
        args = [
            '--SocksPort', str(self._socks_port),
            '--ControlPort', str(self._control_port),
            '--CookieAuthentication', '1',
            '--DataDirectory', self._tor_dir,
            '--ClientOnly', '1',
            '--AvoidDiskWrites', '1',
        ]
        circuit = _TorCircuit(proc, self._socks_port, self._control_port,
                              self._tor_dir)
        circuit.users.add(self)
        self._circuit = circuit
        self._borrowed_tor = False
        proc.start(tor, args)

    def _on_tor_output(self):
        if not self._circuit:
            return
        try:
            txt = bytes(self._circuit.proc.readAllStandardOutput()).decode(
                'utf-8', 'ignore')
        except Exception:
            return
        pct = None
        for m in re.finditer(r'Bootstrapped (\d+)%', txt):
            pct = int(m.group(1))
        if 'Bootstrapped 100%' in txt or pct == 100:
            # Point the browser at Tor's SOCKS port.
            self._apply_socks('127.0.0.1', self._socks_port)
            self._emit('on', "Tor connected (100%)")
        elif pct is not None:
            self._emit('starting', f"Bootstrapping Tor… {pct}%")
        elif re.search(r'\[(err|warn)\].*(Address already in use|Could not bind)', txt):
            self._emit('error', "Tor could not bind its ports.")

    def _on_tor_finished(self, *args):
        # Only surface an error if we didn't ask it to stop.
        if self.mode == 'tor' and self.state != 'off':
            self._emit('error', "Tor process exited.")
        # The owning process died; drop the circuit for everyone on it.
        circuit = self._circuit
        if circuit is not None:
            circuit.users.discard(self)
            if circuit.tor_dir:
                shutil.rmtree(circuit.tor_dir, ignore_errors=True)
                circuit.tor_dir = None
        self._circuit = None
        self._borrowed_tor = False
        self._tor_dir = None

    def tor_new_identity(self):
        """Ask Tor for a fresh circuit / exit IP via the control port."""
        if self.mode != 'tor' or self.state != 'on':
            return False, "Tor is not connected."
        try:
            cookie_path = os.path.join(self._tor_dir or '', 'control_auth_cookie')
            with open(cookie_path, 'rb') as fh:
                cookie = fh.read().hex()
            with socket.create_connection(('127.0.0.1', self._control_port), 5) as s:
                s.sendall(f'AUTHENTICATE {cookie}\r\n'.encode())
                if b'250' not in s.recv(1024):
                    return False, "Tor control authentication failed."
                s.sendall(b'SIGNAL NEWNYM\r\n')
                if b'250' not in s.recv(1024):
                    return False, "Tor refused NEWNYM."
            self._emit('on', "Tor connected · new identity requested")
            return True, "Requested a new Tor identity."
        except Exception as exc:
            return False, str(exc)

    def stop_tor(self):
        """Detach from the Tor circuit; kill the daemon only if last user."""
        circuit = self._circuit
        if circuit is not None:
            self.state = 'off'  # suppress the "exited" error for our own exit
            circuit.users.discard(self)
            self._circuit = None
            self._borrowed_tor = False
            if not circuit.users:
                # Last tab on this circuit — really shut the daemon down.
                try:
                    circuit.proc.terminate()
                    if not circuit.proc.waitForFinished(3000):
                        circuit.proc.kill()
                except Exception:
                    pass
                if circuit.tor_dir:
                    shutil.rmtree(circuit.tor_dir, ignore_errors=True)
                    circuit.tor_dir = None
        self._tor_dir = None
        self._socks_port = None
        self._control_port = None

    def shutdown(self):
        """Stop everything and restore a direct connection."""
        self.stop_tor()
        QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.NoProxy))
