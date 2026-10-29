"""Tests for source selection without network calls or real market data."""
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime as RealDateTime
from pathlib import Path

import pandas as pd

sys.modules["baostock"] = types.ModuleType("baostock")
source_path = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.2.6.py"
spec = importlib.util.spec_from_file_location("scanner_under_test", source_path)
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)


class AfterClose(RealDateTime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 29, 20, 30, tzinfo=tz)


app.datetime = AfterClose


class FundSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.db = Path(self.temporary.name) / "market.db"
        self.backend = app.BaoStockBackend(self.db)
        self.backend.init_db()
        self.fail_em = False
        self.fail_ths = False

        def mock_request(endpoint, sector="", timeout=20):
            if endpoint == "em_rank":
                if self.fail_em:
                    raise TimeoutError("mock eastmoney outage")
                return pd.DataFrame([
                    {"名称": f"东方行业{i}", "5日主力净流入-净额": (6-i)*100000000}
                    for i in range(1, 6)])
            if endpoint == "ths_rank":
                if self.fail_ths:
                    raise TimeoutError("mock tonghuashun outage")
                return pd.DataFrame([
                    {"行业": f"同花行业{i}", "净额": (6-i)*1.5}
                    for i in range(1, 6)])
            if endpoint in ("em_summary", "em_members"):
                return pd.DataFrame({"代码": ["600001", "000002"]})
            if endpoint == "ths_members":
                return pd.DataFrame({"代码": ["688001", "300002"]})
            raise AssertionError(endpoint)

        self.backend._fund_request = mock_request

    def tearDown(self):
        self.temporary.cleanup()

    def test_eastmoney_healthy(self):
        self.backend.refresh_fund_top5(force=True)
        records, members = self.backend.load_fund_top5()
        self.assertEqual(len(records), 5)
        self.assertEqual(records[0]["source"], "东方财富")
        self.assertEqual(records[0]["net_yuan"], 500000000)
        self.assertEqual(members[1], {"600001", "000002"})

    def test_fallback_and_currency(self):
        self.fail_em = True
        self.backend.refresh_fund_top5(force=True)
        records, members = self.backend.load_fund_top5()
        self.assertEqual(records[0]["source"], "同花顺")
        self.assertEqual(records[0]["net_yuan"], 750000000)
        self.assertEqual(members[1], {"688001", "300002"})
        self.assertEqual(self.backend._fund_source_order()[0], "同花顺")

    def test_failed_sources_preserve_complete_snapshot(self):
        self.backend.refresh_fund_top5(force=True)
        old = self.backend.load_fund_top5()
        self.fail_em = True
        self.fail_ths = True
        with self.assertRaises(RuntimeError):
            self.backend.refresh_fund_top5(force=True)
        self.assertEqual(self.backend.load_fund_top5(), old)

    def test_migrates_legacy_snapshot(self):
        old_path = Path(self.temporary.name) / "legacy.db"
        with sqlite3.connect(old_path) as conn:
            conn.execute("""CREATE TABLE fund_top5_snapshot(
                rank INTEGER PRIMARY KEY, industry TEXT NOT NULL,
                net_yuan REAL NOT NULL, fetched_at TEXT NOT NULL)""")
            conn.execute("INSERT INTO fund_top5_snapshot VALUES (1,'旧行业',123,'2026-10-20 20:00:00')")
        legacy = app.BaoStockBackend(old_path)
        legacy.init_db()
        records, _ = legacy.load_fund_top5()
        self.assertEqual(records[0]["source"], "东方财富")
        self.assertEqual(records[0]["net_yuan"], 123)


if __name__ == "__main__":
    unittest.main()
