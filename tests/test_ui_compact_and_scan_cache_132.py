"""UI screenshot annotations and strategy-switch cache regression (offline).

The test imports current v1.3.2 development source; no user DB or network.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
program = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.2.pyw"
loader = SourceFileLoader("v132_compact_ui", str(program))
spec = importlib.util.spec_from_loader(loader.name, loader)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


def seed_stocks(db, n=135, sessions=66):
    days = pd.date_range("2026-07-01", periods=sessions, freq="B").strftime("%Y-%m-%d")
    rows = []
    for i in range(n):
        code = f"sh.{600000+i:06d}"
        for j, day in enumerate(days):
            close = 9.0 + i * 0.025 + 0.01 * j + 0.1 * math.sin(j*.17+i)
            volume = 240.0 if j == len(days)-1 else 100.0
            rows.append((code, day, f"模拟样本{i}", close, volume, 1, 0, 3.6))
    with scanner.sqlite_connection(db.db_path) as c:
        c.executemany("""
            INSERT INTO daily
              (code,trade_date,name,close,volume,trade_status,is_st,turnover)
            VALUES (?,?,?,?,?,?,?,?)
        """, rows)
    return days


class CachePerformanceRegression(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.backend = scanner.BaoStockBackend(Path(folder.name) / "synthetic.sqlite")
        self.backend.init_db()
        self.days = seed_stocks(self.backend)

    def test_cached_strategy_switch_is_equivalent_and_reads_daily_once(self):
        date = self.days[-1]
        prev = self.days[-2]
        filters = scanner.RangeFilter(1.5, None, 3.0, None)
        calls = []
        original = self.backend._load_scan_data

        def spy(*args, **kwargs):
            calls.append(time.monotonic())
            return original(*args, **kwargs)

        with patch.object(self.backend, "_load_scan_data", side_effect=spy):
            t0 = time.perf_counter()
            first = self.backend.scan_strategy(
                "volume_turnover", date, False, prev, filters)
            cold = time.perf_counter() - t0
            t1 = time.perf_counter()
            second = self.backend.scan_strategy("ma5_turn_up", date, False, prev)
            warm = time.perf_counter() - t1
        self.assertEqual(len(calls), 1, "A strategy switch must not query all historical bars again")
        self.assertGreater(len(first), 0, "Synthetic data must trigger volume threshold")
        self.assertEqual(len(self.backend._scan_prepared_cache[2]), 135)
        # Numerical parity with cold backend on the same source SQLite database.
        cold_backend = scanner.BaoStockBackend(self.backend.db_path)
        replay = cold_backend.scan_strategy("ma5_turn_up", date, False, prev)
        pd.testing.assert_frame_equal(second.reset_index(drop=True),
                                      replay.reset_index(drop=True), check_dtype=False)
        print(f"Windows-compatible scan benchmark: cold={cold:.3f}s warm={warm:.3f}s "
              f"ratio={cold/max(warm,0.001):.2f}x", flush=True)

    def test_cancelled_prepare_is_not_cached(self):
        stop = threading.Event()
        stop.set()
        self.assertIsNone(self.backend._prepared_scan_session(self.days[-1], stop))
        self.assertIsNone(self.backend._scan_prepared_cache)

    def test_cache_invalidation_when_market_refreshes(self):
        date = self.days[-1]
        p1 = self.backend._prepared_scan_session(date)
        self.assertIsNotNone(p1)
        self.backend._scan_prepared_cache = None
        with scanner.sqlite_connection(self.backend.db_path) as c:
            c.execute("UPDATE daily SET close=99 WHERE code='sh.600000' AND trade_date=?",
                      (date,))
        p2 = self.backend._prepared_scan_session(date)
        first_stock = next(g for code,g in p2[1] if code=="sh.600000")
        self.assertEqual(float(first_stock.iloc[-1]["close"]),99)


class CompactWidgetRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_screenshot_markup_requests_implemented(self):
        win = scanner.ScannerWindow(demo=True)
        win.show()
        self.app.processEvents()
        try:
            self.assertNotIn("完整率", win.header_status.text())
            self.assertFalse(win.refresh_market.isVisible())
            self.assertTrue(win.update_button.isVisible())
            self.assertTrue(win.fund_source_label.isHidden())
            self.assertTrue(win.result_info.isHidden())
            self.assertTrue(win.chart_status.isHidden())
            self.assertFalse(win.statusBar().isVisible())
            self.assertEqual(win.sector_table.height(), 166)
            self.assertEqual(win.sector_table.horizontalHeader().height(), 25)
            self.assertEqual(win.sector_table.verticalHeader().defaultSectionSize(),22)
            self.assertIn("QComboBox::drop-down",win.styleSheet())
            self.assertIn("border: 0;",win.styleSheet())
            self.assertTrue(win.strategy_loading.isHidden())
            self.assertEqual(len(win.buttons), 8)
        finally:
            win.close()
            self.app.processEvents()

    def test_progress_bar_visible_during_actual_strategy_worker(self):
        win = scanner.ScannerWindow(demo=True)
        win.show()
        self.app.processEvents()

        class SlowBackend:
            def scan_strategy(self, *args, **kwargs):
                stop = kwargs.get("cancel_event") or args[-1]
                stop.wait(.12)
                return pd.DataFrame()
        try:
            win.demo = False
            win.backend = SlowBackend()
            win._select_strategy("ma5_turn_up")
            self.app.processEvents()
            self.assertTrue(win.strategy_loading.isVisible())
            self.assertEqual(win.strategy_loading.maximum(), 0)
            deadline = time.monotonic()+4
            while win.strategy_loading.isVisible() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.assertFalse(win.strategy_loading.isVisible())
        finally:
            if win._scan_cancel_event:
                win._scan_cancel_event.set()
            deadline=time.monotonic()+4
            while any(w.isRunning() for w in win.workers) and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.01)
            win.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
