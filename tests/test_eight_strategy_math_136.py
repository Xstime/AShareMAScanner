"""Independent offline reference checks for all eight v1.3.6 MA strategies.

Execute actual strategy engine against temporary SQLite, no BaoStock login.
Fixtures deliberately use the mathematical *minimum* number of valid trading
sessions and hand-computed reference values. Also exercise sector calculations.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import math
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("baostock", types.ModuleType("baostock"))
SOURCE = Path(__file__).resolve().parents[1] / "A股MA扫描器_v1.3.6.pyw"
loader = SourceFileLoader("independent_ma_audit_v136", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

MINIMUM = {
    "breakout_ma5": 6, "breakout_ma10": 11,
    "breakout_ma20": 21, "ma5_cross_ma10": 11,
    "ma5_turn_up": 7, "ma_convergence_up": 22,
    "volume_turnover": 6, "low_first_board": 34,
}


def prices_for(strategy, count):
    if strategy == "low_first_board":
        # Event at exactly 3 MARKET sessions before the target, preceded by
        # 30 reference closes and no 10% gains in the 20-session clear period.
        event = count - 4
        prices = [10.50 + 0.38 * math.sin(i / 2.5) for i in range(count)]
        if event > 0:
            prices[event - 1] = 10.12
            prices[event] = 10.12 * 1.10
            for i in range(event + 1, count):
                prices[i] = prices[i-1] * 1.003
        volumes = [100.0] * count
        if event >= 0:
            volumes[event] = 230.0
        return prices, volumes
    if strategy == "ma5_turn_up":
        # At six unchanged 10's, both older and yesterday MA5 equal 10.
        return [10.0] * (count - 1) + [11.0], [100.0] * count
    if strategy == "volume_turnover":
        return [10.0] * count, [100.0] * (count - 1) + [150.0]
    return [10.0] * (count - 1) + [12.0], (
        [100.0] * (count - 1) +
        [160.0 if strategy.startswith("breakout_ma") else 100.0])


def raw_bars(strategy, count, *, code="sh.600111", turnover=3.125):
    prices, volumes = prices_for(strategy, count)
    dates = pd.bdate_range("2026-06-01", periods=count).strftime("%Y-%m-%d").tolist()
    return pd.DataFrame([
        {"code": code, "trade_date": dates[i], "name": "独立测试",
         "close": prices[i], "volume": volumes[i],
         "trade_status": 1, "is_st": 0, "turnover": turnover}
        for i in range(count)])


class FullStrategyMathAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = m.BaoStockBackend(Path(self.tmp.name) / "signals.db")
        self.backend.init_db()
        # Keep result scan deterministic: "未分类" skips optional industry queries.
        self.backend.get_industry_map = lambda: {}

    def seed(self, bars):
        with m.sqlite_connection(self.backend.db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO daily "
                "(code,trade_date,name,close,volume,trade_status,is_st,turnover)"
                " VALUES (?,?,?,?,?,?,?,?)",
                [tuple(getattr(row, k) for k in
                  ("code","trade_date","name","close","volume",
                   "trade_status","is_st","turnover"))
                 for row in bars.itertuples(index=False)]
            )

    def scan(self, strategy, bars, filters=None):
        self.seed(bars)
        date = str(bars.iloc[-1]["trade_date"])
        # Source session cache must be invalidated between fixtures.
        self.backend._scan_prepared_cache = None
        return self.backend.scan_strategy(strategy, date, False, None, filters)

    def test_all_eight_trigger_with_exact_independent_minimum(self):
        self.assertEqual({x[0] for x in m.STRATEGIES}, set(MINIMUM))
        for strategy, required in MINIMUM.items():
            with self.subTest(strategy=strategy, days=required):
                bars = raw_bars(strategy, required)
                rowset = self.scan(strategy, bars)
                self.assertEqual(len(rowset), 1, f"{strategy}: valid edge excluded")
                row = rowset.iloc[0]
                self.assertEqual(row["触发日"], bars.iloc[-1]["trade_date"])
                self.assertEqual(row["代码"], "600111")
                self.assertEqual(row["板块"], "未分类")
                if strategy.startswith("breakout_ma"):
                    n = int(strategy.split("ma")[-1])
                    self.assertAlmostEqual(row[f"MA{n}"], round(10 + 2 / n, 2), places=2)
                    self.assertAlmostEqual(row["放量倍数"], 1.6, places=6)
                    self.assertAlmostEqual(row["当日涨幅%"], 20, places=6)
                elif strategy == "ma5_cross_ma10":
                    # MA5=(4*10+12)/5=10.4; MA10=(9*10+12)/10=10.2
                    self.assertAlmostEqual(row["MA5"], 10.4, places=6)
                    self.assertAlmostEqual(row["MA10"], 10.2, places=6)
                    self.assertAlmostEqual(row["MA5高于MA10%"],
                                           round((10.4/10.2-1)*100, 3), places=3)
                elif strategy == "ma5_turn_up":
                    self.assertAlmostEqual(row["MA5"], 10.2, places=3)
                    self.assertAlmostEqual(row["昨日MA5"], 10.0, places=3)
                    self.assertAlmostEqual(row["MA5上拐幅度%"], 2.0, places=3)
                elif strategy == "ma_convergence_up":
                    self.assertAlmostEqual(row["MA5"], 10.4, places=3)
                    self.assertAlmostEqual(row["MA10"], 10.2, places=3)
                    self.assertAlmostEqual(row["MA20"], 10.1, places=3)
                    self.assertAlmostEqual(row["昨日粘合度%"], 0.0, places=3)
                    width = ((10.4-10.1) / ((10.4+10.2+10.1)/3))*100
                    self.assertAlmostEqual(row["今日发散度%"], round(width,3), places=3)
                elif strategy == "volume_turnover":
                    self.assertAlmostEqual(row["放量倍数"], 1.5, places=6)
                    self.assertAlmostEqual(row["换手率%"], 3.125, places=6)
                elif strategy == "low_first_board":
                    self.assertEqual(row["距今交易日"], 3)
                    self.assertEqual(row["首板日期"], bars.iloc[-4]["trade_date"])
                    self.assertAlmostEqual(row["首板涨幅%"], 10.0, places=3)
                    self.assertAlmostEqual(row["首板放量倍数"], 2.3, places=3)

    def test_one_session_short_never_triggers(self):
        # A rolling MA cannot be evaluated before the previous MA is valid.
        for strategy, required in MINIMUM.items():
            with self.subTest(strategy=strategy):
                bars = raw_bars(strategy, required - 1)
                self.assertTrue(self.scan(strategy, bars).empty)

    def test_breakout_requires_exact_volume_and_previous_side(self):
        for strategy, required in list(MINIMUM.items())[:3]:
            with self.subTest(strategy=strategy):
                bars = raw_bars(strategy, required)
                bars.loc[required - 1, "volume"] = 149.0
                self.assertTrue(self.scan(strategy, bars).empty)
                bars.loc[required - 1, "volume"] = 150.0
                self.assertEqual(len(self.scan(strategy, bars)), 1)
                # Non-crossing: yesterday was already above yesterday's MA.
                bars.loc[required - 2, "close"] = 20.0
                bars.loc[required - 1, "close"] = 21.0
                self.assertTrue(self.scan(strategy, bars).empty)

    def test_custom_filter_inclusive_and_unrounded_boundaries(self):
        bars = raw_bars("volume_turnover", 6, turnover=3.1254321)
        bounds = m.RangeFilter(volume_min=1.5, volume_max=1.5,
                               turnover_min=3.1254321, turnover_max=3.1254321)
        hit = self.scan("volume_turnover", bars, bounds)
        self.assertEqual(len(hit), 1)
        self.assertAlmostEqual(hit.iloc[0]["放量倍数"], 1.5, places=6)
        self.assertAlmostEqual(hit.iloc[0]["换手率%"], round(3.1254321,6), places=6)
        bars.loc[5,"volume"] = 149.999
        self.assertTrue(self.scan("volume_turnover", bars, bounds).empty)
        bars.loc[5,"volume"] = 150.0
        bars.loc[5,"turnover"] = 3.1254320
        self.assertTrue(self.scan("volume_turnover", bars, bounds).empty)

    def test_missing_halted_and_invalid_bars_not_used_for_ma(self):
        bars = raw_bars("breakout_ma5", 6)
        bars.loc[0, "trade_status"] = 0
        self.assertTrue(self.scan("breakout_ma5", bars).empty)
        bars.loc[0, "trade_status"] = 1
        bars.loc[0, "close"] = float("nan")
        self.assertTrue(self.scan("breakout_ma5", bars).empty)
        bars.loc[0, "close"] = 10.0
        bars.loc[5, "is_st"] = 1
        self.assertTrue(self.scan("breakout_ma5", bars).empty)

    def test_no_future_leak_and_repeat_switch_reads_cached_snapshot(self):
        bars = raw_bars("breakout_ma10", 11)
        first = self.scan("breakout_ma10", bars)
        self.assertEqual(len(first), 1)
        with m.sqlite_connection(self.backend.db_path) as conn:
            conn.execute("INSERT INTO daily "
                         "(code,trade_date,name,close,volume,trade_status,is_st,turnover)"
                         " VALUES (?,?,?,?,?,?,?,?)",
                         ("sh.600111", "2027-01-01", "未来日", 9999, 9999, 1, 0, 3.0))
        second = self.backend.scan_strategy(
            "breakout_ma10", str(bars.iloc[-1]["trade_date"]), False, None)
        self.assertEqual(first["代码"].tolist(), second["代码"].tolist())
        self.assertEqual(first["MA10"].tolist(), second["MA10"].tolist())


class SectorStrategyMathAudit(unittest.TestCase):
    def test_all_seven_applicable_sector_signals_use_same_formulas(self):
        applicable = [x for x in MINIMUM if x != "low_first_board"]
        for strategy in applicable:
            with self.subTest(strategy=strategy):
                bars = raw_bars(strategy, MINIMUM[strategy])
                frame = m.BaoStockBackend._prepare_group(bars)
                date = str(frame.iloc[-1]["trade_date"])
                self.assertTrue(m.BaoStockBackend._sector_strategy_triggered(
                    frame, strategy, date, m.RangeFilter(
                        volume_min=1.5, turnover_min=3.0)))
                if len(frame) > 2:
                    previous = str(frame.iloc[-2]["trade_date"])
                    self.assertFalse(m.BaoStockBackend._sector_strategy_triggered(
                        frame, strategy, previous, m.RangeFilter(
                            volume_min=1.5, turnover_min=3.0)))
        frame = m.BaoStockBackend._prepare_group(
            raw_bars("low_first_board", 34))
        self.assertFalse(m.BaoStockBackend._sector_strategy_triggered(
            frame, "low_first_board", str(frame.iloc[-1]["trade_date"])))

    def test_actual_sector_aggregation_normalizes_prices_and_sums_volumes(self):
        with tempfile.TemporaryDirectory() as root:
            b = m.BaoStockBackend(Path(root)/"sector.db")
            b.init_db()
            bars_a = raw_bars("breakout_ma20",21,code="sh.600111",turnover=3.0)
            bars_b = raw_bars("breakout_ma20",21,code="sh.600222",turnover=5.0)
            bars_b["close"] *= 2.0
            bars_b["volume"] *= 2.0
            with m.sqlite_connection(b.db_path) as conn:
                conn.executemany(
                    "INSERT INTO daily "
                    "(code,trade_date,name,close,volume,trade_status,is_st,turnover)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    [tuple(getattr(row,k) for k in
                        ("code","trade_date","name","close","volume",
                         "trade_status","is_st","turnover"))
                     for bars in (bars_a,bars_b)
                     for row in bars.itertuples(index=False)])
                conn.executemany("INSERT INTO industry_cache "
                    "(code,name,industry,update_date,classification,fetched_at)"
                    "VALUES (?,?,?,?,?,?)",
                    [(code,"独立测试","审计行业","2026-10-01","测试","2026-10-01")
                     for code in ("sh.600111","sh.600222")])
            target = str(bars_a.iloc[-1]["trade_date"])
            sector = b.get_sector_chart_data("审计行业",target)
            self.assertEqual(len(sector),21)
            today = sector.iloc[-1]
            self.assertEqual(int(today["members"]),2)
            self.assertAlmostEqual(today["close"],120.0,places=5)
            self.assertAlmostEqual(today["MA5"],104.0,places=5)
            self.assertAlmostEqual(today["MA10"],102.0,places=5)
            self.assertAlmostEqual(today["MA20"],101.0,places=5)
            self.assertAlmostEqual(today["volume"],480.0,places=5)
            self.assertAlmostEqual(today["放量倍数"],1.6,places=5)
            self.assertAlmostEqual(today["turnover"],4.0,places=5)
            self.assertEqual(
                b.get_sector_strategy_status("审计行业","breakout_ma20",
                    target,False,None), "今日触发")


if __name__=="__main__":
    unittest.main(verbosity=2)
