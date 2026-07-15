"""API Studio — a Postman-style API client that runs inside the integrated
browser and is backed by a small local (127.0.0.1) HTTP server."""

from ui.api_studio.backend import ensure_server, stop_server, base_url

__all__ = ["ensure_server", "stop_server", "base_url"]
