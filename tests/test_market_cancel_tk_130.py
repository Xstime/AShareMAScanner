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
source=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.3.0.pyw"
loader=SourceFileLoader("v130_tk_cancel_test",str(source))
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
            def mainloop(self, n=0):
                # Drive the genuine Tcl event queue deterministically under
                # CI/Xvfb, independent of any window manager that might
                # terminate Tk's native mainloop before autostart.
                self._test_loop_quit = False
                deadline = time.monotonic()+6
                while not self._test_loop_quit and time.monotonic()<deadline:
                    try:
                        self.update()
                    except tk.TclError:
                        break
                    time.sleep(.01)

            def quit(self):
                self._test_loop_quit = True
                return super().quit()

            def protocol(self, name=None, func=None):
                result=super().protocol(name,func)
                if name=="WM_DELETE_WINDOW" and func:
                    deadline=time.monotonic()+5
                    def click_when_running():
                        if started.is_set():
                            func()
                        elif time.monotonic()<deadline:
                            self.after(60,click_when_running)
                        else:
                            self.quit()
                    self.after(250,click_when_running)
                return result
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
