"""v1.2.9 manual self-update tests: no network, no edits to user data."""
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.modules.setdefault("baostock",types.ModuleType("baostock"))
p=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.9.pyw"
loader=SourceFileLoader("v129_manual_update_under_test",str(p))
spec=importlib.util.spec_from_loader(loader.name,loader)
scanner=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=scanner
spec.loader.exec_module(scanner)


class Response:
    def __init__(self,body,url):
        self.body=body
        self.url=url
        self.position=0
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n=-1):
        if n<0:n=len(self.body)-self.position
        data=self.body[self.position:self.position+n]
        self.position+=len(data)
        return data
    def geturl(self):return self.url


class UpdateTesting(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.local=self.root/"A股MA扫描器_v1.2.9.pyw"
        self.local.write_text("APP_VERSION = '1.2.9'\n",encoding="utf8")
        self.release_url="https://github.com/Xstime/AShareMAScanner/releases/download/v1.2.9/AShareMAScanner_v1.2.9.pyw"
        self.source=b'APP_VERSION = "1.2.9"\ndef main():\n    return "--update-ack"\n'
        self.source=self.source.replace(b"\\\n",b"\n")
    def tearDown(self):self.temp.cleanup()
    def api(self,tag="v1.2.9",source=None,sha=None,size=None,url=None,draft=False):
        source=self.source if source is None else source
        sha=hashlib.sha256(source).hexdigest() if sha is None else sha
        size=len(source) if size is None else size
        url=self.release_url if url is None else url
        payload=json.dumps({"tag_name":tag,"draft":draft,"prerelease":False,
            "assets":[{"name":f"AShareMAScanner_{tag}.pyw","browser_download_url":url,
                       "size":size,"digest":"sha256:"+sha}]}).encode()
        def serve(request,timeout=None):
            path=request.full_url if hasattr(request,"full_url") else str(request)
            if path==scanner.RELEASE_API:
                return Response(payload,scanner.RELEASE_API)
            return Response(source,"https://release-assets.githubusercontent.com/signed")
        return serve

    def test_user_press_is_only_update_trigger(self):
        self.assertEqual(scanner.APP_VERSION,"1.2.9")
        for fn in (scanner.main,scanner.ScannerWindow.__init__):
            self.assertNotIn("prepare_manual_update(",inspect.getsource(fn))
            self.assertNotIn("fetch_latest_release(",inspect.getsource(fn))
        self.assertIn("prepare_manual_update(",inspect.getsource(scanner.VersionWorker.run))
        self.assertIn("_show_release_info",inspect.getsource(scanner.ScannerWindow._make_workspace))

    def test_matching_file_is_current_no_download(self):
        payload=self.source
        self.local.write_bytes(payload)
        api=self.api()
        calls=[]
        def serve(req,timeout=None):
            calls.append(req.full_url)
            return api(req,timeout)
        with patch.object(scanner.urllib.request,"urlopen",side_effect=serve):
            message,candidate=scanner.prepare_manual_update(self.local)
        self.assertIsNone(candidate)
        self.assertEqual(len(calls),1)
        self.assertIn("最新",message)

    def test_same_version_with_different_digest_updates_recalled_build(self):
        with patch.object(scanner.urllib.request,"urlopen",side_effect=self.api()):
            message,candidate=scanner.prepare_manual_update(self.local)
        self.assertIsNotNone(candidate)
        self.assertEqual(Path(candidate).read_bytes(),self.source)
        self.assertEqual(self.local.read_text(), "APP_VERSION = '1.2.9'\n")
        candidate.unlink()

    def test_new_version_staged_by_content_hash_and_syntax(self):
        new=b'APP_VERSION = "1.2.10"\ndef main():\n    return "--update-ack"\n'
        new=new.replace(b"\\\n",b"\n")
        url=self.release_url.replace("v1.2.9","v1.2.10")
        with patch.object(scanner.urllib.request,"urlopen",
                          side_effect=self.api(tag="v1.2.10",source=new,url=url)):
            message,candidate=scanner.prepare_manual_update(self.local)
        self.assertIn("v1.2.10",message)
        self.assertEqual(candidate.read_bytes(),new)
        candidate.unlink()

    def test_never_downgrade_on_github(self):
        with patch.object(scanner.urllib.request,"urlopen",side_effect=self.api(tag="v1.2.8")) as mocked:
            message,candidate=scanner.prepare_manual_update(self.local)
        self.assertIsNone(candidate)
        self.assertIn("不会自动降级",message)
        self.assertEqual(mocked.call_count,1)

    def test_invalid_digest_never_leaves_staged_file(self):
        with patch.object(scanner.urllib.request,"urlopen",
                          side_effect=self.api(sha="0"*64)):
            with self.assertRaisesRegex(RuntimeError,"SHA-256"):
                scanner.prepare_manual_update(self.local)
        self.assertEqual(list(self.root.glob(".ashare-update-*")),[])
        self.assertTrue(self.local.exists())

    def test_invalid_size_is_rejected(self):
        with patch.object(scanner.urllib.request,"urlopen",
                          side_effect=self.api(size=50000000)):
            with self.assertRaisesRegex(RuntimeError,"大小"):
                scanner.prepare_manual_update(self.local)
        self.assertEqual(list(self.root.glob(".ashare-update-*")),[])

    def test_untrusted_release_url_is_rejected(self):
        with patch.object(scanner.urllib.request,"urlopen",
                          side_effect=self.api(url="https://evil.example/malware.pyw")):
            with self.assertRaisesRegex(RuntimeError,"不可信"):
                scanner.prepare_manual_update(self.local)

    def test_bad_python_syntax_never_replaces_original(self):
        bad=b'APP_VERSION = "1.2.9"\ndef main():\n    broken = (\n# --update-ack\n'
        bad=bad.replace(b"\\\n",b"\n")
        with patch.object(scanner.urllib.request,"urlopen",
                          side_effect=self.api(source=bad)):
            with self.assertRaisesRegex(RuntimeError,"编译"):
                scanner.prepare_manual_update(self.local)
        self.assertEqual(self.local.read_text(),"APP_VERSION = '1.2.9'\n")
        self.assertEqual(list(self.root.glob(".ashare-update-*")),[])

    def test_backup_guard_prevents_overwriting_existing_rollback(self):
        backup=self.root/(self.local.name+".old-update.bak")
        backup.write_text("do not destroy")
        with patch.object(scanner.urllib.request,"urlopen",
                          side_effect=self.api()):
            with self.assertRaisesRegex(RuntimeError,"备份"):
                scanner.prepare_manual_update(self.local)
        self.assertEqual(backup.read_text(),"do not destroy")
        self.assertEqual(list(self.root.glob(".ashare-update-*")),[])

    def run_helper(self,newsource):
        old=self.local
        old.write_text("old version",encoding="utf8")
        staged=self.root/"new.pyw"
        staged.write_text(newsource,encoding="utf8")
        backup=self.root/(old.name+".old-update.bak")
        ack=self.root/"test-ack"
        helper=self.root/"helper.py"
        helper.write_text(scanner.UPDATE_HELPER,encoding="utf8")
        # PID 999999 is not live in CI; on Windows an invalid OpenProcess handle
        # means the old parent is already gone.
        proc=subprocess.run([sys.executable,str(helper),"999999",str(old),
            str(staged),str(backup),str(ack),"1.2.8"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=12)
        # The helper deliberately starts a fresh app process that outlives it.
        # This synthetic app sleeps briefly after ACK. Wait for it to release
        # its Windows working-directory handle before TemporaryDirectory cleanup.
        import time
        time.sleep(1.5)
        return proc,old,staged,backup,ack

    def test_helper_replaces_and_deletes_old_after_new_ack(self):
        new='''from pathlib import Path
import sys
p=Path(sys.argv[sys.argv.index("--update-ack")+1])
p.write_text("ready", encoding="utf8")
import time;time.sleep(1)
'''
        proc,old,staged,backup,ack=self.run_helper(new)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(old.read_text(),new)
        self.assertFalse(backup.exists())
        self.assertFalse(staged.exists())

    def test_helper_rolls_back_on_new_process_failure(self):
        proc,old,staged,backup,ack=self.run_helper("raise RuntimeError('boot failed')\n")
        self.assertNotEqual(proc.returncode,0)
        self.assertEqual(old.read_text(),"old version")
        self.assertFalse(backup.exists())
        self.assertFalse(staged.exists())

    def test_data_directory_is_not_touched_by_update_helper(self):
        data=self.root/"data"
        data.mkdir()
        db=data/"a_share_baostock_hfq.db"
        db.write_bytes(b"private user database data")
        proc,*_=self.run_helper('''from pathlib import Path
import sys
Path(sys.argv[sys.argv.index("--update-ack")+1]).write_text("ready",encoding="utf8")
import time; time.sleep(1)
''')
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(db.read_bytes(),b"private user database data")


if __name__=="__main__":unittest.main(verbosity=2)
