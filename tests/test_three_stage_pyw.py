"""Qt UI and fund-flow tests of the assembled self-contained three-stage .pyw."""
from __future__ import annotations
import importlib.util
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime as RealDateTime
from importlib.machinery import SourceFileLoader
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication,QSplitter,QLabel
import pandas as pd

APP_PATH=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("scanner_three_stage_test",str(APP_PATH))
spec=importlib.util.spec_from_loader(loader.name,loader)
app=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=app
spec.loader.exec_module(app)

class AfterClose(RealDateTime):
    @classmethod
    def now(cls,tz=None):
        return cls(2026,10,29,20,30,tzinfo=tz)
app.datetime=AfterClose

class ThreeStageUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        self.window=app.ScannerWindow(demo=True)
        self.window.show()
        self.qt.processEvents()

    def tearDown(self):
        self.window.close()
        self.qt.processEvents()

    def test_exactly_one_qt_workspace_after_two_tk_stages(self):
        self.assertTrue(callable(app.stage1_dependencies))
        self.assertTrue(callable(app.stage2_update_market))
        self.assertEqual(self.window.page.count(),1)
        self.assertEqual(self.window.page.currentIndex(),0)
        self.assertEqual(self.window.size().width(),1120)
        self.assertEqual(self.window.size().height(),840)
        split=self.window.page.currentWidget().findChildren(QSplitter)
        self.assertEqual(len(split),1)
        self.assertEqual(split[0].count(),3)

    def test_seven_strategies_and_read_only_top5(self):
        self.assertEqual(len(self.window.buttons),7)
        self.assertEqual(len(self.window.fund_cards),5)
        self.assertTrue(all(isinstance(card,QLabel) for card in self.window.fund_cards))
        rows=self.window.table.rowCount()
        self.assertGreater(rows,0)
        self.assertIn("亿",self.window.fund_cards[0].text())
        self.window._render_funds()
        self.assertEqual(self.window.table.rowCount(),rows)
        self.window._select_strategy("volume_turnover")
        self.assertFalse(self.window.volume_options.isHidden())
        self.window._select_strategy("ma5_turn_up")
        self.assertTrue(self.window.volume_options.isHidden())

    def test_stock_detail_and_chart(self):
        self.window.query.setText("演示科技")
        self.assertEqual(self.window.table.rowCount(),1)
        self.qt.processEvents()
        self.assertEqual(self.window.stock_name.text(),"演示科技")
        self.assertFalse(self.window.chart.data.empty)

class FundOnlyTHSTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.backend=app.BaoStockBackend(Path(self.temp.name)/"prices.db")
        self.backend.init_db()
        self.calls=[]

    def tearDown(self):
        self.temp.cleanup()

    def only_ths(self,endpoint,sector="",timeout=20):
        self.calls.append(endpoint)
        if endpoint!="ths_rank":
            raise AssertionError("Unexpected network endpoint "+endpoint)
        return pd.DataFrame([{"行业":f"示例板块{i}","净额":float(6-i)} for i in range(1,6)])

    def test_only_ths_called_and_cached(self):
        self.backend._fund_request=self.only_ths
        msg=self.backend.refresh_fund_top5(force=True)
        self.assertEqual(self.calls,["ths_rank"])
        self.assertIn("同花顺",msg)
        rank,members=self.backend.load_fund_top5()
        self.assertEqual(len(rank),5)
        self.assertEqual(members,{})
        self.assertEqual(rank[0]["net_yuan"],500_000_000)
        with sqlite3.connect(self.backend.db_path) as conn:
            self.assertEqual(conn.execute("select count(*) from fund_top5_member").fetchone()[0],0)

    def test_eastmoney_legacy_cache_not_displayed(self):
        with sqlite3.connect(self.backend.db_path) as conn:
            conn.execute("insert into fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) values(1,'旧东财',100,'2026-10-29 20:00','东方财富')")
        self.assertEqual(self.backend.load_fund_top5(),([],{}))

    def test_error_preserves_ths_cache(self):
        self.backend._fund_request=self.only_ths
        self.backend.refresh_fund_top5(force=True)
        cached=self.backend.load_fund_top5()
        self.backend._fund_request=lambda *a,**k: (_ for _ in ()).throw(TimeoutError("test timeout"))
        with self.assertRaisesRegex(RuntimeError,"同花顺"):
            self.backend.refresh_fund_top5(force=True)
        self.assertEqual(cached,self.backend.load_fund_top5())
        self.assertEqual(len(self.backend._fund_last_errors),1)


if __name__=="__main__":
    unittest.main()
