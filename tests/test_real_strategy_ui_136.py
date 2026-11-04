"""Integration tests: real SQLite -> QThread -> Qt table and zero-hit UI.

Specifically regress "scan finishes but no result appears".  The downloaded
market-data UI is bypassed: no network, no BaoStock login, no user database.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest

import pandas as pd
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
PROGRAM = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.6.pyw"
loader = SourceFileLoader("v136_real_ui_pipeline", str(PROGRAM))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class RealDataToQTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = m.BaoStockBackend(Path(self.temp.name) / "stocks.sqlite")
        self.backend.init_db()
        self.backend.get_industry_map = lambda: {}
        self.days = pd.bdate_range("2026-07-01", periods=31).strftime("%Y-%m-%d").tolist()
        self.win = None
        self.errors = []

    def tearDown(self):
        if self.win is None:
            return
        deadline = time.monotonic() + 8
        while any(w.isRunning() for w in self.win.workers) and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        if self.win._scan_cancel_event is not None:
            self.win._scan_cancel_event.set()
        self.win.close()
        self.app.processEvents()
        self.assertEqual(self.errors, [], "Real Qt worker raised an exception")

    def seed(self, event="today"):
        dates = self.days
        rows = []
        for code in ("sh.600111", "sh.600222"):
            for index, date in enumerate(dates):
                close = 10.0
                volume = 100.0
                if code == "sh.600111":
                    if event == "today" and index == len(dates) - 1:
                        close, volume = 12.0, 160.0
                    elif event == "yesterday":
                        if index >= len(dates) - 2:
                            close = 12.0
                        if index == len(dates) - 2:
                            volume = 160.0
                rows.append((code, date, "测试样本", close,
                             volume, 1, 0, 3.5))
        with m.sqlite_connection(self.backend.db_path) as conn:
            conn.executemany("""
                INSERT INTO daily
                (code,trade_date,name,close,volume,trade_status,is_st,turnover)
                VALUES (?,?,?,?,?,?,?,?)
            """, rows)

    def open(self, target=None, completeness=100.0):
        target = target or self.days[-1]
        result = m.UpdateResult(
            scan_date=target, previous_trade_date=self.days[-2],
            completeness=completeness, expected=2, saved=2,
            failed=0, today_pending=False)
        self.win = m.ScannerWindow(
            demo=False, prepared_backend=self.backend, prepared_result=result)
        self.win._show_error = lambda title, detail: self.errors.append((title, detail))
        self.win.show()
        self.settle()

    def settle(self):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            self.app.processEvents()
            if self.win.strategy_loading.isHidden():
                self.app.processEvents()
                break
            time.sleep(.01)
        self.assertTrue(self.win.strategy_loading.isHidden(),
                        "QThread scan must finish and hide spinner")
        self.app.processEvents()
        self.assertEqual(self.errors, [])

    def test_real_stock_result_renders_after_async_switch(self):
        self.seed("today")
        self.open()
        for strategy in ("breakout_ma5", "breakout_ma10", "breakout_ma20",
                         "ma5_cross_ma10", "ma5_turn_up",
                         "ma_convergence_up", "volume_turnover"):
            with self.subTest(strategy=strategy):
                self.win._select_strategy(strategy)
                self.settle()
                self.assertEqual(len(self.win.frame), 1)
                self.assertEqual(len(self.win.filtered), 1)
                self.assertEqual(self.win.table.rowCount(), 1)
                self.assertEqual(self.win.table.item(0, 0).text(), "600111")
                self.assertTrue(self.win.scan_notice.isHidden())
                self.assertIn("命中 1 只", self.win.hit_count.text())

    def test_no_trigger_explained_not_blank(self):
        self.seed("yesterday")
        self.open()
        self.win._select_strategy("breakout_ma5")
        self.settle()
        self.assertTrue(self.win.frame.empty)
        self.assertEqual(self.win.table.rowCount(), 0)
        self.assertTrue(self.win.scan_notice.isVisible())
        self.assertIn("没有新触发", self.win.scan_notice.text())
        self.assertIn("上一交易日", self.win.scan_notice.text())
        # The optional previous-day checkbox must NOT silently change default.
        self.assertFalse(self.win.show_previous.isChecked())
        self.win.show_previous.setChecked(True)
        self.settle()
        self.assertEqual(len(self.win.frame), 1)
        self.assertEqual(self.win.table.rowCount(), 1)
        self.assertEqual(self.win.table.item(0, 3).text(), self.days[-2])

    def test_empty_due_to_filters_is_distinct_from_no_signal(self):
        self.seed("today")
        self.open()
        self.win._select_strategy("breakout_ma5")
        self.settle()
        self.assertEqual(len(self.win.frame), 1)
        self.win.query.setText("不存在股票")
        self.app.processEvents()
        self.assertEqual(self.win.table.rowCount(), 0)
        self.assertEqual(len(self.win.frame), 1)
        self.assertTrue(self.win.scan_notice.isVisible())
        self.assertIn("计算出 1 只", self.win.scan_notice.text())
        self.win.clear_filters()
        self.app.processEvents()
        self.assertEqual(self.win.table.rowCount(), 1)
        self.assertTrue(self.win.scan_notice.isHidden())

    def test_stale_target_date_is_not_mistaken_for_zero_signal(self):
        self.seed("today")
        self.open(target="2026-12-31", completeness=50.0)
        self.win._select_strategy("breakout_ma5")
        self.settle()
        self.assertEqual(self.win.table.rowCount(), 0)
        self.assertTrue(self.win.scan_notice.isVisible())
        self.assertIn("没有找到任何有效的个股日线", self.win.scan_notice.text())
        self.assertIn(self.days[-1], self.win.scan_notice.text())
        self.assertIn("50.00%", self.win.scan_notice.text())

    def test_no_valid_data_reports_missing_market_cache(self):
        self.open()
        self.win._select_strategy("breakout_ma5")
        self.settle()
        self.assertTrue(self.win.scan_notice.isVisible())
        self.assertIn("缓存没有足够的有效日线", self.win.scan_notice.text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
