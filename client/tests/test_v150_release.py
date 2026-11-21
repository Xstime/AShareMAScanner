"""v1.5.0 default VPS behavior and release source invariant tests."""
import ast
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
from remote_marketdata import RemoteMarketdataClient, DEFAULT_MARKETDATA_URL
URL = "https://[2607:9d00:2000:3fa::b389:941d]:8443/marketdata/latest.json"

class V150ReleaseTests(unittest.TestCase):
    def test_default_works_without_config(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"ASHARE_MARKETDATA_URL": ""}):
                obj=RemoteMarketdataClient(Path(temp))
            self.assertTrue(obj.enabled)
            self.assertEqual(obj.manifest_url, URL)
    def test_config_override_and_env_priority(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"marketdata_client.json").write_text(json.dumps({"manifest_url":"https://example.org/m/latest.json"}),encoding="utf8")
            with patch.dict(os.environ, {"ASHARE_MARKETDATA_URL": ""}):
                self.assertEqual(RemoteMarketdataClient(root).manifest_url,"https://example.org/m/latest.json")
            with patch.dict(os.environ, {"ASHARE_MARKETDATA_URL":"https://example.com/another/latest.json"}):
                self.assertEqual(RemoteMarketdataClient(root).manifest_url,"https://example.com/another/latest.json")
    def test_release_embeds_url_and_preserves_separate_databases(self):
        for version in ("1.5.0", "1.5.1"):
            with self.subTest(version=version):
                release = ROOT / f"A股MA扫描器_v{version}.pyw"
                src = release.read_text(encoding="utf-8")
                ast.parse(src, filename=str(release))
                self.assertIn(f'APP_VERSION = "{version}"', src)
                self.assertIn('DEFAULT_MARKETDATA_URL = "'+URL+'"',src)
                self.assertIn('or DEFAULT_MARKETDATA_URL)',src)
                self.assertIn('DB_PATH = DATA_DIR / "a_share_akshare_hfq.db"',src)
                self.assertIn('self.db_path = self.data_dir / "a_share_baostock_hfq.db"',src)
                self.assertIn('remote_client.sync(',src)
                self.assertIn('engine_backend.update_all(',src)
                self.assertIn('def export_strategy_xlsx(',src)
    def test_v151_trusts_only_the_expected_ipv6_mirror(self):
        path = ROOT / "A股MA扫描器_v1.5.1.pyw"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = {"MIRROR_BASE", "MIRROR_LATEST", "MIRROR_HOST", "MIRROR_PORT"}
        nodes = [node for node in tree.body if
                 (isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id in constants
                     for target in node.targets))
                 or (isinstance(node, ast.FunctionDef) and node.name == "_trusted_update_url")]
        namespace = {"urllib": urllib}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        trusted = namespace["_trusted_update_url"]
        base = "https://[2607:9d00:2000:3fa::b389:941d]:8443/ashare"
        self.assertTrue(trusted(base + "/latest.json", "mirror", redirect=True))
        self.assertFalse(trusted("https://198.143.122.37:8443/ashare/latest.json", "mirror"))
        self.assertFalse(trusted(base.replace(":8443", ":443") + "/latest.json", "mirror"))

    def test_v151_supports_old_and_new_akshare_names(self):
        release = ROOT / "A股MA扫描器_v1.5.1.pyw"
        tree = ast.parse(release.read_text(encoding="utf-8"))
        adapter = next(node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == "_akshare_call")
        namespace = {}
        exec(compile(ast.Module(body=[adapter], type_ignores=[]), str(release), "exec"), namespace)
        run = namespace["_akshare_call"]
        for name in ("index_zh_daily_tx", "stock_zh_index_daily_tx"):
            with self.subTest(name=name):
                client = SimpleNamespace()
                provider = unittest.mock.Mock(return_value="dates")
                setattr(client, name, provider)
                namespace["ak"] = client
                result = run("index_zh_daily_tx", "stock_zh_index_daily_tx",
                             symbol="sh000001", start_date="20260101")
                self.assertEqual(result, "dates")
                provider.assert_called_once_with(symbol="sh000001", start_date="20260101")
