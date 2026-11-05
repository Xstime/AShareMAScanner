"""Repro and recovery tests for missing sectors in AKShare development version."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager, ExitStack
from unittest import mock

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SOURCE = Path(__file__).resolve().parents[1] / "A股MA扫描器_dev_AKShare.pyw"
loader = SourceFileLoader("ashare_dev_sectors", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

STOCKS = pd.DataFrame([
    {"code": "sh.600001", "name": "电源股份", "trade_status": 1},
    {"code": "sz.000001", "name": "深市一号", "trade_status": 1},
    {"code": "sh.600123", "name": "材料股份", "trade_status": 1},
])


@contextmanager
def mock_providers(primary_fails=False, backup_fails=False):
    def em_members(symbol):
        if symbol == "有色金属" and primary_fails:
            raise ConnectionError("mock EM sector blocked")
        if symbol == "电力设备":
            return pd.DataFrame({"代码": ["600001", "000001"],
                                 "名称": ["电源股份", "深市一号"]})
        return pd.DataFrame({"代码": ["600123"], "名称": ["材料股份"]})

    def sina_members(sector):
        if backup_fails:
            raise ConnectionError("mock Sina sector blocked")
        if sector == "hangye_1":
            return pd.DataFrame({
                "symbol": ["sh600001", "sz000001"],
                "name": ["电源股份", "深市一号"]})
        return pd.DataFrame({"symbol": ["sh600123"],
                             "name": ["材料股份"]})

    patches = [
        mock.patch.object(m.ak, "stock_board_industry_name_em",
                          return_value=pd.DataFrame({"板块名称": ["电力设备", "有色金属"]})),
        mock.patch.object(m.ak, "stock_board_industry_cons_em",
                          side_effect=em_members),
        mock.patch.object(m.ak, "stock_sector_spot",
                          return_value=pd.DataFrame({"label": ["hangye_1", "hangye_2"],
                                                     "板块": ["设备", "有色"]})),
        mock.patch.object(m.ak, "stock_sector_detail",
                          side_effect=sina_members),
    ]
    with ExitStack() as stack:
        yield [stack.enter_context(patch) for patch in patches]


class SectorRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = m.AKShareBackend(Path(self.temp.name) / "sectors.sqlite")
        self.backend.init_db()
        self.backend._quotes._pace = lambda: None
        self.progress = []

    def refresh(self):
        return self.backend.refresh_industry_cache(
            STOCKS, lambda p, msg: self.progress.append((p, msg)), 96, 97,
            force=True)

    def test_partial_em_failure_is_saved_and_sina_fills_missing(self):
        with mock_providers(primary_fails=True) as p:
            warning = self.refresh()
        mapped = self.backend.get_industry_map()
        self.assertEqual(len(mapped), 3)
        self.assertEqual(mapped["sh.600001"], "电力设备")
        self.assertEqual(mapped["sz.000001"], "电力设备")
        self.assertEqual(mapped["sh.600123"], "新浪·有色")
        self.assertIn("不完整", warning)
        self.assertTrue(any("已保存" in task for _, task in self.progress))
        with m.sqlite_connection(self.backend.db_path) as db:
            rows = dict(db.execute("SELECT code, classification FROM industry_cache"))
        self.assertEqual(rows["sh.600001"], "AKShare-EM")
        self.assertEqual(rows["sh.600123"], "AKShare-Sina")

    def test_backup_never_overwrites_primary_classification(self):
        with mock_providers(primary_fails=True):
            self.refresh()
        result = self.backend.get_industry_map()
        self.assertEqual(result["sh.600001"], "电力设备")
        self.assertNotIn("新浪·设备", result.values())

    def test_failure_retains_successful_batches_and_next_retry_recovers(self):
        with mock_providers(primary_fails=True, backup_fails=True):
            warning1 = self.refresh()
        self.assertEqual(set(self.backend.get_industry_map()), {"sh.600001", "sz.000001"})
        self.assertIn("不完整", warning1)
        with mock_providers(primary_fails=False, backup_fails=True):
            warning2 = self.refresh()
        self.assertEqual(len(self.backend.get_industry_map()), 3)
        self.assertFalse(warning2)

    def test_empty_behind_both_sources_reports_reason_and_can_retry(self):
        with mock.patch.object(m.ak, "stock_board_industry_name_em",
                               side_effect=ConnectionError("eastmoney unavailable")), \
             mock.patch.object(m.ak, "stock_sector_spot",
                               side_effect=ConnectionError("sina unavailable")):
            warning = self.refresh()
        self.assertIn("板块分类获取失败", warning)
        self.assertEqual(len(self.backend.get_industry_map()), 0)
        with mock_providers(primary_fails=False):
            self.assertEqual(self.refresh(), "")
        self.assertEqual(len(self.backend.get_industry_map()), 3)

    def test_fresh_high_coverage_skips_redundant_network(self):
        with mock_providers(primary_fails=False):
            self.refresh()
        with mock.patch.object(self.backend._quotes, "industries",
                               side_effect=AssertionError("unexpected network call")):
            result = self.backend.refresh_industry_cache(
                STOCKS, lambda *_: None, 96, 97, force=False)
        self.assertEqual(result, "")

    def test_sector_chart_still_uses_membership_and_all_actual_prices(self):
        with mock_providers(primary_fails=False):
            self.refresh()
        dates = pd.bdate_range("2026-10-01", periods=25).strftime("%Y-%m-%d")
        with m.sqlite_connection(self.backend.db_path) as db:
            db.executemany(
                "INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) "
                "VALUES(?,?,?,?,?,?,?,?)",
                [(code, day, "测试", 10.0 + i * .05, 5000.0, 1, 0, 2.3)
                 for code in ("sh.600001", "sz.000001")
                 for i, day in enumerate(dates)]
            )
        sector = self.backend.get_sector_chart_data("电力设备", dates[-1])
        self.assertEqual(len(sector), 25)
        self.assertTrue({"close", "MA5", "MA10", "MA20"}.issubset(sector.columns))
        self.assertAlmostEqual(float(sector.iloc[0]["close"]), 100.0, places=3)
        self.assertTrue(pd.notna(sector.iloc[-1]["MA20"]))

    def test_cancelled_sector_refresh_stops_without_losing_existing_rows(self):
        with mock_providers(primary_fails=False):
            self.backend._cancel_update_event.set()
            with self.assertRaises(m.MarketUpdateCancelled):
                self.refresh()
            self.backend._cancel_update_event.clear()
            self.assertEqual(len(self.backend.get_industry_map()), 0)
            self.assertEqual(self.refresh(), "")
            self.assertEqual(len(self.backend.get_industry_map()), 3)

    def test_failed_persist_does_not_mark_stock_as_classified(self):
        adapter = self.backend._quotes
        writes = []
        def persist(batch, provider, sector):
            if provider == "eastmoney":
                raise sqlite3.OperationalError("readonly simulated cache")
            writes.append((provider, sector, batch.copy()))
        with mock_providers(primary_fails=False):
            frame = adapter.industries(persist, set(STOCKS["code"]))
        self.assertEqual(len(frame), 3)
        self.assertTrue(all(name.startswith("新浪·") for name in frame["industry"]))
        self.assertTrue(any(source == "sina" for source, _, _ in writes))

    def test_repeated_upstream_failures_abort_early_and_use_backup(self):
        calls = []
        sectors = [f"板块{i}" for i in range(30)]
        def unavailable(symbol):
            calls.append(symbol)
            raise ConnectionError("upstream refuses request")
        with mock.patch.object(m.ak, "stock_board_industry_name_em",
                               return_value=pd.DataFrame({"板块名称": sectors})), \
             mock.patch.object(m.ak, "stock_board_industry_cons_em",
                               side_effect=unavailable), \
             mock.patch.object(m.ak, "stock_sector_spot",
                               return_value=pd.DataFrame({"label": ["h1", "h2"],
                                                          "板块": ["备用1", "备用2"]})), \
             mock.patch.object(m.ak, "stock_sector_detail",
                               side_effect=[
                                   pd.DataFrame({"symbol": ["sh600001", "sz000001"],
                                                 "name": ["A", "B"]}),
                                   pd.DataFrame({"symbol": ["sh600123"],
                                                 "name": ["C"]}),
                               ]):
            warning = self.refresh()
        self.assertEqual(len(calls), 8)  # Four boards, two retries per board.
        self.assertEqual(len(self.backend.get_industry_map()), 3)
        self.assertIn("部分不完整", warning)

    def test_timeout_configuration_is_bounded(self):
        from akshare.utils.context import get_timeout
        self.assertEqual(get_timeout(), (5, 12))

    def test_update_result_includes_nonfatal_sector_warning(self):
        b = self.backend
        b.prepare_storage = lambda cb: None
        b.login = lambda: None
        b.logout = lambda: None
        b.is_today_trading_day = lambda: False
        b.get_latest_available_trade_date = lambda: "2026-11-04"
        b.query_all_a_stocks = lambda day: STOCKS
        b.retry_init_queue = lambda *a: None
        b.initialize_missing_histories = lambda *a: None
        b.retry_partial_dates = lambda *a: None
        b.process_new_trade_dates = lambda *a: None
        b.backfill_turnover = lambda *a: ""
        b.refresh_industry_cache = lambda *a: "板块分类不完整，模拟的备用源失败"
        b.get_day_universe = lambda d: STOCKS
        b.update_day_status = lambda d: {
            "expected": 3, "saved": 3, "failed": 0, "status": "complete"}
        b.get_previous_market_trade_date = lambda d: "2026-11-03"
        result = b.update_all(lambda *args: None)
        self.assertIn("板块分类不完整", result.warning)


class SectorGuiRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.gui = m.ScannerWindow(demo=True)
        self.addCleanup(self.gui.close)

    def test_zero_strategy_hits_still_list_all_cached_sectors(self):
        self.gui.demo = False
        self.gui.backend = mock.Mock()
        self.gui.backend.get_industry_map.return_value = {
            "sh.600001": "电力设备", "sz.000001": "电力设备",
            "sh.600123": "有色金属"}
        self.gui.frame = pd.DataFrame()
        self.gui._update_industry_filter()
        self.gui._populate_sector_table()
        choices = [self.gui.industry.itemText(i) for i in range(self.gui.industry.count())]
        names = [self.gui.sector_table.item(i, 0).text()
                 for i in range(self.gui.sector_table.rowCount())]
        self.assertIn("电力设备", choices)
        self.assertIn("有色金属", choices)
        self.assertEqual(set(names), {"电力设备", "有色金属"})
        self.assertEqual(self.gui.sector_table.rowCount(), 2)
        statuses = [self.gui.sector_table.item(i, 2).text() for i in range(2)]
        self.assertEqual(statuses, ["待检查", "待检查"])

    def test_ui_has_independent_industry_retry_control(self):
        self.assertEqual(self.gui.industry_retry.text(), "重新获取分类")
        self.assertFalse(self.gui.industry_retry.isEnabled())  # demo must not fetch

    def test_missing_cache_is_visible_not_silent(self):
        self.gui.demo = False
        self.gui.backend = mock.Mock()
        self.gui.backend.get_industry_map.return_value = {}
        self.gui.frame = pd.DataFrame()
        self.gui._update_industry_filter()
        self.assertTrue(self.gui.industry_notice.isVisible()
                        or not self.gui.industry_notice.isHidden())
        self.assertIn("暂无板块分类", self.gui.industry_notice.text())


if __name__ == "__main__":
    unittest.main()
