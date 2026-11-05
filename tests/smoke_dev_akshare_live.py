"""Independent bounded AKShare live checks on GitHub hosted runner.

Each endpoint gets its own OS-process deadline: one blocked source cannot
prevent checking the others. Never reads user databases and never fetches
the entire stock history.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import akshare as ak

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def one(name):
    ak.set_timeout((4, 9))
    source = Path(__file__).resolve().parents[1] / "A股MA扫描器_dev_AKShare.pyw"
    loader = SourceFileLoader("dev_live_" + name, str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as td:
        quotes = mod.AKShareQuotes(Path(td) / "scratch.sqlite")
        if name == "index":
            dates = quotes.index_dates()
            assert dates and dates[-1] >= "2026-10-20"
            return f"index trading days={len(dates)}, last={dates[-1]}"
        if name == "universe":
            df = quotes.stocks("2026-11-04")
            assert len(df) > 1000 and {"code", "tradeStatus", "code_name"}.issubset(df.columns)
            return f"A-share stock universe={len(df)}"
        if name in ("eastmoney", "sina", "tencent"):
            frame = quotes._download("sz.000001", "2026-10-20", "2026-11-04", name)
            assert len(frame) >= 2 and frame["close"].gt(0).all()
            assert frame["volume"].ge(0).all()
            return f"{name} HFQ daily rows={len(frame)} last={frame.iloc[-1]['date']}"
        if name == "industry_em":
            df = ak.stock_board_industry_name_em()
            assert "板块名称" in df and not df.empty
            name0 = df.iloc[0]["板块名称"]
            members = ak.stock_board_industry_cons_em(symbol=name0)
            assert {"代码", "名称"}.issubset(members) and not members.empty
            return f"EastMoney sectors={len(df)}, first={name0}, members={len(members)}"
        if name == "industry_sina":
            df = ak.stock_sector_spot(indicator="新浪行业")
            assert {"label", "板块"}.issubset(df) and not df.empty
            code = str(df.iloc[0]["label"])
            members = ak.stock_sector_detail(sector=code)
            assert {"symbol", "name"}.issubset(members) and not members.empty
            return f"Sina sectors={len(df)}, first={code}, members={len(members)}"
        raise ValueError(name)

if len(sys.argv) == 2:
    try:
        print(one(sys.argv[1]), flush=True)
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc)[:500], flush=True)
        raise SystemExit(1)
    raise SystemExit(0)

names = ("index", "universe", "eastmoney", "sina", "tencent",
         "industry_em", "industry_sina")
statuses = {}
for name in names:
    try:
        child = subprocess.run([sys.executable, __file__, name], capture_output=True,
                               text=True, timeout=21)
        statuses[name] = child.returncode == 0
        print(("PASS" if statuses[name] else "FAIL"), name,
              (child.stdout + child.stderr)[-800:].strip(), flush=True)
    except subprocess.TimeoutExpired:
        statuses[name] = False
        print("TIMEOUT", name, "endpoint not confirmed within 21s", flush=True)
print("BOUNDED LIVE RESULTS:", statuses, flush=True)
if (not statuses["index"] or not statuses["universe"] or
        not any(statuses[n] for n in ("eastmoney", "sina", "tencent")) or
        not any(statuses[n] for n in ("industry_em", "industry_sina"))):
    raise SystemExit(1)
