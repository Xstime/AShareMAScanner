from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone

from .api import serve
from .config import settings
from .db import MarketDB
from .provider import BaoStockBlacklistError, BaoStockProvider
from .updater import MarketUpdater

CST = timezone(timedelta(hours=8))


def configure_logging() -> None:
    settings.log_path.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        from logging.handlers import RotatingFileHandler
        handlers.append(RotatingFileHandler(
            settings.log_path / "marketdata.log", maxBytes=8 * 1024 * 1024,
            backupCount=5, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=getattr(logging, settings.api_log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def command_probe() -> int:
    db = MarketDB(settings.db_path, settings.max_api_requests_per_day,
                  settings.retry_base_hours, settings.retry_max_hours)
    provider = BaoStockProvider(request_counter=db.consume_api_request)
    try:
        provider.login()
        today = datetime.now(CST).strftime("%Y-%m-%d")
        frame = provider.query_trade_dates(today, today)
        if frame.empty:
            raise RuntimeError("BaoStock 登录成功，但今日交易日历为空")
        print(json.dumps({
            "login": "ok",
            "china_date": today,
            "trade_calendar_rows": len(frame),
            "api_requests_today": db.api_requests_today(),
            "message": "BaoStock 登录和最小查询均通过；尚未执行全市场采集",
        }, ensure_ascii=False, indent=2))
        return 0
    except BaoStockBlacklistError as exc:
        logging.error("%s", exc)
        return 3
    except Exception:
        logging.exception("BaoStock probe failed")
        return 1
    finally:
        provider.logout()


def command_status() -> int:
    db = MarketDB(settings.db_path, settings.max_api_requests_per_day,
                  settings.retry_base_hours, settings.retry_max_hours)
    payload = {
        "db_path": str(settings.db_path),
        "latest_daily_date": None,
        "latest_complete_date": db.latest_complete_date(),
        "api_requests_today": db.api_requests_today(),
        "manifest_exists": settings.manifest_path.is_file(),
    }
    if settings.manifest_path.is_file():
        try:
            payload["manifest"] = json.loads(settings.manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            payload["manifest_error"] = str(exc)
    from .db import connect
    with connect(settings.db_path) as conn:
        row = conn.execute("SELECT MAX(trade_date) FROM daily").fetchone()
        payload["latest_daily_date"] = row[0] if row else None
        payload["active_history_ready"] = int(conn.execute(
            "SELECT COUNT(*) FROM stock_state WHERE history_ready=1").fetchone()[0])
        payload["pending_history_retries"] = int(conn.execute(
            "SELECT COUNT(*) FROM init_queue").fetchone()[0])
        payload["pending_daily_retries"] = int(conn.execute(
            "SELECT COUNT(*) FROM fetch_queue").fetchone()[0])
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="AShareMAScanner BaoStock VPS market-data service")
    parser.add_argument("command", choices=("update", "probe", "status", "serve"))
    parser.add_argument("--as-of", help="仅 update 使用：指定不晚于今天的交易日，格式 YYYY-MM-DD")
    args = parser.parse_args(argv)
    if args.as_of and args.command != "update":
        parser.error("--as-of 仅适用于 update")
    if args.command == "update":
        result = MarketUpdater().run(as_of=args.as_of)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("published") else 2
    if args.command == "probe":
        return command_probe()
    if args.command == "status":
        return command_status()
    if args.command == "serve":
        serve()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
