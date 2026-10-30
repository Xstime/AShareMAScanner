"""Tk safe-stop signal wiring and real backend cancellation without flaky Xvfb clicks.

True window-manager close behavior still requires Windows desktop acceptance.
"""
import inspect
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
import types
import unittest

import pandas as pd

sys.modules.setdefault("baostock", types.ModuleType("baostock"))
source=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.9.pyw"
loader=SourceFileLoader("v129_tk_cancel_checks",str(source))
spec=importlib.util.spec_from_loader(loader.name,loader)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class CancelWiringTests(unittest.TestCase):
    def test_tk_close_signals_backend_and_waits_for_safe_completion(self):
        source=inspect.getsource(mod.run_tk_data_phase)
        self.assertIn("engine_backend.cancel_update()",source)
        self.assertIn('root.protocol("WM_DELETE_WINDOW",abort)',source)
        self.assertIn("except MarketUpdateCancelled as exc:",source)
        self.assertIn('elif kind=="cancelled":',source)
        self.assertIn("root.after(160,root.quit)",source)
        self.assertIn('state["cancel_requested"]',source)
        self.assertIn('state["running"]',source)

    def test_backend_cancellation_prevents_further_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend=mod.BaoStockBackend(Path(tmp)/"market.db")
            backend.init_db()
            date="2026-10-27"
            backend.persist_day_universe(date,pd.DataFrame([
                {"code":"sh.600000","name":"暂停测试","trade_status":1},
                {"code":"sh.600001","name":"暂停测试二","trade_status":1},
            ]))
            backend.cancel_update()
            with self.assertRaises(mod.MarketUpdateCancelled):
                backend.process_trade_date(date,lambda *_:None,80,94)
            with mod.sqlite_connection(backend.db_path) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0],0)

if __name__=="__main__":
    unittest.main(verbosity=2)
