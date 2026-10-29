"""Offline regression checks for the startup progress visualizer."""
import importlib.util
from importlib.machinery import SourceFileLoader
import sys
import types
import unittest
from pathlib import Path

sys.modules['baostock'] = types.ModuleType('baostock')
path=Path(__file__).resolve().parents[1]/'A股MA扫描器_v1.2.6.pyw'
loader=SourceFileLoader('progress_visualizer_test',str(path))
spec=importlib.util.spec_from_loader(loader.name,loader)
scanner=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=scanner
spec.loader.exec_module(scanner)


class ProgressDescriptionTests(unittest.TestCase):
    def test_all_stages_are_defined(self):
        self.assertEqual(len(scanner.UPDATE_PHASES),8)
        self.assertEqual(scanner.UPDATE_PHASES[0][1],0)
        self.assertEqual(scanner.UPDATE_PHASES[-1][2],100)

    def test_first_stock_is_not_counted_as_completed(self):
        item=scanner.describe_update_progress(80.0,'更新 2026-10-29 · 1/5000 · 600000')
        self.assertEqual(item['phase'],4)
        self.assertEqual(item['completed'],0)
        self.assertEqual(item['current'],1)
        self.assertEqual(item['stock'],'600000')
        self.assertEqual(item['fraction'],0.0)

    def test_progress_in_daily_increment(self):
        item=scanner.describe_update_progress(86.9,'更新 2026-10-29 · 248/5000 · 000001')
        self.assertEqual(item['phase'],4)
        self.assertEqual(item['completed'],247)
        self.assertEqual(item['total'],5000)
        self.assertAlmostEqual(item['fraction'],247/5000)
        self.assertAlmostEqual(item['overall'],86.9)

    def test_history_and_failed_day_stages(self):
        self.assertEqual(scanner.describe_update_progress(13,'补历史失败 7/10 · 600001')['phase'],1)
        self.assertEqual(scanner.describe_update_progress(30,'初始化历史 12/100 · 600001')['phase'],2)
        self.assertEqual(scanner.describe_update_progress(72,'更新 2026-10-28 · 1/50 · 600001')['phase'],3)
        self.assertEqual(scanner.describe_update_progress(95,'补换手率 4/12 · 000001')['phase'],5)

    def test_no_new_dates_is_complete_stage_not_fake_count(self):
        item=scanner.describe_update_progress(94,'没有新的交易日')
        self.assertEqual(item['phase'],4)
        self.assertEqual(item['fraction'],1.0)
        self.assertIsNone(item['total'])

    def test_final_phase_and_range_limits(self):
        self.assertEqual(scanner.describe_update_progress(100,'数据检查完成')['phase'],7)
        self.assertEqual(scanner.describe_update_progress(100,'数据检查完成')['fraction'],1)
        self.assertEqual(scanner.describe_update_progress(-10,'开始检查数据')['overall'],0)
        self.assertEqual(scanner.describe_update_progress(300,'数据检查完成')['overall'],100)


if __name__=='__main__':
    unittest.main()
