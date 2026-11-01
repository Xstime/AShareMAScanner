"""Low-position first-limit-up board strategy tests (offline and reproducible)."""
import importlib.util
from importlib.machinery import SourceFileLoader
import math
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
app = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.0.pyw"
loader = SourceFileLoader("low_first_board_under_test", str(app))
spec = importlib.util.spec_from_loader(loader.name, loader)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


def sample(code="sh.600001", offset=4, volume_ratio=2.3,
           low=True, old_board=False, st=False, count=55):
    """Synthetic CLOSE data, no claim about actual Shanghai/Shenzhen stocks."""
    dates = pd.date_range("2026-08-03", periods=count, freq="B").strftime("%Y-%m-%d").tolist()
    event_idx = count - 1 - offset
    prices = [10.7 + 0.48 * math.sin(i / 3) for i in range(count)]
    if event_idx < 31:
        raise ValueError("event too early for test fixture")
    prices[event_idx - 1] = 10.13 if low else 11.3
    rate = .2 if code.startswith(("sz.300", "sz.301", "sh.688")) else .1
    prices[event_idx] = prices[event_idx - 1] * (1.0 + rate)
    for k in range(event_idx + 1, count):
        prices[k] = prices[k - 1] * 1.005
    if old_board:
        i = event_idx - 8
        prices[i] = prices[i - 1] * (1 + rate)
    records = []
    for i, date in enumerate(dates):
        records.append({
            "code": code,
            "trade_date": date,
            "name": "ST测试" if st else "测试样本",
            "close": prices[i], "volume": 100 * (
                volume_ratio if i == event_idx else 1.0),
            "trade_status": 1, "is_st": int(st), "turnover": 3.5,
        })
    return pd.DataFrame(records), dates, event_idx


class LowFirstBoardMathTests(unittest.TestCase):
    def metrics(self, **kwargs):
        raw, dates, event_idx = sample(**kwargs)
        prepared = scanner.BaoStockBackend._prepare_group(raw)
        return scanner.low_first_board_metrics(
            prepared, len(prepared) - 1, str(raw.iloc[0]["code"]), dates)

    def test_mainboard_first_limit_up_with_volume_and_low_position(self):
        result = self.metrics()
        self.assertIsNotNone(result)
        self.assertEqual(result["距今交易日"], 4)
        self.assertAlmostEqual(result["首板涨幅%"], 10, places=5)
        self.assertAlmostEqual(result["首板放量倍数"], 2.3, places=5)
        self.assertLessEqual(result["首板前30日位置%"], 35)

    def test_chinext_and_star_20_percent_are_not_confused_with_mainboard(self):
        self.assertIsNotNone(self.metrics(code="sz.300125"))
        self.assertIsNotNone(self.metrics(code="sh.688333"))
        self.assertTrue(scanner.is_approx_limit_up(10, 12, "sz.300123"))
        self.assertFalse(scanner.is_approx_limit_up(10, 11, "sz.300123"))
        self.assertFalse(scanner.is_approx_limit_up(10, 12, "sh.600123"))

    def test_three_to_five_day_window_is_market_calendar_based(self):
        for delta in (3, 4, 5):
            with self.subTest(delta=delta):
                self.assertIsNotNone(self.metrics(offset=delta))
        for delta in (2, 6):
            with self.subTest(delta=delta):
                self.assertIsNone(self.metrics(offset=delta))

    def test_previous_20_day_limit_up_not_first_board(self):
        self.assertIsNone(self.metrics(old_board=True))

    def test_no_false_positive_from_ordinary_growth(self):
        self.assertFalse(scanner.is_approx_limit_up(10, 10.6, "sh.600001"))
        self.assertFalse(scanner.is_approx_limit_up(10, 13, "sh.600001"))
        self.assertFalse(scanner.is_approx_limit_up(10, 0, "sh.600001"))

    def test_not_low_or_not_volume_or_st_rejected(self):
        self.assertIsNone(self.metrics(low=False))
        self.assertIsNone(self.metrics(volume_ratio=1.49))
        self.assertIsNone(self.metrics(st=True))

    def test_missing_market_day_does_not_reindex_suspension(self):
        raw, dates, event_idx = sample(offset=4)
        raw = raw[raw.trade_date != dates[event_idx]]
        prepared = scanner.BaoStockBackend._prepare_group(raw)
        self.assertIsNone(scanner.low_first_board_metrics(
            prepared, len(prepared)-1, "sh.600001", dates))

    def test_insufficient_history_and_invalid_volumes(self):
        raw, dates, idx = sample()
        prepared = scanner.BaoStockBackend._prepare_group(raw)
        self.assertIsNone(scanner.low_first_board_metrics(
            prepared, 22, "sh.600001", dates))
        raw.loc[idx, "volume"] = 100
        prepared = scanner.BaoStockBackend._prepare_group(raw)
        self.assertIsNone(scanner.low_first_board_metrics(
            prepared, len(prepared)-1, "sh.600001", dates))


class StrategyBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = scanner.BaoStockBackend(Path(self.tmp.name) / "stock.db")
        self.backend.init_db()
        self.raw, self.dates, _ = sample()
        with scanner.sqlite_connection(self.backend.db_path) as c:
            c.executemany("""
            INSERT INTO daily (code,trade_date,name,close,volume,trade_status,is_st,turnover)
            VALUES (?,?,?,?,?,?,?,?)
            """, [tuple(row[col] for col in
                         ("code", "trade_date", "name", "close", "volume",
                          "trade_status", "is_st", "turnover"))
                  for _, row in self.raw.iterrows()])
        self.backend.get_industry_map = lambda: {"sh.600001": "测试板块"}

    def test_stock_scan_uses_current_trigger_date_and_actual_board_date(self):
        target = self.dates[-1]
        result = self.backend.scan_strategy(
            "low_first_board", target, False, self.dates[-2])
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["触发日"], target)
        self.assertEqual(row["首板日期"], self.dates[-5])
        self.assertEqual(row["距今交易日"], 4)
        self.assertEqual(row["板块信号"], "仅个股适用")

    def test_stock_history_backfill_and_no_database_migration(self):
        history = self.backend.get_signal_history("sh.600001", self.dates[-1])
        ours = history[history.strategy == "low_first_board"]
        self.assertGreaterEqual(len(ours), 1)
        with scanner.sqlite_connection(self.backend.db_path) as c:
            colnames = [row[1] for row in c.execute("PRAGMA table_info(daily)")]
        self.assertNotIn("high", colnames)
        self.assertNotIn("low", colnames)


class QtIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_new_strategy_tab_and_column_headers(self):
        win = scanner.ScannerWindow(demo=True)
        try:
            self.assertEqual(len(scanner.STRATEGIES), 8)
            self.assertIn("low_first_board", win.buttons)
            win._select_strategy("low_first_board")
            headers = [win.table.horizontalHeaderItem(i).text()
                       for i in range(win.table.columnCount())]
            for col in ("首板日期", "距今交易日", "首板放量倍数", "首板前30日位置%"):
                self.assertIn(col, headers)
            self.assertGreater(win.table.rowCount(), 0)
        finally:
            win.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
