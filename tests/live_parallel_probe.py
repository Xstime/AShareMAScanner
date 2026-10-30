"""Read-only comparison of live single and three-session BaoStock day requests."""
import os
import time
from _speed_spawn_loader import _day_pool_fetch, multiprocessing

CODES = [
    "sh.600000","sh.600036","sh.600519","sh.601318",
    "sz.000001","sz.000333","sz.002594","sz.300750",
    "sz.300059","sh.688981","sh.603019","sz.002415",
]
TASKS = [(code,code,"2026-10-27") for code in CODES]

def valid(result):
    code, name, fields, values, error = result
    return not error and bool(values) and "close" in fields and all(
        row[fields.index("code")] == code for row in values
    )

def main():
    start=time.monotonic()
    serial=[_day_pool_fetch(task) for task in TASKS]
    serial_sec=time.monotonic()-start
    start=time.monotonic()
    with multiprocessing.get_context("spawn").Pool(processes=3) as pool:
        parallel=list(pool.imap_unordered(_day_pool_fetch,TASKS,chunksize=1))
    parallel_sec=time.monotonic()-start
    a=sum(map(valid,serial))
    b=sum(map(valid,parallel))
    print(f"LIVE READ ONLY BaoStock: serial={serial_sec:.2f}s ({a}/{len(TASKS)} valid); "
          f"3-worker={parallel_sec:.2f}s ({b}/{len(TASKS)} valid); "
          f"ratio={serial_sec/max(parallel_sec,1e-6):.2f}x",flush=True)
    for res in parallel:
        if not valid(res):
            print("Parallel failure:",res[0],res[-1],flush=True)
    assert a>=10 and b>=10, "Live provider rate limit or connectivity failure"
if __name__=="__main__":
    main()
