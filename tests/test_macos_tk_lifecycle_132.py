"""Tk-to-Qt lifecycle regression, especially for macOS Tcl wrong-thread aborts.

Runs a real Tk instance and enters a real Qt loop after Tk is destroyed,
with synthetic backend events and no network or SQLite writes.
"""
import gc
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
import types
import unittest
import weakref
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
file = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.1.pyw"
loader = SourceFileLoader("v131_tk_cocoa_lifecycle_test", str(file))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

RealTk = tk.Tk
RealStringVar, RealDoubleVar = tk.StringVar, tk.DoubleVar


class FastTk(RealTk):
    """Pump native Tk events only until application requests quit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._should_quit = False

    def quit(self):
        self._should_quit = True
        return super().quit()

    def mainloop(self, n=0):
        stop_at = time.monotonic() + 8
        while not self._should_quit and time.monotonic() < stop_at:
            self.update()
            time.sleep(0.012)
        if not self._should_quit:
            raise TimeoutError("Tk lifecycle phase did not finish")


class FinishedBackend:
    def __init__(self):
        self.completed = threading.Event()

    def update_all(self, progress):
        progress(33.0, "测试本机 Tcl Tk 子阶段")
        progress(100.0, "已完成（本测试不访问真实市场）")
        self.completed.set()
        return {"synthetic": "complete"}


class TclQtLifecycleTests(unittest.TestCase):

    def test_three_real_tk_stages_collect_variables_on_main_thread(self):
        self.assertIs(threading.current_thread(), threading.main_thread())
        vars_weak = []
        roots_weak = []

        def tracked_string(*args, **kwargs):
            value = RealStringVar(*args, **kwargs)
            vars_weak.append(weakref.ref(value))
            return value

        def tracked_double(*args, **kwargs):
            value = RealDoubleVar(*args, **kwargs)
            vars_weak.append(weakref.ref(value))
            return value

        class ObservedTk(FastTk):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                roots_weak.append(weakref.ref(self))

        for round_id in range(3):
            backend = FinishedBackend()
            with (patch.object(tk, "Tk", ObservedTk),
                  patch.object(tk, "StringVar", tracked_string),
                  patch.object(tk, "DoubleVar", tracked_double)):
                phase = module.run_tk_data_phase(backend=backend)
            self.assertIsNotNone(phase)
            self.assertIs(phase[0], backend)
            self.assertTrue(backend.completed.is_set())
            self.assertTrue(all(ref() is None for ref in vars_weak),
                            f"Tk Variable survived stage {round_id} cleanup")
            self.assertTrue(all(ref() is None for ref in roots_weak),
                            f"Tk root survived stage {round_id} cleanup")
            self.assertIsNone(tk._default_root)
            del phase

        from PySide6.QtWidgets import QApplication, QWidget
        from PySide6.QtCore import QTimer
        app = QApplication.instance() or QApplication([])
        ui = QWidget()
        ui.setWindowTitle("Tk to Qt lifecycle test")
        ui.show()

        # Deliberately trigger Python collection from a Qt-side worker.
        # No Tk interpreter is allowed to be finalized in that thread.
        worker_results = []

        def threaded_collect():
            worker_results.append(gc.collect())

        worker = threading.Thread(target=threaded_collect)
        worker.start()
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(worker_results), 1)
        QTimer.singleShot(200, app.quit)
        self.assertEqual(app.exec(), 0)
        ui.close()
        del ui
        module._collect_finished_tk_on_main_thread()

    def test_tk_cleanup_refuses_non_main_thread(self):
        exceptions = []

        def misuse():
            try:
                module._collect_finished_tk_on_main_thread()
            except BaseException as exc:
                exceptions.append(exc)

        t = threading.Thread(target=misuse)
        t.start()
        t.join(timeout=2)
        self.assertEqual(len(exceptions), 1)
        self.assertIsInstance(exceptions[0], RuntimeError)

    def test_macos_font_does_not_require_segoe_ui(self):
        from PySide6.QtGui import QFont
        family = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"
        chosen = QFont(family, 10)
        self.assertEqual(chosen.family(), family)


if __name__ == "__main__":
    unittest.main(verbosity=2)
