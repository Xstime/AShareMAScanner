"""Regression tests for fast whole-market BaoStock daily updates.

Use real temporary SQLite and exercise parallel-result validation, out-of-order
delivery, interrupted pools, fallbacks, and resumability; never contact upstream.
"""
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import pandas as pd
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
script = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.0.pyw"
loader = SourceFileLoader("v130_market_parallel_tests", str(script))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class FakeStream:
    def __init__(self, items, crash_after=None):
        self.items = iter(items)
        self.crash_after = crash_after
        self.done = 0

    def next(self, timeout=None):
        if self.crash_after is not None and self.done >= self.crash_after:
            raise TimeoutError("injected worker stall")
        self.done += 1
        return next(self.items)


class FakePool:
    def __init__(self, results, crash_after=None):
        self.results, self.crash_after = results, crash_after
        self.closed = self.joined = self.terminated = False

    def imap_unordered(self, fn, jobs, chunksize=1):
        self.jobs = list(jobs)
        assert fn is m._day_pool_fetch
        assert chunksize == 1
        return FakeStream(self.results, self.crash_after)

    def close(self): self.closed = True
    def terminate(self): self.terminated = True
    def join(self): self.joined = True


class FakeContext:
    def __init__(self, pool): self.pool = pool
    def Pool(self, processes, maxtasksperchild):
        assert 2 <= processes <= 4
        assert maxtasksperchild == 400
        return self.pool


class DayParallelTests(unittest.TestCase):
    def setUp(self):
        # The fake pool raises immediately; shorten only the test's stall
        # deadline so a simulated dead worker does not consume 90 seconds.
        old_stall = m.DAILY_WORKER_STALL_SECONDS
        m.DAILY_WORKER_STALL_SECONDS = .15
        self.addCleanup(setattr, m, "DAILY_WORKER_STALL_SECONDS", old_stall)
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = m.BaoStockBackend(Path(self.tmp.name)/"market.db")
        self.backend.init_db()
        self.trade_date = "2026-10-27"
        self.universe = pd.DataFrame([
            dict(code=f"sh.{600000+i:06d}",name=f"个股{i}",trade_status=1)
            for i in range(130)
        ])
        self.backend.persist_day_universe(self.trade_date, self.universe)
        self.notes = []

    def tearDown(self):
        if self.backend._instance_lock_file is not None:
            self.backend._instance_lock_file.close()
        self.tmp.cleanup()

    def results(self, error_code=None):
        all_items = []
        for r in self.universe.itertuples(index=False):
            fields = ["date","code","close","volume","tradestatus","isST","turn"]
            values = [[self.trade_date,r.code,"10.25","1000","1","0","3.2"]]
            err = "injected network issue" if r.code == error_code else ""
            all_items.append((r.code,r.name,fields,values,err))
        return all_items

    def run_parallel(self, results, crash_after=None):
        pool=FakePool(results,crash_after)
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(pool)):
            state=self.backend.process_trade_date(self.trade_date,self.notes.append,80,94)
        return state,pool

    def test_01_parallel_out_of_order_persists_all_rows_and_is_complete(self):
        # Set a fake context but use the real core day-update storage logic.
        pool=FakePool(list(reversed(self.results())))
        def cb(*a):self.notes.append(a)
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(pool)):
            state=self.backend.process_trade_date(self.trade_date,cb,80,94)
        self.assertEqual((state["saved"],state["expected"],state["failed"]),(130,130,0))
        self.assertTrue(pool.closed and pool.joined)
        self.assertFalse(pool.terminated)
        with m.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0],130)
        self.assertTrue(any("预计剩余" in x[1] for x in self.notes))
        self.assertAlmostEqual(self.notes[-1][0],94)

    def test_02_one_failed_fetch_remains_queued_and_resume_skips_129_successes(self):
        err_code="sh.600003"
        p=FakePool(self.results(error_code=err_code))
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(p)):
            state=self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        self.assertEqual((state["saved"],state["failed"]),(129,1))
        calls=[]
        def rescue(code,name,date):
            calls.append(code)
            return [(code,date,name,10.25,1000,1,0,3.2)]
        self.backend.fetch_exact_day_for_stock=rescue
        state=self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        self.assertEqual(calls,[err_code])
        self.assertEqual((state["saved"],state["failed"]),(130,0))

    def test_03_worker_stall_falls_back_without_refetching_completed_rows(self):
        p=FakePool(self.results(),crash_after=25)
        calls=[]
        self.backend.fetch_exact_day_for_stock=lambda code,name,date: (
            calls.append(code) or [(code,date,name,12.,2000.,1,0,4.)]
        )
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(p)):
            state=self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        self.assertEqual((state["saved"],state["failed"]),(130,0))
        self.assertEqual(len(calls),105)
        self.assertTrue(p.terminated and p.joined)

    def test_04_parallel_results_never_accept_another_stock_code_or_date(self):
        bad=self.results()
        code,name,fields,values,_=bad[0]
        bad[0]=(code,name,fields,[[self.trade_date,"sh.999999","99","1000","1","0","2"]],"")
        p=FakePool(bad)
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(p)):
            state=self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        self.assertEqual((state["saved"],state["failed"]),(129,1))
        with m.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM daily WHERE code='sh.999999'").fetchone()[0],0)

    def test_05_all_worker_logins_fail_retries_all_tasks_serially(self):
        out=[(code,name,[],[],"failed login") for code,name,_,_,_ in self.results()]
        p=FakePool(out)
        calls=[]
        self.backend.fetch_exact_day_for_stock=lambda code,name,date: (
            calls.append(code) or [(code,date,name,10.,1000.,1,0,3.)]
        )
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(p)):
            status=self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        self.assertEqual(len(calls),130)
        self.assertEqual((status["saved"],status["failed"]),(130,0))
        self.assertTrue(p.terminated)

    def test_06_second_update_does_not_contact_workers_or_network(self):
        p=FakePool(self.results())
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(p)):
            self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        with patch.object(m.multiprocessing,"get_context",side_effect=AssertionError("unexpected worker")):
            state=self.backend.process_trade_date(self.trade_date,lambda *a:None,80,94)
        self.assertEqual((state["saved"],state["failed"]),(130,0))


    def test_07_safe_stop_commits_downloaded_rows_and_resume_skips_them(self):
        pool = FakePool(self.results())
        def progress(value, message):
            if "25/130" in message:
                self.backend.cancel_update()
        with patch.object(m.multiprocessing, "get_context", return_value=FakeContext(pool)):
            with self.assertRaises(m.MarketUpdateCancelled):
                self.backend.process_trade_date(self.trade_date, progress, 80, 94)
        self.assertTrue(pool.terminated and pool.joined)
        with m.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0], 25)
        self.backend._cancel_update_event.clear()
        # Ensure resume stays offline; only the saved-row logic is being tested.
        self.backend.query_stock_history = lambda *a, **k: None
        missed = []
        def resume(code, name, date):
            missed.append(code)
            return [(code,date,name,10.25,1000,1,0,3.2)]
        self.backend.fetch_exact_day_for_stock = resume
        self.backend.query_stock_history = lambda *args: None  # explicit sequential resume
        state = self.backend.process_trade_date(self.trade_date, lambda *_: None, 80, 94)
        self.assertEqual((state["saved"], state["expected"], state["failed"]), (130,130,0))
        self.assertEqual(len(missed), 105)

    def test_08_network_outage_circuit_breaker_prevents_unbounded_stock_retries(self):
        data = self.results()
        # First 10 are valid, followed by 30 continuous network failures.
        broken = [(*item[:4], "network down" if 10 <= n < 45 else item[4])
                  for n, item in enumerate(data)]
        pool = FakePool(broken)
        with patch.object(m.multiprocessing, "get_context", return_value=FakeContext(pool)):
            with self.assertRaises(m.MarketDataUnavailable):
                self.backend.process_trade_date(self.trade_date, lambda *_: None, 80, 94)
        self.assertTrue(pool.terminated and pool.joined)
        with m.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0], 10)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fetch_queue").fetchone()[0], 25)
        # Next launch with healthy source resumes every missing stock without duplication.
        self.backend.query_stock_history = lambda *a, **k: None
        self.backend.fetch_exact_day_for_stock = lambda code, name, date: [
            (code,date,name,10.25,1000,1,0,3.2)]
        status = self.backend.process_trade_date(self.trade_date, lambda *_: None, 80, 94)
        self.assertEqual((status["saved"], status["failed"]), (130,0))

    def test_09_first_install_fetches_45_history_days_in_parallel(self):
        days=pd.bdate_range(end=self.trade_date,periods=45).strftime("%Y-%m-%d").tolist()
        self.backend.recent_n_trade_dates=lambda end,n:days[-n:]
        result=[]
        for rec in self.universe.itertuples(index=False):
            result.append((rec.code,rec.name,
                ["date","code","close","volume","tradestatus","isST","turn"],
                [[day,rec.code,"10.0","1000","1","0","3.5"] for day in days],""))
        pool=FakePool(list(reversed(result)))
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(pool)):
            self.backend.initialize_missing_histories(
                self.universe,self.trade_date,lambda *a:None,20,66)
        self.assertTrue(pool.closed and pool.joined)
        with m.sqlite_connection(self.backend.db_path) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM daily").fetchone()[0],130*45)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM stock_state WHERE history_ready=1").fetchone()[0],130)
        with patch.object(m.multiprocessing,"get_context",side_effect=AssertionError("duplicate fetch")):
            self.backend.initialize_missing_histories(
                self.universe,self.trade_date,lambda *a:None,20,66)

    def test_10_history_partial_failure_does_not_mark_missing_stock_ready(self):
        days=pd.bdate_range(end=self.trade_date,periods=45).strftime("%Y-%m-%d").tolist()
        self.backend.recent_n_trade_dates=lambda end,n:days[-n:]
        errors_code="sh.600005"
        result=[]
        for rec in self.universe.itertuples(index=False):
            err="isolated BaoStock failure" if rec.code==errors_code else ""
            result.append((rec.code,rec.name,
                ["date","code","close","volume","tradestatus","isST","turn"],
                [[day,rec.code,"10.0","1000","1","0","3.5"] for day in days],err))
        pool=FakePool(result)
        with patch.object(m.multiprocessing,"get_context",return_value=FakeContext(pool)):
            self.backend.initialize_missing_histories(
                self.universe,self.trade_date,lambda *a:None,20,66)
        with m.sqlite_connection(self.backend.db_path) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM init_queue").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM stock_state WHERE history_ready=1").fetchone()[0],129)
        fetched=[]
        def rescue(code,start,end):
            fetched.append(code)
            return pd.DataFrame([dict(date=day,code=code,close="10.0",volume="1000",
                  tradestatus="1",isST="0",turn="3.5") for day in days])
        self.backend.query_stock_history=rescue
        self.backend.initialize_missing_histories(
            self.universe,self.trade_date,lambda *a:None,20,66)
        self.assertEqual(fetched,[errors_code])
        with m.sqlite_connection(self.backend.db_path) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM init_queue").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM daily").fetchone()[0],130*45)

if __name__=="__main__":
    unittest.main(verbosity=2)
