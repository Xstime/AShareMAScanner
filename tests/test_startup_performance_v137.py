"""Offline performance regressions for the v1.3.7 startup updater.

All network calls are mocked. Uses temporary SQLite files only.
"""
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SOURCE = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.7.pyw"
loader = SourceFileLoader("startup_performance_v137", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class RetryPolicyTests(unittest.TestCase):
    def test_exponential_backoff_is_bounded(self):
        self.assertEqual(m.retry_delay_hours(1), 6)
        self.assertEqual(m.retry_delay_hours(2), 12)
        self.assertEqual(m.retry_delay_hours(3), 24)
        self.assertEqual(m.retry_delay_hours(4), 48)
        self.assertEqual(m.retry_delay_hours(6), 168)
        self.assertEqual(m.retry_delay_hours(20), 168)

    def test_due_check_uses_last_failure_time_and_attempt_count(self):
        now = datetime(2026, 11, 6, 12, 0, 0)
        self.assertFalse(m.retry_is_due("2026-11-06 07:00:00", 1, now=now))
        self.assertTrue(m.retry_is_due("2026-11-06 05:00:00", 1, now=now))
        self.assertFalse(m.retry_is_due("2026-11-05 23:00:00", 2, now=now))
        self.assertTrue(m.retry_is_due("2026-11-05 23:00:00", 2, now=now))
        self.assertTrue(m.retry_is_due("invalid", 5, now=now))

    def test_akshare_adapter_is_not_wrapped_in_redundant_three_attempt_retry(self):
        backend = object.__new__(m.AKShareBackend)
        calls = []
        def fail():
            calls.append(1)
            raise RuntimeError("upstream unavailable")
        with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
            backend.run_query(fail)
        self.assertEqual(calls, [1])


class PersistentRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "startup.sqlite"
        self.backend = m.AKShareBackend(self.path)
        self.backend.init_db()

    def test_failed_history_queue_is_skipped_until_backoff_expires(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with m.sqlite_connection(self.path) as db:
            db.execute(
                "INSERT INTO init_queue(code,name,start_date,end_date,reason,retry_count,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("sh.600001", "测试", "2026-09-01", "2026-11-05", "timeout", 1, now),
            )
        calls = []
        self.backend.query_stock_history = lambda *a, **k: (
            calls.append(a) or (_ for _ in ()).throw(AssertionError("must be deferred")))
        messages = []
        result = self.backend.retry_init_queue(lambda p, t: messages.append(t), 12, 20)
        self.assertEqual(result, {"retried": 0, "deferred": 1})
        self.assertEqual(calls, [])
        self.assertIn("跳过重复网络请求", messages[-1])

    def test_due_history_failure_is_attempted_once_and_its_retry_count_increases(self):
        old = (datetime.now() - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        with m.sqlite_connection(self.path) as db:
            db.execute(
                "INSERT INTO init_queue(code,name,start_date,end_date,reason,retry_count,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("sh.600002", "测试", "2026-09-01", "2026-11-05", "timeout", 1, old),
            )
        calls = []
        def fail(*args, **kwargs):
            calls.append(args)
            raise RuntimeError("still offline")
        self.backend.query_stock_history = fail
        self.backend.retry_init_queue(lambda *_: None, 12, 20)
        self.assertEqual(len(calls), 1)
        with m.sqlite_connection(self.path) as db:
            count, updated = db.execute(
                "SELECT retry_count,updated_at FROM init_queue WHERE code='sh.600002'"
            ).fetchone()
        self.assertEqual(count, 2)
        self.assertGreaterEqual(updated, datetime.now().strftime("%Y-%m-%d %H:%M:%S")[:16])

    def test_queued_history_failure_is_not_immediately_reinitialized(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with m.sqlite_connection(self.path) as db:
            db.execute(
                "INSERT INTO init_queue(code,name,start_date,end_date,reason,retry_count,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("sh.600003", "测试", "2026-09-01", "2026-11-05", "timeout", 1, now),
            )
        self.backend.recent_n_trade_dates = lambda *_: (
            (_ for _ in ()).throw(AssertionError("calendar should not be fetched"))
        )
        self.backend.query_stock_history = lambda *a, **k: (
            (_ for _ in ()).throw(AssertionError("history should not be fetched"))
        )
        messages = []
        stocks = pd.DataFrame([{"code": "sh.600003", "name": "测试", "trade_status": 1}])
        self.backend.initialize_missing_histories(stocks, "2026-11-05",
                                                   lambda p, t: messages.append(t), 20, 66)
        self.assertIn("退避间隔等待重试", messages[-1])

    def test_partial_trade_date_skips_recently_failed_stocks_without_network(self):
        trade_date = "2026-11-05"
        universe = pd.DataFrame([{
            "code": "sh.600004", "name": "测试", "trade_status": 1
        }])
        self.backend.persist_day_universe(trade_date, universe)
        with m.sqlite_connection(self.path) as db:
            self.backend.queue_day_failure(db, "sh.600004", trade_date, "测试", "timeout")
        self.backend.fetch_exact_day_for_stock = lambda *a: (
            (_ for _ in ()).throw(AssertionError("must not fetch during cooldown"))
        )
        messages = []
        status = self.backend.process_trade_date(
            trade_date, lambda p, t: messages.append(t), 66, 80)
        self.assertEqual(status["status"], "partial")
        self.assertEqual(status["failed"], 1)
        self.assertIn("退避等待", messages[-1])


class TurnoverBackfillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "turnover.sqlite"

    def test_upgrade_bootstraps_cooldown_for_existing_missing_turnover(self):
        # Emulate the existing v1.3.7 DB before the new retry-state table exists.
        import sqlite3
        db = sqlite3.connect(self.path)
        db.execute("""
            CREATE TABLE daily (
                code TEXT NOT NULL, trade_date TEXT NOT NULL, name TEXT,
                close REAL, volume REAL, trade_status INTEGER, is_st INTEGER,
                PRIMARY KEY(code,trade_date))
        """)
        db.executemany(
            "INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st) "
            "VALUES(?,?,?,?,?,?,?)",
            [("sh.600005", f"2026-11-0{day}", "测试", 10.0, 1000, 1, 0)
             for day in range(2, 6)],
        )
        db.commit()
        db.close()

        backend = m.AKShareBackend(self.path)
        backend.init_db()
        with m.sqlite_connection(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0], 4)
            count, retry_at = conn.execute(
                "SELECT retry_count,next_retry_at FROM turnover_retry_state WHERE code='sh.600005'"
            ).fetchone()
        self.assertEqual(count, 1)
        self.assertGreater(retry_at, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        backend.query_stock_history = lambda *a, **k: (
            (_ for _ in ()).throw(AssertionError("upgrade should not re-fetch legacy missing rows"))
        )
        warning = backend.backfill_turnover("2026-11-05", lambda *_: None)
        self.assertIn("退避等待重试", warning)

    def test_failed_turnover_backfill_is_not_repeated_on_every_start(self):
        backend = m.AKShareBackend(self.path)
        backend.init_db()
        with m.sqlite_connection(self.path) as conn:
            conn.execute(
                "INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) "
                "VALUES(?,?,?,?,?,?,?,NULL)",
                ("sh.600006", "2026-11-05", "测试", 10.0, 1000, 1, 0),
            )
        calls = []
        def fail(*args, **kwargs):
            calls.append(args)
            raise RuntimeError("no turnover provider")
        backend.query_stock_history = fail
        backend.backfill_turnover("2026-11-05", lambda *_: None)
        self.assertEqual(len(calls), 1)
        backend.backfill_turnover("2026-11-05", lambda *_: None)
        self.assertEqual(len(calls), 1)

    def test_due_turnover_retry_can_fill_cache_and_clear_state(self):
        backend = m.AKShareBackend(self.path)
        backend.init_db()
        with m.sqlite_connection(self.path) as conn:
            conn.execute(
                "INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) "
                "VALUES(?,?,?,?,?,?,?,NULL)",
                ("sh.600007", "2026-11-05", "测试", 10.0, 1000, 1, 0),
            )
            conn.execute(
                "INSERT INTO turnover_retry_state(code,retry_count,updated_at,next_retry_at) "
                "VALUES(?,?,?,?)",
                ("sh.600007", 1, "2026-11-04 10:00:00", "2000-01-01 00:00:00"),
            )
        calls = []
        backend.query_stock_history = lambda *a, **k: (
            calls.append((a, k)) or pd.DataFrame([{
                "date": "2026-11-05", "code": "sh.600007", "close": 10.0,
                "volume": 1000.0, "tradestatus": 1, "isST": 0, "turn": 2.5,
            }])
        )
        backend.backfill_turnover("2026-11-05", lambda *_: None)
        self.assertEqual(len(calls), 1)
        with m.sqlite_connection(self.path) as conn:
            turnover = conn.execute(
                "SELECT turnover FROM daily WHERE code='sh.600007'"
            ).fetchone()[0]
            state = conn.execute(
                "SELECT COUNT(*) FROM turnover_retry_state WHERE code='sh.600007'"
            ).fetchone()[0]
        self.assertEqual(turnover, 2.5)
        self.assertEqual(state, 0)

    def test_turnover_mode_tries_sources_until_a_valid_turnover_is_found(self):
        backend = m.AKShareBackend(self.path)
        backend.init_db()
        quotes = backend._quotes
        quotes._preferred["sh.600008"] = "tencent"
        attempts = []
        def fake_download(code, first, last, source):
            attempts.append(source)
            return pd.DataFrame([{
                "date": last, "code": code, "close": 10.0, "volume": 1000.0,
                "tradestatus": 1, "isST": 0,
                "turn": 2.0 if source == "sina" else float("nan"),
            }], columns=quotes.FIELDS)
        quotes._download = fake_download
        result = quotes.history("sh.600008", "2026-11-05", "2026-11-05",
                                require_turnover=True)
        self.assertEqual(attempts, ["tencent", "eastmoney", "sina"])
        self.assertEqual(result.iloc[0]["turn"], 2.0)


if __name__ == "__main__":
    unittest.main()
