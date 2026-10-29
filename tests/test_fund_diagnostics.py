"""TOP5 now ranks sectors only. No constituent requests or stock filtering."""
from datetime import datetime as RealDateTime
from importlib.machinery import SourceFileLoader
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
import pandas as pd

sys.modules["baostock"] = types.ModuleType("baostock")
source = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.2.7.pyw"
loader=SourceFileLoader("qt_backend_rank_only_test",str(source))
spec=importlib.util.spec_from_loader(loader.name,loader)
engine=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=engine
spec.loader.exec_module(engine)


class AfterClose(RealDateTime):
    @classmethod
    def now(cls,tz=None):
        return cls(2026,10,29,20,30,tzinfo=tz)
engine.datetime = AfterClose


class RankOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"prices.db"
        self.backend=engine.BaoStockBackend(self.path)
        self.backend.init_db()
        self.requests=[]

    def tearDown(self):
        self.tmp.cleanup()

    def provider(self,endpoint,sector="",timeout=20):
        self.requests.append((endpoint,sector))
        if endpoint=="em_rank":
            return pd.DataFrame([
                {"名称":f"东方行业{i}","5日主力净流入-净额":(6-i)*100000000}
                for i in range(1,6)])
        if endpoint=="ths_rank":
            return pd.DataFrame([
                {"行业":f"同花行业{i}","净额":(6-i)*1.5}
                for i in range(1,6)])
        raise AssertionError("No constituent endpoint should be requested: "+endpoint)

    def test_rank_only_is_saved_and_never_requests_constituents(self):
        self.backend._fund_request=self.provider
        messages=[]
        result=self.backend.refresh_fund_top5(force=True,progress=messages.append)
        rows,members=self.backend.load_fund_top5()
        self.assertEqual(len(rows),5)
        self.assertEqual(members,{})
        self.assertEqual(rows[0]["source"],"东方财富")
        self.assertEqual(rows[0]["net_yuan"],500000000)
        self.assertEqual(self.requests,[("em_rank","")])
        self.assertTrue(any("排名获取成功" in m for m in messages))
        self.assertIn("TOP5",result)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fund_top5_member").fetchone()[0],0)

    def test_fallback_to_ths_ranking_without_members(self):
        def request(endpoint,sector="",timeout=20):
            if endpoint=="em_rank":
                self.requests.append((endpoint,sector))
                raise TimeoutError("eastmoney unavailable")
            return self.provider(endpoint,sector,timeout)
        self.backend._fund_request=request
        result=self.backend.refresh_fund_top5(force=True)
        rows,members=self.backend.load_fund_top5()
        self.assertEqual(rows[0]["source"],"同花顺")
        self.assertEqual(rows[0]["net_yuan"],750000000)
        self.assertEqual(members,{})
        self.assertEqual(self.requests,[("em_rank",""),("ths_rank","")])
        self.assertIn("同花顺",result)

    def test_today_cache_needs_no_members(self):
        self.backend._fund_request=self.provider
        self.backend.refresh_fund_top5(force=True)
        self.requests.clear()
        self.assertIn("缓存",self.backend.refresh_fund_top5(force=False))
        self.assertEqual(self.requests,[])

    def test_failed_sources_preserve_previous_rankings(self):
        self.backend._fund_request=self.provider
        self.backend.refresh_fund_top5(force=True)
        before=self.backend.load_fund_top5()
        self.backend._fund_request=lambda *a,**k: (_ for _ in ()).throw(TimeoutError("offline"))
        with self.assertRaisesRegex(RuntimeError,"两个来源的行业资金排名"):
            self.backend.refresh_fund_top5(force=True)
        self.assertEqual(self.backend.load_fund_top5(),before)
        self.assertEqual(len(self.backend._fund_last_errors),2)

    def test_existing_member_rows_are_cleared_on_refresh(self):
        self.backend._fund_request=self.provider
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO fund_top5_member VALUES(1,'600001')")
        self.backend.refresh_fund_top5(force=True)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fund_top5_member").fetchone()[0],0)
        self.assertEqual(self.backend.load_fund_top5()[1],{})

    def test_bad_field_response_falls_back(self):
        def request(endpoint,sector="",timeout=20):
            if endpoint=="em_rank":
                return pd.DataFrame({"unexpected":[1,2,3,4,5]})
            return self.provider(endpoint,sector,timeout)
        self.backend._fund_request=request
        result=self.backend.refresh_fund_top5(force=True)
        self.assertIn("同花顺",result)


if __name__=="__main__":
    unittest.main()
