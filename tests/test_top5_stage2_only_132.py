"""TOP5 stage timing and visible text regressions; no real network or DB writes."""
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
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
file=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.3.2.pyw"
loader=SourceFileLoader("v132_stage2_top5_only",str(file))
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
NativeTk=tk.Tk


class FiniteTk(NativeTk):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.quit_seen=False
    def quit(self):
        self.quit_seen=True
        return super().quit()
    def mainloop(self,n=0):
        deadline=time.monotonic()+8
        while not self.quit_seen and time.monotonic()<deadline:
            self.update()
            time.sleep(.01)
        if not self.quit_seen:
            raise TimeoutError("Tk second stage did not reach a terminal state")


class StageBackend:
    def __init__(self,should_fail=False):
        self.order=[]
        self.should_fail=should_fail
        self.top5_forced=[]
    def update_all(self,progress):
        self.order.append("update")
        progress(84,"行情数据缓存准备完毕")
        return {"pretend_market_result":True}
    def refresh_fund_top5(self,force=False,progress=None):
        self.order.append("top5")
        self.top5_forced.append(force)
        if progress:
            progress("同花顺资金排名更新中")
        if self.should_fail:
            raise RuntimeError("synthetic timeout, previous cached snapshot preserved")
        return "TOP5 已写入本地缓存"


class TkTop5OnlyTests(unittest.TestCase):
    def test_second_gui_auto_refreshes_top5_after_market_update(self):
        backend=StageBackend()
        with patch.object(tk,"Tk",FiniteTk):
            result=module.run_tk_data_phase(backend=backend,autostart=True)
        self.assertIsNotNone(result)
        self.assertIs(result[0],backend)
        self.assertEqual(backend.order,["update","top5"])
        self.assertEqual(backend.top5_forced,[False])

    def test_failed_top5_is_non_fatal_to_stock_update_and_not_retried_by_qt(self):
        backend=StageBackend(should_fail=True)
        with patch.object(tk,"Tk",FiniteTk):
            result=module.run_tk_data_phase(backend=backend,autostart=True)
        self.assertIsNotNone(result)
        self.assertEqual(backend.order,["update","top5"])
        self.assertEqual(backend.top5_forced,[False])


class QtOnlyReadsSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_main_gui_no_refresh_button_or_py_side_title(self):
        from PySide6.QtWidgets import QPushButton
        window=module.ScannerWindow(demo=True)
        window.show()
        self.app.processEvents()
        try:
            self.assertEqual(window.windowTitle(),"A股 MA 扫描器 v1.3.2")
            self.assertFalse(hasattr(window,"fund_refresh"))
            self.assertFalse(hasattr(window,"start_fund_refresh"))
            self.assertFalse(hasattr(module,"FundWorker"))
            self.assertFalse(any(
                button.text()=="刷新"
                for button in window.findChildren(QPushButton)))
            self.assertTrue(window.fund_cards)
            self.assertTrue(all(card.text() for card in window.fund_cards))
            self.assertNotIn("PySide6",window.header_status.text())
            self.assertNotIn("4:3",window.header_status.text())
        finally:
            window.close()
            self.app.processEvents()

    def test_main_gui_on_ready_reads_cache_and_does_not_fetch_funds(self):
        from types import SimpleNamespace
        window=module.ScannerWindow(demo=True)
        events=[]
        saved=window.demo
        try:
            window.demo=False
            with patch.object(window,"_select_strategy",side_effect=lambda key: events.append("scan")),patch.object(
                window,"_load_funds_from_cache",side_effect=lambda: events.append("cache")
            ):
                window._on_update_ready(SimpleNamespace(scan_date="2026-11-02",warning=""))
            self.assertEqual(events,["scan","cache"])
            self.assertEqual(window.header_status.text(),"行情日期 2026-11-02")
        finally:
            window.demo=saved
            window.close()
            self.app.processEvents()


if __name__=="__main__":
    unittest.main(verbosity=2)
