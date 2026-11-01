"""Live-code updater regression (no network, no user DB changes).

All mock sources exercise the exact v1.3.2 source file, not old versions.
"""
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
sys.modules.setdefault("baostock", types.ModuleType("baostock"))

path = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.2.pyw"
loader = SourceFileLoader("mirror_v132", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class Response:
    def __init__(self, raw, url, *, status=200, headers=None, error_at=None):
        self.raw = raw
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.cursor = 0
        self.error_at = error_at

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self.url

    def read(self, n=-1):
        if self.error_at is not None and self.cursor >= self.error_at:
            self.error_at = None
            raise TimeoutError("simulated interrupted socket")
        if n < 0:
            n = len(self.raw)
        chunk = self.raw[self.cursor:self.cursor + n]
        self.cursor += len(chunk)
        return chunk


class MirrorUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = self.root / "AShareMAScanner_v1.3.2.pyw"
        self.old.write_text("APP_VERSION = '1.3.2'\n", encoding="utf8")
        self.tag = "v1.3.2"
        self.program = (b'APP_VERSION = "1.3.2"\n'
                        b'def main():\n    return "--update-ack"\n')
        self.sha = hashlib.sha256(self.program).hexdigest()
        self.fname = f"AShareMAScanner_{self.tag}.pyw"
        self.murl = f"{m.MIRROR_BASE}/files/{self.sha}/{self.fname}"
        self.gurl = f"https://github.com/Xstime/AShareMAScanner/releases/download/{self.tag}/{self.fname}"
        self.gh_final = "https://release-assets.githubusercontent.com/file-signed"
        self.calls = []

    def mirror(self, *, tag=None, digest=None, url=None, size=None, upstream=None):
        tag = self.tag if tag is None else tag
        digest = self.sha if digest is None else digest
        name = f"AShareMAScanner_{tag}.pyw"
        url = self.murl if url is None else url
        return json.dumps({
            "schema_version": 1, "repository": "Xstime/AShareMAScanner",
            "sync_request_id": "receipt-20261101", "synced_at": "2026-11-01T12:00:00Z",
            "tag_name": tag, "draft": False, "prerelease": False,
            "name": "AShareMAScanner", "body": "Release notes", "id": 234,
            "html_url": f"https://github.com/Xstime/AShareMAScanner/releases/tag/{tag}",
            "published_at": "2026-11-01T12:00:00Z",
            "assets": [{
                "name": name, "digest": "sha256:" + digest,
                "size": len(self.program) if size is None else size,
                "browser_download_url": url,
                "upstream_download_url": self.gurl if upstream is None else upstream,
            }],
        }).encode()

    def github(self, *, tag=None, digest=None, size=None):
        tag = tag or self.tag
        return json.dumps({
            "tag_name": tag, "draft": False, "prerelease": False,
            "assets": [{
                "name": f"AShareMAScanner_{tag}.pyw",
                "digest": "sha256:" + (digest or self.sha),
                "size": len(self.program) if size is None else size,
                "browser_download_url": f"https://github.com/Xstime/AShareMAScanner/releases/download/{tag}/AShareMAScanner_{tag}.pyw",
            }],
        }).encode()

    def response(self, req, timeout=None):
        url = req.full_url
        self.calls.append((url, req.get_header("Range"), req.get_header("If-range")))
        if url == m.MIRROR_LATEST:
            return Response(self.mirror(), url)
        if url == m.RELEASE_API:
            return Response(self.github(), url)
        if url == self.murl:
            return Response(self.program, url, headers={"ETag": '"mirror-signed"'})
        if url == self.gurl:
            return Response(self.program, self.gh_final)
        raise AssertionError("unexpected request " + url)

    def prepared(self, service=None, **callbacks):
        with patch.object(m.urllib.request, "urlopen", side_effect=service or self.response):
            return m.prepare_manual_update(self.old, **callbacks)

    def test_mirror_preferred_and_same_version_repair(self):
        seen = []
        msg, staged = self.prepared(on_update_found=lambda *v: seen.append(v))
        self.assertIn("v1.3.2", msg)
        self.assertEqual(staged.read_bytes(), self.program)
        self.assertEqual(self.calls[0][0], m.MIRROR_LATEST)
        self.assertEqual(self.calls[1][0], self.murl)
        self.assertFalse(any(url == m.RELEASE_API for url, *_ in self.calls))
        self.assertEqual(seen, [("v1.3.2", len(self.program))])
        staged.unlink()

    def test_same_version_same_digest_no_download(self):
        self.old.write_bytes(self.program)
        msg, path = self.prepared()
        self.assertIsNone(path)
        self.assertIn("最新", msg)
        self.assertEqual(len(self.calls), 1)

    def test_mirror_unreachable_uses_github(self):
        def server(req, timeout=None):
            if req.full_url == m.MIRROR_LATEST:
                raise TimeoutError("mirror inaccessible")
            return self.response(req, timeout)
        _, staged = self.prepared(server)
        self.assertEqual(staged.read_bytes(), self.program)
        self.assertIn((m.RELEASE_API, None, None), self.calls)
        staged.unlink()

    def test_network_failure_during_mirror_download_fallback_resets_bytes(self):
        cut = len(self.program) // 2
        mirror_calls = 0
        def server(req, timeout=None):
            nonlocal mirror_calls
            if req.full_url == self.murl:
                mirror_calls += 1
                if mirror_calls == 1:
                    # Serve truncated response to raise an interrupted socket on read.
                    return Response(self.program[:cut], self.murl,
                                    headers={"ETag": '"abc"'}, error_at=cut)
                raise TimeoutError("mirror stops answering")
            return self.response(req, timeout)
        with patch.object(m.time, "sleep", return_value=None):
            _, staged = self.prepared(server)
        self.assertEqual(staged.read_bytes(), self.program)
        self.assertGreaterEqual(mirror_calls, 2)
        self.assertTrue(any(url == m.RELEASE_API for url, *_ in self.calls))
        staged.unlink()

    def test_cross_source_digest_mismatch_must_fail_not_download(self):
        def server(req, timeout=None):
            if req.full_url == self.murl:
                raise TimeoutError("unavailable")
            if req.full_url == m.RELEASE_API:
                return Response(self.github(digest="0" * 64), m.RELEASE_API)
            return self.response(req, timeout)
        with patch.object(m.time, "sleep", return_value=None):
            with self.assertRaises(m.UpdateIntegrityError):
                self.prepared(server)
        self.assertEqual(list(self.root.glob(".ashare-update-*")), [])

    def test_invalid_manifest_not_masked_by_fallback(self):
        invalid = [
            self.mirror(url="https://evil.invalid/attack.pyw"),
            self.mirror(url=self.murl + "?download=1"),
            self.mirror(url=self.murl.replace("/files/", ":443/files/")),
            self.mirror(url=self.murl.replace(self.sha, "0" * 64)),
            self.mirror(digest="A" * 64),
            self.mirror(size=4194305),
            self.mirror(upstream="https://evil.invalid/surprise.pyw"),
            self.mirror(tag="v1.3.5"),
        ]
        for raw in invalid:
            with self.subTest(raw=raw[:120]):
                calls = []
                def server(req, timeout=None):
                    calls.append(req.full_url)
                    return Response(raw, m.MIRROR_LATEST)
                with self.assertRaises(m.UpdateIntegrityError):
                    self.prepared(server)
                self.assertEqual(calls, [m.MIRROR_LATEST])
                self.assertEqual(list(self.root.glob(".ashare-update-*")), [])

    def test_corrupt_payload_never_falls_back(self):
        def server(req, timeout=None):
            if req.full_url == self.murl:
                return Response(self.program + b"other", self.murl)
            return self.response(req, timeout)
        with self.assertRaises(m.UpdateIntegrityError):
            self.prepared(server)
        self.assertFalse(any(url == m.RELEASE_API for url, *_ in self.calls))
        self.assertEqual(list(self.root.glob(".ashare-update-*")), [])

    def test_206_resume_and_if_range(self):
        cut = len(self.program) // 2
        hits = []
        def server(req, timeout=None):
            if req.full_url != self.murl:
                return self.response(req, timeout)
            range_header = req.get_header("Range")
            if not range_header:
                return Response(self.program[:cut], self.murl,
                                headers={"ETag": '"immutable"'}, error_at=cut)
            hits.append((range_header, req.get_header("If-range")))
            return Response(self.program[cut:], self.murl, status=206, headers={
                "Content-Range": f"bytes {cut}-{len(self.program)-1}/{len(self.program)}"
            })
        with patch.object(m.time, "sleep", return_value=None):
            _, staged = self.prepared(server)
        self.assertEqual(staged.read_bytes(), self.program)
        self.assertEqual(hits, [(f"bytes={cut}-{len(self.program)-1}", '"immutable"')])
        staged.unlink()

    def test_206_wrong_range_rejected_and_original_preserved(self):
        cut = len(self.program) // 2
        def server(req, timeout=None):
            if req.full_url != self.murl:
                return self.response(req, timeout)
            if not req.get_header("Range"):
                return Response(self.program[:cut], self.murl, error_at=cut)
            return Response(self.program[cut:], self.murl, status=206, headers={
                "Content-Range": f"bytes 0-{len(self.program)-1}/{len(self.program)}"})
        with patch.object(m.time, "sleep", return_value=None):
            with self.assertRaises(m.UpdateIntegrityError):
                self.prepared(server)
        self.assertEqual(list(self.root.glob(".ashare-update-*")), [])
        self.assertIn("APP_VERSION", self.old.read_text())

    def test_cancel_clears_temp_not_db(self):
        db = self.root / "data" / "a_share_baostock_hfq.db"
        db.parent.mkdir()
        db.write_bytes(b"user database must remain intact")
        stopped = threading.Event()
        def stop_on_first_chunk(*values):
            stopped.set()
        with self.assertRaises(m.UpdateDownloadCancelled):
            self.prepared(on_progress=stop_on_first_chunk, cancel_event=stopped)
        self.assertEqual(list(self.root.glob(".ashare-update-*")), [])
        self.assertEqual(db.read_bytes(), b"user database must remain intact")

    def test_no_app_update_network_at_import(self):
        self.assertEqual(m.APP_VERSION, "1.3.2")
        self.assertEqual(m.MIRROR_LATEST,
                         "https://23.95.88.6:8443/ashare/latest.json")
        self.assertTrue(m._trusted_update_url(self.murl, "mirror",
                       tag=self.tag, name=self.fname, digest=self.sha))
        for bad in ("http://23.95.88.6:8443/ashare/latest.json",
                    "https://user@23.95.88.6:8443/ashare/latest.json",
                    "https://23.95.88.6:8443/ashare/latest.json#x"):
            self.assertFalse(m._trusted_update_url(bad, "mirror"))


class MinimalDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qt = QApplication.instance() or QApplication([])

    def test_only_one_minimal_window_no_logs_or_traceback(self):
        from PySide6.QtWidgets import QPlainTextEdit, QDialog, QLabel
        w = m.ScannerWindow(demo=True)
        w.show()
        self.qt.processEvents()
        cancel = threading.Event()
        def slow(_original, on_update_found=None, on_progress=None,
                 on_status=None, cancel_event=None):
            on_update_found("v1.3.3", 1000)
            on_progress(400, 1000, 64000)
            while not cancel_event.wait(.01):
                pass
            raise m.UpdateDownloadCancelled()
        try:
            with patch.object(m, "prepare_manual_update", side_effect=slow):
                w._show_release_info()
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    self.qt.processEvents()
                    if w._download_ui and w._download_ui[0].value() > 0:
                        break
                    time.sleep(.01)
                self.assertEqual(w._download_ui[0].maximum(), 1000)
                self.assertEqual(w._download_ui[0].value(), 400)
                self.assertIsNotNone(w._download_dialog)
                self.assertFalse(w._download_dialog.findChildren(QPlainTextEdit))
                texts = [x.text() for x in w._download_dialog.findChildren(QLabel)]
                self.assertFalse(any("http" in x or "Traceback" in x or "token" in x for x in texts))
                w._version_worker.cancel_download()
                deadline = time.monotonic() + 5
                while w._update_in_progress and time.monotonic() < deadline:
                    self.qt.processEvents()
                    time.sleep(.01)
                self.assertFalse(w._update_in_progress)
                self.assertTrue(w.update_button.isEnabled())
        finally:
            w.close()
            self.qt.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
