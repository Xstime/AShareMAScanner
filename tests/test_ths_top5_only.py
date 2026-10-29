"""Single-file v1.2.8 stock scanner: Tonghuashun-only sector rankings."""
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime as RealDateTime
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch
import pandas as pd

sys.modules["baostock"]=types.ModuleType("baostock")
file=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("ma128_backend_tests",str(file))
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)


class AfterClose(RealDateTime):
    @classmethod
    def now(cls,tz=None):
        return cls(2026,10,29,20,30,tzinfo=tz)


class TonghuashunRankTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.backend=module.BaoStockBackend(Path(self.temp.name)/"data.db")
        self.backend.init_db()
        self.calls=[]
        self.fake_now=patch.object(module,"datetime",AfterClose)
        self.fake_sleep=patch.object(module.time,"sleep",return_value=None)
        self.fake_now.start()
        self.fake_sleep.start()

    def tearDown(self):
        self.fake_sleep.stop()
        self.fake_now.stop()
        self.temp.cleanup()

    def ranking(self,endpoint,sector="",timeout=20):
        self.calls.append((endpoint,sector))
        if endpoint!="ths_rank":
            raise AssertionError("Unexpected endpoint: "+str(endpoint))
        return pd.DataFrame([
            {"行业":n,"净额":v} for n,v in
            [("证券",3.02),("电池",14.53),("白色家电",3.01),("银行",13.5),("保险",2.02)]
        ])

    def test_single_source_converts_billion_yuan_and_keeps_order(self):
        self.backend._fund_request=self.ranking
        notes=[]
        result=self.backend.refresh_fund_top5(force=True,progress=notes.append)
        rows,members=self.backend.load_fund_top5()
        self.assertEqual([r["name"] for r in rows],["电池","银行","证券","白色家电","保险"])
        self.assertEqual(rows[0]["net_yuan"],1453000000)
        self.assertTrue(all(r["source"]=="同花顺" for r in rows))
        self.assertEqual(members,{})
        self.assertEqual(self.calls,[("ths_rank","")])
        self.assertIn("同花顺",result)
        self.assertTrue(any("5/5" in m for m in notes))
        with module.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("select count(*) from fund_top5_member").fetchone()[0],0)

    def test_retries_once_and_preserves_old_cache_on_failure(self):
        self.backend._fund_request=self.ranking
        self.backend.refresh_fund_top5(force=True)
        original=self.backend.load_fund_top5()
        calls=[]
        def fail(endpoint,sector="",timeout=20):
            calls.append(endpoint)
            raise TimeoutError("network dropped")
        self.backend._fund_request=fail
        with self.assertRaisesRegex(RuntimeError,"同花顺五日资金TOP5排名刷新失败"):
            self.backend.refresh_fund_top5(force=True)
        self.assertEqual(calls,["ths_rank","ths_rank"])
        self.assertEqual(self.backend.load_fund_top5(),original)

    def test_caches_today_data_without_new_calls(self):
        self.backend._fund_request=self.ranking
        self.backend.refresh_fund_top5(force=True)
        self.calls.clear()
        self.assertIn("缓存",self.backend.refresh_fund_top5(force=False))
        self.assertEqual(self.calls,[])

    def test_rejects_invalid_fields_and_keeps_cache(self):
        self.backend._fund_request=self.ranking
        self.backend.refresh_fund_top5(force=True)
        prior=self.backend.load_fund_top5()
        self.backend._fund_request=lambda *a,**k: pd.DataFrame({"错误字段":[1,2,3,4,5]})
        with self.assertRaises(RuntimeError):
            self.backend.refresh_fund_top5(force=True)
        self.assertEqual(self.backend.load_fund_top5(),prior)

    def test_clears_members_left_by_old_versions(self):
        self.backend._fund_request=self.ranking
        with module.sqlite_connection(self.backend.db_path) as conn:
            conn.execute("INSERT INTO fund_top5_member VALUES (?,?)",(1,"600001"))
        self.backend.refresh_fund_top5(force=True)
        with module.sqlite_connection(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("select count(*) from fund_top5_member").fetchone()[0],0)

    def test_rank_script_contains_no_other_providers_or_members(self):
        self.assertIn("stock_fund_flow_industry",self.backend.FUND_CHILD)
        self.assertNotIn("stock_sector_fund_flow_rank",self.backend.FUND_CHILD)
        self.assertNotIn("stock_board_industry_cons",self.backend.FUND_CHILD)
        with self.assertRaises(ValueError):
            self.backend._fund_request("em_rank")


if __name__=="__main__":
    unittest.main()
