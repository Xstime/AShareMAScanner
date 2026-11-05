"""Offline regression tests for dev AKShare migration; no upstream HTTP calls."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec

import pandas as pd
import openpyxl

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SOURCE = Path(__file__).resolve().parents[1] / "A股MA扫描器_dev_AKShare.pyw"
loader = SourceFileLoader("ashare_dev_akshare", str(SOURCE))
spec = spec_from_loader(loader.name, loader)
m = module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class AdapterAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = m.AKShareBackend(Path(self.tmp.name) / "new_akshare.db")
        self.backend.init_db()
        self.quotes = self.backend._quotes
        self.quotes.names["sz.000001"] = "平安银行"

    def test_eastmoney_lots_to_shares_and_percent_turnover(self):
        bars = self.quotes.normalize(pd.DataFrame({
            "日期":["2026-11-03"], "收盘":[10.2], "成交量":[123],
            "换手率":[3.25]}), "sz.000001", "eastmoney")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars.iloc[0]["volume"], 12300)
        self.assertEqual(bars.iloc[0]["turn"], 3.25)
        self.assertEqual(bars.iloc[0]["date"], "2026-11-03")

    def test_sina_shares_and_ratio_to_percent(self):
        bars = self.quotes.normalize(pd.DataFrame({
            "date":["2026-11-03"], "close":[10.2],
            "volume":[12300], "turnover":[0.0325]}), "sz.000001", "sina")
        self.assertEqual(bars.iloc[0]["volume"], 12300)
        self.assertAlmostEqual(bars.iloc[0]["turn"], 3.25)
        self.assertEqual(bars.iloc[0]["close"], 10.2)

    def test_tencent_volume_not_amount(self):
        bars = self.quotes.normalize(pd.DataFrame({
            "date":["2026-11-03"], "close":[10.2],
            "volume":[12300], "amount":[900000000]}), "sz.000001", "tencent")
        self.assertEqual(bars.iloc[0]["volume"], 12300)
        self.assertTrue(pd.isna(bars.iloc[0]["turn"]))

    def test_suspended_bar_does_not_advance_ma(self):
        bars = self.quotes.normalize(pd.DataFrame({
            "日期":["2026-11-03"],"收盘":[10.2],"成交量":[0],
            "换手率":[0]}), "sz.000001", "eastmoney")
        self.assertEqual(bars.iloc[0]["tradestatus"], 0)

    def test_source_conflict_is_not_silently_merged(self):
        with m.sqlite_connection(self.backend.db_path) as db:
            db.execute("INSERT INTO daily "
                "(code,trade_date,name,close,volume,trade_status,is_st,turnover) "
                "VALUES (?,?,?,?,?,?,?,?)",
                ("sz.000001","2026-11-03","平安银行",10.2,1000,1,0,2.0))
        providers = []
        def bad_feed(code, first, last, provider):
            providers.append(provider)
            price = 11.2 if provider != "eastmoney" else 11.0
            return self.quotes.normalize(pd.DataFrame({
                "日期":["2026-11-03","2026-11-04"],
                "收盘":[price,11.5],"成交量":[100,100],"换手率":[2.,2.]
            }), code, "eastmoney")
        self.quotes._download = bad_feed
        with self.assertRaisesRegex(RuntimeError, "后复权价格"):
            self.quotes.history("sz.000001","2026-11-04","2026-11-04")
        self.assertEqual(providers,["eastmoney","sina","tencent"])
        with m.sqlite_connection(self.backend.db_path) as db:
            count = db.execute("SELECT COUNT(*) FROM daily").fetchone()[0]
        self.assertEqual(count,1)

    def test_actual_fallback_after_primary_error_with_compatible_prices(self):
        def feed(code, first, last, provider):
            if provider == "eastmoney":
                raise RuntimeError("upstream blocked")
            return self.quotes.normalize(pd.DataFrame({
                "date":["2026-11-03","2026-11-04"],"close":[10.2,10.4],
                "volume":[10000,12000],"turnover":[.03,.035]
            }),code,"sina")
        with m.sqlite_connection(self.backend.db_path) as db:
            db.execute("INSERT INTO daily "
                "(code,trade_date,name,close,volume,trade_status,is_st,turnover) "
                "VALUES (?,?,?,?,?,?,?,?)",
                ("sz.000001","2026-11-03","平安银行",10.2,10000,1,0,3.0))
        self.quotes._download = feed
        bars = self.quotes.history("sz.000001","2026-11-04","2026-11-04")
        self.assertEqual(len(bars),1)
        self.assertEqual(bars.iloc[0]["close"],10.4)
        self.assertEqual(bars.iloc[0]["volume"],12000)
        self.assertAlmostEqual(bars.iloc[0]["turn"],3.5)
        self.assertEqual(self.quotes._preferred["sz.000001"],"sina")

    def test_eastmoney_rate_limit_cools_down_without_repeated_requests(self):
        class Push2RateLimitError(Exception):
            pass
        attempts=[]
        def fake_download(code, first, last, provider):
            attempts.append((code, provider))
            if provider == "eastmoney":
                raise Push2RateLimitError("东方财富 push2 当前 IP 被临时限流")
            return self.quotes.normalize(pd.DataFrame({
                "date": [last], "close": [10.0], "volume": [15000],
                "turnover": [.025]}), code, "sina")
        self.quotes._download = fake_download
        first=self.quotes.history("sz.000001","2026-11-04","2026-11-04")
        self.assertEqual(len(first),1)
        self.assertGreater(self.quotes._em_banned_until,0)
        second=self.quotes.history("sh.600111","2026-11-04","2026-11-04")
        self.assertEqual(len(second),1)
        self.assertEqual([p for code,p in attempts if p=="eastmoney"],["eastmoney"])
        self.assertEqual(self.quotes._preferred["sh.600111"],"sina")

    def test_universe_uses_sina_when_eastmoney_is_cooled_down(self):
        import time
        self.quotes._em_banned_until=time.monotonic()+60
        self.quotes.index_dates=lambda:["2026-11-04"]
        symbols=[f"{600000+i:06d}" for i in range(1001)]
        with mock.patch.object(m.ak,"stock_zh_a_spot_em",
                               side_effect=AssertionError("EM should not be requested")), \
             mock.patch.object(m.ak,"stock_zh_a_spot",
                               return_value=pd.DataFrame({"symbol":symbols,
                                                          "name":["模拟"]*1001})):
            frame=self.quotes.stocks("2026-11-04")
        self.assertEqual(len(frame),1001)

    def test_index_tries_tencent_before_banned_eastmoney(self):
        from datetime import datetime, timedelta
        day=(datetime.now(m.CST)-timedelta(days=1)).strftime("%Y-%m-%d")
        with mock.patch.object(m.ak,"stock_zh_index_daily_tx",
                               return_value=pd.DataFrame({"date":[day]})) as tx, \
             mock.patch.object(m.ak,"index_zh_a_hist",
                               side_effect=AssertionError("EM should not run")) as em:
            days=self.quotes.index_dates()
        self.assertEqual(days[-1],day)
        tx.assert_called_once()
        em.assert_not_called()

    def test_old_baostock_file_is_never_reused(self):
        self.assertEqual(self.backend.db_path.name,"new_akshare.db")
        self.assertEqual(m.DB_PATH.name,"a_share_akshare_hfq.db")

    def test_calendar_works_after_2025_without_stale_sina_data(self):
        self.quotes._sina_calendar=["2025-12-31"]
        self.quotes.index_dates=lambda:["2026-11-03","2026-11-04"]
        df=self.quotes.calendar("2026-11-03","2026-11-05")
        self.assertEqual(df["is_trading_day"].tolist(),["1","1","0"])


class ExcelAudit(unittest.TestCase):
    def test_codes_numeric_cells_and_no_formula_injection(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"results.xlsx"
            data=pd.DataFrame({
                "代码":["000001","600519"],
                "名称":["=HYPERLINK(\"https://example.com\",\"bad\")","正常名称"],
                "收盘价":[10.2,998.5],
                "换手率%":[3.1,float("nan")]})
            m.export_strategy_xlsx(path,list(data.columns),data)
            wb=openpyxl.load_workbook(path)
            ws=wb.active
            self.assertEqual(ws["A2"].value,"000001")
            self.assertEqual(ws["A2"].data_type,"s")
            self.assertEqual(ws["B2"].data_type,"s")
            self.assertEqual(ws["B2"].value,data["名称"][0])
            self.assertEqual(ws["C2"].value,10.2)
            self.assertEqual(ws["C2"].data_type,"n")
            self.assertEqual(ws["A3"].value,"600519")
            self.assertIsNone(ws["D3"].value)
            self.assertEqual(ws.freeze_panes,"A2")


class GUICheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def test_previous_day_option_removed_and_excel_button_exists(self):
        win=m.ScannerWindow(demo=True)
        self.addCleanup(win.close)
        self.assertFalse(hasattr(win,"show_previous"))
        self.assertEqual(win.export_excel.text(),"导出 Excel")
        self.assertTrue(win.export_excel.isEnabled())

    def test_scan_worker_always_scans_one_date(self):
        got=[]
        class Backend:
            def scan_strategy(self, strategy, date, include_previous, previous, filters, **kwargs):
                got.append((date,include_previous))
                return pd.DataFrame()
        worker=m.ScanWorker(Backend(),1,"ma5_turn_up","2026-11-04","2026-11-03",None)
        worker.run()
        self.assertEqual(got,[("2026-11-04",False)])


if __name__=="__main__":
    unittest.main()
