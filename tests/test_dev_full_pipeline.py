"""Offline end-to-end AKShare pipeline: fake upstream -> SQLite -> Qt strategy/chart/export.

No external HTTP, no user database, no version update, no release automation.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
SOURCE=Path(__file__).resolve().parents[1]/"A股MA扫描器_dev_AKShare.pyw"
loader=SourceFileLoader("ashare_dev_full_pipeline",str(SOURCE))
spec=importlib.util.spec_from_loader(loader.name,loader)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class FullOfflinePipeline(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend=m.AKShareBackend(Path(self.tmp.name)/"akshare_pipeline.sqlite")
        self.backend.prepare_storage=lambda callback: None
        self.days=pd.bdate_range(end="2026-11-04",periods=50).strftime("%Y-%m-%d").tolist()
        self.names={"sh.600001":"电力股份","sz.000001":"银行股份","sh.600123":"材料股份"}
        q=self.backend._quotes
        q.index_dates=lambda: self.days
        def calendar(start,end):
            a=pd.date_range(start,end,freq="D").strftime("%Y-%m-%d").tolist()
            return pd.DataFrame({"calendar_date":a,"is_trading_day":[
                "1" if d in self.days else "0" for d in a]})
        q.calendar=calendar
        def stocks(day):
            return pd.DataFrame({
                "code":list(self.names),"tradeStatus":["1"]*3,
                "code_name":list(self.names.values())})
        q.stocks=stocks
        def history(code,start,end):
            result=[]
            for i,day in enumerate(self.days):
                if not start<=day<=end:
                    continue
                event=code=="sh.600001" and day==self.days[-1]
                result.append({
                    "date":day,"code":code,"close":12.0 if event else 10.0,
                    "volume":16000.0 if event else 10000.0,
                    "tradestatus":1,"isST":0,"turn":3.5})
            return pd.DataFrame(result,columns=q.FIELDS)
        q.history=history
        def industries(callback=None,target_codes=None,check_cancel=None):
            batches=[
                {"code":"sh.600001","code_name":"电力股份","industry":"电力设备",
                 "updateDate":"","industryClassification":"AKShare-EM"},
                {"code":"sz.000001","code_name":"银行股份","industry":"银行",
                 "updateDate":"","industryClassification":"AKShare-EM"},
                {"code":"sh.600123","code_name":"材料股份","industry":"有色金属",
                 "updateDate":"","industryClassification":"AKShare-EM"},
            ]
            frame=pd.DataFrame(batches)
            if callback is not None:
                for record in batches:
                    callback(pd.DataFrame([record]),"eastmoney",record["industry"])
            frame.attrs["industry_statistics"]={"eastmoney_ok":3,"eastmoney_failed":0,
                                                "sina_ok":0,"sina_failed":0,"errors":[]}
            return frame
        q.industries=industries
        self.logs=[]
        self.result=self.backend.update_all(lambda pct,task:self.logs.append((pct,task)))

    def test_full_startup_update_completeness_and_cache(self):
        self.assertEqual(self.result.scan_date,self.days[-1])
        self.assertAlmostEqual(self.result.completeness,100.0)
        self.assertEqual(self.result.expected,3)
        self.assertEqual(self.result.saved,3)
        self.assertEqual(self.result.warning,"")
        with m.sqlite_connection(self.backend.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM daily").fetchone()[0],135)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM day_universe").fetchone()[0],3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM industry_cache").fetchone()[0],3)
            row=db.execute("SELECT saved_count,expected_count,status FROM day_status").fetchone()
            self.assertEqual(tuple(row),(3,3,"complete"))
        self.assertEqual(self.backend.get_industry_map()["sh.600001"],"电力设备")
        self.assertTrue(self.logs and self.logs[-1][0]==100)

    def test_end_to_end_strategy_sector_status_and_historical_chart(self):
        today=self.result.scan_date
        output=self.backend.scan_strategy("breakout_ma5",today,False,
                                           self.result.previous_trade_date)
        self.assertEqual(len(output),1)
        self.assertEqual(output.iloc[0]["代码"],"600001")
        self.assertEqual(output.iloc[0]["板块"],"电力设备")
        self.assertAlmostEqual(output.iloc[0]["放量倍数"],1.6)
        self.assertTrue(self.backend.get_chart_data("sh.600001",today).shape[0]>=45)
        sector=self.backend.get_sector_chart_data("电力设备",today)
        self.assertFalse(sector.empty)
        self.assertTrue({"close","MA5","MA10","MA20"}.issubset(sector.columns))
        self.assertIsInstance(self.backend.get_sector_strategy_status(
            "电力设备","breakout_ma5",today,False,
            self.result.previous_trade_date),str)

    def test_all_eight_strategies_can_run_after_updated_cache(self):
        for strategy,_,_ in m.STRATEGIES:
            with self.subTest(strategy=strategy):
                frame=self.backend.scan_strategy(
                    strategy,self.days[-1],False,self.days[-2])
                self.assertIsInstance(frame,pd.DataFrame)
                if not frame.empty:
                    self.assertIn("板块",frame.columns)

    def test_signal_history_and_filtering_persist(self):
        date=self.days[-1]
        self.backend.scan_strategy("breakout_ma5",date,False,self.days[-2])
        hist=self.backend.get_signal_history("sh.600001",date)
        self.assertIsInstance(hist,pd.DataFrame)
        with m.sqlite_connection(self.backend.db_path) as db:
            self.assertGreater(db.execute("SELECT COUNT(*) FROM signal_history").fetchone()[0],0)

    def test_incremental_second_run_does_not_refetch_all_history(self):
        q=self.backend._quotes
        q.history=lambda *_: (_ for _ in ()).throw(
            AssertionError("fresh complete cache should not redownload history"))
        again=self.backend.update_all(lambda *a:None)
        self.assertAlmostEqual(again.completeness,100.)

    def test_fund_top5_still_loads_from_local_snapshot(self):
        with m.sqlite_connection(self.backend.db_path) as db:
            db.execute("INSERT INTO fund_top5_snapshot "
                       "(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)",
                       (1,"电力设备",123000000.0,"2026-11-04 18:30:00","同花顺"))
        rows,members=self.backend.load_fund_top5()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["name"],"电力设备")
        self.assertEqual(rows[0]["net_yuan"],123000000.0)
        self.assertEqual(members,{})


if __name__=="__main__":
    unittest.main()
