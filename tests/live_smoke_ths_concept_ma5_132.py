"""Live read-only THS smoke: directory and real concept index, no market DB writes."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import types
import datetime

sys.modules.setdefault("baostock", types.ModuleType("baostock"))
p = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.2.pyw"
loader = SourceFileLoader("live_concept_v132", str(p))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
catalog = m.ConceptIndexService._fetch_catalog()
assert len(catalog) >= 20
robot = next(x for x in catalog if x["name"] == "机器人概念")
date = "2026-10-30"
bars = m.ConceptIndexService._fetch_history(robot["name"], date)
frame = m.concept_index_frame(bars)
assert len(frame) >= 7
assert frame.iloc[-1]["trade_date"] <= date
assert frame["MA5"].notna().sum() > 0
print(f"REAL THS catalog={len(catalog)} robot_code={robot['code']} "
      f"bars={len(frame)} last={frame.iloc[-1]['trade_date']} "
      f"MA5={frame.iloc[-1]['MA5']:.3f}", flush=True)
