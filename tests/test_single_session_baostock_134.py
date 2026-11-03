"""v1.3.4 BaoStock single-session / sequential-only regressions.

No network requests: real SQLite and deterministic fake stock bars.
The former 100+ stock parallel threshold is deliberately exceeded.
"""
import ast
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
PROGRAM = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.4.pyw"
loader = SourceFileLoader("v134_single_session", str(PROGRAM))
spec = importlib.util.spec_from_loader(loader.name, loader)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


class SingleSessionBaoStockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = scanner.BaoStockBackend(Path(self.tmp.name) / "market.db")
        self.backend.init_db()
        self.date = "2026-10-27"
        self.universe = pd.DataFrame([
            dict(code=f"sh.{600000 + i:06d}", name=f"测试{i}", trade_status=1)
            for i in range(125)
        ])
        self.backend.persist_day_universe(self.date, self.universe)

    def tearDown(self):
        if self.backend._instance_lock_file is not None:
            self.backend._instance_lock_file.close()

    def test_no_pool_or_worker_login_left_in_source(self):
        source = PROGRAM.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertEqual(scanner.APP_VERSION, "1.3.4")
        self.assertNotIn("multiprocessing", source)
        self.assertNotIn("_day_pool_fetch", source)
        self.assertNotIn("ASHARE_MA_FETCH_WORKERS", source)
        self.assertNotIn("DAILY_PARALLEL_", source)
        self.assertFalse(any(isinstance(n, ast.Import) and any(
            x.name == "multiprocessing" for x in n.names) for n in ast.walk(tree)))
        self.assertNotIn("Pool(", source)
        self.assertIn("BATCH_PAUSE", source)

    def test_125_stock_daily_downloads_sequentially_and_skips_cached(self):
        seen = []
        main_thread = threading.get_ident()

        def fetch(code, name, day):
            self.assertEqual(threading.get_ident(), main_thread)
            seen.append(code)
            return [(code, day, name, 10.25, 1000, 1, 0, 3.2)]

        self.backend.fetch_exact_day_for_stock = fetch
        with patch.dict(os.environ, {"ASHARE_MA_FETCH_WORKERS": "8"}), patch.object(
            scanner, "BATCH_PAUSE", 0
        ):
            state = self.backend.process_trade_date(self.date, lambda *_: None, 80, 94)
            self.assertEqual((state["saved"], state["expected"], state["failed"]), (125, 125, 0))
            self.assertEqual(seen, self.universe["code"].tolist())
            second = self.backend.process_trade_date(self.date, lambda *_: None, 80, 94)
        self.assertEqual((second["saved"], second["failed"]), (125, 0))
        self.assertEqual(len(seen), 125, "A fully cached trading day must never refetch stocks")
        with scanner.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0], 125)

    def test_125_stock_history_initialization_is_sequential_and_resumable(self):
        days = pd.bdate_range(end=self.date, periods=45).strftime("%Y-%m-%d").tolist()
        self.backend.recent_n_trade_dates = lambda end, n: days[-n:]
        seen = []
        main_thread = threading.get_ident()

        def query(code, start, end):
            self.assertEqual(threading.get_ident(), main_thread)
            seen.append(code)
            return pd.DataFrame([
                dict(date=d, code=code, close="10.25", volume="1000",
                     tradestatus="1", isST="0", turn="3.2")
                for d in days
            ])

        self.backend.query_stock_history = query
        with patch.dict(os.environ, {"ASHARE_MA_FETCH_WORKERS": "8"}), patch.object(
            scanner, "BATCH_PAUSE", 0
        ):
            self.backend.initialize_missing_histories(
                self.universe, self.date, lambda *_: None, 20, 66)
            self.backend.initialize_missing_histories(
                self.universe, self.date, lambda *_: None, 20, 66)
        self.assertEqual(seen, self.universe["code"].tolist())
        with scanner.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0], 125*45)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM stock_state WHERE history_ready=1"
            ).fetchone()[0], 125)


if __name__ == "__main__":
    unittest.main(verbosity=2)
