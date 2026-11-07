"""v1.5.0 default VPS behavior and release source invariant tests."""
import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
from remote_marketdata import RemoteMarketdataClient, DEFAULT_MARKETDATA_URL
RELEASE = ROOT / "A股MA扫描器_v1.5.0.pyw"
URL = "https://23.95.88.6:8443/marketdata/latest.json"

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
        src=RELEASE.read_text(encoding="utf-8")
        ast.parse(src,filename=str(RELEASE))
        self.assertIn('APP_VERSION = "1.5.0"',src)
        self.assertIn('DEFAULT_MARKETDATA_URL = "'+URL+'"',src)
        self.assertIn('or DEFAULT_MARKETDATA_URL)',src)
        self.assertIn('DB_PATH = DATA_DIR / "a_share_akshare_hfq.db"',src)
        self.assertIn('self.db_path = self.data_dir / "a_share_baostock_hfq.db"',src)
        self.assertIn('remote_client.sync(',src)
        self.assertIn('engine_backend.update_all(',src)
        self.assertIn('def export_strategy_xlsx(',src)
