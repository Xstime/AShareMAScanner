# v1.2.8 Recall & Functional Regression Audit

Audit date: 2026-10-30 (Asia/Singapore); GitHub Action timestamps may show 2026-10-29 UTC.

## Release status
- v1.2.8 public release 428114244 was changed to **Draft**.
- The v1.2.8 automatic publishing workflow was disabled.
- GitHub `/releases/latest` resolves to **v1.2.6**.
- Recalled source and tag are retained for investigation; `main` is not replaced or rewritten.

## Executed tests

Run: https://github.com/Xstime/AShareMAScanner/actions/runs/40919397717

Environment: Ubuntu GitHub runner, Python 3.12, installed project dependencies, Xvfb + Tkinter + PySide6 offscreen.
Total: **46 tests: 34 pass, 11 assertion failures, 1 runtime error**.

| Group | Tests | Result | Actual target |
| --- | ---: | --- | --- |
| test_hybrid_pyside6.py | 4 | Pass | v1.2.8 synthetic GUI |
| test_ths_top5_only.py | 6 | Pass | v1.2.8 TOP5 mocks and local database |
| test_three_stage_tk.py | 2 | Pass | v1.2.8 Tk phase |
| test_github_updates.py | 6 | Pass | **v1.2.6**, not v1.2.8 |
| test_progress_visualizer.py | 6 | Pass | **v1.2.6**, not v1.2.8 |
| test_startup_splash.py | 3 | Pass | **v1.2.6**, not v1.2.8 |
| test_fund_sources.py | 4 | Pass | **v1.2.6**, not v1.2.8 |
| test_v128_full_audit.py | 15 | **3 pass, 11 failures, 1 error** | v1.2.8 real synthetic SQLite + offscreen GUI |

This means the 34 passing tests cannot be interpreted as 34 independent confirmations of all v1.2.8 features: 19 of these tests run v1.2.6.

### Verified blocking regressions
1. Runtime error: `BaoStockBackend.get_signal_history` invokes deleted `StockScannerApp.STRATEGIES`; real local stock price fixture caused `NameError`.
2. Old source pollution: `load_fund_top5` shows historical Eastmoney rows instead of filtering THS-only source.
3. Version check PySide6 button does not invoke GitHub update checker.
4. Fourth-parameter range UI: missing maximum volume and turnover bounds.
5. Change percentage range quick filter is absent.
6. Sector summary and sector price/MA chart no longer reachable through PySide6 workbench.
7. Seven-strategy-specific metrics (including divergence percentages) not displayed in static result columns.
8. History dialog omits streak, saved parameters and much detail.
9. History dialog ignores active fifth-strategy filters.
10. Full chart omits volume and turnover curves.
11. Strategy QThread fails to pass cancellation token, though backend supports cancellation.
12. Clear-selection leaves stale selected stock object.

Some GUI parity tests above are source/structure assertions. They prove a missing integration or UI feature at the code level, but do not substitute for full end-to-end GUI interaction testing.

### Verified preserved functionality
- Valid Python syntax for both version files.
- Qt 3-column window, seven strategy controls, and five non-clickable TOP5 cards in demo.
- Backend SQLite daily chart data, MA5/10/20, four-bound RangeFilter behavior.
- Seven strategy calculations executed on synthetic 30-day SQLite fixture.
- THS-only request parser/currency conversion and retry+cache behavior using mocks.
- Tk update stage handoff with injected backend.

## Important limits of this audit
- No Windows physical machine and no Windows .pyw file association test.
- No live full A-share BaoStock initial/incremental market download; synthetic 30-day fixture only.
- No guarantee of live THS endpoint connectivity at time of launch; tests mock THS.
- No real-world corrupt/locked/large database full load, long-run stress, historical trading-day discontinuities, or network interruption acceptance test.
- No user manual acceptance test for full v1.2.6 feature parity.

**Release decision: BLOCKED.** Restore missing features on a development branch, expand real v1.2.8 test coverage, and publish only after green regression CI plus Windows/BaoStock/THS acceptance.
