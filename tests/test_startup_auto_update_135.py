"""v1.3.5 startup auto-updater tests (offline fixtures only).

The real v1.3.5 module is loaded; no BaoStock connections or live VPS calls.
"""
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
import urllib.error
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
PROGRAM = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.5.pyw"
loader = SourceFileLoader("v135_startup_update", str(PROGRAM))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class FakeResponse:
    def __init__(self, body, url):
        self.body, self.url = body, url
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def geturl(self):
        return self.url
    def read(self, n=-1):
        return self.body[:n]


class StartupUpdateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.old = self.root / "AShareMAScanner_v1.3.5.pyw"
        self.old.write_text('APP_VERSION = "1.3.5"\n')
        self.new_source = b'APP_VERSION = "1.3.6"\ndef main():\n    return "--update-ack"\n'
        self.digest = hashlib.sha256(self.new_source).hexdigest()
        self.tag = "v1.3.6"
        self.name = f"AShareMAScanner_{self.tag}.pyw"
        self.mirror_url = f"{m.MIRROR_BASE}/files/{self.digest}/{self.name}"
        self.manifest = self.make_manifest()

    def make_manifest(self):
        tag, name = self.tag, self.name
        archive = b"zip-placeholder"
        archive_digest = hashlib.sha256(archive).hexdigest()
        return {
            "schema_version": 1, "repository": m.REPO_FULL_NAME,
            "sync_request_id": "sync-test-135", "synced_at": "2026-11-03T00:00:00Z",
            "tag_name": tag, "draft": False, "prerelease": False,
            "name": "Release", "body": "Safe automatic updates", "id": 99,
            "html_url": f"{m.RELEASES_PAGE}/tag/{tag}",
            "published_at": "2026-11-03T00:00:00Z",
            "assets": [
                {"name": name, "size": len(self.new_source),
                 "digest": "sha256:" + self.digest,
                 "browser_download_url": self.mirror_url,
                 "upstream_download_url":
                     f"https://github.com/Xstime/AShareMAScanner/releases/download/{tag}/{name}"},
                {"name": f"AShareMAScanner_{tag}.zip", "size": len(archive),
                 "digest": "sha256:" + archive_digest,
                 "browser_download_url":
                     f"{m.MIRROR_BASE}/files/{archive_digest}/AShareMAScanner_{tag}.zip",
                 "upstream_download_url":
                     f"https://github.com/Xstime/AShareMAScanner/releases/download/{tag}/AShareMAScanner_{tag}.zip"}
            ]
        }

    def test_pinned_vps_probed_before_dependency_bootstrap(self):
        source = PROGRAM.read_text(encoding="utf8")
        self.assertLess(source.index("_STARTUP_VPS_PROBE = _probe_startup_vps()"),
                        source.index("_bootstrap_dependencies()\n    finally:"))
        self.assertTrue(m._should_skip_startup_update(["--demo"]))
        self.assertTrue(m._should_skip_startup_update(["--screenshot", "ui.png"]))
        self.assertTrue(m._should_skip_startup_update(["--update-preview-ack", "some-ack"]))
        self.assertFalse(m._should_skip_startup_update([]))

    def test_vps_probe_uses_https_pinned_url(self):
        payload = json.dumps(self.manifest).encode()
        with patch.object(m.urllib.request, "urlopen",
                          return_value=FakeResponse(payload, m.MIRROR_LATEST)) as req:
            status, parsed = m._probe_startup_vps()
        self.assertEqual(status, "mirror")
        self.assertEqual(parsed["tag_name"], self.tag)
        self.assertEqual(req.call_args.args[0].full_url, m.MIRROR_LATEST)
        self.assertNotIn("context", req.call_args.kwargs)

    def test_offline_probe_remains_safe(self):
        with patch.object(m.urllib.request, "urlopen",
                          side_effect=urllib.error.URLError("offline")):
            self.assertEqual(m._probe_startup_vps(), ("offline", None))

    def test_redirect_or_malformed_mirror_is_not_trusted(self):
        with patch.object(m.urllib.request, "urlopen", return_value=FakeResponse(
                json.dumps(self.manifest).encode(), "https://evil.example/latest.json")):
            self.assertEqual(m._probe_startup_vps(), ("invalid", None))
        with patch.object(m.urllib.request, "urlopen", return_value=FakeResponse(
                b"not-json", m.MIRROR_LATEST)):
            self.assertEqual(m._probe_startup_vps(), ("invalid", None))

    def test_newer_version_downloaded_and_validated_without_second_manifest_fetch(self):
        received = []
        def download(url, size, file, progress, status, cancel, **identity):
            received.append((url, identity))
            Path(file).write_bytes(self.new_source)
            return self.digest
        with patch.object(m, "_load_update_release", side_effect=AssertionError("duplicate fetch")), \
             patch.object(m, "_download_release_asset", side_effect=download):
            message, staged = m.prepare_manual_update(
                self.old, newer_only=True, prechecked=("mirror", self.manifest))
        self.addCleanup(staged.unlink, missing_ok=True)
        self.assertEqual(message, "已验证 v1.3.6")
        self.assertEqual(staged.read_bytes(), self.new_source)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], self.mirror_url)
        self.assertEqual(received[0][1]["source"], "mirror")
        self.assertEqual(self.old.read_text(), 'APP_VERSION = "1.3.5"\n')

    def test_equal_version_never_auto_reinstalls_or_downloads(self):
        same = dict(self.manifest)
        same["tag_name"] = "v1.3.5"
        with patch.object(m, "_download_release_asset",
                          side_effect=AssertionError("must not download")):
            message, staged = m.prepare_manual_update(
                self.old, newer_only=True, prechecked=("mirror", same))
        self.assertEqual((message, staged), ("已是最新版本", None))

    def test_offline_mirror_can_check_official_release_and_continue(self):
        same = {"tag_name": "v1.3.5", "draft": False, "prerelease": False}
        with patch.object(m, "_fetch_release_json", return_value=same) as fetch, \
             patch.object(m, "_download_release_asset",
                          side_effect=AssertionError("must not download")):
            message, staged = m.prepare_manual_update(
                self.old, newer_only=True, prechecked=("offline", None))
        self.assertIsNone(staged)
        fetch.assert_called_once_with(m.RELEASE_API, "github_api")

    def test_integrity_error_never_falls_back(self):
        with patch.object(m, "_fetch_release_json",
                          side_effect=AssertionError("unexpected fallback")):
            with self.assertRaises(m.UpdateIntegrityError):
                m.prepare_manual_update(
                    self.old, newer_only=True, prechecked=("invalid", None))
        bad = dict(self.manifest)
        bad["repository"] = "wrong/owner"
        with patch.object(m, "_download_release_asset",
                          side_effect=AssertionError("unsafe download")):
            with self.assertRaises(m.UpdateIntegrityError):
                m.prepare_manual_update(
                    self.old, newer_only=True, prechecked=("mirror", bad))

    def test_main_returns_on_successful_handoff_without_market_login(self):
        with patch.object(sys, "argv", [str(PROGRAM)]), \
             patch.object(m, "_startup_auto_update", return_value=True) as update, \
             patch.object(m, "run_tk_data_phase",
                          side_effect=AssertionError("market must not start")):
            self.assertEqual(m.main(), 0)
        update.assert_called_once_with(None)

    def test_helper_uses_shared_verified_handoff_without_modifying_old(self):
        staged = self.root / "downloaded.pyw"
        staged.write_bytes(self.new_source)
        old_bytes = self.old.read_bytes()
        with patch.object(m, "__file__", str(self.old)), \
             patch.object(m.subprocess, "Popen", return_value=MagicMock()) as spawn:
            control, process = m._launch_verified_update_helper(staged)
        self.assertEqual(self.old.read_bytes(), old_bytes)
        args = spawn.call_args.args[0]
        self.assertEqual(Path(args[3]).resolve(), self.old.resolve())
        self.assertEqual(Path(args[4]).resolve(), staged.resolve())
        self.assertEqual(Path(args[5]).resolve(), (self.root / self.name).resolve())
        self.assertTrue(Path(args[1]).is_file())
        self.assertIsNotNone(process)
        self.addCleanup(Path(args[1]).unlink, missing_ok=True)
        self.addCleanup(Path(args[7]).unlink, missing_ok=True)
        self.addCleanup(control.unlink, missing_ok=True)

    def test_gui_auto_update_waits_for_helper_visible_ack_before_exiting_old(self):
        staged = self.root / "verified-new.pyw"
        staged.write_bytes(self.new_source)
        control = self.root / "ashare-update-control-test-success"
        old_bytes = self.old.read_bytes()

        def launch(file):
            self.assertEqual(Path(file), staged)
            # Simulate the helper's visible Qt preview ACK + close-old signal.
            control.write_text("close-old", encoding="utf8")
            process = MagicMock()
            process.poll.return_value = None
            return control, process

        with patch.object(m, "prepare_manual_update",
                          return_value=("已验证 v1.3.6", staged)) as check, \
             patch.object(m, "_launch_verified_update_helper",
                          side_effect=launch) as install:
            handed_off = m._startup_auto_update(("mirror", self.manifest))
        if not check.called:
            self.skipTest("No Tk GUI available on this runner")
        self.assertTrue(handed_off)
        install.assert_called_once_with(staged)
        self.assertEqual(self.old.read_bytes(), old_bytes,
                         "Old file must survive until helper reaps its process")

    def test_gui_update_failure_continues_old_version(self):
        staged = self.root / "verified-failed.pyw"
        staged.write_bytes(self.new_source)
        control = self.root / "ashare-update-control-test-failure"
        old_bytes = self.old.read_bytes()

        def launch(file):
            control.write_text("failed", encoding="utf8")
            process = MagicMock()
            process.poll.return_value = 1
            return control, process

        with patch.object(m, "prepare_manual_update",
                          return_value=("已验证 v1.3.6", staged)) as check, \
             patch.object(m, "_launch_verified_update_helper",
                          side_effect=launch) as install:
            handed_off = m._startup_auto_update(("mirror", self.manifest))
        self.assertFalse(handed_off)
        if check.called:
            install.assert_called_once_with(staged)
        self.assertEqual(self.old.read_bytes(), old_bytes)

    def test_offline_window_automatically_continues_to_market(self):
        # On headless macOS the window is intentionally unavailable; Linux
        # Xvfb and Windows exercise the actual Tk event loop.
        with patch.object(m, "prepare_manual_update",
                          return_value=("已是最新版本", None)) as check:
            handoff = m._startup_auto_update(("offline", None))
        self.assertFalse(handoff)
        if check.called:
            self.assertTrue(check.call_args.kwargs["newer_only"])
            self.assertEqual(check.call_args.kwargs["prechecked"], ("offline", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
