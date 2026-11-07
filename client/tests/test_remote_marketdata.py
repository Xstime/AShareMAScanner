import hashlib
import contextlib
import json
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote_marketdata import (RemoteMarketdataClient, RemoteMarketdataError,
                               RemoteMarketdataCancelled)


def fixture(root, market_date, expected=2):
    path = root / "marketdata.sqlite3"
    if path.exists(): path.unlink()
    with contextlib.closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
        CREATE TABLE daily (code TEXT NOT NULL, trade_date TEXT NOT NULL,name TEXT,
          close REAL,volume REAL,trade_status INTEGER,is_st INTEGER,turnover REAL,
          PRIMARY KEY(code,trade_date));
        CREATE TABLE day_universe (trade_date TEXT NOT NULL,code TEXT NOT NULL,name TEXT,
          trade_status INTEGER,PRIMARY KEY(trade_date,code));
        CREATE TABLE day_status (trade_date TEXT PRIMARY KEY,expected_count INTEGER NOT NULL DEFAULT 0,
          saved_count INTEGER NOT NULL DEFAULT 0,failed_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'partial',updated_at TEXT);
        CREATE TABLE industry_cache (code TEXT PRIMARY KEY,name TEXT,industry TEXT,
          update_date TEXT,classification TEXT,fetched_at TEXT);
        CREATE TABLE server_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        older=(datetime.strptime(market_date,'%Y-%m-%d').date()-timedelta(days=1)).isoformat()
        for i in range(expected):
            code=f'sh.{600001+i:06d}'
            db.execute('INSERT INTO daily VALUES (?,?,?,?,?,?,?,?)',
                       (code, older,'test',2.0,1000.,1,0,1.2))
            db.execute('INSERT INTO daily VALUES (?,?,?,?,?,?,?,?)',
                       (code, market_date,'test',3.0,2000.,1,0,1.3))
            db.execute('INSERT INTO day_universe VALUES (?,?,?,?)', (market_date,code,'test',1))
            db.execute('INSERT INTO industry_cache VALUES (?,?,?,?,?,?)', (code,'test','industry',market_date,'A','now'))
        db.execute('INSERT INTO day_status VALUES (?,?,?,?,?,?)', (market_date,expected,expected,0,'complete','now'))
        for key,value in [('schema_version','1'),('market_date',market_date),('provider','BaoStock')]:
            db.execute('INSERT INTO server_meta VALUES (?,?)', (key,value))
    target=root/'snapshot.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(path,arcname='marketdata.sqlite3')
    blob=target.read_bytes()
    manifest={'schema_version':1,'dataset_version':'test','provider':'BaoStock','market_date':market_date,
              'expected_count':expected,'saved_count':expected,'failed_count':0,
              'completeness':1.0,'status':'complete','snapshot_size':len(blob),
              'snapshot_sha256':hashlib.sha256(blob).hexdigest(),
              'snapshot_url':'https://evil.example/other.zip'}
    return manifest,blob

class StubHandler(BaseHTTPRequestHandler):
    manifest=None; blob=None; downloads=0
    def do_GET(self):
        if self.path.endswith('/latest.json'):
            data=json.dumps(type(self).manifest).encode()
        elif self.path.endswith('/snapshot.zip'):
            type(self).downloads+=1
            data=type(self).blob
        else:
            self.send_error(404);return
        self.send_response(200);self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
    def log_message(self,*_): pass

class RemoteClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.data=self.base/'data';self.data.mkdir()
        self.manifest,self.blob=fixture(self.base,'2026-11-06')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),StubHandler)
        StubHandler.manifest=self.manifest;StubHandler.blob=self.blob;StubHandler.downloads=0
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.url=f'http://127.0.0.1:{self.server.server_port}/marketdata/latest.json'
        (self.data/'marketdata_client.json').write_text(json.dumps({'manifest_url':self.url}))
        self.events=[]
        self.client=RemoteMarketdataClient(self.data)

    def run_sync(self): return self.client.sync(lambda pct,msg:self.events.append((pct,msg)))

    def test_first_download_creates_isolated_database(self):
        result=self.run_sync()
        self.assertEqual(result['scan_date'],'2026-11-06')
        self.assertEqual(result['completeness'],100.)
        self.assertEqual(StubHandler.downloads,1)
        with contextlib.closing(sqlite3.connect(self.client.db_path)) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM daily').fetchone()[0],4)
        self.assertFalse((self.data/'a_share_akshare_hfq.db').exists())

    def test_unchanged_manifest_does_not_download_twice(self):
        self.run_sync();self.run_sync()
        self.assertEqual(StubHandler.downloads,1)

    def test_invalid_hash_never_replaces_existing_cache(self):
        self.run_sync();original=self.client.db_path.read_bytes()
        StubHandler.manifest=dict(self.manifest,snapshot_sha256='a'*64)
        with self.assertRaisesRegex(RemoteMarketdataError,'SHA-256'):
            self.run_sync()
        self.assertEqual(original,self.client.db_path.read_bytes())

    def test_merge_preserves_local_only_tables_and_earlier_rows(self):
        self.run_sync()
        with contextlib.closing(sqlite3.connect(self.client.db_path)) as db, db:
            db.execute('CREATE TABLE signal_history (id INTEGER PRIMARY KEY, payload TEXT)')
            db.execute('INSERT INTO signal_history(payload) VALUES (?)',('KEEP',))
        newer,blob=fixture(self.base,'2026-11-09')
        StubHandler.manifest=newer;StubHandler.blob=blob
        result=self.run_sync()
        self.assertEqual(result['scan_date'],'2026-11-09')
        with contextlib.closing(sqlite3.connect(self.client.db_path)) as db, db:
            self.assertEqual(db.execute('SELECT payload FROM signal_history').fetchone()[0],'KEEP')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM daily WHERE trade_date='2026-11-06'").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM daily WHERE trade_date='2026-11-09'").fetchone()[0],2)

    def test_old_manifest_cannot_downgrade(self):
        self.run_sync()
        old,blob=fixture(self.base,'2026-11-03')
        StubHandler.manifest=old;StubHandler.blob=blob
        r=self.run_sync()
        self.assertEqual(r['scan_date'],'2026-11-06')
        self.assertEqual(StubHandler.downloads,1)

    def test_invalid_zip_never_replaces_cache(self):
        self.run_sync()
        old=self.client.db_path.read_bytes()
        blob=b'not-a-zip'*100
        StubHandler.blob=blob
        StubHandler.manifest=dict(self.manifest,snapshot_sha256=hashlib.sha256(blob).hexdigest(),snapshot_size=len(blob))
        with self.assertRaisesRegex(RemoteMarketdataError,'ZIP'):
            self.run_sync()
        self.assertEqual(old,self.client.db_path.read_bytes())

    def test_manifest_incomplete_is_rejected(self):
        StubHandler.manifest=dict(self.manifest,completeness=.90)
        with self.assertRaisesRegex(RemoteMarketdataError,'完整率'):
            self.run_sync()
        self.assertFalse(self.client.db_path.exists())

    def test_cancel_before_request(self):
        event=threading.Event();event.set()
        with self.assertRaises(RemoteMarketdataCancelled):
            self.client.sync(lambda *args:None,event)
        self.assertFalse(self.client.db_path.exists())

    def test_https_required_for_remote_host(self):
        with patch.dict('os.environ',{'ASHARE_MARKETDATA_URL':'http://example.com/marketdata/latest.json'}):
            with self.assertRaisesRegex(RemoteMarketdataError,'HTTPS'):
                RemoteMarketdataClient(self.data)

    def test_offline_cached_snapshot_includes_staleness_warning(self):
        now=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        manifest,blob=fixture(self.base,now)
        StubHandler.manifest=manifest;StubHandler.blob=blob
        self.run_sync()
        cached=self.client.use_offline_cache('HTTP 503')
        self.assertIsNotNone(cached)
        self.assertIn('HTTP 503',cached['warning'])

if __name__=='__main__': unittest.main()
