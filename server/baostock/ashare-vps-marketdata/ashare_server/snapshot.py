from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import connect, now_text

LOG = logging.getLogger(__name__)
CST = timezone(timedelta(hours=8))


class SnapshotPublisher:
    """Publish an immutable, client-compatible market-data SQLite snapshot."""

    def __init__(self, db_path: Path, public_dir: Path, public_base_url: str = "",
                 retention_days: int = 120):
        self.db_path = Path(db_path)
        self.public_dir = Path(public_dir)
        self.public_base_url = public_base_url.rstrip("/")
        self.retention_days = retention_days
        self.public_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _build_snapshot_db(self, target: Path, market_date: str, status: dict,
                           history_ready: int) -> None:
        # ATTACH lets SQLite copy tables server-side without loading hundreds of
        # thousands of daily rows into Python memory on the 1 GB VPS.
        with connect(self.db_path) as src:
            dates = [r[0] for r in src.execute(
                "SELECT DISTINCT trade_date FROM daily WHERE trade_date<=? "
                "ORDER BY trade_date DESC LIMIT ?", (market_date, self.retention_days)
            ).fetchall()]
            cutoff = min(dates) if dates else market_date
            src.execute("ATTACH DATABASE ? AS snapshot", (str(target),))
            try:
                src.executescript("""
                CREATE TABLE snapshot.daily (
                    code TEXT NOT NULL, trade_date TEXT NOT NULL, name TEXT,
                    close REAL, volume REAL, trade_status INTEGER, is_st INTEGER,
                    turnover REAL, PRIMARY KEY(code,trade_date));
                CREATE INDEX snapshot.idx_daily_date ON daily(trade_date);
                CREATE INDEX snapshot.idx_daily_code_date ON daily(code,trade_date);
                CREATE TABLE snapshot.day_universe (
                    trade_date TEXT NOT NULL, code TEXT NOT NULL, name TEXT,
                    trade_status INTEGER, PRIMARY KEY(trade_date,code));
                CREATE TABLE snapshot.day_status (
                    trade_date TEXT PRIMARY KEY, expected_count INTEGER NOT NULL DEFAULT 0,
                    saved_count INTEGER NOT NULL DEFAULT 0, failed_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'partial', updated_at TEXT);
                CREATE TABLE snapshot.industry_cache (
                    code TEXT PRIMARY KEY, name TEXT, industry TEXT, update_date TEXT,
                    classification TEXT, fetched_at TEXT);
                CREATE TABLE snapshot.server_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                """)
                src.execute("INSERT INTO snapshot.daily SELECT code,trade_date,name,close,volume,trade_status,is_st,turnover "
                            "FROM main.daily WHERE trade_date>=? AND trade_date<=?", (cutoff, market_date))
                src.execute("INSERT INTO snapshot.day_universe SELECT trade_date,code,name,trade_status "
                            "FROM main.day_universe WHERE trade_date>=? AND trade_date<=?", (cutoff, market_date))
                src.execute("INSERT INTO snapshot.day_status SELECT trade_date,expected_count,saved_count,failed_count,status,updated_at "
                            "FROM main.day_status WHERE trade_date>=? AND trade_date<=?", (cutoff, market_date))
                src.execute("INSERT INTO snapshot.industry_cache SELECT code,name,industry,update_date,classification,fetched_at "
                            "FROM main.industry_cache")
                metadata = {
                    "schema_version": "1",
                    "market_date": market_date,
                    "generated_at": now_text(),
                    "provider": "BaoStock",
                    "adjustment": "不复权 (adjustflag=3)",
                    "volume_unit": "shares",
                    "turnover_unit": "percent",
                    "history_ready_count": str(history_ready),
                    "retention_days": str(len(dates)),
                    "completeness": str(status.get("completeness", 0.0)),
                }
                src.executemany("INSERT INTO snapshot.server_meta(key,value) VALUES(?,?)", metadata.items())
                src.commit()
                check = src.execute("PRAGMA snapshot.integrity_check").fetchone()[0]
                if check != "ok":
                    raise RuntimeError(f"snapshot SQLite integrity_check failed: {check}")
            finally:
                src.execute("DETACH DATABASE snapshot")

    def publish(self, market_date: str, status: dict, history_ready: int) -> dict:
        fd, temp_db_name = tempfile.mkstemp(prefix="marketdata-", suffix=".sqlite3", dir=self.public_dir)
        os.close(fd)
        temp_db = Path(temp_db_name)
        temp_zip = self.public_dir / "snapshot.zip.tmp"
        temp_manifest = self.public_dir / "latest.json.tmp"
        final_manifest = self.public_dir / "latest.json"
        try:
            self._build_snapshot_db(temp_db, market_date, status, history_ready)
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.write(temp_db, arcname="marketdata.sqlite3")
            with zipfile.ZipFile(temp_zip, "r") as archive:
                bad = archive.testzip()
                if bad:
                    raise RuntimeError(f"snapshot ZIP CRC check failed: {bad}")
            digest = self.sha256(temp_zip)
            size = temp_zip.stat().st_size
            snapshot_file = f"snapshot-{digest[:16]}.zip"
            final_zip = self.public_dir / snapshot_file
            snapshot_url = (self.public_base_url + "/snapshot.zip") if self.public_base_url else "snapshot.zip"
            manifest = {
                "schema_version": 1,
                "dataset_version": f"baostock-{market_date}-{digest[:12]}",
                "provider": "BaoStock",
                "market_date": market_date,
                "generated_at": now_text(),
                "status": status.get("status", "partial"),
                "expected_count": int(status.get("expected", 0)),
                "saved_count": int(status.get("saved", 0)),
                "failed_count": int(status.get("failed", 0)),
                "completeness": round(float(status.get("completeness", 0.0)), 6),
                "history_ready_count": int(history_ready),
                "snapshot_name": "snapshot.zip",
                "snapshot_file": snapshot_file,
                "snapshot_url": snapshot_url,
                "snapshot_size": size,
                "snapshot_sha256": digest,
                "adjustment": "不复权 (adjustflag=3)",
                "volume_unit": "shares",
                "turnover_unit": "percent",
            }
            temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            # Snapshot is replaced first; the manifest is the commit marker clients trust.
            os.replace(temp_zip, final_zip)
            os.replace(temp_manifest, final_manifest)
            # Keep the current and previous immutable snapshots for in-flight downloads.
            versions = sorted(self.public_dir.glob("snapshot-*.zip"),
                              key=lambda item: item.stat().st_mtime, reverse=True)
            for obsolete in versions[2:]:
                obsolete.unlink(missing_ok=True)
            LOG.info("Published market snapshot: date=%s rows=%s bytes=%s sha256=%s",
                     market_date, status.get("saved", 0), size, digest)
            return manifest
        finally:
            temp_db.unlink(missing_ok=True)
            temp_zip.unlink(missing_ok=True)
            temp_manifest.unlink(missing_ok=True)
