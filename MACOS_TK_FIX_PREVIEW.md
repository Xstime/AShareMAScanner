# macOS Tkinter/Tcl crash fix — v1.3.2 preview (not yet released)

This experimental branch includes `A股MA扫描器_v1.3.2.pyw` for macOS Apple Silicon testing. **The published v1.3.1 release and official v1.3.1 source remain unchanged.** The preview is NOT an official Release yet.

## Root cause

On macOS the scanner runs Tkinter stage 1 (dependency window), Tkinter stage 2 (BaoStock update), then PySide6 stage 3. After the Tk event loop exits, unreachable Tk `StringVar` and `DoubleVar` cycles can be finalized by Python's GC on a background thread. This triggers `RuntimeError: main thread is not in main loop` and, on some Tcl builds, fatal `Tcl_AsyncDelete: async handler deleted by the wrong thread`.

`qt.qpa.fonts: ... "Segoe UI"` is only a cosmetic warning; BaoStock "login success/logout success" are expected session logs.

## Changes

- Explicit main-thread garbage collection after each completed Tk stage, **before** creating Qt `QApplication`.
- Separate Tk stage worker scope so all local Tcl vars and callback cycles become collectible on the GUI thread.
- Join market update worker before the transition, avoiding leftover worker access to shared resources.
- Use macOS `Helvetica Neue` for the PySide6 application font.
- The legacy published v1.3.1 source remains byte-for-byte identical to main.
- No stock scan, update/release, BaoStock, cache path or SQLite schema changes.

## Validation

`.github/workflows/test-macos-tk-teardown.yml` tests a real Tk to Qt transition, three consecutive Tk stage lifecycles, forced garbage collection on a worker thread **after** Tk disposal, cancellation behavior, and existing scanner/update routines on native macOS arm64, Windows, and Linux.

The CI environment cannot guarantee the same exact Tcl/Tk and Python framework as an individual user's `/usr/local/bin/python3` installation. The preview needs validation on the affected computer.

## Try manually

Download `A股MA扫描器_v1.3.2.pyw` from this branch, place it next to your existing `data/` folder and launch with your existing Python executable. Do not delete or overwrite `data/`. Back up the database directory first if using real market data.

This test version is ahead of the latest published v1.3.1, so the manual updater will not intentionally downgrade it. Do not publish v1.3.2 until the macOS lifecycle tests have passed.
