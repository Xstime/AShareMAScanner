from __future__ import annotations

import json
import os
import sqlite3
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ashare_server.config import Settings
import ashare_server.api as api_module
from ashare_server.db import MarketDB, connect, retry_delay_hours, retry_is_due
from ashare_server.provider import (
    BaoStockBlacklistError, BaoStockProvider, HISTORY_FIELDS,
)
from ashare_server.snapshot import SnapshotPublisher
from ashare_server.updater import MarketUpdater


class FakeResult:
    def __init__(self, fields, rows, error_code="0", error_msg="success"):
        self.fields = fields
        self.rows = list(rows)
        self.error_code = error_code
        self.error_msg = error_msg
        self.index = 0

    def next(self):
        if self.index >= len(self.rows):
            return False
        self.index += 1
        return True

    def get_row_data(self):
        return list(self.rows[self.index - 1])


class FakeBaoStock:
    def __init__(self, login_code="0", login_message="success"):
        self.login_code = login_code
        self.login_message = login_message
        self.calls = []
        self.logged_out = False

    def login(self):
        return SimpleNamespace(error_code=self.login_code, error_msg=self.login_message)

    def logout(self):
        self.logged_out = True

    def query_history_k_data_plus(self, *args, **kwargs):
        self.calls.append(("history", args, kwargs))
        fields = HISTORY_FIELDS.split(",")
        code = args[0]
        day = kwargs["start_date"]
        return FakeResult(fields, [[day, code, "10.5", "10000", "1", "0", "2.5"]])

    def query_trade_dates(self, **kwargs):
        self.calls.append(("calendar", kwargs))
        return FakeResult(["calendar_date", "is_trading_day"], [[kwargs["end_date"], "1"]])

    def query_all_stock(self, **kwargs):
        self.calls.append(("universe", kwargs))
        return FakeResult(["code", "tradeStatus", "code_name"], [["sh.600000", "1", "浦发银行"]])

    def query_stock_industry(self):
        self.calls.append(("industry", {}))
        return FakeResult(["code", "code_name", "industry", "updateDate", "industryClassification"],
                          [["sh.600000", "浦发银行", "J66货币金融服务", "2026-11-06", "证监会行业"]])


class ProviderTests(unittest.TestCase):
    def test_blacklisted_login_fails_fast_without_retry(self):
        fake = FakeBaoStock("10001011", "黑名单用户，请与管理员联系")
        provider = BaoStockProvider(fake)
        with self.assertRaises(BaoStockBlacklistError):
            provider.login()
        self.assertEqual(fake.calls, [])
        self.assertFalse(provider.logged_in)

    def test_history_uses_unadjusted_prices_and_required_fields(self):
        fake = FakeBaoStock()
        provider = BaoStockProvider(fake)
        provider.login()
        frame = provider.query_history("sh.600000", "2026-11-06", "2026-11-06")
        self.assertEqual(frame.iloc[0]["close"], "10.5")
        call = fake.calls[0]
        self.assertEqual(call[1][1], HISTORY_FIELDS)
        self.assertEqual(call[2]["adjustflag"], "3")
        self.assertEqual(call[2]["frequency"], "d")
        provider.logout()
        self.assertTrue(fake.logged_out)

    def test_a_share_filter_excludes_b_share_and_non_equity(self):
        fake = FakeBaoStock()
        provider = BaoStockProvider(fake)
        provider.login()
        frame = provider.query_all_stocks("2026-11-06")
        self.assertEqual(frame["code"].tolist(), ["sh.600000"])


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "market.sqlite3"
        self.db = MarketDB(self.path, max_api_requests_per_day=5)

    def test_client_compatible_market_tables_and_turnover_column(self):
        with connect(self.path) as db:
            daily = {r[1] for r in db.execute("PRAGMA table_info(daily)")}
            industry = {r[1] for r in db.execute("PRAGMA table_info(industry_cache)")}
        self.assertTrue({"code", "trade_date", "close", "volume", "trade_status", "is_st", "turnover"}.issubset(daily))
        self.assertTrue({"code", "name", "industry", "update_date", "classification", "fetched_at"}.issubset(industry))

    def test_daily_request_budget_is_persisted_and_capped(self):
        for _ in range(5):
            self.db.consume_api_request()
        with self.assertRaisesRegex(RuntimeError, "安全请求上限"):
            self.db.consume_api_request()
        self.assertEqual(self.db.api_requests_today(), 5)

    def test_backoff_is_exponential_and_bounded(self):
        self.assertEqual([retry_delay_hours(i) for i in range(1, 7)], [6, 12, 24, 48, 96, 168])
        now = datetime(2026, 11, 6, 18, 0, 0)
        self.assertFalse(retry_is_due("2026-11-06 19:00:00", now))
        self.assertTrue(retry_is_due("2026-11-06 11:00:00", now))


class SnapshotTests(unittest.TestCase):
    def test_snapshot_is_integrity_checked_and_contains_compatible_tables(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db_path = root / "market.sqlite3"
            db = MarketDB(db_path)
            universe = pd.DataFrame([{"code": "sh.600000", "name": "浦发银行", "trade_status": 1}])
            db.persist_universe("2026-11-06", universe)
            with connect(db_path) as conn:
                db.upsert_daily_rows(conn, [("sh.600000", "2026-11-06", "浦发银行", 10.5, 10000, 1, 0, 2.5)])
                conn.execute("INSERT INTO industry_cache VALUES(?,?,?,?,?,?)",
                             ("sh.600000", "浦发银行", "货币金融服务", "2026-11-06", "证监会行业", "2026-11-06 18:00:00"))
            status = db.update_day_status("2026-11-06")
            publisher = SnapshotPublisher(db_path, root / "public", "https://example.test/marketdata", 120)
            manifest = publisher.publish("2026-11-06", status, 1)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["snapshot_url"], "https://example.test/marketdata/snapshot.zip")
            with zipfile.ZipFile(root / "public" / manifest["snapshot_file"]) as archive:
                self.assertIsNone(archive.testzip())
                archive.extract("marketdata.sqlite3", root)
            snap = sqlite3.connect(root / "marketdata.sqlite3")
            self.assertEqual(snap.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(snap.execute("SELECT turnover FROM daily").fetchone()[0], 2.5)
            self.assertEqual(snap.execute("SELECT industry FROM industry_cache").fetchone()[0], "货币金融服务")
            self.assertEqual(snap.execute("SELECT value FROM server_meta WHERE key='provider'").fetchone()[0], "BaoStock")
            snap.close()


class FakeProvider:
    def __init__(self, latest="2026-11-06", incomplete=False):
        self.latest = latest
        self.incomplete = incomplete
        self.history_calls = []
        self.industry_calls = 0
        self.logged_in = False

    def login(self):
        self.logged_in = True

    def logout(self):
        self.logged_in = False

    def query_trade_dates(self, start, end):
        days = pd.bdate_range(end=self.latest, periods=3).strftime("%Y-%m-%d").tolist()
        return pd.DataFrame([{"calendar_date": d, "is_trading_day": "1"} for d in days])

    def query_index_history(self, start, end):
        return pd.DataFrame([{"date": self.latest, "code": "sh.000001", "close": "3000", "volume": "1"}])

    def query_all_stocks(self, trade_date):
        return pd.DataFrame([
            {"code": "sh.600000", "name": "浦发银行", "trade_status": 1},
            {"code": "sz.000001", "name": "平安银行", "trade_status": 1},
        ])

    def query_history(self, code, start, end):
        self.history_calls.append((code, start, end))
        if self.incomplete and code == "sz.000001":
            return pd.DataFrame(columns=["date", "code", "close", "volume", "tradestatus", "isST", "turn"])
        dates = pd.bdate_range(start=start, end=end).strftime("%Y-%m-%d").tolist()
        return pd.DataFrame([{
            "date": d, "code": code, "close": "10.5", "volume": "10000",
            "tradestatus": "1", "isST": "0", "turn": "2.5",
        } for d in dates])

    def query_stock_industry(self):
        self.industry_calls += 1
        return pd.DataFrame([
            {"code": "sh.600000", "code_name": "浦发银行", "industry": "J66货币金融服务",
             "updateDate": self.latest, "industryClassification": "证监会行业"},
            {"code": "sz.000001", "code_name": "平安银行", "industry": "J66货币金融服务",
             "updateDate": self.latest, "industryClassification": "证监会行业"},
        ])


class ApiTests(unittest.TestCase):
    def test_read_only_api_serves_health_manifest_and_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public = root / "public"
            public.mkdir()
            snapshot = public / "snapshot-aabbccddeeff0011.zip"
            snapshot.write_bytes(b"test-snapshot")
            manifest = {
                "snapshot_file": snapshot.name,
                "snapshot_size": snapshot.stat().st_size,
                "snapshot_sha256": "aabbccddeeff0011" + "0" * 48,
            }
            manifest_path = public / "latest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            original = api_module.settings
            api_module.settings = SimpleNamespace(public_dir=public, manifest_path=manifest_path)
            server = ThreadingHTTPServer(("127.0.0.1", 0), api_module.MarketDataHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["ok"])
                with urllib.request.urlopen(base + "/latest.json", timeout=3) as response:
                    self.assertEqual(json.loads(response.read())["snapshot_file"], snapshot.name)
                with urllib.request.urlopen(base + "/snapshot.zip", timeout=3) as response:
                    self.assertEqual(response.read(), b"test-snapshot")
                request = urllib.request.Request(base + "/snapshot.zip", method="POST")
                with self.assertRaises(Exception):
                    urllib.request.urlopen(request, timeout=3)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                api_module.settings = original


class UpdaterTests(unittest.TestCase):
    def _settings(self, root: Path) -> Settings:
        return Settings(data_dir=root, history_days=3, retention_days=10,
                        batch_size=200, batch_pause=0, max_consecutive_errors=25,
                        max_api_requests_per_day=45000, retry_base_hours=6,
                        retry_max_hours=168, industry_refresh_days=7,
                        min_publish_completeness=0.995)

    def test_new_market_day_fetches_only_incremental_bars(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = FakeProvider(latest="2026-11-06")
            updater = MarketUpdater(self._settings(root), provider)
            first = updater.run()
            self.assertTrue(first["published"])
            self.assertEqual(len(provider.history_calls), 2)
            provider.latest = "2026-11-09"
            second = updater.run()
            self.assertTrue(second["published"])
            self.assertEqual(len(provider.history_calls), 4)
            self.assertEqual(provider.history_calls[-2][1:], ("2026-11-09", "2026-11-09"))
            self.assertEqual(provider.history_calls[-1][1:], ("2026-11-09", "2026-11-09"))

    def test_explicit_market_date_is_used_for_both_readiness_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            updater = MarketUpdater(self._settings(Path(temp)), FakeProvider())
            result = updater.run(as_of="2026-11-06")
            self.assertTrue(result["published"])
            self.assertEqual(result["market_date"], "2026-11-06")
            self.assertEqual(json.loads(updater.config.manifest_path.read_text())["market_date"], "2026-11-06")

    def test_explicit_nontrading_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            updater = MarketUpdater(self._settings(Path(temp)), FakeProvider())
            with self.assertRaisesRegex(Exception, "不是可用交易日"):
                updater.run(as_of="2026-11-07")
            self.assertFalse(updater.config.manifest_path.exists())

    def test_stale_index_never_replaces_existing_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = FakeProvider()
            updater = MarketUpdater(self._settings(root), provider)
            updater.run()
            manifest_path = root / "public" / "latest.json"
            previous = manifest_path.read_bytes()
            provider.query_trade_dates = lambda start, end: pd.DataFrame([
                {"calendar_date": "2026-11-06", "is_trading_day": "1"},
                {"calendar_date": "2026-11-09", "is_trading_day": "1"}])
            with self.assertRaisesRegex(Exception, "尚未就绪"):
                updater.run()
            self.assertEqual(previous, manifest_path.read_bytes())

    def test_unadjusted_database_is_independent_of_old_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "market.sqlite3"
            old.write_bytes(b"old database stays untouched")
            updater = MarketUpdater(self._settings(root), FakeProvider())
            self.assertNotEqual(updater.config.db_path, old)
            self.assertTrue(updater.run()["published"])
            self.assertEqual(old.read_bytes(), b"old database stays untouched")
            manifest = json.loads((root / "public" / "latest.json").read_text())
            self.assertEqual(manifest["adjustment"], "不复权 (adjustflag=3)")

    def test_wrong_stock_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            provider = FakeProvider()
            original = provider.query_history
            def incorrect(code, start, end):
                frame = original(code, start, end)
                frame["code"] = "sh.600999"
                return frame
            provider.query_history = incorrect
            updater = MarketUpdater(self._settings(Path(temp)), provider)
            result = updater.run()
            self.assertFalse(result["published"])

    def test_retention_prunes_old_daily_rows_only_after_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = MarketDB(root / "market.sqlite3")
            days = pd.bdate_range(end="2026-11-06", periods=130).strftime("%Y-%m-%d").tolist()
            with connect(db.path) as conn:
                db.upsert_daily_rows(conn, [
                    ("sh.600000", day, "浦发银行", 10.0, 1000, 1, 0, 2.0)
                    for day in days
                ])
            removed = db.prune_old_data(120)
            self.assertEqual(removed, 10)
            with connect(db.path) as conn:
                remaining = conn.execute("SELECT COUNT(DISTINCT trade_date) FROM daily").fetchone()[0]
            self.assertEqual(remaining, 120)

    def test_initial_run_publishes_and_second_run_does_not_redownload_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = FakeProvider()
            updater = MarketUpdater(self._settings(root), provider)
            result = updater.run()
            self.assertTrue(result["published"])
            self.assertEqual(result["status"]["status"], "complete")
            self.assertEqual(len(provider.history_calls), 2)
            self.assertEqual(provider.industry_calls, 1)
            self.assertTrue((root / "public" / "latest.json").is_file())
            # Re-running the same date should be idempotent: no history or industry requests.
            second = updater.run()
            self.assertTrue(second["published"])
            self.assertEqual(len(provider.history_calls), 2)
            self.assertEqual(provider.industry_calls, 1)

    def test_incomplete_market_data_does_not_replace_or_publish_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            provider = FakeProvider(incomplete=True)
            updater = MarketUpdater(self._settings(root), provider)
            result = updater.run()
            self.assertFalse(result["published"])
            self.assertFalse((root / "public" / "latest.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
