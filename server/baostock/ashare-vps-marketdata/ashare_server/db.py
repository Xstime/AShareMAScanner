from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

CST = timezone(timedelta(hours=8))


@contextmanager
def connect(path: Path, timeout: float = 30):
    conn = sqlite3.connect(path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def now_text() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def retry_delay_hours(count: int, base: int = 6, maximum: int = 168) -> int:
    count = max(1, int(count or 1))
    return min(maximum, base * (2 ** min(count - 1, 5)))


def retry_is_due(next_retry_at: str | None, now: datetime | None = None) -> bool:
    if not next_retry_at:
        return True
    try:
        due = datetime.strptime(next_retry_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
    except (TypeError, ValueError):
        return True
    current = now or datetime.now(CST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=CST)
    return current >= due


class MarketDB:
    def __init__(self, path: Path, max_api_requests_per_day: int = 45000,
                 retry_base_hours: int = 6, retry_max_hours: int = 168):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_api_requests_per_day = max_api_requests_per_day
        self.retry_base_hours = retry_base_hours
        self.retry_max_hours = retry_max_hours
        self.init_schema()

    def init_schema(self) -> None:
        with connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS daily (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                name TEXT,
                close REAL,
                volume REAL,
                trade_status INTEGER,
                is_st INTEGER,
                turnover REAL,
                PRIMARY KEY(code, trade_date)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_date ON daily(trade_date);
            CREATE INDEX IF NOT EXISTS idx_daily_code_date ON daily(code, trade_date);

            CREATE TABLE IF NOT EXISTS day_universe (
                trade_date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                trade_status INTEGER,
                PRIMARY KEY(trade_date, code)
            );
            CREATE TABLE IF NOT EXISTS day_status (
                trade_date TEXT PRIMARY KEY,
                expected_count INTEGER NOT NULL DEFAULT 0,
                saved_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'partial',
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS fetch_queue (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                name TEXT,
                reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                next_retry_at TEXT,
                PRIMARY KEY(code, trade_date)
            );
            CREATE TABLE IF NOT EXISTS stock_state (
                code TEXT PRIMARY KEY,
                name TEXT,
                history_ready INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS init_queue (
                code TEXT PRIMARY KEY,
                name TEXT,
                start_date TEXT,
                end_date TEXT,
                reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                next_retry_at TEXT
            );
            CREATE TABLE IF NOT EXISTS industry_cache (
                code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                update_date TEXT,
                classification TEXT,
                fetched_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_industry_name ON industry_cache(industry);
            CREATE TABLE IF NOT EXISTS server_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_usage (
                china_date TEXT PRIMARY KEY,
                request_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS update_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                market_date TEXT,
                expected_count INTEGER DEFAULT 0,
                saved_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                api_requests INTEGER DEFAULT 0,
                duration_seconds REAL,
                message TEXT
            );
            """)
            # Upgrade old scanner-compatible databases without deleting any data.
            for table, column, declaration in (
                ("fetch_queue", "next_retry_at", "TEXT"),
                ("init_queue", "next_retry_at", "TEXT"),
            ):
                columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                if column not in columns:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
            db.execute("INSERT OR REPLACE INTO server_meta(key,value) VALUES('schema_version','1')")

    def consume_api_request(self) -> int:
        today = datetime.now(CST).strftime("%Y-%m-%d")
        with connect(self.path) as db:
            row = db.execute("SELECT request_count FROM api_usage WHERE china_date=?", (today,)).fetchone()
            current = int(row[0]) if row else 0
            if current >= self.max_api_requests_per_day:
                raise RuntimeError(
                    f"已达到 BaoStock 安全请求上限 {self.max_api_requests_per_day}/日；"
                    "本次停止，避免触发接口限制，明日 18:00 自动续跑"
                )
            new_count = current + 1
            db.execute("""INSERT INTO api_usage(china_date,request_count,updated_at)
                VALUES(?,?,?) ON CONFLICT(china_date) DO UPDATE SET
                request_count=excluded.request_count,updated_at=excluded.updated_at""",
                (today, new_count, now_text()))
        return new_count

    def api_requests_today(self) -> int:
        today = datetime.now(CST).strftime("%Y-%m-%d")
        with connect(self.path) as db:
            row = db.execute("SELECT request_count FROM api_usage WHERE china_date=?", (today,)).fetchone()
            return int(row[0]) if row else 0

    def set_meta(self, key: str, value: str) -> None:
        with connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO server_meta(key,value) VALUES(?,?)", (key, str(value)))

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with connect(self.path) as db:
            row = db.execute("SELECT value FROM server_meta WHERE key=?", (key,)).fetchone()
            return str(row[0]) if row else default

    def persist_universe(self, trade_date: str, universe: pd.DataFrame) -> None:
        rows = [(trade_date, str(r.code), str(r.name or ""), int(r.trade_status))
                for r in universe.itertuples(index=False)]
        with connect(self.path) as db:
            db.executemany("""INSERT OR REPLACE INTO day_universe
                (trade_date,code,name,trade_status) VALUES(?,?,?,?)""", rows)

    def get_universe(self, trade_date: str) -> pd.DataFrame:
        with connect(self.path) as db:
            rows = db.execute("SELECT code,name,trade_status FROM day_universe WHERE trade_date=? ORDER BY code",
                              (trade_date,)).fetchall()
        return pd.DataFrame([dict(r) for r in rows], columns=["code", "name", "trade_status"])

    def history_ready_codes(self) -> set[str]:
        with connect(self.path) as db:
            rows = db.execute("SELECT code FROM stock_state WHERE history_ready=1").fetchall()
        return {str(r[0]) for r in rows}

    def init_retry_map(self) -> dict[str, tuple[int, str | None]]:
        with connect(self.path) as db:
            rows = db.execute("SELECT code,retry_count,next_retry_at FROM init_queue").fetchall()
        return {str(r[0]): (int(r[1]), r[2]) for r in rows}

    def mark_history_ready(self, db: sqlite3.Connection, code: str, name: str) -> None:
        db.execute("""INSERT INTO stock_state(code,name,history_ready,updated_at)
            VALUES(?,?,1,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name,
            history_ready=1,updated_at=excluded.updated_at""", (code, name, now_text()))
        db.execute("DELETE FROM init_queue WHERE code=?", (code,))

    def queue_init_failure(self, db: sqlite3.Connection, code: str, name: str,
                           start_date: str, end_date: str, reason: str) -> None:
        old = db.execute("SELECT retry_count FROM init_queue WHERE code=?", (code,)).fetchone()
        count = (int(old[0]) if old else 0) + 1
        delay = retry_delay_hours(count, self.retry_base_hours, self.retry_max_hours)
        stamp = datetime.now(CST)
        db.execute("""INSERT INTO init_queue(code,name,start_date,end_date,reason,retry_count,updated_at,next_retry_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET
            name=excluded.name,start_date=excluded.start_date,end_date=excluded.end_date,
            reason=excluded.reason,retry_count=excluded.retry_count,updated_at=excluded.updated_at,
            next_retry_at=excluded.next_retry_at""",
            (code, name, start_date, end_date, str(reason)[:500], count,
             stamp.strftime("%Y-%m-%d %H:%M:%S"),
             (stamp + timedelta(hours=delay)).strftime("%Y-%m-%d %H:%M:%S")))

    def day_retry_map(self, trade_date: str) -> dict[str, tuple[int, str | None]]:
        with connect(self.path) as db:
            rows = db.execute("SELECT code,retry_count,next_retry_at FROM fetch_queue WHERE trade_date=?",
                              (trade_date,)).fetchall()
        return {str(r[0]): (int(r[1]), r[2]) for r in rows}

    def queue_day_failure(self, db: sqlite3.Connection, code: str, trade_date: str,
                          name: str, reason: str) -> None:
        old = db.execute("SELECT retry_count FROM fetch_queue WHERE code=? AND trade_date=?",
                         (code, trade_date)).fetchone()
        count = (int(old[0]) if old else 0) + 1
        delay = retry_delay_hours(count, self.retry_base_hours, self.retry_max_hours)
        stamp = datetime.now(CST)
        db.execute("""INSERT INTO fetch_queue(code,trade_date,name,reason,retry_count,updated_at,next_retry_at)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(code,trade_date) DO UPDATE SET
            name=excluded.name,reason=excluded.reason,retry_count=excluded.retry_count,
            updated_at=excluded.updated_at,next_retry_at=excluded.next_retry_at""",
            (code, trade_date, name, str(reason)[:500], count,
             stamp.strftime("%Y-%m-%d %H:%M:%S"),
             (stamp + timedelta(hours=delay)).strftime("%Y-%m-%d %H:%M:%S")))

    def clear_day_failure(self, db: sqlite3.Connection, code: str, trade_date: str) -> None:
        db.execute("DELETE FROM fetch_queue WHERE code=? AND trade_date=?", (code, trade_date))

    def upsert_daily_rows(self, db: sqlite3.Connection, rows: Iterable[tuple]) -> None:
        db.executemany("""INSERT OR REPLACE INTO daily
            (code,trade_date,name,close,volume,trade_status,is_st,turnover)
            VALUES(?,?,?,?,?,?,?,?)""", list(rows))

    def get_existing_codes(self, trade_date: str) -> set[str]:
        with connect(self.path) as db:
            rows = db.execute("SELECT code FROM daily WHERE trade_date=? AND trade_status=1", (trade_date,)).fetchall()
        return {str(r[0]) for r in rows}

    def update_day_status(self, trade_date: str) -> dict:
        with connect(self.path) as db:
            expected = int(db.execute("SELECT COUNT(*) FROM day_universe WHERE trade_date=? AND trade_status=1",
                                      (trade_date,)).fetchone()[0])
            saved = int(db.execute("""SELECT COUNT(*) FROM day_universe u JOIN daily d
                ON d.code=u.code AND d.trade_date=u.trade_date
                WHERE u.trade_date=? AND u.trade_status=1 AND d.trade_status=1""",
                (trade_date,)).fetchone()[0])
            failed = max(0, expected - saved)
            status = "complete" if expected > 0 and failed == 0 else "partial"
            db.execute("""INSERT OR REPLACE INTO day_status
                (trade_date,expected_count,saved_count,failed_count,status,updated_at)
                VALUES(?,?,?,?,?,?)""", (trade_date, expected, saved, failed, status, now_text()))
        return {"trade_date": trade_date, "expected": expected, "saved": saved,
                "failed": failed, "status": status,
                "completeness": (saved / expected) if expected else 0.0}

    def day_status(self, trade_date: str) -> dict | None:
        with connect(self.path) as db:
            row = db.execute("SELECT * FROM day_status WHERE trade_date=?", (trade_date,)).fetchone()
        return dict(row) if row else None

    def latest_complete_date(self) -> str | None:
        with connect(self.path) as db:
            row = db.execute("SELECT MAX(trade_date) FROM day_status WHERE status='complete'").fetchone()
        return row[0] if row and row[0] else None

    def partial_dates(self, latest: str) -> list[str]:
        with connect(self.path) as db:
            rows = db.execute("SELECT trade_date FROM day_status WHERE status!='complete' AND trade_date<=? ORDER BY trade_date",
                              (latest,)).fetchall()
        return [str(r[0]) for r in rows]

    def industry_info(self) -> tuple[int, str | None]:
        with connect(self.path) as db:
            row = db.execute("SELECT COUNT(*),MAX(fetched_at) FROM industry_cache").fetchone()
        return int(row[0] or 0), row[1]

    def replace_industry(self, rows: Iterable[tuple]) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM industry_cache")
            db.executemany("""INSERT INTO industry_cache
                (code,name,industry,update_date,classification,fetched_at)
                VALUES(?,?,?,?,?,?)""", list(rows))

    def record_run_start(self) -> int:
        with connect(self.path) as db:
            cur = db.execute("INSERT INTO update_runs(started_at,status) VALUES(?,'running')", (now_text(),))
            return int(cur.lastrowid)

    def record_run_end(self, run_id: int, status: str, market_date: str | None,
                       expected: int, saved: int, failed: int, requests: int,
                       duration: float, message: str) -> None:
        with connect(self.path) as db:
            db.execute("""UPDATE update_runs SET finished_at=?,status=?,market_date=?,
                expected_count=?,saved_count=?,failed_count=?,api_requests=?,duration_seconds=?,message=?
                WHERE run_id=?""", (now_text(), status, market_date, expected, saved, failed,
                requests, duration, message[:2000], run_id))

    def prune_old_data(self, retention_days: int = 120) -> int:
        """Keep a bounded rolling market history after a verified snapshot is published."""
        with connect(self.path) as db:
            dates = [r[0] for r in db.execute(
                "SELECT DISTINCT trade_date FROM daily ORDER BY trade_date DESC LIMIT ?",
                (int(retention_days),)
            ).fetchall()]
            if not dates:
                return 0
            cutoff = min(dates)
            before = int(db.execute("SELECT COUNT(*) FROM daily").fetchone()[0])
            db.execute("DELETE FROM daily WHERE trade_date<?", (cutoff,))
            db.execute("DELETE FROM day_universe WHERE trade_date<?", (cutoff,))
            db.execute("DELETE FROM day_status WHERE trade_date<?", (cutoff,))
            db.execute("DELETE FROM fetch_queue WHERE trade_date<?", (cutoff,))
            after = int(db.execute("SELECT COUNT(*) FROM daily").fetchone()[0])
            db.execute("PRAGMA optimize")
        return before - after
