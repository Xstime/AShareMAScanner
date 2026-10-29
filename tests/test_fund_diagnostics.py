"""Tests for ranking-only diagnostics (never mistaken for filter-ready snapshots)."""
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
loader=SourceFileLoader("qt_backend_diagnostics_test",str(source))
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

    def tearDown(self):
        self.tmp.cleanup()

    def test_stock_code_parses_decimal_serialization(self):
        self.assertEqual(self.backend._fund_stock_symbol(600001.0),"600001")
        self.assertEqual(self.backend._fund_stock_symbol("000001"),"000001")
        self.assertIsNone(self.backend._fund_stock_symbol("invalid"))

    def test_rank_only_does_not_overwrite_complete_snapshot(self):
        def ranking_but_no_constituents(endpoint,sector="",timeout=20):
            if endpoint == "em_rank":
                return pd.DataFrame([
                    {"名称":f"行业{i}","5日主力净流入-净额":(6-i)*100000000}
                    for i in range(1,6)
                ])
            if endpoint == "ths_rank":
                raise TimeoutError("THS mock timeout")
            raise RuntimeError("constituent API blocked")
        self.backend._fund_request=ranking_but_no_constituents
        notices=[]
        with self.assertRaisesRegex(RuntimeError,"两个来源均未获取完整榜单"):
            self.backend.refresh_fund_top5(force=True,progress=notices.append)
        self.assertTrue(any("排名 5/5 已获取" in msg for msg in notices))
        self.assertTrue(any("成功0、失败5" in msg for msg in notices))
        self.assertEqual(len(self.backend._last_rank_only),5)
        self.assertTrue(self.backend._last_rank_only[0]["ranking_only"])
        self.assertEqual(self.backend._last_rank_only[0]["source"],"东方财富")
        self.assertEqual(self.backend.load_fund_top5(),([],{}))
        self.assertEqual(len(self.backend._fund_last_errors),2)
        self.assertIn("constituent API blocked",self.backend._fund_last_errors[0]["error"])

    def test_both_rank_sources_blocked_have_no_rank_only(self):
        def blocked(endpoint,sector="",timeout=20):
            raise TimeoutError("offline")
        self.backend._fund_request=blocked
        with self.assertRaises(RuntimeError):
            self.backend.refresh_fund_top5(force=True)
        self.assertEqual(self.backend._last_rank_only,[])
        self.assertEqual(len(self.backend._fund_last_errors),2)


if __name__=="__main__":
    unittest.main()
