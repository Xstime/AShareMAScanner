"""Live Qt + actual local SQLite + real ScanWorker/ChartWorker end-to-end audit.

No BaoStock or Tonghuashun outbound HTTP; synthetic fixtures and mock fund refresh.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import sqlite3
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import pandas as pd
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication,QDialog,QTableWidget
sys.modules.setdefault("baostock",types.ModuleType("baostock"))
filename=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("v128_real_sqlite_gui",str(filename))
spec=importlib.util.spec_from_loader(loader.name,loader)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class ActualBackendGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.b=mod.BaoStockBackend(Path(self.tmp.name)/"test.db")
        self.b.init_db()
        days=pd.date_range("2026-08-17",periods=35,freq="B").strftime("%Y-%m-%d").tolist()
        self.end=days[-1]
        self.prev=days[-2]
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) VALUES(?,?,?,?,?,?,?,?)",
                         [("sh.600000",d,"真实GUI银行",10+i*.2,40000 if i==34 else 10000,1,0,4.0)
                          for i,d in enumerate(days)])
            c.execute("INSERT INTO industry_cache(code,name,industry) VALUES(?,?,?)",
                      ("sh.600000","真实GUI银行","银行"))
        result=mod.UpdateResult(self.end,self.prev,100,1,1,0,False,"")
        self.fund_patch=patch.object(self.b,"refresh_fund_top5",return_value="使用测试缓存")
        self.fund_patch.start()
        self.win=mod.ScannerWindow(demo=False,prepared_backend=self.b,prepared_result=result)
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.pump(lambda:not any(w.isRunning() for w in self.win.workers), timeout=10)
        self.win.close()
        self.app.processEvents()
        self.fund_patch.stop()
        self.tmp.cleanup()

    def pump(self,condition,timeout=8):
        limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            self.app.processEvents()
            if condition():return True
            time.sleep(.015)
        self.app.processEvents()
        return bool(condition())

    def test_01_main_window_runs_actual_scan_worker_without_network(self):
        self.win._select_strategy("volume_turnover")
        self.assertTrue(self.pump(lambda:self.win.table.rowCount()==1))
        self.assertEqual(self.win.table.item(0,0).text(),"600000")
        self.assertEqual(self.win.stock_name.text(),"真实GUI银行")
        self.assertEqual(self.win.sector_table.rowCount(),1)
        self.assertTrue(self.pump(lambda:not self.win.chart.data.empty))
        self.assertGreater(len(self.win.chart.data),0)
        self.assertIn("MA20",self.win.chart.data.columns)

    def test_02_sector_filter_and_range_stay_in_sync_on_actual_scan(self):
        self.win._select_strategy("volume_turnover")
        self.assertTrue(self.pump(lambda:self.win.table.rowCount()==1))
        self.win.change_min.setText("100")
        self.win.apply_filters()
        self.assertEqual(self.win.table.rowCount(),0)
        self.win.change_min.setText("1")
        self.win.apply_filters()
        self.assertEqual(self.win.table.rowCount(),1)
        self.win.sector_table.selectRow(0)
        self.win._on_sector_selected()
        self.assertEqual(self.win.sector_filter,"银行")
        self.assertEqual(self.win.table.rowCount(),1)
        self.win.clear_filters()
        self.assertIsNone(self.win.sector_filter)

    def test_03_real_signal_history_dialog_and_worker(self):
        self.win._select_strategy("volume_turnover")
        self.assertTrue(self.pump(lambda:self.win.table.rowCount()==1))
        self.win._history_dialog()
        dialogs=[d for d in self.win.findChildren(QDialog) if d.windowTitle().endswith("信号历史")]
        self.assertEqual(len(dialogs),1)
        dialog=dialogs[0]
        table=dialog.findChild(QTableWidget)
        self.assertIsNotNone(table)
        self.assertEqual(table.columnCount(),8)
        self.assertTrue(self.pump(lambda:table.rowCount()>0))
        self.assertEqual(table.item(0,0).text(),self.end)
        dialog.close()

    def test_04_scans_can_cancel_obsolete_work_without_stale_results(self):
        self.win._select_strategy("volume_turnover")
        self.win._select_strategy("ma5_turn_up")
        self.win._select_strategy("volume_turnover")
        self.assertTrue(self.pump(lambda:self.win.table.rowCount()==1))
        self.assertEqual(self.win.current_key,"volume_turnover")
        self.assertEqual(self.win.table.item(0,0).text(),"600000")
        self.assertTrue(self.pump(lambda:not any(isinstance(w,mod.ScanWorker) and w.isRunning()
                                              for w in self.win.workers)))

    def test_05_deselecting_last_stock_clears_stale_detail_panel(self):
        self.win._select_strategy("volume_turnover")
        self.assertTrue(self.pump(lambda:self.win.table.rowCount()==1))
        self.assertIsNotNone(self.win.selected_stock)
        self.win.table.clearSelection()
        self.app.processEvents()
        self.assertIsNone(self.win.selected_stock)
        self.assertEqual(self.win.stock_name.text(),"请选择股票")

    def test_06_history_window_is_disposed_after_close(self):
        from PySide6.QtCore import Qt
        self.win._select_strategy("volume_turnover")
        self.assertTrue(self.pump(lambda:self.win.table.rowCount()==1))
        self.win._history_dialog()
        dialogs=[d for d in self.win.findChildren(QDialog) if d.windowTitle().endswith("信号历史")]
        self.assertEqual(len(dialogs),1)
        self.assertTrue(dialogs[0].testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose),
            "Frequent history queries must not accumulate closed QDialogs and tables")
        self.assertTrue(self.pump(lambda:not any(isinstance(w,mod.HistoryWorker) and w.isRunning()
                                               for w in self.win.workers)))
        dialogs[0].close()

    def test_07_morning_top5_without_cache_is_a_normal_status_not_error(self):
        from datetime import datetime as StdDateTime
        class TradingMorning(StdDateTime):
            @classmethod
            def now(cls,tz=None):
                return cls(2026,10,30,10,0,tzinfo=tz)
        self.assertTrue(self.pump(lambda:not any(isinstance(w,mod.FundWorker) and w.isRunning()
                                               for w in self.win.workers)))
        self.win.funds=[]
        before=self.b.refresh_fund_top5.call_count
        with patch.object(mod,"datetime",TradingMorning):
            self.win.start_fund_refresh()
        self.assertIn("18:00",self.win.fund_source_label.text())
        self.assertEqual(self.b.refresh_fund_top5.call_count,before)

if __name__=="__main__":unittest.main(verbosity=2)
