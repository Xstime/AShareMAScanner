from __future__ import annotations

import fcntl
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .config import Settings, settings
from .db import MarketDB, connect, now_text, retry_is_due
from .provider import (BaoStockBlacklistError, BaoStockProvider,
                       BaoStockRequestLimitError, is_a_share_code,
                       normalize_industry)
from .snapshot import SnapshotPublisher

LOG = logging.getLogger(__name__)
CST = timezone(timedelta(hours=8))


class MarketDataUnavailable(RuntimeError):
    pass


def safe_float(value):
    try:
        if value in (None, "", "nan", "NaN"):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def safe_int(value, default=0):
    try:
        if value in (None, "", "nan", "NaN"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _row_value(row, name, default=None):
    try:
        return getattr(row, name)
    except AttributeError:
        return default


class MarketUpdater:
    def __init__(self, config: Settings = settings, provider: BaoStockProvider | None = None):
        self.config = config
        self.db = MarketDB(
            config.db_path,
            max_api_requests_per_day=config.max_api_requests_per_day,
            retry_base_hours=config.retry_base_hours,
            retry_max_hours=config.retry_max_hours,
        )
        self.provider = provider or BaoStockProvider(request_counter=self.db.consume_api_request)
        self.publisher = SnapshotPublisher(
            config.db_path, config.public_dir, config.public_base_url,
            retention_days=config.retention_days,
        )

    def _rows_to_daily(self, frame: pd.DataFrame, fallback_name: str = "") -> list[tuple]:
        if frame is None or frame.empty:
            return []
        rows = []
        for item in frame.itertuples(index=False):
            code = str(_row_value(item, "code", "") or "")
            trade_date = str(_row_value(item, "date", "") or "")
            if not is_a_share_code(code) or len(trade_date) != 10:
                continue
            close = safe_float(_row_value(item, "close"))
            volume = safe_float(_row_value(item, "volume"))
            if close is None or close <= 0 or volume is None or volume < 0:
                continue
            trade_status = safe_int(_row_value(item, "tradestatus", 1), 1)
            is_st = safe_int(_row_value(item, "isST", 0), 0)
            turnover = safe_float(_row_value(item, "turn"))
            rows.append((code, trade_date, fallback_name, close, volume,
                         trade_status, is_st, turnover))
        return rows

    @staticmethod
    def _calendar_dates(frame: pd.DataFrame) -> list[str]:
        if frame is None or frame.empty:
            return []
        required = {"calendar_date", "is_trading_day"}
        if not required.issubset(frame.columns):
            raise MarketDataUnavailable("BaoStock 交易日历字段不完整")
        return sorted(set(frame.loc[
            frame["is_trading_day"].astype(str) == "1", "calendar_date"
        ].astype(str).tolist()))

    def _latest_market_date(self, today: str) -> tuple[str, list[str]]:
        start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=180)).strftime("%Y-%m-%d")
        calendar = self.provider.query_trade_dates(start, today)
        trade_dates = self._calendar_dates(calendar)
        if not trade_dates:
            raise MarketDataUnavailable("BaoStock 没有返回最近交易日历")
        index_bars = self.provider.query_index_history(trade_dates[0], today)
        if index_bars.empty or "date" not in index_bars.columns:
            raise MarketDataUnavailable("BaoStock 未返回上证综指日线，无法确认最新行情日期")
        available = sorted(set(index_bars["date"].astype(str).tolist()) & set(trade_dates))
        if not available:
            raise MarketDataUnavailable("交易日历与上证综指日线没有交集")
        if available[-1] != trade_dates[-1]:
            raise MarketDataUnavailable(
                f"最新交易日 {trade_dates[-1]} 的指数行情尚未就绪；保留上一快照"
            )
        return available[-1], trade_dates

    def _history_initialization(self, universe: pd.DataFrame, start_date: str,
                                end_date: str) -> tuple[int, int]:
        ready = self.db.history_ready_codes()
        retry_map = self.db.init_retry_map()
        todo = universe[universe["trade_status"] == 1]
        tasks = [r for r in todo.itertuples(index=False) if str(r.code) not in ready]
        if not tasks:
            LOG.info("历史缓存已就绪：%d 只活跃股票，无需重复下载历史K线", len(ready))
            return 0, 0

        attempted = 0
        failed = 0
        consecutive_errors = 0
        LOG.info("开始历史初始化：待处理 %d 只股票，范围 %s 至 %s（%d 个交易日以内）",
                 len(tasks), start_date, end_date, self.config.history_days)
        with connect(self.config.db_path) as db:
            for idx, item in enumerate(tasks, start=1):
                code = str(item.code)
                name = str(item.name or "")
                retry = retry_map.get(code)
                if retry and not retry_is_due(retry[1]):
                    continue
                try:
                    frame = self.provider.query_history(code, start_date, end_date)
                    rows = self._rows_to_daily(frame, name)
                    if any(r[0] != code or not start_date <= r[1] <= end_date for r in rows):
                        raise ValueError("历史数据股票代码或日期超出请求范围")
                    if not rows:
                        raise RuntimeError("历史K线为空或没有有效收盘价/成交量")
                    self.db.upsert_daily_rows(db, rows)
                    self.db.mark_history_ready(db, code, name)
                    consecutive_errors = 0
                except (BaoStockBlacklistError, BaoStockRequestLimitError):
                    db.commit()
                    raise
                except Exception as exc:
                    failed += 1
                    consecutive_errors += 1
                    self.db.queue_init_failure(db, code, name, start_date, end_date, str(exc))
                    LOG.warning("历史初始化失败 %s %s: %s", code, name, exc)
                # End each stock's write transaction before the next BaoStock call:
                # its request counter writes api_usage through a separate connection.
                # Holding this transaction across calls causes SQLITE_BUSY on stock 2+.
                db.commit()
                attempted += 1
                if attempted % 50 == 0 or idx == len(tasks):
                    db.commit()
                    LOG.info("历史初始化进度 %d/%d；本批失败 %d；API 请求累计 %d",
                             idx, len(tasks), failed, self.db.api_requests_today())
                if consecutive_errors >= self.config.max_consecutive_errors:
                    db.commit()
                    raise MarketDataUnavailable(
                        f"连续 {consecutive_errors} 只股票历史请求失败，已安全停止；"
                        "已成功数据已提交，失败项会按退避间隔重试"
                    )
                if attempted % self.config.batch_size == 0 and self.config.batch_pause > 0:
                    time.sleep(self.config.batch_pause)
            db.commit()
        return attempted, failed

    def _process_trade_date(self, trade_date: str) -> dict:
        universe = self.db.get_universe(trade_date)
        if universe.empty:
            universe = self.provider.query_all_stocks(trade_date)
            self.db.persist_universe(trade_date, universe)
        active = universe[universe["trade_status"] == 1]
        existing = self.db.get_existing_codes(trade_date)
        init_retry = self.db.init_retry_map()
        day_retry = self.db.day_retry_map(trade_date)
        now = datetime.now(CST)
        tasks = []
        deferred = 0
        for item in active.itertuples(index=False):
            code = str(item.code)
            if code in existing:
                continue
            init_state = init_retry.get(code)
            if init_state and not retry_is_due(init_state[1], now):
                deferred += 1
                continue
            day_state = day_retry.get(code)
            if day_state and not retry_is_due(day_state[1], now):
                deferred += 1
                continue
            tasks.append((code, str(item.name or "")))

        if not tasks:
            status = self.db.update_day_status(trade_date)
            if deferred:
                LOG.warning("%s 有 %d 只失败股票处于退避等待；跳过重复请求", trade_date, deferred)
            else:
                LOG.info("%s 已完整，无需重复抓取", trade_date)
            return status

        LOG.info("更新交易日 %s：待抓取 %d 只股票", trade_date, len(tasks))
        failed = 0
        consecutive_errors = 0
        with connect(self.config.db_path) as db:
            for idx, (code, name) in enumerate(tasks, start=1):
                try:
                    frame = self.provider.query_history(code, trade_date, trade_date)
                    rows = [r for r in self._rows_to_daily(frame, name)
                            if r[0] == code and r[1] == trade_date and r[5] == 1]
                    if not rows:
                        raise RuntimeError("没有返回目标交易日有效日K")
                    self.db.upsert_daily_rows(db, rows)
                    self.db.clear_day_failure(db, code, trade_date)
                    consecutive_errors = 0
                except (BaoStockBlacklistError, BaoStockRequestLimitError):
                    db.commit()
                    raise
                except Exception as exc:
                    failed += 1
                    consecutive_errors += 1
                    self.db.queue_day_failure(db, code, trade_date, name, str(exc))
                    LOG.warning("日线失败 %s %s %s: %s", trade_date, code, name, exc)
                # Avoid retaining a write transaction while the provider writes
                # api_usage in another SQLite connection for the next request.
                db.commit()
                if idx % 50 == 0 or idx == len(tasks):
                    LOG.info("%s 进度 %d/%d；本批失败 %d；API 请求累计 %d",
                             trade_date, idx, len(tasks), failed, self.db.api_requests_today())
                if consecutive_errors >= self.config.max_consecutive_errors:
                    db.commit()
                    raise MarketDataUnavailable(
                        f"{trade_date} 连续 {consecutive_errors} 只股票请求失败，已安全停止"
                    )
                if idx % self.config.batch_size == 0 and self.config.batch_pause > 0:
                    time.sleep(self.config.batch_pause)
            db.commit()
        status = self.db.update_day_status(trade_date)
        LOG.info("交易日 %s 完成：%d/%d，缺失 %d，完整率 %.3f%%",
                 trade_date, status["saved"], status["expected"], status["failed"],
                 status["completeness"] * 100)
        return status

    def _refresh_industry_if_needed(self, latest_universe: pd.DataFrame) -> None:
        count, fetched_at = self.db.industry_info()
        fresh = False
        if fetched_at:
            try:
                previous = datetime.strptime(fetched_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
                fresh = datetime.now(CST) - previous < timedelta(days=self.config.industry_refresh_days)
            except ValueError:
                fresh = False
        latest_codes = set(latest_universe["code"].astype(str).tolist())
        with connect(self.config.db_path) as db:
            cached_codes = {str(r[0]) for r in db.execute("SELECT code FROM industry_cache").fetchall()}
        coverage = len(latest_codes & cached_codes) / len(latest_codes) if latest_codes else 0.0
        if fresh and coverage >= 0.90:
            LOG.info("行业分类缓存新鲜且覆盖率 %.2f%%，跳过网络请求", coverage * 100)
            return
        LOG.info("行业分类需要刷新：缓存 %d 条，覆盖率 %.2f%%", count, coverage * 100)
        try:
            frame = self.provider.query_stock_industry()
            required = {"code", "industry"}
            if frame.empty or not required.issubset(frame.columns):
                raise RuntimeError("BaoStock 行业分类返回空数据或缺少字段")
            for field in ("code_name", "updateDate", "industryClassification"):
                if field not in frame.columns:
                    frame[field] = ""
            fetched = now_text()
            rows = []
            for item in frame.itertuples(index=False):
                code = str(_row_value(item, "code", "") or "")
                if not is_a_share_code(code):
                    continue
                rows.append((code, str(_row_value(item, "code_name", "") or ""),
                             normalize_industry(_row_value(item, "industry", "")),
                             str(_row_value(item, "updateDate", "") or ""),
                             str(_row_value(item, "industryClassification", "") or ""), fetched))
            if not rows:
                raise RuntimeError("行业分类没有可用 A 股记录")
            self.db.replace_industry(rows)
            LOG.info("行业分类刷新成功：%d 条记录", len(rows))
        except (BaoStockBlacklistError, BaoStockRequestLimitError):
            raise
        except Exception:
            LOG.exception("行业分类刷新失败；保留旧缓存，不阻断行情快照")

    def run(self) -> dict:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.config.log_path.mkdir(parents=True, exist_ok=True)
        with self.config.lock_path.open("w") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("另一个行情更新任务正在运行，本次退出") from exc
            run_id = self.db.record_run_start()
            started = time.monotonic()
            start_requests = self.db.api_requests_today()
            market_date = None
            status = {"expected": 0, "saved": 0, "failed": 0, "completeness": 0.0, "status": "partial"}
            message = ""
            run_status = "failed"
            try:
                self.provider.login()
                today = datetime.now(CST).strftime("%Y-%m-%d")
                market_date, trade_dates = self._latest_market_date(today)
                LOG.info("最新可用交易日：%s；日历中近期交易日 %d 个", market_date, len(trade_dates))
                latest_universe = self.provider.query_all_stocks(market_date)
                if latest_universe.empty:
                    raise MarketDataUnavailable("最新交易日股票列表为空")
                self.db.persist_universe(market_date, latest_universe)

                history_dates = [d for d in trade_dates if d <= market_date][-self.config.history_days:]
                if not history_dates:
                    raise MarketDataUnavailable("无法确定历史初始化日期范围")
                self._history_initialization(latest_universe, history_dates[0], market_date)

                # First bootstrap: historical bars already contain the latest day.
                # Create its status before deciding whether a separate daily pull is needed.
                self.db.update_day_status(market_date)
                last_market_date = self.db.get_meta("last_market_date")
                if last_market_date:
                    new_dates = [d for d in trade_dates if last_market_date < d <= market_date]
                else:
                    new_dates = [market_date]
                partial_dates = self.db.partial_dates(market_date)
                dates_to_process = sorted(set(new_dates) | set(partial_dates))
                for trade_date in dates_to_process:
                    if self.db.get_universe(trade_date).empty:
                        universe = self.provider.query_all_stocks(trade_date)
                        self.db.persist_universe(trade_date, universe)
                    self._process_trade_date(trade_date)
                self.db.set_meta("last_market_date", market_date)

                self._refresh_industry_if_needed(latest_universe)
                status = self.db.update_day_status(market_date)
                with connect(self.config.db_path) as db:
                    active_codes = {str(r[0]) for r in db.execute(
                        "SELECT code FROM day_universe WHERE trade_date=? AND trade_status=1",
                        (market_date,)).fetchall()}
                    ready_codes = {str(r[0]) for r in db.execute(
                        "SELECT code FROM stock_state WHERE history_ready=1").fetchall()}
                history_ready = len(active_codes & ready_codes)
                history_coverage = history_ready / len(active_codes) if active_codes else 0.0
                LOG.info("历史缓存覆盖率 %.3f%%（%d/%d）", history_coverage * 100,
                         history_ready, len(active_codes))

                confirmed_date, _ = self._latest_market_date(datetime.now(CST).strftime("%Y-%m-%d"))
                if confirmed_date != market_date:
                    raise MarketDataUnavailable("采集期间行情日期变化，保留上一快照并等待下次更新")

                if (status["completeness"] >= self.config.min_publish_completeness
                        and history_coverage >= self.config.min_publish_completeness):
                    self.publisher.publish(market_date, status, history_ready)
                    pruned = self.db.prune_old_data(self.config.retention_days)
                    if pruned:
                        LOG.info("按 %d 个交易日保留策略清理旧行情 %d 行",
                                 self.config.retention_days, pruned)
                    run_status = "success" if status["status"] == "complete" else "partial_published"
                    message = "行情快照已发布"
                else:
                    run_status = "partial"
                    message = (
                        f"数据未达到发布阈值 {self.config.min_publish_completeness:.3%}；"
                        "保留上一份已发布快照，不覆盖客户端可下载数据。"
                    )
                    LOG.error(message)
                return {
                    "market_date": market_date,
                    "status": status,
                    "history_ready": history_ready,
                    "history_coverage": history_coverage,
                    "api_requests_today": self.db.api_requests_today(),
                    "published": run_status in ("success", "partial_published"),
                    "message": message,
                }
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                LOG.exception("行情更新失败：%s", message)
                raise
            finally:
                self.provider.logout()
                duration = time.monotonic() - started
                try:
                    self.db.record_run_end(
                        run_id, run_status, market_date,
                        int(status.get("expected", 0)), int(status.get("saved", 0)),
                        int(status.get("failed", 0)),
                        self.db.api_requests_today() - start_requests,
                        duration, message or run_status,
                    )
                except Exception:
                    LOG.exception("无法写入更新运行记录")
                LOG.info("本次更新结束：status=%s duration=%.1fs API requests=%d",
                         run_status, duration, self.db.api_requests_today() - start_requests)
