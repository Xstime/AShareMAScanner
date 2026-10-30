"""Cancellable progress update / retry regression tests. All network calls mocked."""
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
p = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.0.pyw"
loader = SourceFileLoader("v130_progress_under_test", str(p))
spec = importlib.util.spec_from_loader(loader.name, loader)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


class FakeResponse:
    def __init__(self, data, url, *, status=200, headers=None, raise_once_at=None):
        self.data = data
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.pos = 0
        self.raise_once_at = raise_once_at

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, n=-1):
        if self.raise_once_at is not None and self.pos >= self.raise_once_at:
            self.raise_once_at = None
            raise TimeoutError("simulated inactive socket")
        if n < 0:
            n = len(self.data) - self.pos
        part = self.data[self.pos:self.pos + n]
        self.pos += len(part)
        return part


class ProgressUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.local = self.root / "A股MA扫描器_v1.3.0.pyw"
        self.local.write_text('APP_VERSION = "1.3.0"\n', encoding="utf8")
        self.tag = "v1.3.1"
        self.source = (b'APP_VERSION = "1.3.1"\n'
                       b'def main():\n    return "--update-ack"\n')
        self.url = ("https://github.com/Xstime/AShareMAScanner/"
                    "releases/download/v1.3.1/AShareMAScanner_v1.3.1.pyw")
        self.target = "https://release-assets.githubusercontent.com/signed-test"
        self.release = json.dumps({
            "tag_name": self.tag, "draft": False, "prerelease": False,
            "assets": [{
                "name": "AShareMAScanner_v1.3.1.pyw",
                "browser_download_url": self.url,
                "size": len(self.source),
                "digest": "sha256:" + hashlib.sha256(self.source).hexdigest(),
            }],
        }).encode()

    def server(self, asset_response, calls):
        def serve(request, timeout=None):
            uri = request.full_url
            calls.append((uri, timeout, request.get_header("Range")))
            if uri == scanner.RELEASE_API:
                return FakeResponse(self.release, uri)
            return asset_response(request)
        return serve

    def test_window_notifications_and_staged_source_integrity(self):
        calls, found, progress, states = [], [], [], []
        server = self.server(lambda _r: FakeResponse(self.source, self.target), calls)
        with patch.object(scanner.urllib.request, "urlopen", side_effect=server):
            message, staged = scanner.prepare_manual_update(
                self.local, on_update_found=lambda *v: found.append(v),
                on_progress=lambda *v: progress.append(v),
                on_status=states.append)
        self.assertEqual(found, [("v1.3.1", len(self.source))])
        self.assertTrue(progress)
        self.assertEqual(progress[-1][:2], (len(self.source), len(self.source)))
        self.assertEqual(staged.read_bytes(), self.source)
        self.assertTrue(any("验证" in state for state in states))
        self.assertIn("1.3.1", message)
        self.assertEqual(calls[0][1], 8)
        self.assertEqual(calls[1][1], 30)  # per-socket guard, not total time
        staged.unlink()

    def test_socket_timeout_resumes_using_checked_http_range(self):
        calls = []
        split = len(self.source) // 2
        def asset(request):
            part = request.get_header("Range")
            if part is None:
                return FakeResponse(self.source, self.target, raise_once_at=split)
            self.assertEqual(part, f"bytes={split}-")
            return FakeResponse(
                self.source[split:], self.target, status=206,
                headers={"Content-Range": f"bytes {split}-{len(self.source)-1}/{len(self.source)}"})
        # Force first read into two parts. FakeResponse.read() accepts a large read,
        # so the first response serves only half and raises on the next call.
        def first_then_resume(request):
            if request.get_header("Range") is None:
                return FakeResponse(self.source[:split], self.target, raise_once_at=split)
            return asset(request)
        with patch.object(scanner.urllib.request, "urlopen",
                          side_effect=self.server(first_then_resume, calls)):
            with patch.object(scanner.time, "sleep", return_value=None):
                message, staged = scanner.prepare_manual_update(self.local)
        self.assertEqual(staged.read_bytes(), self.source)
        self.assertEqual(len(calls), 3)
        self.assertIn("1.3.1", message)
        staged.unlink()

    def test_range_ignored_restarts_safely(self):
        calls = []
        split = len(self.source) // 2
        def asset(request):
            if request.get_header("Range") is None:
                return FakeResponse(self.source[:split], self.target, raise_once_at=split)
            return FakeResponse(self.source, self.target, status=200)
        with patch.object(scanner.urllib.request, "urlopen",
                          side_effect=self.server(asset, calls)):
            with patch.object(scanner.time, "sleep", return_value=None):
                _, staged = scanner.prepare_manual_update(self.local)
        self.assertEqual(staged.read_bytes(), self.source)
        staged.unlink()

    def test_invalid_range_refuses_unsafe_append(self):
        split = len(self.source) // 2
        def asset(request):
            if request.get_header("Range") is None:
                return FakeResponse(self.source[:split], self.target, raise_once_at=split)
            return FakeResponse(
                self.source[split:], self.target, status=206,
                headers={"Content-Range": f"bytes 0-{len(self.source)-1}/{len(self.source)}"})
        with patch.object(scanner.urllib.request, "urlopen",
                          side_effect=self.server(asset, [])):
            with patch.object(scanner.time, "sleep", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "区间不可信"):
                    scanner.prepare_manual_update(self.local)
        self.assertEqual(list(self.root.glob(".ashare-update-*")), [])

    def test_cancel_during_download_removes_staged_and_preserves_old(self):
        stop = threading.Event()
        progress = []
        server = self.server(lambda _r: FakeResponse(self.source, self.target), [])
        def on_progress(*numbers):
            progress.append(numbers)
            stop.set()
        with patch.object(scanner.urllib.request, "urlopen", side_effect=server):
            with self.assertRaises(scanner.UpdateDownloadCancelled):
                scanner.prepare_manual_update(self.local, on_progress=on_progress,
                                              cancel_event=stop)
        self.assertEqual(len(progress), 1)
        self.assertEqual(list(self.root.glob(".ashare-update-*")), [])
        self.assertEqual(self.local.read_text(encoding="utf8"),
                         'APP_VERSION = "1.3.0"\n')

    def test_existing_data_folder_unchanged(self):
        data = self.root / "data"
        data.mkdir()
        db = data / "a_share_baostock_hfq.db"
        db.write_bytes(b"known database bytes")
        with patch.object(scanner.urllib.request, "urlopen",
                          side_effect=self.server(
                              lambda _r: FakeResponse(self.source, self.target), [])):
            _, staged = scanner.prepare_manual_update(self.local)
        staged.unlink()
        self.assertEqual(db.read_bytes(), b"known database bytes")


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_download_dialog_visible_and_cancelable(self):
        window = scanner.ScannerWindow(demo=True)
        window.show()
        self.app.processEvents()
        entered = threading.Event()
        def slow_update(_original, on_update_found=None, on_progress=None,
                        on_status=None, cancel_event=None):
            on_update_found("v1.3.1", 1000000)
            on_progress(4096, 1000000, 2048.0)
            entered.set()
            while not cancel_event.wait(0.01):
                pass
            raise scanner.UpdateDownloadCancelled("cancelled")
        try:
            with patch.object(scanner, "prepare_manual_update", side_effect=slow_update):
                window._show_release_info()
                deadline = time.monotonic() + 5
                while (window._download_dialog is None and time.monotonic() < deadline):
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertIsNotNone(window._download_dialog)
                self.assertTrue(window._download_dialog.isVisible())
                self.assertTrue(entered.is_set())
                self.assertEqual(window._download_ui[0].maximum(), 1000)
                self.assertGreater(window._download_ui[0].value(), 0)
                window._version_worker.cancel_download()
                deadline = time.monotonic() + 5
                while window._update_in_progress and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertFalse(window._update_in_progress)
                self.assertIsNone(window._download_dialog)
                self.assertTrue(window.update_button.isEnabled())
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
