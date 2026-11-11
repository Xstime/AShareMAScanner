"""Integration against the actual v1.5.0 RemoteMarketdataClient.

Set ASHARE_CLIENT_150_FILE to the v1.5.0 .pyw source before running.
"""
import ast
import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import test_server
import ashare_server.api as api
from ashare_server.db import connect
from ashare_server.updater import MarketUpdater


def load_client(path):
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {"RemoteMarketdataError", "RemoteMarketdataCancelled", "RemoteMarketdataClient"}
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    if {n.name for n in classes} != names:
        raise RuntimeError("v1.5.0 client classes missing")
    namespace = dict(Path=Path, json=json, os=os, re=re, urllib=urllib,
                     hashlib=hashlib, datetime=datetime, timedelta=timedelta,
                     timezone=timezone, sqlite3=sqlite3, contextlib=contextlib,
                     tempfile=tempfile, zipfile=zipfile, shutil=shutil,
                     DEFAULT_MARKETDATA_URL="http://127.0.0.1/latest.json")
    exec(compile(ast.Module(body=classes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["RemoteMarketdataClient"]


@unittest.skipUnless(os.getenv("ASHARE_CLIENT_150_FILE"), "set ASHARE_CLIENT_150_FILE to v1.5.0 source")
class ClientCompatibilityTests(unittest.TestCase):
    def test_v150_downloads_imports_and_refreshes_same_day(self):
        client_type = load_client(os.environ["ASHARE_CLIENT_150_FILE"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            updater = MarketUpdater(test_server.UpdaterTests()._settings(root / "server"), test_server.FakeProvider())
            self.assertTrue(updater.run()["published"])
            old_settings = api.settings
            api.settings = SimpleNamespace(public_dir=updater.config.public_dir,
                                           manifest_path=updater.config.manifest_path)
            server = ThreadingHTTPServer(("127.0.0.1", 0), api.MarketDataHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client_dir = root / "client"
                client_dir.mkdir()
                (client_dir / "marketdata_client.json").write_text(json.dumps({
                    "manifest_url": f"http://127.0.0.1:{server.server_port}/latest.json"}))
                client = client_type(client_dir)
                messages = []
                result = client.sync(lambda _, message: messages.append(message))
                self.assertEqual(result["scan_date"], "2026-11-06")
                with sqlite3.connect(client.db_path) as db:
                    self.assertEqual(db.execute("SELECT close FROM daily WHERE code='sh.600000' AND trade_date='2026-11-06'").fetchone()[0], 10.5)
                    db.execute("CREATE TABLE user_cache (v TEXT)")
                    db.execute("INSERT INTO user_cache VALUES ('preserved')")
                first_sha = json.loads(updater.config.manifest_path.read_text())["snapshot_sha256"]
                with connect(updater.config.db_path) as db:
                    db.execute("UPDATE daily SET close=11.5 WHERE code='sh.600000' AND trade_date='2026-11-06'")
                status = updater.db.update_day_status("2026-11-06")
                manifest = updater.publisher.publish("2026-11-06", status, 2)
                self.assertNotEqual(first_sha, manifest["snapshot_sha256"])
                messages.clear()
                self.assertEqual(client.sync(lambda _, message: messages.append(message))["scan_date"], "2026-11-06")
                self.assertTrue(any("发现 VPS 新快照" in m for m in messages))
                with sqlite3.connect(client.db_path) as db:
                    self.assertEqual(db.execute("SELECT close FROM daily WHERE code='sh.600000' AND trade_date='2026-11-06'").fetchone()[0], 11.5)
                    self.assertEqual(db.execute("SELECT v FROM user_cache").fetchone()[0], "preserved")
                    self.assertEqual(db.execute("SELECT value FROM server_meta WHERE key='adjustment'").fetchone()[0], "不复权 (adjustflag=3)")
                messages.clear()
                client.sync(lambda _, message: messages.append(message))
                self.assertTrue(any("VPS 行情无变化" in m for m in messages))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                api.settings = old_settings

if __name__ == "__main__":
    unittest.main()
