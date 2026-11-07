"""Verified BaoStock snapshot synchronizer for AShareMAScanner stage 2.

The module is also inlined into the development .pyw for single-file delivery.
Default VPS HTTPS URL is built in. Override via data/marketdata_client.json
or ASHARE_MARKETDATA_URL. Existing AKShare storage is never modified.
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


class RemoteMarketdataError(RuntimeError):
    """A remote dataset is not available, safe or complete."""


class RemoteMarketdataCancelled(RemoteMarketdataError):
    """The user stopped the stage-2 import."""


DEFAULT_MARKETDATA_URL = "https://23.95.88.6:8443/marketdata/latest.json"


class RemoteMarketdataClient:
    MAX_MANIFEST_BYTES = 65536
    MAX_ZIP_BYTES = 128 * 1024 * 1024
    MAX_SQLITE_BYTES = 384 * 1024 * 1024
    SNAPSHOT_MEMBER = "marketdata.sqlite3"
    TABLE_COLUMNS = {
        "daily": "code,trade_date,name,close,volume,trade_status,is_st,turnover",
        "day_universe": "trade_date,code,name,trade_status",
        "day_status": "trade_date,expected_count,saved_count,failed_count,status,updated_at",
        "industry_cache": "code,name,industry,update_date,classification,fetched_at",
        "server_meta": "key,value",
    }

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "a_share_baostock_hfq.db"
        self.config_path = self.data_dir / "marketdata_client.json"
        cfg = {}
        if self.config_path.exists():
            try:
                cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
                if not isinstance(cfg, dict):
                    raise ValueError("配置必须是 JSON 对象")
            except (OSError, ValueError) as exc:
                raise RemoteMarketdataError(f"远程数据配置无效：{exc}") from exc
        raw_url = (os.environ.get("ASHARE_MARKETDATA_URL", "").strip()
                   or str(cfg.get("manifest_url", "")).strip()
                   or DEFAULT_MARKETDATA_URL)
        if raw_url and not raw_url.endswith(".json"):
            raw_url = raw_url.rstrip("/") + "/latest.json"
        self.manifest_url = raw_url
        self.min_completeness = max(0.995, float(cfg.get("min_completeness", 0.995)))
        self.cached_max_days = max(0, min(10, int(cfg.get("offline_cache_max_days", 4))))
        if self.manifest_url:
            self._validate_url(self.manifest_url)

    @property
    def enabled(self) -> bool:
        return bool(self.manifest_url)

    @staticmethod
    def _validate_url(url: str):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme == "https" and parsed.hostname and not parsed.username
                and not parsed.password):
            return
        if (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
                and not parsed.username and not parsed.password):
            return
        raise RemoteMarketdataError("远程行情仅允许 HTTPS；本机测试可使用 localhost HTTP")

    def _validate_final_url(self, response):
        original = urllib.parse.urlsplit(self.manifest_url)
        actual = urllib.parse.urlsplit(response.geturl())
        if (original.scheme, original.hostname, original.port) != (actual.scheme, actual.hostname, actual.port):
            raise RemoteMarketdataError("远程接口重定向到了其他站点，拒绝下载")

    @staticmethod
    def _check_cancel(cancel_event):
        if cancel_event is not None and cancel_event.is_set():
            raise RemoteMarketdataCancelled("已停止远程数据同步；原数据库保持不变")

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(part)
        return h.hexdigest()

    def _read_manifest(self, cancel_event):
        self._check_cancel(cancel_event)
        request = urllib.request.Request(self.manifest_url, headers={
            "Accept": "application/json", "Cache-Control": "no-cache",
            "User-Agent": "AShareMAScanner-RemoteData/1.0",
        })
        try:
            with urllib.request.urlopen(request, timeout=12) as resp:
                self._validate_final_url(resp)
                content = resp.read(self.MAX_MANIFEST_BYTES + 1)
        except (OSError, ValueError) as exc:
            raise RemoteMarketdataError(f"服务器清单暂不可用：{exc}") from exc
        if len(content) > self.MAX_MANIFEST_BYTES:
            raise RemoteMarketdataError("服务器清单超过大小限制")
        try:
            manifest = json.loads(content.decode("utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("清单不是 JSON 对象")
            if manifest.get("provider") != "BaoStock" or int(manifest.get("schema_version", -1)) != 1:
                raise ValueError("不是受支持的 BaoStock 快照")
            market_date = str(manifest["market_date"])
            if datetime.strptime(market_date, "%Y-%m-%d").strftime("%Y-%m-%d") != market_date:
                raise ValueError("行情日期格式无效")
            digest = str(manifest["snapshot_sha256"]).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("缺少合法的 SHA-256 校验值")
            size = int(manifest["snapshot_size"])
            if size < 100 or size > self.MAX_ZIP_BYTES:
                raise ValueError("ZIP 文件大小超出安全范围")
            completeness = float(manifest["completeness"])
            expected, saved = int(manifest["expected_count"]), int(manifest["saved_count"])
            if (expected <= 0 or saved <= 0 or saved > expected
                    or completeness < self.min_completeness or completeness > 1.0
                    or saved / expected + 1e-6 < self.min_completeness):
                raise ValueError("服务器数据完整率不足，拒绝覆盖本地缓存")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise RemoteMarketdataError(f"服务器清单校验失败：{exc}") from exc
        self._check_cancel(cancel_event)
        return manifest

    def _read_cached(self):
        if not self.db_path.is_file():
            return None
        try:
            with contextlib.closing(sqlite3.connect(self.db_path, timeout=3)) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    return None
                meta = dict(db.execute("SELECT key,value FROM server_meta WHERE key IN "
                                       "('remote_snapshot_sha256','remote_snapshot_market_date')"))
                market_date = meta.get("remote_snapshot_market_date")
                if not market_date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", market_date):
                    return None
                row = db.execute("SELECT expected_count,saved_count,failed_count "
                                 "FROM day_status WHERE trade_date=?", (market_date,)).fetchone()
                if not row or row[0] <= 0 or row[1] / row[0] < self.min_completeness:
                    return None
                prior = db.execute("SELECT MAX(trade_date) FROM daily WHERE trade_date<?", (market_date,)).fetchone()[0]
                return {"market_date": market_date, "digest": meta.get("remote_snapshot_sha256"),
                        "expected": int(row[0]), "saved": int(row[1]), "failed": int(row[2]),
                        "previous": prior}
        except (OSError, sqlite3.Error):
            return None

    @staticmethod
    def _to_result(cached, warning):
        return {
            "scan_date": cached["market_date"],
            "previous_trade_date": cached["previous"],
            "completeness": cached["saved"] / cached["expected"] * 100,
            "expected": cached["expected"], "saved": cached["saved"],
            "failed": cached["failed"], "today_pending": False,
            "warning": warning,
        }

    def use_offline_cache(self, reason):
        cached = self._read_cached()
        if cached is None:
            return None
        age = (datetime.now(timezone(timedelta(hours=8))).date()
               - datetime.strptime(cached["market_date"], "%Y-%m-%d").date()).days
        if not 0 <= age <= self.cached_max_days:
            return None
        return self._to_result(cached,
                               f"VPS 暂不可用（{reason}）；使用已验证的 BaoStock 缓存 {cached['market_date']}，请注意行情时效。")

    def _download_snapshot(self, manifest, dest, cb, cancel_event):
        # Deliberately derive the snapshot URL from the validated manifest origin.
        # An untrusted snapshot_url in JSON cannot redirect to a different host.
        snapshot_url = urllib.parse.urljoin(self.manifest_url, "snapshot.zip")
        self._validate_url(snapshot_url)
        request = urllib.request.Request(snapshot_url, headers={
            "Accept": "application/zip", "User-Agent": "AShareMAScanner-RemoteData/1.0",
        })
        received = 0
        expected = int(manifest["snapshot_size"])
        h = hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=45) as resp, dest.open("wb") as stream:
                self._validate_final_url(resp)
                while True:
                    self._check_cancel(cancel_event)
                    part = resp.read(1024 * 1024)
                    if not part:
                        break
                    received += len(part)
                    if received > expected or received > self.MAX_ZIP_BYTES:
                        raise RemoteMarketdataError("下载文件超过清单指定大小")
                    h.update(part)
                    stream.write(part)
                    cb(10 + 45 * received / expected,
                       f"从 VPS 下载行情快照 {received / 1048576:.1f}/{expected / 1048576:.1f} MiB")
        except (OSError, ValueError) as exc:
            raise RemoteMarketdataError(f"下载行情快照失败：{exc}") from exc
        if received != expected or h.hexdigest() != manifest["snapshot_sha256"].lower():
            raise RemoteMarketdataError("下载文件大小或 SHA-256 不匹配，已拒绝导入")

    def _extract(self, path, dest, cancel_event):
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if len(members) != 1 or members[0].filename != self.SNAPSHOT_MEMBER:
                    raise RemoteMarketdataError("ZIP 内容不符合服务器快照格式")
                info = members[0]
                if not 4096 <= info.file_size <= self.MAX_SQLITE_BYTES:
                    raise RemoteMarketdataError("SQLite 文件大小不在安全范围")
                total = 0
                with archive.open(info) as src, dest.open("wb") as dst:
                    while True:
                        self._check_cancel(cancel_event)
                        part = src.read(1024 * 1024)
                        if not part:
                            break
                        total += len(part)
                        if total > self.MAX_SQLITE_BYTES:
                            raise RemoteMarketdataError("解压内容超过安全大小")
                        dst.write(part)
                if total != info.file_size:
                    raise RemoteMarketdataError("SQLite 解压长度不一致")
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise RemoteMarketdataError(f"ZIP 校验失败：{exc}") from exc

    def _validate_sqlite(self, path, manifest):
        try:
            with contextlib.closing(sqlite3.connect(path, timeout=5)) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("SQLite quick_check 失败")
                for table, fields in self.TABLE_COLUMNS.items():
                    columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                    if not set(fields.split(",")).issubset(columns):
                        raise ValueError(f"{table} 表缺失必要字段")
                meta = dict(db.execute("SELECT key,value FROM server_meta"))
                if (meta.get("provider") != "BaoStock"
                        or meta.get("market_date") != manifest["market_date"]
                        or meta.get("schema_version") != "1"):
                    raise ValueError("SQLite 内部元信息与清单不一致")
                date = manifest["market_date"]
                expected = db.execute("SELECT COUNT(*) FROM day_universe WHERE trade_date=? "
                                      "AND trade_status=1", (date,)).fetchone()[0]
                saved = db.execute("SELECT COUNT(*) FROM day_universe u JOIN daily d "
                                   "ON d.trade_date=u.trade_date AND d.code=u.code "
                                   "WHERE u.trade_date=? AND u.trade_status=1 AND d.trade_status=1 "
                                   "AND d.close>0 AND d.volume>=0", (date,)).fetchone()[0]
                if expected != int(manifest["expected_count"]) or saved != int(manifest["saved_count"]):
                    raise ValueError("SQLite 当日数据量与清单不符")
                row = db.execute("SELECT expected_count,saved_count FROM day_status "
                                 "WHERE trade_date=?", (date,)).fetchone()
                if not row or tuple(row) != (expected, saved):
                    raise ValueError("SQLite 当日状态与实际数据不符")
        except (sqlite3.Error, ValueError) as exc:
            raise RemoteMarketdataError(f"SQLite 快照校验失败：{exc}") from exc

    def _install(self, incoming, manifest, stage, cancel_event):
        target = self.db_path
        staged_db = stage / "new-local.sqlite3"
        self._check_cancel(cancel_event)
        if target.is_file():
            # Stage 2 runs before Qt / scanner workers. Checkpoint old WAL before
            # replacement; a busy database must not be silently overwritten.
            with contextlib.closing(sqlite3.connect(target, timeout=5)) as old:
                old.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                old.execute("PRAGMA journal_mode=DELETE")
                old.commit()
                with contextlib.closing(sqlite3.connect(staged_db)) as new:
                    old.backup(new)
                    new.commit()
            with contextlib.closing(sqlite3.connect(staged_db)) as db:
                db.execute("PRAGMA journal_mode=DELETE")
                db.execute("ATTACH DATABASE ? AS incoming", (str(incoming),))
                try:
                    start = db.execute("SELECT MIN(trade_date) FROM incoming.daily").fetchone()[0]
                    end = manifest["market_date"]
                    if not start:
                        raise RemoteMarketdataError("快照没有历史交易记录")
                    with db:
                        for name in ("daily", "day_universe", "day_status"):
                            db.execute(f"DELETE FROM main.{name} WHERE trade_date BETWEEN ? AND ?", (start, end))
                            cols = self.TABLE_COLUMNS[name]
                            db.execute(f"INSERT INTO main.{name} ({cols}) SELECT {cols} FROM incoming.{name}")
                        db.execute("DELETE FROM main.industry_cache")
                        db.execute("INSERT INTO main.industry_cache SELECT * FROM incoming.industry_cache")
                        db.execute("CREATE TABLE IF NOT EXISTS main.server_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                        db.execute("INSERT OR REPLACE INTO main.server_meta SELECT key,value FROM incoming.server_meta")
                finally:
                    db.execute("DETACH DATABASE incoming")
        else:
            shutil.copyfile(incoming, staged_db)
        with contextlib.closing(sqlite3.connect(staged_db, timeout=5)) as db:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS server_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("INSERT OR REPLACE INTO server_meta VALUES ('remote_snapshot_sha256', ?)",
                           (manifest["snapshot_sha256"].lower(),))
                db.execute("INSERT OR REPLACE INTO server_meta VALUES ('remote_snapshot_market_date', ?)",
                           (manifest["market_date"],))
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RemoteMarketdataError("导入后的数据库完整性校验失败")
        self._check_cancel(cancel_event)
        os.replace(staged_db, target)

    def sync(self, cb, cancel_event=None):
        if not self.enabled:
            raise RemoteMarketdataError("未配置远程市场数据地址")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        cb(1, "连接 VPS 行情服务，读取最新数据清单")
        manifest = self._read_manifest(cancel_event)
        cached = self._read_cached()
        if cached and cached["market_date"] > manifest["market_date"]:
            cb(97, "本地 BaoStock 快照比服务器新，保留本地数据")
            return self._to_result(cached, f"使用本地较新快照 {cached['market_date']}，未覆盖旧版服务器数据")
        if cached and cached["digest"] == manifest["snapshot_sha256"].lower():
            cb(97, f"VPS 行情无变化，直接使用本地快照 {cached['market_date']}")
            return self._to_result(cached, "已使用验证过的 VPS BaoStock 行情缓存")
        cb(8, f"发现 VPS 新快照：{manifest['market_date']}，准备校验下载")
        with tempfile.TemporaryDirectory(prefix=".marketdata-", dir=self.data_dir) as temp:
            stage = Path(temp)
            archive = stage / "snapshot.zip"
            incoming = stage / self.SNAPSHOT_MEMBER
            self._download_snapshot(manifest, archive, cb, cancel_event)
            cb(58, "校验 ZIP 并提取 SQLite 快照")
            self._extract(archive, incoming, cancel_event)
            cb(67, "验证 SQLite 数据库结构、行情日期及数据完整率")
            self._validate_sqlite(incoming, manifest)
            cb(78, "将远程行情安全导入独立 BaoStock 本地缓存")
            self._install(incoming, manifest, stage, cancel_event)
        cb(97, f"BaoStock 行情已更新至 {manifest['market_date']}")
        current = self._read_cached()
        if not current or current["digest"] != manifest["snapshot_sha256"].lower():
            raise RemoteMarketdataError("安装完成但本地数据库校验失败")
        return self._to_result(current, "行情来自 VPS BaoStock 已验证快照")
