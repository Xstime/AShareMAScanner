"""Actually spawn 3 isolated Windows/Linux processes using an offline BaoStock stub."""
import os
import pathlib
import sys
import tempfile
import unittest

class SpawnIsolationTest(unittest.TestCase):
    def test_actual_spawn_processes_have_independent_fake_baostock_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            stub=pathlib.Path(tmp)/"baostock.py"
            stub.write_text("""
import os
class Response:
    error_code='0'
    error_msg='ok'
def login():return Response()
def logout():return Response()
class Result(Response):
    fields=['date','code','close','volume','tradestatus','isST','turn']
    def __init__(self,code,date):
        self.code,self.date=code,date
        self._done=False
    def next(self):
        if self._done:return False
        self._done=True
        return True
    def get_row_data(self):
        return [self.date,self.code,'10.25','1000','1','0','3.2']
def query_history_k_data_plus(code,fields,start_date,end_date,frequency,adjustflag):
    assert start_date==end_date
    assert adjustflag=='1'
    return Result(code,start_date)
""",encoding="utf-8")
            oldpath=os.environ.get("PYTHONPATH")
            # Child Python imports the stub first, never contacting BaoStock.
            os.environ["PYTHONPATH"]=tmp+os.pathsep+str(pathlib.Path(__file__).parent)+(
                os.pathsep+oldpath if oldpath else "")
            try:
                import _speed_spawn_loader as m
                jobs=[(f"sh.{600000+i:06d}",f"Test{i}","2026-10-27")
                      for i in range(12)]
                with m.multiprocessing.get_context("spawn").Pool(processes=3) as pool:
                    found=list(pool.imap_unordered(m._day_pool_fetch,jobs,chunksize=1))
                self.assertEqual(len(found),len(jobs))
                self.assertEqual(set(r[0] for r in found),set(j[0] for j in jobs))
                self.assertTrue(all(not error for *_,error in found),found)
                self.assertTrue(all(raw[0][1]==code for code,_,_,raw,_ in found))
            finally:
                if oldpath is None:os.environ.pop("PYTHONPATH",None)
                else:os.environ["PYTHONPATH"]=oldpath

if __name__=="__main__":
    unittest.main()
