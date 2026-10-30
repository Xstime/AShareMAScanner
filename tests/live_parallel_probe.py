"""Read-only comparison of live single and three-session BaoStock day requests."""
import os
import time
from _speed_spawn_loader import _day_pool_fetch, multiprocessing

CODES = [
    "sh.600000","sh.600036","sh.600519","sh.601318",
    "sz.000001","sz.000333","sz.002594","sz.300750",
    "sz.300059","sh.688981","sh.603019","sz.002415",
]
def fetch_market_tasks():
    import baostock as bs
    logged = bs.login()
    if logged.error_code != "0":
        raise RuntimeError("Cannot collect real stock codes: " + str(logged.error_msg))
    try:
        rs = bs.query_all_stock(day="2026-10-27")
        if rs.error_code != "0":
            raise RuntimeError("Cannot read market universe: " + str(rs.error_msg))
        columns = list(rs.fields)
        code_index = columns.index("code")
        status_index = columns.index("tradeStatus") if "tradeStatus" in columns else None
        names = []
        while rs.next():
            row = rs.get_row_data()
            code = row[code_index]
            if (code.startswith(("sh.6", "sz.0", "sz.3"))
                    and (status_index is None or row[status_index] == "1")):
                names.append(code)
        names = sorted(set(names))[:120]
        if len(names) < 60:
            raise RuntimeError(f"Only {len(names)} suitable A-share market codes returned")
        return [(code,code,"2026-10-27") for code in names]
    finally:
        bs.logout()

def valid(result):
    code, name, fields, values, error = result
    return not error and bool(values) and "close" in fields and all(
        row[fields.index("code")] == code for row in values
    )

def main():
    tasks=fetch_market_tasks()
    start=time.monotonic()
    serial=[_day_pool_fetch(task) for task in tasks]
    serial_sec=time.monotonic()-start
    start=time.monotonic()
    with multiprocessing.get_context("spawn").Pool(processes=3) as pool:
        parallel=list(pool.imap_unordered(_day_pool_fetch,tasks,chunksize=1))
    parallel_sec=time.monotonic()-start
    a=sum(map(valid,serial))
    b=sum(map(valid,parallel))
    print(f"LIVE READ ONLY BaoStock: serial={serial_sec:.2f}s ({a}/{len(tasks)} valid); "
          f"3-worker={parallel_sec:.2f}s ({b}/{len(tasks)} valid); "
          f"ratio={serial_sec/max(parallel_sec,1e-6):.2f}x",flush=True)
    for res in parallel:
        if not valid(res):
            print("Parallel failure:",res[0],res[-1],flush=True)
    assert a >= len(tasks)-2 and b >= len(tasks)-2, "Live provider rate limit or connectivity failure"
if __name__=="__main__":
    main()
