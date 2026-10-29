import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.modules['baostock'] = types.ModuleType('baostock')
path = Path(__file__).resolve().parents[1] / 'A股MA扫描器_v1.2.6.py'
spec = importlib.util.spec_from_file_location('release_checker_test', path)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, n):
        return self.payload[:n]


class UpdateCheckTests(unittest.TestCase):
    def test_latest_is_newer(self):
        with patch.object(scanner.urllib.request, 'urlopen', return_value=Response({
            'tag_name': 'v1.2.7',
            'html_url': 'https://github.com/Xstime/AShareMAScanner/releases/tag/v1.2.7',
        })):
            status, url = scanner.fetch_latest_release()
        self.assertIn('v1.2.7', status)
        self.assertEqual(url, 'https://github.com/Xstime/AShareMAScanner/releases/tag/v1.2.7')

    def test_latest_is_current(self):
        with patch.object(scanner.urllib.request, 'urlopen', return_value=Response({
            'tag_name': 'v1.2.6',
            'html_url': 'https://github.com/Xstime/AShareMAScanner/releases/tag/v1.2.6',
        })):
            self.assertEqual(scanner.fetch_latest_release(), ('当前已是最新版本', None))

    def test_bad_release_url_falls_back_to_own_repository(self):
        with patch.object(scanner.urllib.request, 'urlopen', return_value=Response({
            'tag_name': 'v1.2.7',
            'html_url': 'https://malicious.example/install.py',
        })):
            _, url = scanner.fetch_latest_release()
        self.assertEqual(url, 'https://github.com/Xstime/AShareMAScanner/releases')

    def test_no_official_releases(self):
        def not_found(*args, **kwargs):
            raise HTTPError('https://api.github.com/', 404, 'Not Found', None, None)
        with patch.object(scanner.urllib.request, 'urlopen', side_effect=not_found):
            self.assertEqual(scanner.fetch_latest_release(), ('尚无正式发布版本', None))

    def test_network_failure_raises_brief_error(self):
        with patch.object(scanner.urllib.request, 'urlopen', side_effect=URLError('offline')):
            with self.assertRaises(RuntimeError):
                scanner.fetch_latest_release()

    def test_reject_prerelease_tag(self):
        with patch.object(scanner.urllib.request, 'urlopen', return_value=Response({
            'tag_name': 'v1.2.7-rc1', 'html_url': 'https://github.com/Xstime/AShareMAScanner/releases'
        })):
            with self.assertRaises(RuntimeError):
                scanner.fetch_latest_release()


if __name__ == '__main__':
    unittest.main()
