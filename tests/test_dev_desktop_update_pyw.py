"""Checks GUI pythonw streams and the actual self-updater's Desktop file writes.

These tests create disposable folders called Desktop; they NEVER touch the
user's Desktop, use network data, publish releases, or invoke the live updater.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from importlib.machinery import SourceFileLoader
import importlib.util

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SOURCE = Path(__file__).resolve().parents[1] / "A股MA扫描器_dev_AKShare.pyw"
loader = SourceFileLoader("dev_updater_desktop_checks", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class WindowsPywChecks(unittest.TestCase):
    def test_simulated_pythonw_null_std_streams_can_load_and_fetch_stocks(self):
        code = r"""
import runpy
import sys
from pathlib import Path
import pandas as pd
real_out=sys.stdout
sys.stdout=None
sys.stderr=None
program=runpy.run_path(sys.argv[1],run_name="windows_pyw_simulation")
assert sys.stdout is not None and hasattr(sys.stdout,"write")
assert sys.stderr is not None and hasattr(sys.stderr,"write")
quotes=program["AKShareQuotes"](Path(sys.argv[2]) / "missing.sqlite")
quotes.index_dates=lambda:["2026-11-04"]
def fake_spot():
    sys.stdout.write("AKShare progress output")
    sys.stderr.write("AKShare warning output")
    return pd.DataFrame({"代码":[str(600000+i) for i in range(1050)],
                         "名称":["测试"]*1050,"成交量":[100]*1050})
program["ak"].stock_zh_a_spot_em=fake_spot
quotes._pace=lambda:None
data=quotes.stocks("2026-11-04")
assert len(data)==1050
assert data.iloc[0]["code"]=="sh.600000"
real_out.write("PYW_STREAMS_OK")
"""
        with tempfile.TemporaryDirectory() as td:
            p = subprocess.run(
                [sys.executable, "-c", code, str(SOURCE), td],
                capture_output=True, text=True, timeout=35,
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("PYW_STREAMS_OK", p.stdout)


class DesktopUpdaterChecks(unittest.TestCase):
    """Runs the same UPDATE_HELPER as the app, with fake downloads in a sandbox."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.desktop = self.root / "Desktop"
        self.desktop.mkdir()

    @staticmethod
    def fake_program(version, ready=True):
        return textwrap.dedent('''\
            APP_VERSION = %(version)r
            import sys
            from pathlib import Path
            import time
            args = sys.argv
            if "--update-preview-ack" in args:
                ack = Path(args[args.index("--update-preview-ack") + 1])
                control = Path(args[args.index("--update-preview-control") + 1])
                if %(ready)s:
                    ack.write_text("ready", encoding="utf-8")
                    for index in range(300):
                        if control.exists() and control.read_text(encoding="utf-8") in ("done", "failed"):
                            break
                        time.sleep(0.03)
            def main():
                return 0
            if __name__ == "__main__":
                main()
            ''' % {"version":version, "ready":repr(ready)}).encode("utf-8")

    def run_install(self, folder, old_version, new_version, *, existing=None, ready=True):
        folder.mkdir(exist_ok=True, parents=True)
        old = existing if existing is not None else folder / f"AShareMAScanner_v{old_version}.pyw"
        if not old.exists():
            old.write_bytes(self.fake_program(old_version))
        old_before = old.read_bytes()
        staged = folder / ".downloaded-update.pyw"
        new_bytes = self.fake_program(new_version, ready=ready)
        staged.write_bytes(new_bytes)
        target = folder / f"AShareMAScanner_v{new_version}.pyw"
        backup = old.with_name(old.name + ".old-update.bak")
        ack = folder / "ashare-update-ack-test"
        control = folder / "ashare-update-control-test"
        helper = folder / "ashare-updater-test.py"
        helper.write_text(module.UPDATE_HELPER, encoding="utf-8")
        args = [
            sys.executable, str(helper), "2000000000", str(old.resolve()),
            str(staged.resolve()), str(target.resolve()), str(backup.resolve()),
            str(ack.resolve()), str(control.resolve()), old_version,
            new_version, hashlib.sha256(new_bytes).hexdigest(), str(len(new_bytes))]
        finished = subprocess.run(
            args, cwd=str(folder), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30)
        return finished, old, old_before, staged, target, new_bytes, control

    def test_first_and_second_update_both_write_new_program_on_desktop(self):
        result = self.run_install(self.desktop, "1.3.5", "1.3.6")
        p, old, old_bytes, stage, new, expected, control = result
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(new.parent, self.desktop)
        self.assertTrue(new.is_file())
        self.assertEqual(new.read_bytes(), expected)
        self.assertEqual(control.read_text(encoding="utf-8"), "done")
        self.assertFalse(old.exists())
        self.assertFalse(stage.exists())
        second = self.run_install(self.desktop, "1.3.6", "1.3.7", existing=new)
        p2, old2, _, stage2, new2, expected2, control2 = second
        self.assertEqual(p2.returncode, 0, p2.stderr)
        self.assertEqual(new2.parent, self.desktop)
        self.assertEqual(new2.read_bytes(), expected2)
        self.assertEqual(control2.read_text(encoding="utf-8"), "done")
        self.assertFalse(old2.exists())
        self.assertFalse(stage2.exists())

    def test_starting_from_another_folder_does_not_save_on_desktop(self):
        program_folder = self.root / "Applications"
        p, old, _, stage, final, new_data, control = self.run_install(
            program_folder, "1.3.5", "1.3.6")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(final.parent, program_folder)
        self.assertEqual(final.read_bytes(), new_data)
        self.assertFalse((self.desktop / final.name).exists())

    def test_clashing_desktop_filename_must_never_be_overwritten(self):
        existing = self.desktop / "AShareMAScanner_v1.3.6.pyw"
        existing.write_bytes(b"some other user's program")
        p, old, old_bytes, stage, _, expected, control = self.run_install(
            self.desktop, "1.3.5", "1.3.6")
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(old.read_bytes(), old_bytes)
        self.assertEqual(existing.read_bytes(), b"some other user's program")
        self.assertEqual(control.read_text(encoding="utf-8"), "failed")

    def test_failing_new_program_keeps_old_program_and_reports_failure(self):
        p, old, old_bytes, stage, final, new_data, control = self.run_install(
            self.desktop, "1.3.5", "1.3.6", ready=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(old.read_bytes(), old_bytes)
        self.assertEqual(control.read_text(encoding="utf-8"), "failed")
        self.assertEqual(final.read_bytes(), new_data)
        # The candidate is left for inspection, but no success is claimed.

    def test_quoted_dev_program_location_also_resolves_to_its_own_directory(self):
        # Mirrors the user's desktop filename, not the official release name.
        desktop_file = self.desktop / "A股MA扫描器_dev_AKShare.pyw"
        desktop_file.write_bytes(self.fake_program("1.3.6"))
        target = desktop_file.with_name("AShareMAScanner_v1.3.6.pyw")
        self.assertEqual(target.parent, self.desktop)
        self.assertNotEqual(target.name, desktop_file.name)
        # The normal update helper would replace the dev file with the same-version
        # official release, so that behavior is a known risk, not a test success.
        self.assertTrue(desktop_file.exists())
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
