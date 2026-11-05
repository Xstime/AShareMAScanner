"""Release guard: v1.3.7 matches tested dev logic apart from intended release changes.

This test does not use the network, modify a user file or inspect the actual Desktop.
"""
import os
from pathlib import Path
import unittest
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
DEV=ROOT/"A股MA扫描器_dev_AKShare.pyw"
PROD=ROOT/"A股MA扫描器_v1.3.7.pyw"

class ReleaseIntegrity(unittest.TestCase):
    def test_release_matches_approved_dev_changes(self):
        dev=DEV.read_text(encoding="utf-8")
        prod=PROD.read_text(encoding="utf-8")
        expected=dev.replace('APP_TITLE = "A股 MA 扫描器 · DEV AKShare"',
                             'APP_TITLE = "A股 MA 扫描器"')
        expected=expected.replace('APP_VERSION = "1.3.6"',
                                  'APP_VERSION = "1.3.7"')
        expected=expected.replace(
            'if False and not _should_skip_startup_update(sys.argv[1:]):',
            'if not _should_skip_startup_update(sys.argv[1:]):')
        expected=expected.replace(
            'if (False and not args.demo and not args.screenshot and not args.skip_startup_update',
            'if (not args.demo and not args.screenshot and not args.skip_startup_update')
        self.assertEqual(prod,expected,"Production source must equal audited dev source + 4 declared release changes")

    def test_only_latest_trading_day_and_excel_remain(self):
        content=PROD.read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "1.3.7"', content)
        self.assertIn('def export_strategy_xlsx(', content)
        self.assertIn('"a_share_akshare_hfq.db"', content)
        self.assertNotIn('self.show_previous', content)
        self.assertNotIn('import baostock as bs', content)
        self.assertIn('self.strategy, self.date, False', content)

    def test_normal_launch_auto_updates_but_demo_is_skipped(self):
        source=PROD.read_text(encoding="utf-8")
        self.assertIn('if not _should_skip_startup_update(sys.argv[1:]):',source)
        self.assertIn('if (not args.demo and not args.screenshot and not args.skip_startup_update',source)
        self.assertNotIn('if False and not _should_skip_startup_update(',source)

    def test_compiles_without_fetching_quotes(self):
        compile(PROD.read_bytes(),str(PROD),"exec")

if __name__=="__main__":
    unittest.main()
