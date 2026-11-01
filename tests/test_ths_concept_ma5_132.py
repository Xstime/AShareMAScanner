"""Standalone Tonghuashun concept-index MA5 integration tests, no public writes."""
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
path = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.2.pyw"
loader = SourceFileLoader("dev_v132_concept", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)


def bars_from_closes(prices, start="2026-10-20"):
    dates = pd.bdate_range(start, periods=len(prices)).strftime("%Y-%m-%d")
    return [{"trade_date": date, "close": float(price)}
            for date, price in zip(dates, prices)]


class ConceptSignalTests(unittest.TestCase):
    def setUp(self):
        self.bars = bars_from_closes([12, 11, 10, 9, 8, 9, 13])
        self.today = self.bars[-1]["trade_date"]
        self.previous = self.bars[-2]["trade_date"]

    def test_exact_three_day_ma5_down_then_up(self):
        self.assertEqual(app.concept_ma5_status(
            self.bars, self.today, self.previous), "今日触发")
        frame = app.concept_index_frame(self.bars)
        self.assertLessEqual(frame["MA5"].iloc[-2], frame["MA5"].iloc[-3])
        self.assertGreater(frame["MA5"].iloc[-1], frame["MA5"].iloc[-2])
        self.assertTrue((frame["close"] > 0).all())

    def test_stale_or_short_index_cannot_trigger(self):
        self.assertEqual(app.concept_ma5_status(
            self.bars, "2026-12-01", "2026-11-30"), "数据待更新")
        self.assertEqual(app.concept_ma5_status(
            self.bars[:6], self.previous), "数据不足")
        self.assertEqual(app.concept_ma5_status(
            self.bars, "2026-12-01", self.today), "昨日触发")

    def test_dirty_index_rows_sorted_and_invalid_close_ignored(self):
        rows = self.bars[::-1] + [
            {"trade_date": "2026-10-30", "close": "nan"},
            {"trade_date": "not-a-date", "close": -10},
            {"trade_date": self.today, "close": 13},
        ]
        frame = app.concept_index_frame(rows)
        self.assertEqual(len(frame), len(self.bars))
        self.assertEqual(frame["trade_date"].iloc[-1], self.today)
        self.assertAlmostEqual(frame["close"].iloc[-1], 13)

    def test_cache_persists_without_sqlite_or_requiring_data_migration(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "data" / "ths_concept_indices.json"
            old_db = Path(td) / "data" / "a_share_baostock_hfq.db"
            old_db.parent.mkdir()
            old_db.write_bytes(b"existing user database")
            service = app.ConceptIndexService(dest)
            snap = service.load()
            self.assertEqual(snap["indices"], {})
            snap["catalog"] = [{"name": "机器人概念", "code": "300816"}]
            snap["indices"]["300816"] = {"bars": self.bars, "attempted": self.today}
            service.save(snap)
            self.assertEqual(service.load()["indices"]["300816"]["bars"], self.bars)
            self.assertEqual(old_db.read_bytes(), b"existing user database")
            self.assertEqual(list(dest.parent.glob(".concept-indices-*")), [])

    def test_incremental_resume_and_catalog_network_failure_preserves_cache(self):
        with tempfile.TemporaryDirectory() as td:
            service = app.ConceptIndexService(Path(td) / "concepts.json")
            catalog = [{"name": "机器人概念", "code": "300816"},
                       {"name": "阿里巴巴概念", "code": "301558"}]
            seen = []
            calls = []
            def fetch(name, date):
                calls.append(name)
                return self.bars
            with patch.object(service, "_fetch_catalog", return_value=catalog), patch.object(
                    service, "_fetch_history", side_effect=fetch):
                service.run(self.today, self.previous,
                            lambda rows, status: seen.append((rows, status)),
                            threading.Event())
            self.assertEqual(calls, ["机器人概念", "阿里巴巴概念"])
            self.assertEqual(len(service.load()["indices"]), 2)
            self.assertEqual(sum(x["status"] == "今日触发"
                                 for x in seen[-1][0]), 2)
            # Subsequent run reuses both completed indices and requires zero
            # market calls even when updating its catalog.
            with patch.object(service, "_fetch_catalog", side_effect=RuntimeError(
                    "no concept network available")), patch.object(
                    service, "_fetch_history", side_effect=AssertionError("unwanted refetch")):
                service.run(self.today, self.previous,
                            lambda rows, status: None, threading.Event())
            self.assertEqual(len(service.load()["indices"]), 2)

    def test_partial_cancel_preserves_completed_progress(self):
        with tempfile.TemporaryDirectory() as td:
            service = app.ConceptIndexService(Path(td) / "index.json")
            stop = threading.Event()
            catalog = [{"name": f"概念{i}", "code": f"{300000+i:06d}"}
                       for i in range(5)]
            calls=[]
            def fetch(name, target):
                calls.append(name)
                stop.set()
                return self.bars
            with patch.object(service, "_fetch_catalog", return_value=catalog), patch.object(
                    service, "_fetch_history", side_effect=fetch):
                service.run(self.today, self.previous,
                            lambda *_: None, stop)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(service.load()["indices"]), 1)


class ConceptQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.qt = QApplication.instance() or QApplication([])

    def test_demo_industry_concept_toggle_does_not_connect_network(self):
        win = app.ScannerWindow(demo=True)
        win.show()
        self.qt.processEvents()
        try:
            self.assertEqual(win.sector_type.count(), 2)
            self.assertEqual(win.sector_type.itemText(0), "行业板块")
            self.assertEqual(win.sector_type.itemText(1), "概念指数")
            with patch.object(win.concept_service, "_fetch_catalog",
                              side_effect=AssertionError("demo accessed network")):
                win.sector_type.setCurrentIndex(1)
                self.qt.processEvents()
            self.assertTrue(win.concept_refresh.isVisible())
            self.assertEqual(win.sector_table.horizontalHeaderItem(0).text(),
                             "概念指数")
            self.assertTrue(win.sector_reset.isHidden())
            win.sector_type.setCurrentIndex(0)
            self.qt.processEvents()
            self.assertTrue(win.concept_refresh.isHidden())
            self.assertEqual(win.sector_table.horizontalHeaderItem(0).text(), "板块")
        finally:
            win.close()
            self.qt.processEvents()

    def test_concept_results_are_independent_of_stock_scan_strategy(self):
        win = app.ScannerWindow(demo=True)
        try:
            win.sector_type.setCurrentIndex(1)
            win.concept_rows = [{"name": "机器人概念", "code": "300816",
                                "close": 3500.0, "status": "今日触发",
                                "date": "2026-10-30"},
                               {"name": "人工智能", "code": "301558",
                                "close": 2300.0, "status": "未触发",
                                "date": "2026-10-30"}]
            win._render_concepts()
            self.assertEqual(win.sector_table.rowCount(), 2)
            self.assertEqual(win.sector_table.item(0, 2).text(), "今日触发")
            self.assertEqual(win.sector_table.item(1, 1).text(), "2300.00")
            win._select_strategy("breakout_ma5")
            self.assertEqual(win.sector_table.rowCount(), 2,
                             "Concept board must not depend on matched stocks")
        finally:
            win.close()
            self.qt.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
