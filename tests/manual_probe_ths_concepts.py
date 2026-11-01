"""Standalone live diagnostic of THS AKShare concept endpoints; no app/db writes.

Usage: python tests/manual_probe_ths_concepts.py
All actual AKShare calls run in isolated processes with individual 65s limits.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

CASES = (
    "concept_names",
    "concept_index_robot",
    "concept_index_alibaba",
    "concept_constituents_robot",
    "fund_top5_control",
)


def run_one(case):
    import akshare as ak
    import pandas as pd

    print("AKSHARE_VERSION", getattr(ak, "__version__", "unknown"), flush=True)
    if case == "concept_names":
        df = ak.stock_board_concept_name_ths()
    elif case == "concept_index_robot":
        df = ak.stock_board_concept_index_ths(
            symbol="机器人概念", start_date="20260801", end_date="20261030"
        )
    elif case == "concept_index_alibaba":
        df = ak.stock_board_concept_index_ths(
            symbol="阿里巴巴概念", start_date="20260801", end_date="20261030"
        )
    elif case == "concept_constituents_robot":
        if hasattr(ak, "stock_board_cons_ths"):
            df = ak.stock_board_cons_ths(symbol="885517")
        elif hasattr(ak, "stock_board_concept_cons_ths"):
            df = ak.stock_board_concept_cons_ths(symbol_code="机器人概念")
        else:
            raise RuntimeError("AKShare has no public THS constituent function")
    elif case == "fund_top5_control":
        df = ak.stock_fund_flow_industry(symbol="5日排行")
    else:
        raise ValueError(f"Unknown case {case}")

    if not isinstance(df, pd.DataFrame):
        raise AssertionError(f"Expected DataFrame, got {type(df).__name__}")
    if df.empty:
        raise AssertionError("DataFrame is empty")
    result = {
        "case": case,
        "rows": len(df),
        "columns": list(map(str, df.columns)),
        "head": df.head(2).astype(str).to_dict(orient="records"),
        "tail": df.tail(2).astype(str).to_dict(orient="records"),
    }
    if case.startswith("concept_index"):
        assert len(df) >= 15, f"Insufficient daily bars for a meaningful MA5: {len(df)}"
        closes = pd.to_numeric(df["收盘价"], errors="coerce")
        assert closes.notna().sum() >= 15, "Closing prices missing"
        result["ma5_latest"] = round(float(closes.tail(5).mean()), 4)
        result["ma5_previous"] = round(float(closes.iloc[-6:-1].mean()), 4)
        result["ma5_before"] = round(float(closes.iloc[-7:-2].mean()), 4)
        result["latest_date"] = str(df.iloc[-1]["日期"])
    print("CASE_RESULT " + json.dumps(result, ensure_ascii=False), flush=True)


def run_parent():
    print("LIVE_PROBE_STARTED", datetime.utcnow().isoformat(), "utc")
    print("OS", sys.platform, "PYTHON", sys.version.split()[0])
    for case in CASES:
        print("CASE_BEGIN", case, flush=True)
        started = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, "-u", __file__, "--case", case],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=65,
            )
            elapsed = round(time.monotonic() - started, 1)
            stdout = result.stdout[-6500:]
            stderr = result.stderr[-3500:]
            if stdout:
                print("STDOUT", stdout, flush=True)
            if stderr:
                print("STDERR", stderr, flush=True)
            print("CASE_END", case,
                  "SUCCESS" if result.returncode == 0 else f"FAILED_EXIT_{result.returncode}",
                  "ELAPSED_SECONDS", elapsed, flush=True)
        except subprocess.TimeoutExpired as exc:
            print("CASE_END", case, "TIMEOUT_65_SEC", flush=True)
    print("LIVE_PROBE_COMPLETE", datetime.utcnow().isoformat(), "utc")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--case":
        run_one(sys.argv[2])
    else:
        run_parent()
