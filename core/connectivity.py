"""Connectivity checker that emits online/offline status periodically.

This module provides a small background checker that probes a well-known
host and emits a Qt signal when connectivity changes. It uses asyncio
to avoid blocking the UI event loop.
"""
import socket
import asyncio
from qtpy.QtCore import QObject, Signal
from typing import Optional


class ConnectivityChecker(QObject):
    """Background connectivity checker.

    Emits:
    - `status_changed(bool)` : True=online, False=offline
    - `probing(bool)` : True when an individual probe starts, False when it ends
    """

    status_changed = Signal(bool)
    probing = Signal(bool)

    # Fallback probe targets tried in order — first success → online
    _PROBE_TARGETS = [
        ('1.1.1.1', 80),     # Cloudflare HTTP
        ('1.1.1.1', 443),    # Cloudflare HTTPS
        ('8.8.8.8', 80),     # Google HTTP
        ('8.8.8.8', 443),    # Google HTTPS
        ('9.9.9.9', 443),    # Quad9 HTTPS
    ]

    def __init__(self, interval=5, host=('8.8.8.8', 53), timeout=3):
        super().__init__()
        self.interval = max(1, int(interval))
        self.host = host  # kept for API compat; actual probe uses _PROBE_TARGETS
        self.timeout = float(timeout)
        self._running = False
        self._task = None
        self._last_status = None

    def start(self):
        if self._running:
            return
        self._running = True
        # Start the background task
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())

    def stop(self):
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self):
        while self._running:
            try:
                try:
                    self.probing.emit(True)
                except Exception:
                    pass

                status = await self._probe_once_async()

                try:
                    self.probing.emit(False)
                except Exception:
                    pass

                if status != self._last_status:
                    self._last_status = status
                    try:
                        self.status_changed.emit(status)
                    except Exception:
                        pass

                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.interval)

    def probe_now(self) -> None:
        """Trigger a single probe asynchronously.

        Emits `probing(True)` before the probe and `probing(False)` after.
        Also emits `status_changed(bool)` if the status differs from the last known.
        Returns immediately; the result is delivered via signals.
        """
        loop = asyncio.get_event_loop()
        loop.create_task(self._probe_now_async())

    async def _probe_now_async(self):
        """Async implementation of immediate probe"""
        try:
            self.probing.emit(True)
        except Exception:
            pass
        
        status = await self._probe_once_async()
        
        try:
            self.probing.emit(False)
        except Exception:
            pass

        if status != self._last_status:
            self._last_status = status
            try:
                self.status_changed.emit(status)
            except Exception:
                pass

    async def _probe_once_async(self):
        """Async probe that doesn't block the event loop"""
        try:
            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(None, self._probe_once_sync)
            return status
        except Exception:
            return False

    def _probe_once_sync(self):
        """Synchronous socket probe — tries multiple targets, returns True on first success."""
        for host, port in self._PROBE_TARGETS:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self.timeout)
                s.connect((host, port))
                s.close()
                return True
            except Exception:
                continue
        return False

