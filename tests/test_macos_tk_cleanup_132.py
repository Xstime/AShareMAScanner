"""Regression for macOS Tk/Tcl Variable finalization before starting Qt.

The standalone process can also exercise an actual three-stage Tk data window:
  python tests/test_macos_tk_cleanup_131.py --tk-smoke
"""
import gc
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import threading
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
script = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.2.pyw"
loader = SourceFileLoader("mac_tk_shutdown_under_test", str(script))
spec = importlib.util.spec_from_loader(loader.name, loader)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


class TestTkVariableRelease(unittest.TestCase):
    def test_string_and_double_var_released_on_main_thread(self):
        import tkinter as tk
        root = tk.Tcl()  # No display server needed.
        txt = scanner._managed_tk_variable(tk.StringVar, root, "hello")
        pct = scanner._managed_tk_variable(tk.DoubleVar, root, 12.5)
        txt_name, pct_name = str(txt), str(pct)
        self.assertEqual(root.getvar(txt_name), "hello")
        self.assertAlmostEqual(root.getdouble(root.getvar(pct_name)), 12.5)
        txt.dispose_tcl()
        pct.dispose_tcl()
        self.assertFalse(root.getboolean(root.call("info", "exists", txt_name)))
        self.assertFalse(root.getboolean(root.call("info", "exists", pct_name)))
        # Idempotent even after the interpreter's Tcl variables are gone.
        txt.dispose_tcl()
        pct.dispose_tcl()
        # A background GC cycle that drops the objects must no longer call Tcl.
        txt.cycle = [txt]
        pct.cycle = [pct]
        del txt, pct
        errors = []
        def collect():
            try:
                gc.collect()
            except BaseException as exc:
                errors.append(str(exc))
        thread = threading.Thread(target=collect)
        thread.start()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    def test_main_thread_disposal_guard(self):
        import tkinter as tk
        root = tk.Tcl()
        txt = scanner._managed_tk_variable(tk.StringVar, root, "hi")
        errors = []
        def attempt():
            try:
                txt.dispose_tcl()
            except RuntimeError as exc:
                errors.append(str(exc))
        worker = threading.Thread(target=attempt)
        worker.start()
        worker.join(timeout=10)
        self.assertTrue(any("main thread" in e for e in errors))
        # No modification to Tcl has occurred, so the main thread can clean up.
        self.assertEqual(txt.get(), "hi")
        txt.dispose_tcl()

    def test_font_is_native_on_macos(self):
        if sys.platform == "darwin":
            self.assertEqual(scanner.UI_FONT_FAMILY, "Helvetica Neue")
        else:
            self.assertEqual(scanner.UI_FONT_FAMILY, "Segoe UI")


def run_tk_smoke():
    # This must be invoked from the main Python thread in a new process.
    class MockBaoStock:
        def update_all(self, notify):
            notify(24.5, "测试数据 1/2")
            notify(100, "测试数据 2/2")
            return {"mock": "success"}
        def cancel_update(self):
            pass
    result = scanner.run_tk_data_phase(MockBaoStock())
    assert result is not None
    assert result[1] == {"mock": "success"}
    scanner._collect_after_tk()
    import tkinter as tk
    assert tk._default_root is None
    print("MAC_TK_SMOKE_SUCCESS: data Tk root and managed Tcl variables cleaned")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    assert app is not None
    print("MAC_TK_TO_QT_SUCCESS")


if __name__ == "__main__":
    if "--tk-smoke" in sys.argv:
        run_tk_smoke()
    else:
        unittest.main(verbosity=2)
