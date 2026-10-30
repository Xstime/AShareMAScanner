"""Read-only BaoStock 45-day history through independent spawned clients."""
import multiprocessing
import time
from _speed_spawn_loader import _day_pool_fetch
CODES=["sh.600000","sh.600519","sz.000001","sz.300750",
       "sh.600036","sh.601318","sz.000333","sz.002594"]
JOBS=[(code,code,"2026-08-17","2026-10-27") for code in CODES]

def main():
    started=time.monotonic()
    with multiprocessing.get_context("spawn").Pool(processes=3) as pool:
        results=list(pool.imap_unordered(_day_pool_fetch,JOBS,chunksize=1))
    for code,name,fields,values,error in results:
        assert not error, f"{code}: {error}"
        assert "close" in fields and "turn" in fields
        assert len(values)>=30, f"{code}: insufficient valid trading days {len(values)}"
        for bar in values:
            assert bar[fields.index("code")]==code
            assert "2026-08-17"<=bar[fields.index("date")]<="2026-10-27"
    print(f"Live isolated 45-day history: {len(results)}/{len(CODES)} stocks; "
          f"{sum(len(x[3]) for x in results)} data bars; "
          f"elapsed {time.monotonic()-started:.2f}s",flush=True)
if __name__=="__main__": main()
