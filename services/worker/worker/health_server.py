"""Cloud Run icin minimal HTTP health endpoint (worker sureci)."""

from __future__ import annotations

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)
_server: HTTPServer | None = None


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health", "/api/v1/health"):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server(port: int | None = None) -> None:
    """Arka planda GET /health sunar (Cloud Run startup/liveness probe)."""
    global _server
    if _server is not None:
        return

    listen_port = port if port is not None else int(os.environ.get("PORT", "8080"))
    _server = HTTPServer(("0.0.0.0", listen_port), _HealthHandler)
    thread = threading.Thread(target=_server.serve_forever, name="worker-health", daemon=True)
    thread.start()
    logger.info("Worker health server dinliyor (port=%s)", listen_port)


def stop_health_server() -> None:
    global _server
    if _server is None:
        return
    _server.shutdown()
    _server = None
