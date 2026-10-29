"""4:3 Tkinter workspace integration checks on an Xvfb display."""
from importlib.machinery import SourceFileLoader
import importlib.util
import sys
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

sys.modules['baostock'] = types.ModuleType('baostock')
script=Path(__file__).resolve().parents[1]/'A股MA扫描器_v1.2.8.pyw'
loader=SourceFileLoader('ma43_desktop_test',str(script))
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)


class DesktopLayoutTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk()
        self.mocks=[
            patch.object(module,'BaoStockBackend',return_value=types.SimpleNamespace(
                get_chart_data=lambda *args,**kwargs:pd.DataFrame())),
            patch.object(module.StockScannerApp,'_update_worker',return_value=None),
        ]
        for item in self.mocks:item.start()
        self.app=module.StockScannerApp(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        try:self.root.destroy()
        finally:
            for item in reversed(self.mocks):item.stop()

    def test_real_three_column_workbench(self):
        # 启动加载窗口尚未完成时，主界面必须隐藏。
        self.assertEqual(self.root.state(), 'withdrawn')
        # Tk hides the scanner at startup; geometry reports 1x1 until it is mapped.
        self.app._enter_scanner()
        self.root.update_idletasks()
        self.assertEqual(self.root.geometry().split('+')[0],'1080x810')
        self.assertEqual(self.app.workspace.winfo_manager(),'grid')
        self.assertIs(self.app.center_panel.master,self.app.workspace)
        self.assertIs(self.app.inspector_panel.master,self.app.workspace)
        self.assertIs(self.app.tree.master.master,self.app.center_panel)
        self.assertEqual(self.app.inspector_chart.master,self.app.inspector_panel)
        self.assertEqual(len(self.app.strategy_buttons),7)
        self.assertEqual(len(self.app.strategy_button_by_key),7)
        self.assertEqual(len(self.app._fund_card_labels),5)
        self.assertEqual(self.root.state(),'normal')

    def test_strategy_sidebar_highlight_and_parameters(self):
        self.app.current_strategy_key='ma5_turn_up'
        self.app._refresh_strategy_selection()
        self.assertEqual(self.app.strategy_button_by_key['ma5_turn_up'].cget('style'),'SelectedNav.TButton')
        self.assertEqual(self.app.parameter_row.winfo_manager(),'')
        self.app.current_strategy_key='volume_turnover'
        self.app._refresh_strategy_selection()
        self.assertEqual(self.app.parameter_row.winfo_manager(),'pack')
        self.assertEqual(self.app.strategy_button_by_key['volume_turnover'].cget('style'),'SelectedNav.TButton')

    def test_selection_drives_actual_inspector(self):
        self.app._populate_tree('ma5_turn_up',pd.DataFrame([{
            '代码':'600001','名称':'测试股票','板块':'电子',
            '触发日':'2026-10-29','收盘价':11.25,
            '当日涨幅%':2.5,'MA5':10.5,'昨日MA5':10.2,
            'MA5上拐幅度%':1.2,'放量倍数':2.1,'换手率%':3.2,
            '_code_full':'sh.600001'}]))
        iid=self.app.tree.get_children()[0]
        self.app.tree.selection_set(iid)
        self.app._on_stock_selection()
        self.assertEqual(self.app.inspector_name_var.get(),'测试股票')
        self.assertEqual(self.app.inspector_price_var.get(),'11.25')
        self.assertIn('2.1',self.app.inspector_metric_vars[0].get())
        self.assertEqual(self.app.inspector_metric_vars[2].get(),'2026-10-29')

    def test_old_splash_still_blocks_scanner_until_ready(self):
        self.assertTrue(self.app.splash_window.winfo_exists())
        self.assertTrue(self.app._startup_loading)
        self.app._enter_scanner()
        self.assertEqual(self.root.state(),'normal')
        self.assertIsNone(self.app.splash_window)


if __name__=='__main__':
    unittest.main()
