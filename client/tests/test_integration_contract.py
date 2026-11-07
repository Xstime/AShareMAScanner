import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / 'A股MA扫描器_v1.3.8_dev_BaoStockRemote.pyw'


class IntegrationContractTests(unittest.TestCase):
    def test_client_syntax(self):
        ast.parse(CLIENT.read_text(encoding='utf-8'), filename=str(CLIENT))

    def test_stage_two_remote_first_and_legacy_fallback(self):
        source = CLIENT.read_text(encoding='utf-8')
        self.assertIn('class RemoteMarketdataClient:', source)
        self.assertIn('remote_client.sync(', source)
        self.assertIn('nonlocal engine_backend', source)
        self.assertIn('engine_backend.update_all(', source)
        self.assertIn('UpdateResult(**payload)', source)
        self.assertIn('RemoteMarketdataCancelled', source)
        self.assertIn('remote_backend.init_db()', source)
        self.assertIn('APP_VERSION = "1.3.8"', source)

    def test_akshare_database_is_separate(self):
        source = CLIENT.read_text(encoding='utf-8')
        self.assertIn('DB_PATH = DATA_DIR / "a_share_akshare_hfq.db"', source)
        self.assertIn('self.db_path = self.data_dir / "a_share_baostock_hfq.db"', source)

if __name__ == '__main__':
    unittest.main()
