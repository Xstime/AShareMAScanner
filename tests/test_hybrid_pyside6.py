"""Real PySide6 4:3 UI and already-completed Tk startup handoff."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pandas as pd
from PySide6.QtWidgets import QApplication,QSplitter,QLabel,QMainWindow

sys.modules.setdefault("baostock",types.ModuleType("baostock"))
file=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("hybrid_qt_test",str(file))
spec=importlib.util.spec_from_loader(loader.name,loader)
ui=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=ui
spec.loader.exec_module(ui)


class HybridQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        self.win=ui.ScannerWindow(demo=True)
        self.win.show()
        self.qt.processEvents()

    def tearDown(self):
        self.win.close()
        self.qt.processEvents()

    def test_real_qt_window_ratio_and_three_columns(self):
        self.assertIsInstance(self.win,QMainWindow)
        self.assertEqual((self.win.width(),self.win.height()),(1120,840))
        self.assertAlmostEqual(self.win.width()/self.win.height(),4/3,places=5)
        self.assertEqual(self.win.page.currentIndex(),1)
        split=self.win.page.currentWidget().findChildren(QSplitter)
        self.assertEqual(len(split),1)
        self.assertEqual(split[0].count(),3)
        self.assertEqual(len(self.win.buttons),7)
        self.assertEqual(len(self.win.fund_cards),5)

    def test_only_readonly_top5_fund_cards(self):
        self.assertTrue(all(isinstance(x,QLabel) for x in self.win.fund_cards))
        self.assertFalse(hasattr(self.win,"selected_fund"))
        count=self.win.table.rowCount()
        self.win._render_funds()
        self.assertEqual(self.win.table.rowCount(),count)

    def test_strategy_navigation_and_stock_chart(self):
        self.win._select_strategy("volume_turnover")
        self.assertFalse(self.win.volume_options.isHidden())
        self.win._select_strategy("ma5_turn_up")
        self.assertTrue(self.win.volume_options.isHidden())
        self.win.query.setText("演示科技")
        self.qt.processEvents()
        self.assertEqual(self.win.table.rowCount(),1)
        self.assertEqual(self.win.stock_name.text(),"演示科技")
        self.assertFalse(self.win.chart.data.empty)

    def test_prepared_mode_does_not_update_market_again(self):
        result=types.SimpleNamespace(
            scan_date="2026-10-29", previous_trade_date="2026-10-28",
            completeness=100., warning="",expected=5000,saved=5000)
        backend=types.SimpleNamespace(
            load_fund_top5=lambda:([],{}),
            update_all=lambda cb: self.fail("should not re-fetch in Qt"))
        with patch.object(ui.ScannerWindow,"_rerun_strategy") as scan, \
             patch.object(ui.ScannerWindow,"start_fund_refresh") as funds:
            prepared=ui.ScannerWindow(demo=False,prepared_backend=backend,
                                      prepared_result=result)
            prepared.show()
            self.qt.processEvents()
            self.assertIs(prepared.backend,backend)
            self.assertIs(prepared.update_result,result)
            self.assertEqual(prepared.page.currentIndex(),1)
            self.assertIn("2026-10-29",prepared.header_status.text())
            scan.assert_called_once()
            funds.assert_called_once()
            prepared.close()


if __name__=="__main__":
    unittest.main()
