#!/usr/bin/env python3
# Cloud validation of sector-only five-day capital-inflow rankings.
"""Live, read-only probe for production TOP5 endpoints; explicitly opt-in only.

Runs the actual backend methods and does not mutate the user's SQLite database.
Results in GitHub Actions show success/failure of the two ranking sources only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
import tempfile
import time
import traceback
from importlib.machinery import SourceFileLoader
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "A股MA扫描器_v1.2.7.pyw"


def load_backend():
    loader = SourceFileLoader("live_probe_ashare", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def emit(kind, **fields):
    print("PROBE " + json.dumps({"event": kind, **fields}, ensure_ascii=False, default=str), flush=True)


def run_probe():
    import akshare as ak
    module = load_backend()
    emit("environment", python=sys.version.split()[0],
         system=platform.platform(), akshare_version=getattr(ak, "__version__", "unknown"),
         pandas_version=module.pd.__version__,
         stock_date=module.datetime.now(module.CST).strftime("%Y-%m-%d %H:%M"))
    outcome = {}
    # No access to the user's local database, no remote credentials.
    with tempfile.TemporaryDirectory() as folder:
        backend = module.BaoStockBackend(Path(folder) / "probe.sqlite3")
        backend.init_db()
        for source in ("东方财富", "同花顺"):
            started = time.monotonic()
            messages = []
            def notify(message):
                messages.append(message)
                emit("progress", source=source, message=message)
            try:
                rows = backend._fund_complete_snapshot(
                    source, notify, module.datetime.now(module.CST)
                )
                outcome[source] = {
                    "ok": True, "elapsed_s": round(time.monotonic() - started, 2),
                    "top5": [{"sector": row[1], "net_yuan": row[2]} for row in rows],
                    "count": len(rows),
                }
                emit("source_success", source=source, **outcome[source])
            except Exception as exc:
                outcome[source] = {"ok": False, "elapsed_s": round(time.monotonic() - started, 2),
                                   "exception": type(exc).__name__, "error": str(exc)[:1800],
                                   "steps": messages[-15:]}
                emit("source_error", source=source, **outcome[source])
                traceback.print_exc(limit=4)
    emit("final", outcomes=outcome)
    # Probes are diagnostic. Do not turn API outages into CI test failures.
    return 0


if __name__ == "__main__":
    raise SystemExit(run_probe())
