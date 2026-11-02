"""End-to-end updater helper tests: canonical new file is durable BEFORE old deletion.

Runs actual standalone helper and child Python processes without market calls.
Protects user data/; tests macOS, Windows, Linux.
"""
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
PROGRAM = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.3.pyw"
loader = SourceFileLoader("v133_update_persistence", str(PROGRAM))
spec = importlib.util.spec_from_loader(loader.name, loader)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


class VersionedFilePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.old = self.parent / "A股MA扫描器_v1.3.2.pyw"
        self.old.write_bytes(b"previous user version; must survive until UI")
        self.final = self.parent / "AShareMAScanner_v1.3.3.pyw"
        self.staged = self.parent / ".ashare-update-tested.pyw"
        self.backup = self.parent / (self.old.name + ".old-update.bak")
        self.ack = self.parent / "ashare-update-ack-for-test"
        self.helper = self.parent / "ashare-updater-test.py"
        self.helper.write_text(scanner.UPDATE_HELPER, encoding="utf-8")
        self.database = self.parent / "data" / "a_share_baostock_hfq.db"
        self.database.parent.mkdir()
        self.database.write_bytes(b"vintage market data remains unchanged")

    def child_source(self, *, fail=False, check_old=True, delay=0.25):
        if fail:
            return b'APP_VERSION = "1.3.3"\nraise RuntimeError("simulated GUI startup failure")\n'
        old_required = (
            f'assert Path(__file__).with_name("{self.old.name}").is_file()\n'
            if check_old else "")
        return (
            'from pathlib import Path\nimport sys,time\n'
            'APP_VERSION = "1.3.3"\n'
            'args = sys.argv\n'
            'assert "--update-preview-ack" in args\n'
            'assert "--update-preview-control" in args\n'
            f'{old_required}'
            'ack=Path(args[args.index("--update-preview-ack")+1])\n'
            'control=Path(args[args.index("--update-preview-control")+1])\n'
            'target=Path(args[args.index("--update-preview-target")+1])\n'
            'assert target.parent == Path(__file__).parent\n'
            f'time.sleep({delay})\n'
            'ack.write_text("ready",encoding="utf-8")\n'
            'end=time.monotonic()+5\n'
            'while time.monotonic()<end:\n'
            '    state=control.read_text() if control.exists() else ""\n'
            '    if state in ("done","failed"):\n'
            '        break\n'
            '    time.sleep(.03)\n'
            'time.sleep(.2)\n'
        ).encode()

    def helper_args(self, source, *, sha=None, final=None, old=None, old_pid=999999):
        self.staged.write_bytes(source)
        expected = hashlib.sha256(source).hexdigest()
        self.control = self.parent / "ashare-update-control-for-test"
        return [
            sys.executable, str(self.helper), str(old_pid), str(old or self.old),
            str(self.staged), str(final or self.final), str(self.backup),
            str(self.ack), str(self.control),
            "1.3.2", "1.3.3", sha or expected, str(len(source))
        ]

    def run_helper(self, source, *, sha=None, final=None, old=None):
        args = self.helper_args(source, sha=sha, final=final, old=old)
        completed = subprocess.run(args, text=True, capture_output=True, timeout=20)
        time.sleep(.6)
        return completed

    def assert_db_intact(self):
        self.assertEqual(self.database.read_bytes(), b"vintage market data remains unchanged")

    def test_new_version_saved_under_own_filename_before_old_is_deleted(self):
        content = self.child_source()
        result = self.run_helper(content)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.final.read_bytes(), content)
        self.assertFalse(self.old.exists())
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.staged.exists())
        self.assert_db_intact()

    def test_new_file_remains_even_if_new_application_cannot_start(self):
        content = self.child_source(fail=True)
        result = self.run_helper(content)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.final.read_bytes(), content)
        self.assertEqual(self.old.read_bytes(), b"previous user version; must survive until UI")
        self.assert_db_intact()

    def test_bad_digest_rejected_before_touching_original_or_final(self):
        result = self.run_helper(self.child_source(), sha="0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.final.exists())
        self.assertTrue(self.old.exists())
        self.assert_db_intact()

    def test_existing_unrelated_target_is_never_overwritten(self):
        self.final.write_bytes(b"not an official release file")
        result = self.run_helper(self.child_source())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.final.read_bytes(), b"not an official release file")
        self.assertTrue(self.old.exists())
        self.assert_db_intact()

    def test_existing_same_digest_target_is_safe_to_reuse(self):
        content = self.child_source()
        self.final.write_bytes(content)
        result = self.run_helper(content)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.final.read_bytes(), content)
        self.assertFalse(self.old.exists())
        self.assert_db_intact()

    def test_repair_same_version_failing_new_program_restores_original(self):
        self.old.unlink()
        self.old = self.final
        old_bytes = b'APP_VERSION = "1.3.3"\nprint("working earlier file")\n'
        self.old.write_bytes(old_bytes)
        self.backup = self.parent / (self.old.name + ".old-update.bak")
        result = self.run_helper(self.child_source(fail=True), old=self.old, final=self.old)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.old.read_bytes(), old_bytes)
        self.assertFalse(self.backup.exists())
        self.assert_db_intact()

    def test_repair_same_version_after_ack_replaces_old_and_clears_backup(self):
        self.old.unlink()
        self.old = self.final
        self.old.write_bytes(b"older same-version but different digest")
        self.backup = self.parent / (self.old.name + ".old-update.bak")
        content = self.child_source(check_old=False)
        result = self.run_helper(content, old=self.old, final=self.old)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.old.read_bytes(), content)
        self.assertFalse(self.backup.exists())
        self.assert_db_intact()

    def test_backup_guard_prevents_destructive_repair(self):
        self.old.unlink()
        self.old = self.final
        self.old.write_bytes(b"older same-version")
        self.backup = self.parent / (self.old.name + ".old-update.bak")
        self.backup.write_bytes(b"must not overwrite")
        result = self.run_helper(self.child_source(check_old=False), old=self.old, final=self.old)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.old.read_bytes(), b"older same-version")
        self.assertEqual(self.backup.read_bytes(), b"must not overwrite")

    def test_cannot_save_to_wrong_versioned_filename(self):
        incorrect = self.parent / "AShareMAScanner_v9.9.9.pyw"
        result = self.run_helper(self.child_source(), final=incorrect)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(incorrect.exists())
        self.assertTrue(self.old.exists())

    def test_target_and_source_paths_cannot_escape_original_directory(self):
        other = self.parent / "other"
        other.mkdir()
        wrong_target = other / "AShareMAScanner_v1.3.3.pyw"
        result = self.run_helper(self.child_source(), final=wrong_target)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(wrong_target.exists())
        self.assertTrue(self.old.exists())

    def test_real_updated_qt_preview_ack_and_visible_notification(self):
        """Real application imports and Qt dialog succeed without DB refresh."""
        self.final.write_bytes(PROGRAM.read_bytes())
        self.assertTrue(self.final.is_file())
        self.control = self.parent / "ashare-update-control-real-qt"
        ack = self.parent / "ashare-update-ack-real-qt"
        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        cmd = [
            sys.executable, str(self.final),
            "--update-preview-ack", str(ack),
            "--update-preview-control", str(self.control),
            "--update-preview-target", str(self.final),
        ]
        child = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 20
            while not ack.exists() and time.monotonic() < deadline:
                if child.poll() is not None:
                    break
                time.sleep(.1)
            if not ack.exists() and child.poll() is not None:
                _, stderr = child.communicate(timeout=5)
                self.fail(f"Real preview GUI exited {child.returncode}: {stderr[-3000:]}")
            self.assertTrue(ack.exists(),
                            f"Real preview GUI did not start: {child.poll()}")
            self.assertEqual(ack.read_text(), "ready")
            self.assertTrue(self.old.is_file(),
                            "Old file must still exist while new Qt UI is visible")
            self.control.write_text("failed", encoding="utf-8")
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)

    def test_real_pyqt_window_writes_ack_only_after_startup(self):
        # Run the full scanner in demo/screenshot mode; unlike helper synthetic
        # tests, this exercises the actual new version's Qt ACK placement.
        screenshot = self.parent / "new-real-window.png"
        actual_ack = self.parent / "ashare-update-ack-real-window"
        env = os.environ.copy()
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        result = subprocess.run(
            [sys.executable, str(PROGRAM), "--demo", "--screenshot",
             str(screenshot), "--update-ack", str(actual_ack)],
            capture_output=True, text=True, timeout=40, env=env)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertTrue(screenshot.exists())
        self.assertEqual(actual_ack.read_text(), "ready")
        self.assert_db_intact()


if __name__ == "__main__":
    unittest.main(verbosity=2)
