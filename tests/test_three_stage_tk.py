"""Second-stage Tk data update must finish and close before Qt is created."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.modules.setdefault("baostock",types.ModuleType("baostock"))
file=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"
loader=SourceFileLoader("hybrid_tk_test",str(file))
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)


class HybridTkTests(unittest.TestCase):
    def test_update_window_completes_and_returns_existing_backend(self):
        events=[]
        result=types.SimpleNamespace(scan_date="2026-10-29",completeness=100.)
        def update(cb):
            cb(5,"连接 BaoStock")
            cb(37,"历史缓存准备 · 70/500 · sh.600000")
            cb(92,"正在更新 2026-10-29 · 500/500")
            cb(100,"数据检查完成")
            events.append("updated")
            return result
        fake_backend=types.SimpleNamespace(update_all=update)
        self.assertIsNone(module.__dict__.get("_qt_app_created"))
        value=module.run_tk_data_phase(backend=fake_backend)
        self.assertIsNotNone(value)
        self.assertIs(value[0],fake_backend)
        self.assertIs(value[1],result)
        self.assertEqual(events,["updated"])

    def test_dependency_setup_mentions_required_pyside6(self):
        import inspect
        source=inspect.getsource(module._bootstrap_dependencies)
        self.assertIn('"PySide6": ("PySide6", True)',source)


if __name__=="__main__":
    unittest.main()
