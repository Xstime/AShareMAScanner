"""Independent robustness audit: real temporary SQLite, invalid market data, and API faults.

Intentionally assert product guarantees; failures must remain visible in CI, not xfailed.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import math
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from datetime import datetime as ActualDateTime

import pandas as pd
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
file=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("v128_fresh_robustness",str(file))
spec=importlib.util.spec_from_loader(loader.name,loader)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class Weekend(ActualDateTime):
    @classmethod
    def now(cls,tz=None):
        return cls(2026,10,31,19,30,tzinfo=tz)

class Backend(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.b=mod.BaoStockBackend(Path(self.tmp.name)/"data.db")
        self.b.init_db()
        self.days=pd.date_range("2026-08-17",periods=35,freq="B").strftime("%Y-%m-%d").tolist()

    def tearDown(self):
        if self.b._instance_lock_file is not None:
            self.b._instance_lock_file.close()
        self.tmp.cleanup()

    def insert(self, code="sh.600000",name="正样本",close=lambda i:10+i*.05,vol=lambda i:10000,
               turnover=3.5,st=0,days=None):
        days=self.days if days is None else days
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("""INSERT OR REPLACE INTO daily
              (code,trade_date,name,close,volume,trade_status,is_st,turnover)
              VALUES(?,?,?,?,?,?,?,?)""",
              [(code,d,name,close(i) if callable(close) else close,
                vol(i) if callable(vol) else vol,1,st,turnover)
               for i,d in enumerate(days)])

    def test_01_data_integrity_rejects_invalid_bars(self):
        frame=pd.DataFrame([
            {"code":"sh.600001","date":"2026-10-29","close":"10.1","volume":"100","tradestatus":"1","isST":"0","turn":"3.5"},
            {"code":"sh.600002","date":"2026-10-29","close":"nan","volume":"100","tradestatus":"1","isST":"0","turn":"2"},
            {"code":"sh.600003","date":"2026-10-29","close":"inf","volume":"100","tradestatus":"1","isST":"0","turn":"2"},
            {"code":"sh.600004","date":"2026-10-29","close":"-1","volume":"100","tradestatus":"1","isST":"0","turn":"2"},
            {"code":"sh.600005","date":"2026-10-29","close":"10","volume":"-1","tradestatus":"1","isST":"0","turn":"2"},
        ])
        rows=self.b.dataframe_to_daily_rows(frame,"合法")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][0],"sh.600001")

    def test_02_range_boundaries_and_nan(self):
        f=mod.RangeFilter(1.5,3,3,5)
        self.assertTrue(f.matches({"volume":150,"VOL5_PREV":100,"turnover":3}))
        self.assertTrue(f.matches({"volume":300,"VOL5_PREV":100,"turnover":5}))
        for row in [
            {"volume":math.nan,"VOL5_PREV":100,"turnover":4},
            {"volume":100,"VOL5_PREV":0,"turnover":4},
            {"volume":400,"VOL5_PREV":100,"turnover":4},
            {"volume":200,"VOL5_PREV":100,"turnover":-1},
        ]:
            self.assertFalse(f.matches(row))
        for args in [(-1,None,3,None),(1,0.5,3,None),(1,None,5,3),(math.inf,None,3,None)]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                mod.RangeFilter(*args)

    def test_03_st_names_excluded_from_all_seven_strategies(self):
        self.insert(name="*ST测试",vol=lambda i:30000 if i==34 else 10000)
        original=self.b.get_industry_map
        self.b.get_industry_map=lambda:{}
        self.b.get_sector_strategy_status=lambda **_: "未触发"
        self.b.record_signals=lambda *a,**k:None
        try:
            for key,_,_ in mod.STRATEGIES:
                with self.subTest(key=key):
                    df=self.b.scan_strategy(key,self.days[-1],False,self.days[-2])
                    self.assertTrue(df.empty,key)
        finally:
            self.b.get_industry_map=original

    def test_04_day_completeness_excludes_wrong_and_inactive_stocks(self):
        d=self.days[-1]
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("INSERT INTO day_universe(trade_date,code,name,trade_status) VALUES(?,?,?,?)",
                          [(d,"sh.600000","A",1),(d,"sh.600001","B",1),(d,"sh.600002","C",0)])
            c.executemany("INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) VALUES(?,?,?,?,?,?,?,?)",
                          [("sh.600000",d,"A",10,100,1,0,2),
                           ("sh.600001",d,"B",-2,100,1,0,2),
                           ("sh.600002",d,"C",10,100,1,0,2)])
        status=self.b.update_day_status(d)
        self.assertEqual((status["expected"],status["saved"],status["status"]),(2,1,"partial"))

    def test_05_successful_retry_removes_obsolete_fetch_failure(self):
        d=self.days[-1]
        with mod.sqlite_connection(self.b.db_path) as c:
            c.execute("INSERT INTO day_universe(trade_date,code,name,trade_status) VALUES(?,?,?,1)",(d,"sh.600000","A"))
            c.execute("INSERT INTO fetch_queue(code,trade_date,name,reason,retry_count) VALUES(?,?,?,?,1)",
                      ("sh.600000",d,"A","timeout"))
            c.execute("INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) VALUES(?,?,?,?,?,?,?,?)",
                      ("sh.600000",d,"A",11,110,1,0,2))
        info=self.b.update_day_status(d)
        self.assertEqual((info["saved"],info["failed"],info["status"]),(1,0,"complete"))
        with mod.sqlite_connection(self.b.db_path) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM fetch_queue").fetchone()[0],0)

    def test_06_corrupted_sqlite_must_not_be_deleted(self):
        path=Path(self.tmp.name)/"broken.db"
        payload=b"NOT A SQLITE DATABASE ORIGINAL CONTENT"
        path.write_bytes(payload)
        b=mod.BaoStockBackend(path)
        with self.assertRaises((RuntimeError,sqlite3.DatabaseError)):
            b.prepare_storage(lambda *_:None)
        self.assertEqual(path.read_bytes(),payload)
        if b._instance_lock_file is not None:b._instance_lock_file.close()

    def test_07_two_process_guards_on_same_data_path(self):
        b2=mod.BaoStockBackend(self.b.db_path)
        self.b.prepare_storage(lambda *_:None)
        with self.assertRaises(RuntimeError):
            b2.prepare_storage(lambda *_:None)
        if b2._instance_lock_file is not None:b2._instance_lock_file.close()

    def test_08_history_is_stable_and_idempotent(self):
        self.insert(vol=lambda i:20000 if i>=25 else 10000)
        end=self.days[-1]
        first=self.b.get_signal_history("sh.600000",end)
        second=self.b.get_signal_history("sh.600000",end)
        self.assertEqual(len(first),len(second))
        self.assertTrue({"streak","strategy","filter_key","payload"}.issubset(first.columns))
        with mod.sqlite_connection(self.b.db_path) as c:
            rows=c.execute("SELECT COUNT(*) FROM signal_history").fetchone()[0]
        self.assertEqual(rows,len(second))

    def test_09_chart_never_leaks_another_stock(self):
        self.insert(code="sh.600000")
        self.insert(code="sz.300001",close=999)
        chart=self.b.get_chart_data("sh.600000",self.days[-1])
        self.assertFalse(chart.empty)
        self.assertTrue((chart["close"]<100).all())
        self.assertEqual(len(chart),30)

    def test_10_sector_cache_returns_independent_copy(self):
        self.insert(code="sh.600000")
        self.insert(code="sh.600001",close=21)
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("INSERT INTO industry_cache(code,name,industry) VALUES(?,?,?)",
                          [("sh.600000","A","电力"),("sh.600001","B","电力")])
        frame=self.b.get_sector_chart_data("电力",self.days[-1])
        self.assertFalse(frame.empty)
        frame.iloc[0,frame.columns.get_loc("close")]=999999
        again=self.b.get_sector_chart_data("电力",self.days[-1])
        self.assertLess(float(again.iloc[0]["close"]),999999)

    def test_11_scan_early_cancellation_does_not_write_signals(self):
        self.insert()
        writes=[]
        self.b.record_signals=lambda *args,**kw:writes.append(True)
        cancel=threading.Event()
        cancel.set()
        result=self.b.scan_strategy("volume_turnover",self.days[-1],False,self.days[-2],
                                    cancel_event=cancel)
        self.assertTrue(result.empty)
        self.assertEqual(writes,[])

    def test_12_empty_stock_history_remains_valid_dataframe(self):
        df=self.b.get_signal_history("sh.600888",self.days[-1])
        self.assertIsInstance(df,pd.DataFrame)
        self.assertTrue(df.empty)

    def test_13_rank_transform_rejects_infinite_and_duplicates(self):
        names=["A","A","B","C","D","E","F","G"]
        values=[math.inf,10,9,8,7,6,5,4]
        self.b._fund_request=lambda *a,**k:pd.DataFrame({"行业":names,"净额":values})
        rows=self.b._fund_complete_snapshot(lambda _:None,Weekend.now())
        self.assertEqual(len(rows),5)
        self.assertEqual(len(set(row[1] for row in rows)),5)
        self.assertTrue(all(math.isfinite(row[2]) for row in rows))

    def test_14_failed_rank_refresh_keeps_complete_previous_snapshot(self):
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("INSERT INTO fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)",
                          [(i,f"Sector{i}",100e8,"2026-10-25 18:00:00","同花顺") for i in range(1,6)])
        before=self.b.load_fund_top5()
        self.b._fund_request=lambda *a,**k: (_ for _ in ()).throw(TimeoutError("outage"))
        with patch.object(mod,"datetime",Weekend),patch.object(mod.time,"sleep",return_value=None):
            with self.assertRaises(RuntimeError):
                self.b.refresh_fund_top5(force=True)
        self.assertEqual(self.b.load_fund_top5(),before)

    def test_15_failed_rank_sqlite_write_does_not_destroy_old_snapshot(self):
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("INSERT INTO fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)",
                          [(i,f"Old{i}",100e8,"2026-10-25 18:00:00","同花顺") for i in range(1,6)])
            c.execute("""CREATE TRIGGER deny_top5 BEFORE INSERT ON fund_top5_snapshot
                      BEGIN SELECT RAISE(ABORT,'database full simulated'); END""")
        original=self.b.load_fund_top5()
        self.b._fund_request=lambda *a,**k:pd.DataFrame({
           "行业":[f"New{i}" for i in range(7)],"净额":[10,9,8,7,6,5,4]})
        with patch.object(mod,"datetime",Weekend),patch.object(mod.time,"sleep",return_value=None):
            with self.assertRaises(RuntimeError):
                self.b.refresh_fund_top5(force=True)
        self.assertEqual(self.b.load_fund_top5(),original)

    def test_16_fund_subprocess_timeout_is_bounded(self):
        import subprocess
        with patch.object(mod.subprocess,"run",side_effect=subprocess.TimeoutExpired("run",1)):
            with self.assertRaises(TimeoutError):
                self.b._fund_request("ths_rank",timeout=1)

    def test_17_fund_snapshot_is_ths_only(self):
        with mod.sqlite_connection(self.b.db_path) as c:
            c.executemany("INSERT INTO fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)",
                          [(i,f"Old{i}",100e8,"2026-10-25 18:00:00","东方财富") for i in range(1,6)])
        self.assertEqual(self.b.load_fund_top5(),([],{}))

    def test_18_utf8_history_payload_contains_no_nan(self):
        self.insert(name="芯片®",vol=lambda i:25000 if i>=30 else 10000)
        hist=self.b.get_signal_history("sh.600000",self.days[-1])
        for p in hist.get("payload",[]):
            import json
            json.loads(p)
            self.assertNotIn("NaN",p)

    def test_19_completeness_does_not_count_infinite_legacy_values(self):
        """Preexisting corrupt-but-readable SQLite values must not imply 100% complete."""
        d=self.days[-1]
        with mod.sqlite_connection(self.b.db_path) as c:
            c.execute("INSERT INTO day_universe(trade_date,code,name,trade_status) VALUES(?,?,?,?)",
                      (d,"sh.600000","A",1))
            c.execute("INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) VALUES(?,?,?,?,?,?,?,?)",
                      ("sh.600000",d,"A",math.inf,100,1,0,2.0))
        state=self.b.update_day_status(d)
        self.assertEqual(state["saved"],0)
        self.assertEqual(state["status"],"partial")
        self.assertNotIn("sh.600000",self.b.get_existing_codes_for_date(d))

if __name__=="__main__":
    unittest.main(verbosity=2)
