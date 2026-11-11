from __future__ import annotations

import logging
import re
from typing import Callable

import pandas as pd

LOG = logging.getLogger(__name__)

SH_PREFIXES = ("600", "601", "603", "605", "688")
SZ_PREFIXES = ("000", "001", "002", "003", "300", "301")
HISTORY_FIELDS = "date,code,close,volume,tradestatus,isST,turn"


class BaoStockError(RuntimeError):
    pass


class BaoStockBlacklistError(BaoStockError):
    """BaoStock rejected the account/IP as blacklisted; do not retry automatically."""


class BaoStockRequestLimitError(BaoStockError):
    pass


def is_a_share_code(code: str) -> bool:
    if not isinstance(code, str) or "." not in code:
        return False
    market, symbol = code.split(".", 1)
    if len(symbol) != 6 or not symbol.isdigit():
        return False
    if market == "sh":
        return symbol.startswith(SH_PREFIXES)
    if market == "sz":
        return symbol.startswith(SZ_PREFIXES)
    return False


def normalize_industry(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return "未分类"
    return re.sub(r"^[A-Za-z]\d+\s*", "", text).strip() or text


class BaoStockProvider:
    """One BaoStock login, one sequential request stream, no worker pool."""

    def __init__(self, bs_module=None, request_counter: Callable[[], int] | None = None):
        if bs_module is None:
            import baostock as bs_module  # type: ignore
        self.bs = bs_module
        self.request_counter = request_counter or (lambda: 0)
        self.logged_in = False
        self.request_count = 0

    @staticmethod
    def _blacklisted(code: str, message: str) -> bool:
        return code == "10001011" or "黑名单" in message or "blacklist" in message.lower()

    def login(self) -> None:
        if self.logged_in:
            return
        result = self.bs.login()
        code = str(getattr(result, "error_code", "-1"))
        message = str(getattr(result, "error_msg", "unknown error"))
        if code != "0":
            if self._blacklisted(code, message):
                raise BaoStockBlacklistError(
                    f"BaoStock 拒绝登录（{code}）：{message}。"
                    "已停止任务，不会循环登录；请先联系 BaoStock 核查黑名单状态。"
                )
            raise BaoStockError(f"BaoStock 登录失败（{code}）：{message}")
        self.logged_in = True
        LOG.info("BaoStock 登录成功；本进程仅使用一个会话并串行请求")

    def logout(self) -> None:
        if not self.logged_in:
            return
        try:
            self.bs.logout()
        except Exception:
            LOG.exception("BaoStock logout 出错")
        finally:
            self.logged_in = False

    def _result_to_df(self, result, operation: str) -> pd.DataFrame:
        code = str(getattr(result, "error_code", "-1"))
        message = str(getattr(result, "error_msg", "unknown error"))
        if code != "0":
            if self._blacklisted(code, message):
                raise BaoStockBlacklistError(
                    f"BaoStock 请求被黑名单拒绝（{code}）：{message}"
                )
            if "超过" in message and "次数" in message:
                raise BaoStockRequestLimitError(message)
            raise BaoStockError(f"{operation} 失败（{code}）：{message}")
        rows = []
        while result.next():
            rows.append(result.get_row_data())
        return pd.DataFrame(rows, columns=getattr(result, "fields", []))

    def _request(self, operation: str, func) -> pd.DataFrame:
        if not self.logged_in:
            raise BaoStockError("BaoStock 尚未登录")
        try:
            self.request_counter()
        except RuntimeError as exc:
            if "请求上限" in str(exc) or "request limit" in str(exc).lower():
                raise BaoStockRequestLimitError(str(exc)) from exc
            raise
        self.request_count += 1
        LOG.debug("BaoStock API #%d: %s", self.request_count, operation)
        return self._result_to_df(func(), operation)

    def query_trade_dates(self, start_date: str, end_date: str) -> pd.DataFrame:
        return self._request(
            f"trade_dates {start_date}..{end_date}",
            lambda: self.bs.query_trade_dates(start_date=start_date, end_date=end_date),
        )

    def query_index_history(self, start_date: str, end_date: str) -> pd.DataFrame:
        return self._request(
            f"index_history {start_date}..{end_date}",
            lambda: self.bs.query_history_k_data_plus(
                "sh.000001", "date,code,close,volume", start_date=start_date,
                end_date=end_date, frequency="d", adjustflag="3"),
        )

    def query_all_stocks(self, trade_date: str) -> pd.DataFrame:
        df = self._request(
            f"all_stock {trade_date}",
            lambda: self.bs.query_all_stock(day=trade_date),
        )
        if df.empty:
            raise BaoStockError(f"{trade_date} 股票列表为空")
        if "code" not in df.columns:
            raise BaoStockError("BaoStock 股票列表缺少 code 字段")
        if "tradeStatus" not in df.columns:
            df["tradeStatus"] = "1"
        if "code_name" not in df.columns:
            df["code_name"] = ""
        df = df[df["code"].astype(str).map(is_a_share_code)].copy()
        df["tradeStatus"] = pd.to_numeric(df["tradeStatus"], errors="coerce").fillna(0).astype(int)
        return (df[["code", "tradeStatus", "code_name"]]
                .rename(columns={"tradeStatus": "trade_status", "code_name": "name"})
                .drop_duplicates("code").sort_values("code").reset_index(drop=True))

    def query_history(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._request(
            f"daily {code} {start_date}..{end_date}",
            lambda: self.bs.query_history_k_data_plus(
                code, HISTORY_FIELDS, start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="3"),
        )

    def query_stock_industry(self) -> pd.DataFrame:
        return self._request("stock_industry", self.bs.query_stock_industry)
