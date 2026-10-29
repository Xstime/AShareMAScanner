"""Display-backed GUI tests; run with xvfb-run on Linux CI."""
import importlib.util
from importlib.machinery import SourceFileLoader
import sys
import tkinter as tk
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.modules['baostock'] = types.ModuleType('baostock')
path=Path(__file__).resolve().parents[1]/'A股MA扫描器_v1.2.6.pyw'
loader=SourceFileLoader('scanner_splash_test',str(path))
spec=importlib.util.spec_from_loader(loader.name,loader)
scanner=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=scanner
spec.loader.exec_module(scanner)


class StartupSplashTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk()
        self.patches=[
            patch.object(scanner,'BaoStockBackend',return_value=object()),
            patch.object(scanner.StockScannerApp,'_display_fund_top5',return_value=None),
            patch.object(scanner.StockScannerApp,'_start_fund_refresh',return_value=None),
            patch.object(scanner.StockScannerApp,'_update_worker',return_value=None),
        ]
        for p in self.patches:
            p.start()
        self.app=scanner.StockScannerApp(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        try:
            if self.root.winfo_exists():self.root.destroy()
        finally:
            for p in reversed(self.patches):
                p.stop()

    def test_main_window_hidden_until_complete(self):
        self.assertEqual(self.root.state(),'withdrawn')
        self.assertTrue(self.app.splash_window.winfo_exists())
        self.app._set_progress(42,'正在补齐本地行情')
        self.assertEqual(self.app.splash_message_var.get(),'正在补齐本地行情')
        self.assertEqual(self.app.splash_percent_label.cget('text'),'42%')
        done=SimpleNamespace(scan_date='2026-10-29',completeness=100.0,
                             saved=100,expected=100,warning='',
                             previous_trade_date='2026-10-28')
        self.app._handle_update_done(done)
        self.assertFalse(self.app._startup_loading)
        self.assertIsNone(self.app.splash_window)
        self.assertEqual(self.root.state(),'normal')

    def test_failure_remains_in_splash_and_retry(self):
        self.app._busy=True
        self.app._handle_error('模拟网络异常','mock traceback')
        self.assertEqual(self.root.state(),'withdrawn')
        self.assertTrue(self.app._startup_loading)
        self.assertEqual(self.app.splash_retry_button.winfo_manager(),'pack')
        self.assertIn('模拟网络异常',self.app.splash_message_var.get())
        self.app.start_update()
        self.assertEqual(self.app.splash_retry_button.winfo_manager(),'')
        self.assertTrue(self.app._busy)


if __name__=='__main__':
    unittest.main()
