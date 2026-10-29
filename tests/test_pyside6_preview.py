"""Test the actual PySide6 preview using synthetic data and an offscreen display."""
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QSplitter, QLabel

source=Path(__file__).resolve().parents[1]/"A股MA扫描器_PySide6_预览.pyw"
loader=SourceFileLoader("pyside6_preview_test",str(source))
spec=importlib.util.spec_from_loader(loader.name,loader)
ui=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=ui
spec.loader.exec_module(ui)


class QtPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        self.window=ui.ScannerWindow(demo=True)
        self.window.show()
        self.qt.processEvents()

    def tearDown(self):
        self.window.close()
        self.qt.processEvents()

    def test_real_43_layout_and_data(self):
        self.assertEqual(self.window.width(),1120)
        self.assertEqual(self.window.height(),840)
        self.assertEqual(self.window.page.currentIndex(),1)
        self.assertEqual(len(self.window.buttons),7)
        self.assertEqual(len(self.window.fund_cards),5)
        self.assertEqual(self.window.table.columnCount(),7)
        self.assertGreater(self.window.table.rowCount(),0)
        self.assertFalse(self.window.chart.data.empty)
        split=self.window.page.currentWidget().findChildren(QSplitter)
        self.assertEqual(len(split),1)
        self.assertEqual(split[0].count(),3)
        self.assertIn("演示",self.window.header_status.text())

    def test_strategies_still_work_but_fund_cards_are_display_only(self):
        count=self.window.table.rowCount()
        self.assertTrue(all(isinstance(card,QLabel) for card in self.window.fund_cards))
        self.assertIn("亿",self.window.fund_cards[0].text())
        self.assertFalse(hasattr(self.window,"selected_fund"))
        self.window._render_funds()
        self.assertEqual(self.window.table.rowCount(),count)
        self.window._select_strategy("volume_turnover")
        self.assertFalse(self.window.volume_options.isHidden())
        self.window._select_strategy("ma5_turn_up")
        self.assertTrue(self.window.volume_options.isHidden())

    def test_search_and_stock_detail(self):
        self.window.query.setText("演示科技")
        self.assertEqual(self.window.table.rowCount(),1)
        self.window.table.selectRow(0)
        self.qt.processEvents()
        self.assertEqual(self.window.stock_name.text(),"演示科技")
        self.assertFalse(self.window.chart.data.empty)
        self.window.clear_filters()
        self.assertGreater(self.window.table.rowCount(),1)


if __name__=="__main__":
    unittest.main()
