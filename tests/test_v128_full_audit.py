"""Independent executable audit of withdrawn v1.2.8 against v1.2.6 features."""
import os,sys,sqlite3,unittest,tempfile,inspect,types,importlib.util
from pathlib import Path
from importlib.machinery import SourceFileLoader
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pandas as pd
from PySide6.QtWidgets import QApplication,QLineEdit
sys.modules.setdefault("baostock",types.ModuleType("baostock"))
p=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("full_audit_module",str(p))
spec=importlib.util.spec_from_loader(loader.name,loader)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class BackendAudit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.b=m.BaoStockBackend(Path(self.tmp.name)/"market.db")
        self.b.init_db()
        self.days=pd.date_range("2026-08-17",periods=30,freq="B").strftime("%Y-%m-%d").tolist()
        with sqlite3.connect(self.b.db_path) as c:
            c.executemany("INSERT INTO daily(code,trade_date,name,close,volume,trade_status,is_st,turnover) VALUES(?,?,?,?,?,?,?,?)",
                [("sh.600000",d,"测试银行",10+i*.1,25000 if i==29 else 10000,1,0,3.5) for i,d in enumerate(self.days)])
    def tearDown(self):self.tmp.cleanup()
    def test_storage_chart_and_filter(self):
        df=self.b.get_chart_data("sh.600000",self.days[-1])
        self.assertTrue({"MA5","MA10","MA20"}.issubset(df.columns))
        self.assertGreater(len(df),0)
        f=m.RangeFilter(1.5,3,2,6)
        self.assertTrue(f.matches({"volume":25000,"VOL5_PREV":10000,"turnover":3.5}))
        self.assertFalse(f.matches({"volume":45000,"VOL5_PREV":10000,"turnover":3.5}))
    def test_seven_real_strategy_calls(self):
        with sqlite3.connect(self.b.db_path) as c:
            raw=pd.read_sql_query("SELECT * FROM daily ORDER BY trade_date",c)
        self.b._load_scan_data=lambda date:raw.copy()
        self.b.get_industry_map=lambda:{"sh.600000":"测试行业"}
        self.b.get_sector_strategy_status=lambda **kw:"未触发"
        self.b.record_signals=lambda *a,**kw:None
        self.assertEqual(len(m.STRATEGIES),7)
        for key,_,_ in m.STRATEGIES:
            with self.subTest(key=key):
                x=self.b.scan_strategy(key,self.days[-1],False,self.days[-2],m.RangeFilter())
                self.assertIsInstance(x,pd.DataFrame)
        x=self.b.scan_strategy("volume_turnover",self.days[-1],False,self.days[-2],m.RangeFilter(1.5,3,3,5))
        self.assertEqual(len(x),1)
    def test_nonempty_stock_history_must_not_crash(self):
        self.assertIsInstance(self.b.get_signal_history("sh.600000",self.days[-1]),pd.DataFrame)
    def test_legacy_eastmoney_snapshot_not_shown(self):
        with sqlite3.connect(self.b.db_path) as c:
            c.executemany("INSERT INTO fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)",
                [(i,"legacy",1e8,"2026-10-28 18:00:00","东方财富") for i in range(1,6)])
        rows,_=self.b.load_fund_top5()
        self.assertEqual(rows,[],"THS-only UI must never display Eastmoney legacy cache")

class GuiParityAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.w=m.ScannerWindow(demo=True)
        self.w.show()
        self.qt.processEvents()
    def tearDown(self):
        self.w.close()
        self.qt.processEvents()
    def test_seven_strategy_buttons_and_five_fund_cards(self):
        self.assertEqual(len(self.w.buttons),7)
        self.assertEqual(len(self.w.fund_cards),5)
    def test_real_update_check_button(self):
        self.assertIn("fetch_latest_release(",inspect.getsource(m.ScannerWindow._show_release_info))
    def test_four_parameter_bounds(self):
        self.w._select_strategy("volume_turnover")
        self.assertGreaterEqual(len(self.w.volume_options.findChildren(QLineEdit)),4)
    def test_price_change_bounds(self):
        source=inspect.getsource(m.ScannerWindow._make_workspace)
        self.assertTrue("涨幅" in source and source.count("涨幅")>=2)
    def test_industry_signals_and_charts_accessible(self):
        source=inspect.getsource(m.ScannerWindow)
        self.assertIn("get_sector_chart_data",source)
        self.assertIn("get_sector_strategy_status",source)
    def test_specific_columns_for_convergence_strategy(self):
        self.w._select_strategy("ma_convergence_up")
        cols=[self.w.table.horizontalHeaderItem(i).text() for i in range(self.w.table.columnCount())]
        self.assertIn("今日发散度%",cols)
    def test_history_shows_streak_and_params(self):
        s=inspect.getsource(m.ScannerWindow._history_dialog)
        self.assertIn("streak",s)
        self.assertIn("filter_key",s)
    def test_history_uses_active_filters(self):
        self.assertNotIn("self.engine.RangeFilter()",inspect.getsource(m.ScannerWindow._history_dialog))
    def test_full_chart_has_volume_and_turnover(self):
        s=inspect.getsource(m.ScannerWindow._full_chart_dialog)
        self.assertIn("volume",s)
        self.assertIn("turnover",s)
    def test_scan_cancel_signal(self):
        self.assertIn("cancel_event",inspect.getsource(m.ScanWorker))
    def test_clear_stock_clears_selection_state(self):
        self.assertIsNotNone(getattr(self.w,"selected_stock",None))
        self.w._clear_stock()
        self.assertIsNone(getattr(self.w,"selected_stock",None))
if __name__=="__main__":unittest.main(verbosity=2)
