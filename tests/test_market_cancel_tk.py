"""Real Tk GUI: closing a running market update must checkpoint and exit."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import os
import sys
import threading
import time
import tkinter as tk
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
source=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.9.pyw"
loader=SourceFileLoader("v129_tk_cancel_test",str(source))
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)

OriginalTk = tk.Tk

class CancelTkTests(unittest.TestCase):
    def test_second_stage_close_interrupts_without_force_killing_writer(self):
        cancelled=threading.Event()
        finished=threading.Event()
        started=threading.Event()
        received=[]
        class ClosingTk(OriginalTk):
            def after(self, milliseconds, func=None, *args):
                if func is not None and getattr(func, "__name__", "") == "start":
                    self._test_start = func
                return super().after(milliseconds, func, *args)

            def protocol(self, name=None, func=None):
                if name == "WM_DELETE_WINDOW" and func:
                    self._test_close = func
                return super().protocol(name,func)

            def quit(self):
                self._test_loop_quit = True
                return super().quit()

            def mainloop(self, n=0):
                # Exercise the actual Tk event handlers. Invoke scheduled
                # start and WM_DELETE deterministically, without relying on
                # Xvfb/Tcl timers or a window manager in CI.
                self._test_loop_quit = False
                assert hasattr(self, "_test_start"), "Tk autostart not installed"
                assert hasattr(self, "_test_close"), "Tk close protocol not installed"
                self._test_start()
                assert started.wait(2), "Tk worker never entered update_all"
                self._test_close()
                limit=time.monotonic()+3
                while not self._test_loop_quit and time.monotonic()<limit:
                    try:
                        self.update()
                    except tk.TclError:
                        break
                    time.sleep(.01)
        class Backend:
            def update_all(self, cb):
                started.set()
                cb(84.4,"更新 2026-10-27 · 1331/5215 · sh.603520")
                if not cancelled.wait(6):
                    raise RuntimeError("Tk cancel request was not delivered")
                finished.set()
                raise module.MarketUpdateCancelled("已保存断点")
            def cancel_update(self):
                received.append("stop requested")
                cancelled.set()
        start=time.monotonic()
        with patch.object(tk,"Tk",ClosingTk):
            result=module.run_tk_data_phase(backend=Backend(),autostart=True)
        self.assertIsNone(result)
        self.assertTrue(cancelled.is_set())
        self.assertTrue(finished.is_set())
        self.assertEqual(received,["stop requested"])
        self.assertLess(time.monotonic()-start,5)

if __name__=="__main__":
    unittest.main(verbosity=2)
