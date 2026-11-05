"""Bounded online smoke test of free AKShare upstreams.

Run only by the dedicated dev-live workflow. This is not a full-market download
and never reads/writes user databases. Network failures are reported precisely.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
from pathlib import Path
import sys
import tempfile
import time

import akshare as ak
import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
src = Path(__file__).resolve().parents[1] / "A股MA扫描器_dev_AKShare.pyw"
loader = SourceFileLoader("dev_live_market", str(src))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

errors = []
result = {}
def step(label, fn):
    begin = time.monotonic()
    try:
        message = fn()
        print("PASS", label, message, f"{time.monotonic()-begin:.1f}s", flush=True)
        result[label] = True
        return True
    except Exception as exc:
        print("FAIL", label, type(exc).__name__, str(exc)[:260],
              f"{time.monotonic()-begin:.1f}s", flush=True)
        errors.append((label, str(exc)))
        result[label] = False
        return False

def stock_from(source):
    with tempfile.TemporaryDirectory() as td:
        client = m.AKShareQuotes(Path(td) / "scratch.sqlite")
        data = client._download("sz.000001", "2026-10-20", "2026-11-04", source)
        assert len(data) >= 2
        assert (data["close"] > 0).all() and (data["volume"] > 0).any()
        assert set(data.columns) == set(client.FIELDS)
        if source == "eastmoney":
            assert data["turn"].notna().any()
        return f"rows={len(data)},last={data.iloc[-1]['date']},source={source}"

def index():
    with tempfile.TemporaryDirectory() as td:
        q = m.AKShareQuotes(Path(td) / "scratch.sqlite")
        days = q.index_dates()
        assert days and days[-1] >= "2026-10-20"
        return f"{len(days)} last={days[-1]}"

def market_universe():
    with tempfile.TemporaryDirectory() as td:
        q = m.AKShareQuotes(Path(td) / "scratch.sqlite")
        rows = q.stocks("2026-11-04")
        assert len(rows) > 1000
        assert {"code", "tradeStatus", "code_name"}.issubset(rows.columns)
        return f"{len(rows)} securities"

def em_sectors():
    boards = ak.stock_board_industry_name_em()
    assert boards is not None and "板块名称" in boards.columns
    for name in boards["板块名称"].dropna().astype(str).head(3):
        members = ak.stock_board_industry_cons_em(symbol=name)
        if {"代码", "名称"}.issubset(members.columns) and len(members) >= 2:
            return f"{len(boards)} boards; {name}={len(members)} symbols"
    raise AssertionError("Sector list accessible, but first 3 member lists unavailable")

def sina_sectors():
    boards = ak.stock_sector_spot(indicator="新浪行业")
    assert {"label", "板块"}.issubset(boards.columns)
    for sector in boards["label"].dropna().head(3):
        members = ak.stock_sector_detail(sector=str(sector))
        if {"symbol", "name"}.issubset(members.columns) and len(members) >= 2:
            return f"{len(boards)} boards; {sector}={len(members)} symbols"
    raise AssertionError("Sina sector list accessible, but first 3 members unavailable")

step("A-share trading index", index)
step("A-share stock universe", market_universe)
for provider in ("eastmoney", "sina", "tencent"):
    step("historical HFQ " + provider, lambda p=provider: stock_from(p))
step("industry EastMoney members", em_sectors)
step("industry Sina backup members", sina_sectors)

print("ONLINE SMOKE SUMMARY:", result, flush=True)
if not result["A-share trading index"] or not result["A-share stock universe"]:
    print("BLOCKER: index/calendar or universe unavailable from GitHub-runner network", flush=True)
if not any(result["historical HFQ " + p] for p in ("eastmoney", "sina", "tencent")):
    print("BLOCKER: no stock historical provider reachable from GitHub-runner network", flush=True)
if not any(result[k] for k in ("industry EastMoney members", "industry Sina backup members")):
    print("BLOCKER: neither industry membership upstream reachable from GitHub-runner network", flush=True)
if (not result["A-share trading index"] or not result["A-share stock universe"] or
    not any(result["historical HFQ " + p] for p in ("eastmoney", "sina", "tencent")) or
    not any(result[k] for k in ("industry EastMoney members", "industry Sina backup members"))):
    raise SystemExit(1)
