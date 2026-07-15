"""Local backend for the API Studio tool.

A stdlib-only (no third-party deps) HTTP server bound to 127.0.0.1 that:

* serves the static web app (``webapp/``),
* proxies outgoing HTTP requests so the in-browser app is not blocked by CORS
  (``POST /api/proxy``),
* persists projects to disk under a per-project folder tree
  (``~/.terminal_browser/api_studio/projects/<name>/``).

The server is a lazily-started singleton: the first tool launch spins it up on
a random free port in a daemon thread; subsequent launches reuse it.
"""

import json
import os
import re
import secrets
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEBAPP_DIR = Path(__file__).parent / "webapp"
DATA_DIR = Path.home() / ".terminal_browser" / "api_studio"
PROJECTS_DIR = DATA_DIR / "projects"

# Per-process secret that gates every request. Only the embedded browser tab is
# handed this token (via the initial URL); it is then pinned to a cookie so
# other local browsers/processes on 127.0.0.1 cannot reach the server.
_TOKEN = None
_COOKIE_NAME = "ast"

# Folders that make up a project on disk.
_RESOURCE_DIRS = ("collections", "environments", "flows")

_SAFE_NAME = re.compile(r"[^A-Za-z0-9 ._\-()]+")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


# ── helpers ────────────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Sanitise a project/resource name so it is a single safe path segment."""
    name = (name or "").strip()
    name = _SAFE_NAME.sub("_", name)
    name = name.strip(". ")
    return name or "untitled"


def _project_dir(name: str) -> Path:
    return PROJECTS_DIR / _safe_name(name)


def _read_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def _scaffold(pdir: Path, name: str) -> dict:
    """Create an empty project folder tree and return its metadata."""
    for sub in _RESOURCE_DIRS:
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name,
        "created": time.time(),
        "updated": time.time(),
        "activeEnv": None,
    }
    _write_json(pdir / "project.json", meta)
    if not (pdir / "history.json").exists():
        _write_json(pdir / "history.json", [])
    return meta


def _load_bundle(name: str):
    """Read a full project (meta + all resources) into a single dict."""
    pdir = _project_dir(name)
    if not pdir.is_dir():
        return None
    meta = _read_json(pdir / "project.json", {"name": name})

    def _load_dir(sub):
        d = pdir / sub
        items = []
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                obj = _read_json(f, None)
                if isinstance(obj, dict):
                    obj.setdefault("id", f.stem)
                    items.append(obj)
        return items

    return {
        "meta": meta,
        "collections": _load_dir("collections"),
        "environments": _load_dir("environments"),
        "flows": _load_dir("flows"),
        "history": _read_json(pdir / "history.json", []),
    }


def _save_bundle(name: str, bundle: dict) -> dict:
    """Persist a full project bundle, mirroring it onto the folder tree."""
    pdir = _project_dir(name)
    meta = bundle.get("meta") or {}
    meta["name"] = name
    meta["updated"] = time.time()
    if not pdir.exists():
        _scaffold(pdir, name)

    for sub in _RESOURCE_DIRS:
        d = pdir / sub
        d.mkdir(parents=True, exist_ok=True)
        keep = set()
        for obj in bundle.get(sub, []) or []:
            if not isinstance(obj, dict):
                continue
            rid = _safe_name(str(obj.get("id") or obj.get("name") or int(time.time() * 1000)))
            obj.setdefault("id", rid)
            keep.add(rid + ".json")
            _write_json(d / (rid + ".json"), obj)
        # Drop files that were deleted in the UI.
        for f in d.glob("*.json"):
            if f.name not in keep:
                try:
                    f.unlink()
                except OSError:
                    pass

    _write_json(pdir / "history.json", bundle.get("history", []) or [])
    _write_json(pdir / "project.json", meta)
    return _load_bundle(name)


def _list_projects():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if p.is_dir():
            meta = _read_json(p / "project.json", {"name": p.name})
            out.append({
                "name": meta.get("name", p.name),
                "updated": meta.get("updated", 0),
            })
    out.sort(key=lambda x: x.get("updated", 0), reverse=True)
    return out


def _do_proxy(payload: dict) -> dict:
    """Perform an outbound HTTP request on behalf of the browser app."""
    method = (payload.get("method") or "GET").upper()
    url = payload.get("url") or ""
    headers = payload.get("headers") or {}
    body = payload.get("body")
    timeout = float(payload.get("timeout") or 30)

    if not re.match(r"^https?://", url, re.IGNORECASE):
        return {"error": "URL must start with http:// or https://"}

    data = None
    if body is not None and body != "" and method not in ("GET", "HEAD"):
        data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    for k, v in headers.items():
        if k and v is not None:
            try:
                req.add_header(str(k), str(v))
            except Exception:
                pass

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            elapsed = (time.time() - start) * 1000
            return _format_response(resp.status, resp.reason, resp.headers, raw, elapsed)
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        elapsed = (time.time() - start) * 1000
        return _format_response(exc.code, exc.reason, exc.headers, raw, elapsed)
    except urllib.error.URLError as exc:
        return {"error": str(getattr(exc, "reason", exc))}
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": str(exc)}


def _format_response(status, reason, headers, raw, elapsed):
    try:
        text = raw.decode("utf-8")
    except Exception:
        text = raw.decode("latin-1", errors="replace")
    hdrs = {}
    try:
        for k, v in headers.items():
            hdrs[k] = v
    except Exception:
        pass
    return {
        "status": status,
        "statusText": reason or "",
        "headers": hdrs,
        "body": text,
        "timeMs": round(elapsed, 1),
        "size": len(raw),
    }


# ── HTTP handler ───────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    server_version = "ApiStudio/1.0"

    def log_message(self, *args):  # silence default stderr logging
        pass

    # -- access control --
    def _authorized(self):
        """Allow only requests bearing the session token (cookie or ?token=)."""
        if _TOKEN is None:
            return True
        cookie = self.headers.get("Cookie", "") or ""
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(_COOKIE_NAME + "=") and part[len(_COOKIE_NAME) + 1:] == _TOKEN:
                return True
        query = urllib.parse.urlparse(self.path).query
        if urllib.parse.parse_qs(query).get("token", [None])[0] == _TOKEN:
            # First navigation: pin the token to an HttpOnly cookie.
            self._set_cookie = True
            return True
        return False

    def _cookie_header(self):
        if getattr(self, "_set_cookie", False):
            self.send_header(
                "Set-Cookie",
                f"{_COOKIE_NAME}={_TOKEN}; Path=/; HttpOnly; SameSite=Strict",
            )

    # -- utilities --
    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cookie_header()
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _path_parts(self):
        path = self.path.split("?", 1)[0]
        return [urllib.parse.unquote(p) for p in path.split("/") if p]

    # -- static files --
    def _serve_static(self):
        rel = self.path.split("?", 1)[0].lstrip("/")
        if rel == "":
            rel = "index.html"
        target = (WEBAPP_DIR / rel).resolve()
        try:
            target.relative_to(WEBAPP_DIR.resolve())
        except ValueError:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        ctype = _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cookie_header()
        self.end_headers()
        self.wfile.write(data)

    # -- verbs --
    def do_GET(self):
        if not self._authorized():
            return self.send_error(403)
        parts = self._path_parts()
        if parts[:1] != ["api"]:
            return self._serve_static()
        try:
            if parts == ["api", "projects"]:
                return self._send_json({"projects": _list_projects()})
            if len(parts) == 3 and parts[1] == "projects":
                bundle = _load_bundle(parts[2])
                if bundle is None:
                    return self._send_json({"error": "not found"}, 404)
                return self._send_json(bundle)
        except Exception as exc:
            return self._send_json({"error": str(exc)}, 500)
        return self._send_json({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        if not self._authorized():
            return self.send_error(403)
        parts = self._path_parts()
        try:
            if parts == ["api", "proxy"]:
                return self._send_json(_do_proxy(self._read_body()))
            if parts == ["api", "projects"]:
                body = self._read_body()
                name = _safe_name(body.get("name", ""))
                pdir = _project_dir(name)
                if pdir.exists():
                    return self._send_json({"error": "Project already exists"}, 409)
                _scaffold(pdir, name)
                return self._send_json(_load_bundle(name))
        except Exception as exc:
            return self._send_json({"error": str(exc)}, 500)
        return self._send_json({"error": "unknown endpoint"}, 404)

    def do_PUT(self):
        if not self._authorized():
            return self.send_error(403)
        parts = self._path_parts()
        try:
            if len(parts) == 3 and parts[1] == "projects":
                bundle = self._read_body()
                saved = _save_bundle(parts[2], bundle)
                return self._send_json(saved)
        except Exception as exc:
            return self._send_json({"error": str(exc)}, 500)
        return self._send_json({"error": "unknown endpoint"}, 404)

    def do_DELETE(self):
        if not self._authorized():
            return self.send_error(403)
        parts = self._path_parts()
        try:
            if len(parts) == 3 and parts[1] == "projects":
                pdir = _project_dir(parts[2])
                if pdir.is_dir():
                    shutil.rmtree(pdir, ignore_errors=True)
                return self._send_json({"ok": True})
        except Exception as exc:
            return self._send_json({"error": str(exc)}, 500)
        return self._send_json({"error": "unknown endpoint"}, 404)


# ── singleton lifecycle ────────────────────────────────────────────────────

_server = None
_thread = None
_lock = threading.Lock()


def ensure_server() -> str:
    """Start the backend if needed and return its token-scoped base URL."""
    global _server, _thread, _TOKEN
    with _lock:
        if _server is None:
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            _TOKEN = secrets.token_urlsafe(24)
            _server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            _server.daemon_threads = True
            _thread = threading.Thread(target=_server.serve_forever, daemon=True)
            _thread.start()
        host, port = _server.server_address[:2]
        return f"http://{host}:{port}/?token={_TOKEN}"


def base_url():
    """Return the running server's token-scoped base URL, or None if not started."""
    if _server is None:
        return None
    host, port = _server.server_address[:2]
    suffix = f"/?token={_TOKEN}" if _TOKEN else ""
    return f"http://{host}:{port}{suffix}"


def stop_server():
    global _server, _thread, _TOKEN
    with _lock:
        if _server is not None:
            try:
                _server.shutdown()
                _server.server_close()
            except Exception:
                pass
            _server = None
            _thread = None
            _TOKEN = None
