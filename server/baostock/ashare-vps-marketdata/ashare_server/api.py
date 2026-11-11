from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .config import settings

LOG = logging.getLogger(__name__)


class MarketDataHandler(BaseHTTPRequestHandler):
    server_version = "AShareMarketData/1.0"
    sys_version = ""

    def _json(self, status: int, payload: dict) -> None:
        body = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):  # noqa: N802
        self._dispatch()

    def do_GET(self):  # noqa: N802
        self._dispatch()

    def do_POST(self):  # noqa: N802
        self._json(405, {"error": "read-only endpoint"})

    def _dispatch(self) -> None:
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/healthz":
            self._json(200, {"ok": True, "service": "ashare-marketdata", "version": "1.0.2-dev"})
            return
        if path == "/latest.json":
            manifest = settings.manifest_path
            if not manifest.is_file():
                self._json(503, {"ok": False, "error": "no verified snapshot published yet"})
                return
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception as exc:
                LOG.exception("Cannot read snapshot manifest")
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self._json(200, payload)
            return
        if path == "/snapshot.zip":
            self._send_snapshot()
            return
        self._json(404, {"error": "not found"})

    def _send_snapshot(self) -> None:
        manifest_path = settings.manifest_path
        if not manifest_path.is_file():
            self._json(503, {"ok": False, "error": "no verified snapshot published yet"})
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            filename = str(manifest.get("snapshot_file", ""))
            if (not filename.startswith("snapshot-") or not filename.endswith(".zip")
                    or Path(filename).name != filename):
                raise RuntimeError("invalid snapshot filename in latest.json")
            path = settings.public_dir / filename
            size = path.stat().st_size
            if size != int(manifest.get("snapshot_size", -1)):
                raise RuntimeError("snapshot size differs from latest.json")
            digest = str(manifest.get("snapshot_sha256", ""))
            if len(digest) != 64:
                raise RuntimeError("snapshot SHA-256 missing from latest.json")
        except Exception as exc:
            LOG.exception("Snapshot metadata check failed")
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", 'attachment; filename="ashare-marketdata.zip"')
        self.send_header("ETag", '"' + digest + '"')
        self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def log_message(self, fmt, *args):
        LOG.info("http %s - %s", self.address_string(), fmt % args)


def serve() -> None:
    server = ThreadingHTTPServer((settings.api_host, settings.api_port), MarketDataHandler)
    server.daemon_threads = True
    LOG.info("Market data API listening on http://%s:%d", settings.api_host, settings.api_port)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
