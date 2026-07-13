"""Browser scraping / dev toolkit.

Instruments the page (via QWebChannel + injected JS hooks) to capture network
requests, WebSocket frames and MSE media segments, and provides on-demand
DOM extraction (links, tokens, source). The ``BrowserToolsWidget`` renders
these as a vertical-tabbed panel that auto-refreshes every second, grouping
new/changed data by capture time (ignoring unchanged repeats), tracking token
lifecycles, and listing each media play / opened file as a separate item.
"""

import os
import re
import json
import shlex
import base64
import shutil
import tempfile
import subprocess
from datetime import datetime
from urllib.parse import urlparse, unquote

from qtpy.QtCore import (Qt, QObject, Slot, Signal, QFile, QIODevice,
                          QTimer, QProcess, QUrl)
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QScrollArea, QStackedWidget,
                             QFileDialog, QApplication, QMessageBox,
                             QLineEdit, QListWidget, QListWidgetItem)

try:
    from qtpy.QtWebChannel import QWebChannel
    from qtpy.QtWebEngineWidgets import QWebEngineScript
    SCRAPER_AVAILABLE = True
except ImportError:  # pragma: no cover
    SCRAPER_AVAILABLE = False

try:
    from qtpy.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    from qtpy.QtWebEngineWidgets import QWebEngineProfile
    INTERCEPTOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    INTERCEPTOR_AVAILABLE = False


# ── Injected instrumentation ──────────────────────────────────────────────
INSTRUMENTATION_JS = r"""
(function(){
  if (window.__scrapeInstalled) return;
  window.__scrapeInstalled = true;
  var bridge = null, queue = [];
  function send(o){
    if (bridge){ try { bridge.report(JSON.stringify(o)); } catch(e){} }
    else { queue.push(o); if (queue.length > 4000) queue.shift(); }
  }
  function initChannel(){
    if (typeof QWebChannel === 'undefined' || !window.qt || !qt.webChannelTransport){
      return setTimeout(initChannel, 50);
    }
    new QWebChannel(qt.webChannelTransport, function(ch){
      bridge = ch.objects.scrapeBridge;
      var q = queue; queue = [];
      q.forEach(function(o){ try { bridge.report(JSON.stringify(o)); } catch(e){} });
    });
  }
  initChannel();

  // fetch()
  var _fetch = window.fetch;
  if (_fetch){
    window.fetch = function(input, init){
      try {
        var url = (typeof input === 'string') ? input : (input && input.url);
        var method = (init && init.method) || (input && input.method) || 'GET';
        var headers = {};
        if (init && init.headers){
          try { new Headers(init.headers).forEach(function(v,k){ headers[k]=v; }); } catch(e){}
        }
        send({t:'req', proto:'fetch', method:method, url:url, headers:headers,
              body: (init && init.body) ? String(init.body) : null});
      } catch(e){}
      return _fetch.apply(this, arguments);
    };
  }

  // XMLHttpRequest
  var XP = XMLHttpRequest.prototype;
  var _open = XP.open, _send = XP.send, _setH = XP.setRequestHeader;
  XP.open = function(m,u){ this.__m=m; this.__u=u; this.__h={}; return _open.apply(this, arguments); };
  XP.setRequestHeader = function(k,v){ try { this.__h[k]=v; } catch(e){} return _setH.apply(this, arguments); };
  XP.send = function(b){
    try { send({t:'req', proto:'xhr', method:this.__m||'GET', url:this.__u,
                headers:this.__h||{}, body: b?String(b):null}); } catch(e){}
    return _send.apply(this, arguments);
  };

  // WebSocket
  var _WS = window.WebSocket;
  if (_WS){
    var W = function(url, protocols){
      var ws = protocols ? new _WS(url, protocols) : new _WS(url);
      send({t:'ws', ev:'open', url:url});
      ws.addEventListener('message', function(e){
        try { send({t:'ws', ev:'recv', url:url, data:(typeof e.data==='string')?e.data:'[binary]'}); } catch(x){}
      });
      var _s = ws.send;
      ws.send = function(d){
        try { send({t:'ws', ev:'send', url:url, data:(typeof d==='string')?d:'[binary]'}); } catch(x){}
        return _s.apply(ws, arguments);
      };
      return ws;
    };
    W.prototype = _WS.prototype;
    W.CONNECTING = _WS.CONNECTING; W.OPEN = _WS.OPEN;
    W.CLOSING = _WS.CLOSING; W.CLOSED = _WS.CLOSED;
    window.WebSocket = W;
  }

  // ---- media: separate each play as its own session ----
  function b64(bytes){
    var bin='', chunk=0x8000;
    for (var i=0;i<bytes.length;i+=chunk){ bin += String.fromCharCode.apply(null, bytes.subarray(i,i+chunk)); }
    return btoa(bin);
  }
  window.__msSession = 0;
  window.__activeSession = 0;
  window.__blobSession = {};
  try {
    var _cou = URL.createObjectURL;
    URL.createObjectURL = function(obj){
      var url = _cou.apply(this, arguments);
      try {
        if (window.MediaSource && obj instanceof MediaSource){
          obj.__session = ++window.__msSession;
          obj.__title = document.title || location.href;
          window.__blobSession[url] = obj.__session;
          window.__activeSession = obj.__session;
          send({t:'msession', id:obj.__session, title:obj.__title, url:location.href});
        }
      } catch(e){}
      return url;
    };
    if (window.MediaSource){
      var _add = MediaSource.prototype.addSourceBuffer;
      MediaSource.prototype.addSourceBuffer = function(mime){
        var sb = _add.apply(this, arguments);
        try { sb.__mime = mime; sb.__session = this.__session||0; sb.__title = this.__title||''; } catch(e){}
        return sb;
      };
    }
    if (window.SourceBuffer){
      var _app = SourceBuffer.prototype.appendBuffer;
      SourceBuffer.prototype.appendBuffer = function(data){
        try {
          window.__activeSession = this.__session || window.__activeSession;
          var u8;
          if (data instanceof ArrayBuffer){
            u8 = new Uint8Array(data);
          } else if (ArrayBuffer.isView(data)){
            // Respect the view's offset/length; the underlying buffer may be
            // larger (a subarray), so copying data.buffer would corrupt it.
            u8 = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
          } else {
            u8 = new Uint8Array(data);
          }
          send({t:'media', session:this.__session||0, title:this.__title||'',
                mime:this.__mime||'application/octet-stream', b64:b64(u8)});
        } catch(e){}
        return _app.apply(this, arguments);
      };
    }
  } catch(e){}

  // ---- media element events: re-identify a newly played video ----
  function onMediaEvent(e){
    try {
      var el = e.target;
      if (!(el instanceof HTMLVideoElement || el instanceof HTMLAudioElement)) return;
      var src = el.currentSrc || el.src || '';
      if (src.indexOf('blob:') === 0){
        var sid = window.__blobSession[src];
        if (sid){ send({t:'mtitle', session:sid, title:document.title || location.href}); }
      } else if (src){
        send({t:'mediafile', url:src, title:document.title,
              kind:(el instanceof HTMLAudioElement)?'audio':'video'});
      }
    } catch(x){}
  }
  ['loadstart','play','playing','loadedmetadata'].forEach(function(ev){
    document.addEventListener(ev, onMediaEvent, true);
  });

  // ---- keep the active session's name in sync with the page title ----
  // (YouTube & other SPAs update document.title asynchronously AFTER a new
  //  video starts, so re-assign the current title to the active session.)
  try {
    var _lastKey = '';
    function pushTitle(){
      var tt = document.title || '';
      var s = window.__activeSession || 0;
      if (!s || !tt) return;
      var key = s + '|' + tt;
      if (key === _lastKey) return;
      _lastKey = key;
      send({t:'mtitle', session:s, title:tt});
    }
    if (window.MutationObserver){
      var mo = new MutationObserver(pushTitle);
      var tEl = document.querySelector('title');
      if (tEl) mo.observe(tEl, {childList:true, characterData:true, subtree:true});
      if (document.head) mo.observe(document.head, {childList:true, subtree:true});
    }
    setInterval(pushTitle, 1000);
  } catch(e){}
})();
"""


LINKS_JS = r"""
JSON.stringify({
  anchors: [...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href))],
  images:  [...new Set([...document.querySelectorAll('img[src]')].map(i=>i.src))],
  scripts: [...new Set([...document.querySelectorAll('script[src]')].map(s=>s.src))],
  styles:  [...new Set([...document.querySelectorAll('link[rel=stylesheet][href]')].map(l=>l.href))],
  media:   [...new Set([...document.querySelectorAll('video[src],audio[src],source[src]')].map(m=>m.src).filter(Boolean))]
})
"""

TOKENS_JS = r"""
(function(){
  var out = {cookies: document.cookie || '', localStorage:{}, sessionStorage:{}, found:[]};
  try { for (var i=0;i<localStorage.length;i++){ var k=localStorage.key(i); out.localStorage[k]=localStorage.getItem(k); } } catch(e){}
  try { for (var j=0;j<sessionStorage.length;j++){ var k2=sessionStorage.key(j); out.sessionStorage[k2]=sessionStorage.getItem(k2); } } catch(e){}
  var html = document.documentElement.outerHTML;
  var pats = [
    /eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}/g,
    /["']?(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|csrf[_-]?token|session[_-]?token|bearer)["']?\s*[:=]\s*["']([^"']{8,})["']/gi
  ];
  pats.forEach(function(p){ var m, n=0; while ((m=p.exec(html)) && n<300){ out.found.push(m[0].slice(0,240)); n++; } });
  out.found = [...new Set(out.found)];
  return JSON.stringify(out);
})()
"""


# ── Helpers ─────────────────────────────────────────────────────────────────
def to_curl(req):
    """Build a curl command string from a captured request dict."""
    url = req.get('url') or ''
    parts = ["curl " + shlex.quote(url)]
    method = (req.get('method') or 'GET').upper()
    if method not in ('GET', 'POST') or (method == 'POST' and not req.get('body')):
        parts.append("-X " + method)
    for k, v in (req.get('headers') or {}).items():
        parts.append("-H " + shlex.quote(f"{k}: {v}"))
    if req.get('body'):
        parts.append("--data-raw " + shlex.quote(req['body']))
    return " \\\n  ".join(parts)


def ext_for_mime(mime):
    m = (mime or '').lower()
    if 'mp4' in m or 'avc1' in m or 'mp4a' in m:
        return '.mp4'
    if 'webm' in m or 'vp9' in m or 'vp8' in m or 'opus' in m or 'vorbis' in m:
        return '.webm'
    if 'mpeg' in m or 'mp3' in m:
        return '.mp3'
    return '.bin'


def track_kind(mime):
    return 'audio' if 'audio' in (mime or '').lower() else 'video'


def sanitize_name(text, default='capture'):
    text = (text or '').strip()
    text = re.sub(r'[\\/:*?"<>|]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return (text[:80] or default)


def basename_from_url(url):
    try:
        path = urlparse(url).path
        name = unquote(os.path.basename(path)) or 'file'
        return sanitize_name(name, 'file')
    except Exception:
        return 'file'


def now_hms():
    return datetime.now().strftime('%H:%M:%S')


# ── Instrumentation bridge + install ────────────────────────────────────────
class ScrapeBridge(QObject):
    """Receives instrumentation reports from the page's JavaScript."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    @Slot(str)
    def report(self, payload):
        try:
            obj = json.loads(payload)
        except Exception:
            return
        self._owner._on_scrape_report(obj)


# --- PDF / downloadable-file request interceptor (routed to active browser) --
_FILE_EXTS = ('.pdf', '.zip', '.mp4', '.mp3', '.wav', '.m4a', '.webm', '.mov',
              '.mkv', '.csv', '.xlsx', '.docx', '.pptx', '.json', '.xml')
_interceptor = None
_active_browser = None


def set_active_browser(browser):
    global _active_browser
    _active_browser = browser


if INTERCEPTOR_AVAILABLE:
    class _FileInterceptor(QWebEngineUrlRequestInterceptor):
        fileSeen = Signal(str, str)  # url, basename

        def interceptRequest(self, info):
            try:
                url = info.requestUrl().toString()
                path = info.requestUrl().path().lower()
                if any(path.endswith(e) for e in _FILE_EXTS):
                    self.fileSeen.emit(url, basename_from_url(url))
            except Exception:
                pass

    def _on_file_seen(url, name):
        b = _active_browser
        if b is not None and hasattr(b, '_on_file_caught'):
            b._on_file_caught(url, name)

    def ensure_interceptor():
        global _interceptor
        if _interceptor is None:
            _interceptor = _FileInterceptor()
            _interceptor.fileSeen.connect(_on_file_seen)
            QWebEngineProfile.defaultProfile().setUrlRequestInterceptor(_interceptor)
else:  # pragma: no cover
    def ensure_interceptor():
        pass


def attach_scraper(browser):
    """Install the QWebChannel bridge + instrumentation scripts on a browser."""
    if not SCRAPER_AVAILABLE:
        return
    ensure_interceptor()
    page = browser.web_view.page()

    bridge = ScrapeBridge(browser)
    channel = QWebChannel(page)
    channel.registerObject('scrapeBridge', bridge)
    page.setWebChannel(channel)
    browser._scrape_bridge = bridge
    browser._scrape_channel = channel

    qwc = ''
    f = QFile(':/qtwebchannel/qwebchannel.js')
    if f.open(QIODevice.ReadOnly):
        qwc = bytes(f.readAll()).decode('utf-8', 'ignore')
        f.close()

    scripts = page.scripts()
    for name, source in (('scrape_qwebchannel', qwc),
                         ('scrape_hooks', INSTRUMENTATION_JS)):
        if not source:
            continue
        s = QWebEngineScript()
        s.setName(name)
        s.setInjectionPoint(QWebEngineScript.DocumentCreation)
        s.setWorldId(QWebEngineScript.MainWorld)
        s.setRunsOnSubFrames(True)
        s.setSourceCode(source)
        scripts.insert(s)


# ── UI ─────────────────────────────────────────────────────────────────────
_BTN = ("QPushButton {{ background-color:{c}; color:white; border:none; "
        "padding:6px 10px; border-radius:3px; font-weight:bold; }}"
        "QPushButton:hover {{ background-color:{h}; }}")


def _copy(text):
    QApplication.clipboard().setText(text)


class ResultItem(QFrame):
    """A result row: a text preview plus a right-side action button."""

    def __init__(self, text, action_text, action_cb, subtitle=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "ResultItem { background-color:#2b2b2b; border:1px solid #555; "
            "border-radius:4px; margin:2px; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        col = QVBoxLayout()
        col.setSpacing(1)
        preview = text if len(text) <= 400 else text[:400] + " …"
        lbl = QLabel(preview)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setStyleSheet("color:#e0e0e0; font-size:11px;")
        col.addWidget(lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet("color:#888; font-size:10px;")
            col.addWidget(sub)
        lay.addLayout(col, 1)

        btn = QPushButton(action_text)
        btn.setStyleSheet(_BTN.format(c='#2196F3', h='#1976D2'))
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, cb=action_cb: cb())
        lay.addWidget(btn, 0, Qt.AlignTop)


class CategoryPage(QWidget):
    """A scrollable results page with two header buttons and time grouping."""

    def __init__(self, action_label, on_action, second_label, on_second, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        bar = QHBoxLayout()
        self.action_btn = QPushButton(action_label)
        self.action_btn.setStyleSheet(_BTN.format(c='#4CAF50', h='#45a049'))
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(lambda _=False, cb=on_action: cb())
        bar.addWidget(self.action_btn, 1)

        self.second_btn = QPushButton(second_label)
        self.second_btn.setStyleSheet(_BTN.format(c='#2196F3', h='#1976D2'))
        self.second_btn.setCursor(Qt.PointingHandCursor)
        self.second_btn.clicked.connect(lambda _=False, cb=on_second: cb())
        bar.addWidget(self.second_btn)
        v.addLayout(bar)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#888; font-size:10px; padding:0 2px;")
        v.addWidget(self.count_lbl)

        self.note_lbl = QLabel("")
        self.note_lbl.setWordWrap(True)
        self.note_lbl.setStyleSheet(
            "color:#D7A100; font-size:10px; padding:2px 4px; "
            "background-color:#332b00; border:1px solid #5a4a00; border-radius:4px;")
        self.note_lbl.hide()
        v.addWidget(self.note_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border:1px solid #555; background-color:#1e1e1e; border-radius:4px; }")
        self._container = QWidget()
        self._list = QVBoxLayout(self._container)
        self._list.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._container)
        v.addWidget(scroll, 1)

        self._seen = set()
        self._all_text = []

    def clear_all(self):
        self._seen = set()
        self._all_text = []
        while self._list.count():
            w = self._list.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _add_time_header(self, label):
        h = QLabel("▸ " + label)
        h.setStyleSheet("color:#4FC3F7; font-size:11px; font-weight:bold; "
                        "padding:4px 2px 0 2px;")
        self._list.addWidget(h)

    def add_header_row(self, label, btn_text, cb, enabled=True):
        """Add a time/section header with a right-aligned action button."""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(2, 4, 2, 0)
        hl.setSpacing(6)
        lbl = QLabel("▸ " + label)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#4FC3F7; font-size:11px; font-weight:bold;")
        hl.addWidget(lbl, 1)
        b = QPushButton(btn_text)
        color = ('#4CAF50', '#45a049') if enabled else ('#777', '#777')
        b.setStyleSheet(_BTN.format(c=color[0], h=color[1]))
        b.setEnabled(enabled)
        if enabled:
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, cb=cb: cb())
        hl.addWidget(b, 0, Qt.AlignTop)
        self._list.addWidget(row)

    def _add_row(self, text, action_text, action_cb, subtitle=None, copy_text=None):
        self._list.addWidget(ResultItem(text, action_text, action_cb, subtitle))
        self._all_text.append(copy_text if copy_text is not None else text)

    def set_count(self, text):
        self.count_lbl.setText(text)

    def set_note(self, text):
        """Show a persistent advisory note under the header (empty = hide)."""
        self.note_lbl.setText(text)
        self.note_lbl.setVisible(bool(text))

    def copy_all(self):
        _copy("\n".join(self._all_text))

    def add_new_group(self, entries):
        """Append only unseen entries under a fresh time header.

        entries: list of dicts {key, text, subtitle, copy}. Returns count added.
        """
        fresh = [e for e in entries if e['key'] not in self._seen]
        for e in entries:
            self._seen.add(e['key'])
        if fresh:
            self._add_time_header(now_hms())
            for e in fresh:
                ct = e.get('copy', e['text'])
                self._add_row(e['text'], "Copy", (lambda t=ct: _copy(t)),
                              e.get('subtitle'), copy_text=ct)
        return len(fresh)


class AdBlockPage(QWidget):
    """Manage the ad blocker's custom domain blocklist."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._browser = None
        self._build_ui()
        self._reload_list()

    def _blocker(self):
        try:
            from ui.browser_widget import BrowserWidget
            return BrowserWidget._shared_ad_blocker
        except Exception:
            return None

    def set_browser(self, browser):
        self._browser = browser

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        title = QLabel("🚫 Ad-block Blocklist")
        title.setStyleSheet("color:#e0e0e0; font-weight:bold; font-size:13px;")
        root.addWidget(title)

        note = QLabel("Add a website or domain to block it everywhere. Paste a "
                      "full link or type a domain like ads.example.com.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#999; font-size:11px;")
        root.addWidget(note)

        entry = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("example.com or https://ads.site.com/…")
        self.input.setStyleSheet(
            "QLineEdit { background:#2d2d2d; color:#e0e0e0; border:1px solid #555; "
            "border-radius:4px; padding:5px 8px; }"
            "QLineEdit:focus { border:1px solid #007acc; }")
        self.input.returnPressed.connect(self._add_current)
        entry.addWidget(self.input, 1)
        add_btn = QPushButton("＋ Add")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(_BTN.format(c='#e84393', h='#c0327b'))
        add_btn.clicked.connect(self._add_current)
        entry.addWidget(add_btn)
        root.addLayout(entry)

        self.block_site_btn = QPushButton("Block current site's domain")
        self.block_site_btn.setCursor(Qt.PointingHandCursor)
        self.block_site_btn.setStyleSheet(_BTN.format(c='#607D8B', h='#455A64'))
        self.block_site_btn.clicked.connect(self._block_current_site)
        root.addWidget(self.block_site_btn)

        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget { background:#1e1e1e; color:#ddd; border:1px solid #333; "
            "border-radius:4px; }"
            "QListWidget::item { padding:4px 6px; }"
            "QListWidget::item:selected { background:#094771; }")
        root.addWidget(self.list, 1)

        remove_btn = QPushButton("🗑 Remove selected")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet(_BTN.format(c='#8B3A3A', h='#6d2d2d'))
        remove_btn.clicked.connect(self._remove_selected)
        root.addWidget(remove_btn)

    def _reload_list(self):
        self.list.clear()
        blocker = self._blocker()
        if blocker is None:
            self.list.addItem("(ad blocker unavailable)")
            return
        for host in sorted(getattr(blocker, 'user_hosts', ())):
            self.list.addItem(QListWidgetItem(host))
        if self.list.count() == 0:
            item = QListWidgetItem("No custom domains yet.")
            item.setForeground(Qt.gray)
            self.list.addItem(item)

    def _add_current(self):
        blocker = self._blocker()
        if blocker is None:
            return
        host = blocker.add_host(self.input.text())
        if host:
            self.input.clear()
            self._reload_list()

    def _block_current_site(self):
        blocker = self._blocker()
        if blocker is None or self._browser is None:
            return
        try:
            url = self._browser.web_view.url().toString()
        except Exception:
            url = ""
        if blocker.add_host(url):
            self._reload_list()

    def _remove_selected(self):
        blocker = self._blocker()
        if blocker is None:
            return
        item = self.list.currentItem()
        if item is None:
            return
        host = item.text()
        if host in getattr(blocker, 'user_hosts', ()):
            blocker.remove_host(host)
            self._reload_list()


class BrowserToolsWidget(QWidget):
    """Vertical-tabbed scraper panel that auto-refreshes every second."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._browser = None
        self._token_state = {}    # name -> {'value','first','changes'}
        self._token_present = set()
        self._req_count = 0
        self._ws_count = 0
        self._muxing = {}         # session id -> percent complete
        self._mux_procs = {}      # session id -> (QProcess, state dict)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._build_ui()

    @staticmethod
    def _downloads(filename):
        """Return a path in the user's Downloads folder for ``filename``."""
        d = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.isdir(d):
            d = os.path.expanduser('~')
        return os.path.join(d, filename)


    # -- construction ------------------------------------------------------
    def _build_ui(self):
        from ui.button_panel import VerticalTabButton

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(5, 5, 5, 5)
        cv.setSpacing(6)

        top = QHBoxLayout()
        self.inspect_btn = QPushButton("⧉ Inspect Element")
        self.inspect_btn.setCheckable(True)
        self.inspect_btn.setStyleSheet(_BTN.format(c='#3F51B5', h='#303F9F'))
        self.inspect_btn.setCursor(Qt.PointingHandCursor)
        self.inspect_btn.clicked.connect(lambda _=False: self._toggle_inspect())
        top.addWidget(self.inspect_btn, 1)
        reload_btn = QPushButton("⟳ Reload")
        reload_btn.setStyleSheet(_BTN.format(c='#607D8B', h='#455A64'))
        reload_btn.setCursor(Qt.PointingHandCursor)
        reload_btn.clicked.connect(lambda _=False: self._browser and self._browser.web_view.reload())
        top.addWidget(reload_btn)
        cv.addLayout(top)

        self.stack = QStackedWidget()
        cv.addWidget(self.stack, 1)

        self.page_links = CategoryPage("Clear", self._clear_links, "Copy All",
                                       lambda: self.page_links.copy_all())
        self.page_tokens = CategoryPage("Clear", self._clear_tokens, "Copy All",
                                        lambda: self.page_tokens.copy_all())
        self.page_requests = CategoryPage("Clear", self._clear_requests, "Copy All",
                                          lambda: self.page_requests.copy_all())
        self.page_source = CategoryPage("Get Source", self.get_source, "Save HTML",
                                        self.save_html)
        self.page_ws = CategoryPage("Clear", self._clear_ws, "Copy All",
                                    lambda: self.page_ws.copy_all())
        self.page_media = CategoryPage("Refresh", self.refresh_media, "Save All",
                                       self.save_all_media)
        self.page_media.set_note(
            "⚠ Play the video straight through without seeking. Skipped or "
            "fast-forwarded parts are never downloaded, so they can't be saved. "
            "When quality changed during playback, Save Video re-encodes to "
            "stitch it into one continuous file — this can take a little while.")
        from ui.network_privacy_widget import NetworkPrivacyPage
        self.page_privacy = NetworkPrivacyPage()
        self.page_blocklist = AdBlockPage()
        for p in (self.page_links, self.page_tokens, self.page_requests,
                  self.page_source, self.page_ws, self.page_media,
                  self.page_privacy, self.page_blocklist):
            self.stack.addWidget(p)

        root.addWidget(content, 1)

        bar = QWidget()
        bar.setStyleSheet("background-color:#1e1e1e;")
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.setAlignment(Qt.AlignTop)
        font = QFont(); font.setPointSize(11); font.setBold(True)

        self._tab_btns = []
        tabs = [("🔗 Links", 0), ("🔑 Tokens", 1), ("🌐 Requests", 2),
                ("📄 Source", 3), ("🔌 Sockets", 4), ("🎵 Media", 5),
                ("🛡 VPN/Tor", 6), ("🚫 Blocklist", 7)]
        for label, idx in tabs:
            b = VerticalTabButton(label)
            b.setFont(font)
            b.setChecked(idx == 0)
            b.clicked.connect(lambda _c, i=idx: self._switch(i))
            bl.addWidget(b)
            self._tab_btns.append(b)
        root.addWidget(bar)

    def _switch(self, index):
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self._tab_btns):
            b.setChecked(i == index)

    # -- binding -----------------------------------------------------------
    def set_browser(self, browser):
        # Detach from a previously bound browser's reset signal.
        if self._browser is not None:
            try:
                self._browser.captureReset.disconnect(self._reset_capture)
            except Exception:
                pass
        self._browser = browser
        set_active_browser(browser)
        if browser is not None:
            try:
                browser.captureReset.connect(self._reset_capture)
            except Exception:
                pass
            self.inspect_btn.setChecked(bool(getattr(browser, 'devtools_view', None)))
            self._reset_capture()
            # Bind the VPN/Tor page to this tab's manager and make its route live.
            mgr = getattr(browser, 'privacy', None)
            self.page_privacy.set_manager(mgr, browser)
            if mgr is not None:
                mgr.reapply()
            self.page_blocklist.set_browser(browser)
            self.page_blocklist._reload_list()
            self._timer.start()
            self._tick()
        else:
            self.page_privacy.set_manager(None, None)
            self.page_blocklist.set_browser(None)
            self._timer.stop()

    def _reset_capture(self):
        """Clear all collected results + dedup state and start fresh."""
        for p in (self.page_links, self.page_tokens, self.page_requests,
                  self.page_ws, self.page_media):
            p.clear_all()
        self._token_state = {}
        self._token_present = set()
        self._req_count = 0
        self._ws_count = 0


    def _toggle_inspect(self):
        if self._browser is not None:
            self._browser.toggle_devtools()
            self.inspect_btn.setChecked(bool(getattr(self._browser, 'devtools_view', None)))

    # -- 1-second refresh --------------------------------------------------
    def _tick(self):
        if not self._browser:
            return
        self._tick_links()
        self._tick_tokens()
        self._tick_requests()
        self._tick_ws()
        self.refresh_media()

    def _clear_links(self):
        self.page_links.clear_all()

    def _clear_tokens(self):
        self.page_tokens.clear_all()
        self._token_state = {}
        self._token_present = set()

    def _clear_requests(self):
        self.page_requests.clear_all()

    def _clear_ws(self):
        self.page_ws.clear_all()

    def _tick_links(self):
        def done(result):
            try:
                data = json.loads(result) if result else {}
            except Exception:
                return
            entries = []
            for group in ('anchors', 'images', 'scripts', 'styles', 'media'):
                for url in data.get(group, []):
                    entries.append({'key': url, 'text': url, 'subtitle': group})
            self.page_links.add_new_group(entries)
            self.page_links.set_count(f"{len(self.page_links._seen)} unique link(s)")
        self._browser.web_view.page().runJavaScript(LINKS_JS, done)

    def _tick_tokens(self):
        def done(result):
            try:
                data = json.loads(result) if result else {}
            except Exception:
                return
            current = {}
            for c in (data.get('cookies') or '').split('; '):
                if '=' in c:
                    k, v = c.split('=', 1)
                    current['cookie:' + k] = v
            for store in ('localStorage', 'sessionStorage'):
                for k, v in (data.get(store) or {}).items():
                    current[f'{store}:{k}'] = v
            for tok in data.get('found', []):
                current['match:' + tok[:40]] = tok
            for req in getattr(self._browser, 'captured_requests', []):
                for hk, hv in (req.get('headers') or {}).items():
                    if hk.lower() in ('authorization', 'x-api-key', 'x-csrf-token'):
                        current['header:' + hk] = hv

            entries = []
            for name, value in current.items():
                st = self._token_state.get(name)
                if st is None:
                    self._token_state[name] = {'value': value, 'first': now_hms(), 'changes': 0}
                    entries.append({'key': f'{name}|{value}',
                                    'text': f'{name} = {value}', 'copy': value,
                                    'subtitle': f'NEW · first seen {now_hms()}'})
                elif st['value'] != value:
                    st['changes'] += 1
                    st['value'] = value
                    entries.append({'key': f'{name}|{value}',
                                    'text': f'{name} = {value}', 'copy': value,
                                    'subtitle': f"CHANGED (#{st['changes']}) · since {st['first']}"})
            removed = self._token_present - set(current)
            for name in removed:
                entries.append({'key': f'{name}|__removed__',
                                'text': f'{name} removed', 'copy': name,
                                'subtitle': 'REMOVED'})
            self._token_present = set(current)
            self.page_tokens.add_new_group(entries)
            self.page_tokens.set_count(
                f"{len(self._token_state)} token(s) tracked · {len(self._token_present)} present")
        self._browser.web_view.page().runJavaScript(TOKENS_JS, done)

    def _tick_requests(self):
        reqs = getattr(self._browser, 'captured_requests', [])
        if len(reqs) <= self._req_count:
            return
        new = reqs[self._req_count:]
        self._req_count = len(reqs)
        entries = []
        for req in new:
            title = f"{(req.get('method') or 'GET')}  {req.get('url','')}"
            entries.append({'key': f"{req.get('method')}|{req.get('url')}|{req.get('body')}",
                            'text': title, 'copy': to_curl(req),
                            'subtitle': f"{req.get('proto','')} · Copy = curl"})
        self.page_requests.add_new_group(entries)
        self.page_requests.set_count(f"{len(self.page_requests._seen)} request(s)")

    def _tick_ws(self):
        frames = getattr(self._browser, 'captured_ws', [])
        if len(frames) <= self._ws_count:
            return
        start = self._ws_count
        new = frames[start:]
        self._ws_count = len(frames)
        entries = []
        for i, fr in enumerate(new, start):
            data = fr.get('data', '') or ''
            entries.append({'key': f"{i}|{fr.get('ev')}|{data[:60]}",
                            'text': f"[{fr.get('ev','')}] {data}", 'copy': data,
                            'subtitle': fr.get('url', '')})
        self.page_ws.add_new_group(entries)
        self.page_ws.set_count(f"{len(frames)} frame(s)")

    # -- source ------------------------------------------------------------
    def get_source(self):
        if not self._browser:
            return
        def done(html):
            self.page_source.clear_all()
            html = html or ""
            self.page_source._add_row(
                (html[:600] + " …") if len(html) > 600 else html,
                "Copy", (lambda h=html: _copy(h)),
                subtitle=f"{len(html)} chars — Copy = full HTML", copy_text=html)
            self.page_source.set_count("page HTML captured")
        self._browser.web_view.page().toHtml(done)

    def save_html(self):
        if not self._browser:
            return
        def done(html):
            title = sanitize_name(self._browser.web_view.title() or
                                  urlparse(self._browser.current_url()).netloc, 'page')
            path, _ = QFileDialog.getSaveFileName(
                self, "Save page HTML", self._downloads(title + ".html"),
                "HTML (*.html);;All files (*)")
            if path:
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(html or "")
        self._browser.web_view.page().toHtml(done)

    # -- media -------------------------------------------------------------
    def refresh_media(self):
        if not self._browser:
            return
        self.page_media.clear_all()
        sessions = getattr(self._browser, 'media_sessions', [])
        total = 0
        for sess in sessions:
            if sess.get('kind') == 'mse':
                name = sanitize_name(sess.get('title'), 'media')
                tracks = sess.get('tracks', {})
                has_v = any(track_kind(m) == 'video' for m in tracks)
                has_a = any(track_kind(m) == 'audio' for m in tracks)
                header = f"Session {sess.get('id')} · {sess.get('time','')} · {name}"
                if has_v and has_a:
                    sid = sess.get('id')
                    if sid in self._muxing:
                        self.page_media.add_header_row(
                            header, f"Processing {self._muxing[sid]}%",
                            (lambda: None), enabled=False)
                    else:
                        self.page_media.add_header_row(
                            header, "Save Video",
                            (lambda s=sess: self._save_session(s)))
                else:
                    self.page_media._add_time_header(header)
                for mime, chunks in tracks.items():
                    size = sum(len(c) for c in chunks)
                    total += size
                    kind = track_kind(mime)
                    self.page_media._add_row(
                        f"{mime}", "Save",
                        (lambda s=sess, m=mime: self._save_track(s, m)),
                        subtitle=f"{kind} · {len(chunks)} seg · {size/1024:.0f} KB")
            else:
                self.page_media._add_time_header(
                    f"{sess.get('kind','file').upper()} · {sess.get('time','')} · {sess.get('name','')}")
                self.page_media._add_row(
                    sess.get('url', ''), "Save",
                    (lambda s=sess: self._save_file(s)),
                    subtitle=sess.get('url', ''))
        self.page_media.set_count(
            f"{len(sessions)} item(s) · {total/1024:.0f} KB buffered" if sessions
            else "no media captured yet")

    def _save_session(self, sess):
        """Combine the session's audio + video tracks into one video file.

        Runs ffmpeg asynchronously (QProcess) so the UI stays responsive and
        the button shows live progress. YouTube delivers the video as fragmented
        MP4 whose quality (and resolution) changes during playback -- even
        without seeking, because of its automatic quality ramp. Each quality
        level is a separate init segment, so a plain stream-copy stops at the
        first resolution change (video freezes while audio keeps going). We
        therefore split the capture at every init-segment boundary and, when
        more than one exists, re-encode + concatenate the pieces into a single
        continuous stream.
        """
        sid = sess.get('id')
        if sid in self._muxing:
            return  # already processing this session
        tracks = sess.get('tracks', {})
        stream = sess.get('stream') or []

        def _ordered(kind):
            """All chunks of ``kind`` in original append order + a repr mime."""
            if stream:
                chunks = [d for m, d in stream if track_kind(m) == kind]
                mime = next((m for m, _ in stream if track_kind(m) == kind), None)
            else:  # fallback for sessions captured before ordering existed
                cands = [(m, c) for m, c in tracks.items() if track_kind(m) == kind]
                if not cands:
                    return None
                m, c = max(cands, key=lambda t: sum(len(x) for x in t[1]))
                return (m, list(c))
            if not chunks:
                return None
            return (mime, chunks)

        video = _ordered('video')
        audio = _ordered('audio')
        if not video and not audio:
            return
        name = sanitize_name(sess.get('title'), 'video')
        path, _ = QFileDialog.getSaveFileName(
            self, "Save combined video", self._downloads(name + ".mp4"),
            "Video (*.mp4);;Matroska (*.mkv);;All files (*)")
        if not path:
            return

        ffmpeg = shutil.which('ffmpeg')
        tmp = tempfile.mkdtemp(prefix='tbmux_')

        # Split each track into self-contained init-segment groups; write every
        # group (a valid standalone fMP4) to its own temp file.
        def _write_groups(trk, tag):
            files = []
            if not trk:
                return files
            ext = ext_for_mime(trk[0])
            for i, g in enumerate(self._split_fmp4_groups(trk[1])):
                p = os.path.join(tmp, f'{tag}{i}{ext}')
                with open(p, 'wb') as fh:
                    fh.write(g)
                files.append(p)
            return files

        vfiles = _write_groups(video, 'v')
        afiles = _write_groups(audio, 'a')

        if not ffmpeg or (not vfiles and not afiles):
            if vfiles or afiles:
                shutil.copy((vfiles or afiles)[0], path)
            shutil.rmtree(tmp, ignore_errors=True)
            if not ffmpeg:
                QMessageBox.warning(
                    self, "ffmpeg not found",
                    "ffmpeg is not installed, so audio and video could not "
                    "be combined. Saved the available track instead.")
            return

        is_mp4 = path.lower().endswith(('.mp4', '.m4v'))
        movflags = ['-movflags', '+faststart'] if is_mp4 else []
        multi = len(vfiles) > 1 or len(afiles) > 1

        if not multi:
            # One quality throughout -> fast, lossless stream copy.
            inputs, maps = [], []
            if vfiles:
                inputs += ['-i', vfiles[0]]
                maps += ['-map', '0:v:0']
            if afiles:
                inputs += ['-i', afiles[0]]
                maps += ['-map', f'{1 if vfiles else 0}:a:0']
            base = [ffmpeg, '-y'] + inputs + maps
            state = {'tmp': tmp, 'path': path, 'mode': 'copy',
                     'dur': self._probe_duration(vfiles[:1] + afiles[:1]),
                     'base': base, 'movflags': movflags,
                     'acodec': 'aac' if is_mp4 else 'libopus',
                     'retry': False, 'log': ''}
            self._muxing[sid] = 0
            args = base + ['-c', 'copy'] + movflags + [
                '-progress', 'pipe:1', '-nostats', path]
            self._start_mux(sid, args, state)
            self.refresh_media()
            return

        # Multiple quality levels -> re-encode + concatenate into one stream.
        # (This also produces H.264/AAC, which QuickTime can play.)
        w, h = self._probe_target_wh(vfiles) if vfiles else (0, 0)
        inputs = []
        for f in vfiles + afiles:
            inputs += ['-i', f]
        nv = len(vfiles)
        filters, maps, vcodec, acodec = [], [], [], []
        vlabels = []
        for i in range(nv):
            lbl = f'[cv{i}]'
            filters.append(
                f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
                f"format=yuv420p,settb=AVTB{lbl}")
            vlabels.append(lbl)
        if vlabels:
            filters.append(''.join(vlabels) + f"concat=n={nv}:v=1:a=0[V]")
            maps += ['-map', '[V]']
            vcodec = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                      '-pix_fmt', 'yuv420p']
        alabels = []
        for j in range(len(afiles)):
            lbl = f'[ca{j}]'
            filters.append(f"[{nv + j}:a]aresample=48000,asettb=AVTB{lbl}")
            alabels.append(lbl)
        if alabels:
            filters.append(
                ''.join(alabels) + f"concat=n={len(alabels)}:v=0:a=1[A]")
            maps += ['-map', '[A]']
            acodec = ['-c:a', 'aac', '-b:a', '192k']
        fc = ';'.join(filters)
        base = [ffmpeg, '-y'] + inputs + ['-filter_complex', fc] + maps
        state = {'tmp': tmp, 'path': path, 'mode': 'reencode',
                 'dur': self._probe_total_duration(vfiles or afiles),
                 'base': base, 'movflags': movflags, 'acodec': 'aac',
                 'retry': True, 'log': ''}
        self._muxing[sid] = 0
        args = base + vcodec + acodec + movflags + [
            '-progress', 'pipe:1', '-nostats', path]
        self._start_mux(sid, args, state)
        self.refresh_media()

    @staticmethod
    def _split_fmp4_groups(chunks):
        """Split fragmented-MP4 bytes into self-contained init+media groups.

        A new group begins at each top-level ``ftyp``/``moov`` box that follows
        media data, i.e. at every quality/resolution switch. Each returned blob
        is a standalone, playable fMP4 (init segment + its media fragments).
        """
        data = b''.join(chunks)
        groups, cur = [], bytearray()
        seen_media = False
        i, n = 0, len(data)
        while i + 8 <= n:
            size = int.from_bytes(data[i:i + 4], 'big')
            btype = data[i + 4:i + 8]
            if size == 1:  # 64-bit extended size
                if i + 16 > n:
                    break
                size = int.from_bytes(data[i + 8:i + 16], 'big')
            if size < 8 or i + size > n:
                break  # truncated / invalid box -> stop cleanly
            if btype in (b'ftyp', b'moov') and seen_media and cur:
                groups.append(bytes(cur))
                cur = bytearray()
                seen_media = False
            cur += data[i:i + size]
            if btype in (b'moof', b'mdat', b'styp', b'sidx'):
                seen_media = True
            i += size
        if cur:
            groups.append(bytes(cur))
        return groups or [data]

    def _probe_target_wh(self, files):
        """Largest width x height among the given video files (even numbers)."""
        ffprobe = shutil.which('ffprobe')
        best = (0, 0)
        if ffprobe:
            for p in files:
                try:
                    r = subprocess.run(
                        [ffprobe, '-v', 'error', '-select_streams', 'v:0',
                         '-show_entries', 'stream=width,height',
                         '-of', 'csv=p=0', p],
                        capture_output=True, timeout=10)
                    ws, hs = r.stdout.decode('utf-8', 'ignore').strip().split(',')
                    wv, hv = int(ws), int(hs)
                    if wv * hv > best[0] * best[1]:
                        best = (wv, hv)
                except Exception:
                    pass
        w, h = best if best[0] and best[1] else (1280, 720)
        return (w - w % 2, h - h % 2)

    def _probe_total_duration(self, files):
        """Sum of the durations of ``files`` (for progress on concatenation)."""
        ffprobe = shutil.which('ffprobe')
        if not ffprobe:
            return None
        total = 0.0
        for p in files:
            try:
                r = subprocess.run(
                    [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=nw=1:nk=1', p],
                    capture_output=True, timeout=10)
                total += float(r.stdout.decode('utf-8', 'ignore').strip())
            except Exception:
                pass
        return total or None

    def _probe_duration(self, inputs):
        ffprobe = shutil.which('ffprobe')
        if not ffprobe:
            return None
        best = None
        for p in inputs:
            try:
                r = subprocess.run(
                    [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=nw=1:nk=1', p],
                    capture_output=True, timeout=10)
                d = float(r.stdout.decode('utf-8', 'ignore').strip())
                if d > 0:
                    best = max(best or 0.0, d)
            except Exception:
                pass
        return best

    def _start_mux(self, sid, args, state):
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(
            lambda p=proc, s=sid: self._mux_read(p, s))
        proc.finished.connect(
            lambda code, status, p=proc, s=sid, st=state: self._mux_done(s, p, st, code))
        self._mux_procs[sid] = (proc, state)
        proc.start(args[0], args[1:])

    def _mux_read(self, proc, sid):
        try:
            txt = bytes(proc.readAllStandardOutput()).decode('utf-8', 'ignore')
        except Exception:
            return
        entry = self._mux_procs.get(sid)
        if not entry:
            return
        state = entry[1]
        state['log'] += txt
        dur = state.get('dur')
        if not dur:
            return
        for line in txt.splitlines():
            if line.startswith('out_time_us='):
                try:
                    us = int(line.split('=', 1)[1])
                    self._muxing[sid] = max(0, min(99, int(us / 1e6 / dur * 100)))
                except Exception:
                    pass

    def _mux_done(self, sid, proc, state, code):
        # Stream-copy failed once -> retry re-encoding audio.
        if code != 0 and state.get('mode') == 'copy' and not state['retry']:
            state['retry'] = True
            state['log'] = ''
            args = (state['base'] + ['-c:v', 'copy', '-c:a', state['acodec']]
                    + state['movflags'] + ['-progress', 'pipe:1', '-nostats', state['path']])
            self._start_mux(sid, args, state)
            return

        shutil.rmtree(state['tmp'], ignore_errors=True)
        self._muxing.pop(sid, None)
        self._mux_procs.pop(sid, None)
        if code != 0:
            QMessageBox.critical(
                self, "Combine failed",
                "ffmpeg could not combine the tracks:\n\n"
                + state.get('log', '')[-800:])
        self.refresh_media()

    def _save_track(self, sess, mime):
        chunks = sess.get('tracks', {}).get(mime) or []
        if not chunks:
            return
        name = sanitize_name(sess.get('title'), 'media')
        kind = track_kind(mime)
        default = f"{name} - {kind}{ext_for_mime(mime)}"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save {kind} ({mime})", self._downloads(default),
            "Media (*);;All files (*)")
        if path:
            with open(path, 'wb') as fh:
                for c in chunks:
                    fh.write(c)

    def _save_file(self, sess):
        url = sess.get('url')
        if not url:
            return
        default = sess.get('name') or basename_from_url(url)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save file", self._downloads(default), "All files (*)")
        if not path:
            return
        # Cross-origin media (e.g. a CDN .mp4 played in the overlay) can't be
        # read back with an in-page fetch() — the CDN's CORS policy makes the
        # fetch throw, so the old path silently saved a 0-byte file. Stream the
        # bytes through Chromium's own download pipeline instead: it uses the
        # browser's network stack (same cookies + active Tor/VPN proxy) and is
        # not subject to CORS.
        page = self._browser.web_view.page()
        profile = page.profile()
        directory = os.path.dirname(path) or '.'
        filename = os.path.basename(path)

        def _on_download(item, u=url):
            try:
                if item.url().toString() != u:
                    return
            except Exception:
                pass
            try:
                item.setDownloadDirectory(directory)
                item.setDownloadFileName(filename)
            except Exception:
                pass
            try:
                profile.downloadRequested.disconnect(_on_download)
            except Exception:
                pass
            item.accept()

        try:
            profile.downloadRequested.connect(_on_download)
            page.download(QUrl(url))
            return
        except Exception:
            try:
                profile.downloadRequested.disconnect(_on_download)
            except Exception:
                pass
        # Fallback (older Qt without QWebEnginePage.download): in-page fetch.
        js = ("(async()=>{try{const r=await fetch(%s);const b=await r.arrayBuffer();"
              "const u=new Uint8Array(b);let s='';const c=0x8000;"
              "for(let i=0;i<u.length;i+=c){s+=String.fromCharCode.apply(null,u.subarray(i,i+c));}"
              "return btoa(s);}catch(e){return '';}})()" % json.dumps(url))

        def done(b64):
            try:
                data = base64.b64decode(b64 or '')
            except Exception:
                data = b''
            with open(path, 'wb') as fh:
                fh.write(data)
        page.runJavaScript(js, done)

    def save_all_media(self):
        if not self._browser:
            return
        for sess in getattr(self._browser, 'media_sessions', []):
            if sess.get('kind') == 'mse':
                for mime in sess.get('tracks', {}):
                    self._save_track(sess, mime)
            else:
                self._save_file(sess)
