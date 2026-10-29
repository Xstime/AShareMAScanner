# -*- coding: utf-8 -*-
"""
A股 MA 图形化扫描器（BaoStock + AKShare · v1.2.7 4:3 工作台开发版）
=====================================

功能
----
- Tkinter 图形化界面，Windows / macOS 均可运行。
- 每次启动先显示独立加载窗口，检查并增量更新 BaoStock 行情完成后才打开选股界面。
- 更新过程中显示“当前任务 + 百分比进度”，策略按钮与参数输入框保持禁用。
- 七个策略：
    1) 放量突破 MA5
    2) 放量突破 MA10
    3) 放量突破 MA20
    4) MA5 上穿 MA10
    5) 放量 + 换手率筛选（可输入上下限，最大值留空为无上限）
    6) MA5 拐头向上：今天MA5>昨日MA5，昨日MA5<=前日MA5
    7) 均线粘合向上：昨日MA5/10/20偏离度≤2%，今日全线上升、MA5>MA10>MA20并向上发散，且仅首次触发
- 个股结果仅显示最新市场交易日触发，所有策略均显示放量倍数与换手率。
- MA5拐头策略不以价格上穿MA5、放量或换手率作为附加门槛。
- 新策略支持行业板块同规则判断、单击板块筛选、双击板块看MA5走势、信号历史回算。
- 七个策略按钮采用两行四列的紧凑布局。
- 第5策略修改参数后，重新点击筛选策略按钮生效。
- 策略扫描期间可直接切换其他策略；旧扫描自动取消，以最后一次点击为准。
- 切换策略时立即清空旧板块过滤和旧个股结果，避免新策略标题配上旧策略数据。
- 结果直接显示在 GUI 表格中，点击表头可排序。
- 七个策略都提供行业板块结果，并判断板块本身是否触发当前策略。
- GUI 采用更简洁的浅色极简排版，接近 Apple 风格。
- 第5策略板块图增加放量倍数和等权换手率曲线。
- 双击板块只显示当前所选策略需要的均线：突破MA5/10/20分别显示对应均线，MA5上穿MA10显示MA5与MA10。
- 双击股票弹出最近 30 个有效交易日的收盘价、MA5、MA10、MA20 走势图。
- 信号历史追踪（含本地回算与参数记录）。
- 个股与板块走势图支持悬停读数；板块名称支持悬停完整提示。
- 个股图增加成交量、放量倍数、换手率与触发日标记。
- 结果支持代码/名称、市场、行业、涨幅范围快捷过滤。
- 新增近5交易日主力净流入TOP5横向卡片；可一键限定五大资金流入行业的成分股。
- 行业资金流来自东方财富（AKShare）；按成分股代码严格匹配，不依赖BaoStock行业名称。
- 资金接口故障不影响七个选股策略，禁止用未验证的板块名称猜测股票。
- 启动时自动检测并安装缺失的 pandas、baostock、akshare；优先清华镜像，失败改用官方 PyPI。
- 无 Excel 导出，无数据库位置按钮。
- 数据库始终固定在程序同级 data/a_share_baostock_hfq.db，不迁移、不清空数据。
- 启动时自动检查原目录写入权限并尝试移除数据库只读属性。
- 增强完整率、失败队列清理、数据合法性检验、资金榜单缓存回退、板块查询效率和异常后重试。
- 同一data数据库只允许一个扫描器进程写入；启动时使用只读快检检查已有SQLite数据库。


数据与计算口径
--------------
- 数据源：BaoStock，无 Token。
- 价格：后复权（adjustflag=1），适合长期增量缓存与均线计算。
- 停牌日不计入个股均线和成交量均线。
- ST / *ST 股票不进入扫描结果。
- 放量突破 MA(N)：
      Close_t > MA(N)_t
      Close_(t-1) <= MA(N)_(t-1)
      Volume_t >= 前5个有效交易日平均成交量 × 1.5
- 放量 + 换手率筛选：当日放量倍数和换手率均落在输入的闭区间内。
  最大值留空为无上限；板块使用成交量总和与换手率等权平均。
- MA5 上穿 MA10：
      MA5_t > MA10_t
      MA5_(t-1) <= MA10_(t-1)
- MA5 拐头向上（仅首次转折，不要求放量、不要求换手率门槛）：
      MA5_t > MA5_(t-1)
      MA5_(t-1) <= MA5_(t-2)
  三个MA值均以该股票实际有效交易K线计算，至少需要7根有效K线。
- 均线粘合向上（使用最近实际有效交易日的MA5、MA10、MA20）：
      昨日粘合度=(昨日三均线最大值-最小值)/昨日三均线平均值≤2%；
      今日三均线均较昨日上升；今日MA5>MA10>MA20；
      今日发散度>昨日发散度（同一归一化计算方式）；
      昨日没有满足完整的粘合向上形态（首次触发）；
      不强制放量和换手率，至少保留23根有效K线以确认首次信号。

首次运行
--------
- 为当前沪深 A 股建立最近约 45 个市场交易日的历史缓存。
- 首次运行需要逐股请求，耗时明显长于日常更新。
- 之后每个新交易日只获取当天缺失的数据；失败项会在下次启动继续补抓。

安装
----
正常直接运行：python A股MA扫描器_v1.2.7.pyw
首次运行自动补装缺少的第三方库（需要联网，不需要任何付费API）。
若安装失败，可手动运行：python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple baostock pandas akshare

macOS 若使用 Homebrew Python 且缺少 Tkinter，可安装对应版本的 python-tk。
"""

from __future__ import annotations

import math
import json
import os
import stat
import tempfile
import queue
import re
import sqlite3
import threading
import time
import traceback
import urllib.request
import urllib.error
import webbrowser
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

# ============================================================
# 启动依赖自检：只在直接运行 .py / .pyw 时执行
# ============================================================

def _bootstrap_dependencies():
    """自动安装缺失依赖；AKShare失败时不影响核心选股功能。"""
    import importlib
    import importlib.util
    import os
    import site
    import subprocess
    import sys

    # '模块名': ('pip包名', 是否为启动必需)
    packages = {
        "pandas": ("pandas", True),
        "baostock": ("baostock", True),
        "akshare": ("akshare", False),
    }
    missing = [(module, pip_name, required)
               for module, (pip_name, required) in packages.items()
               if importlib.util.find_spec(module) is None]
    if not missing:
        return

    # PyInstaller等独立打包程序不能向其内置Python环境使用pip动态补库。
    frozen = bool(getattr(sys, "frozen", False))
    events = queue.Queue()
    failed = []

    # 显式指定镜像；不依赖用户电脑当前 pip 配置。
    sources = (
        ("清华 PyPI 镜像", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("官方 PyPI", "https://pypi.org/simple"),
    )

    def install_all():
        windows_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        def run_pip(command):
            try:
                cp = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    timeout=600,
                    creationflags=windows_flags,
                )
                return cp.returncode == 0, (cp.stdout or "")[-3500:]
            except subprocess.TimeoutExpired:
                return False, "安装超过10分钟，已停止等待。"
            except OSError as exc:
                return False, str(exc)

        for index, (module, pip_name, required) in enumerate(missing, 1):
            if frozen:
                failed.append((
                    pip_name, required,
                    "独立打包程序不支持运行时补装依赖，请重新打包。",
                ))
                continue

            succeeded = False
            errors_by_source = []
            for source_name, source_url in sources:
                events.put((
                    "status",
                    f"正在用{source_name}安装 {pip_name}（{index}/{len(missing)}）…",
                ))

                args = [
                    sys.executable, "-m", "pip", "install",
                    "--disable-pip-version-check", "--no-input",
                    "--timeout", "20", "--retries", "2",
                    "--index-url", source_url, pip_name,
                ]
                ok, details = run_pip(args)

                # 只有权限相关错误才额外尝试 --user，避免网络失败时重复等待。
                permission_errors = (
                    "permission denied", "access is denied", "winerror 5",
                    "not writable", "write permission", "没有权限", "拒绝访问",
                )
                if (not ok and sys.prefix == sys.base_prefix
                        and site.ENABLE_USER_SITE
                        and any(term in details.lower() for term in permission_errors)):
                    events.put((
                        "status",
                        f"{source_name}：尝试在当前用户目录安装 {pip_name}…",
                    ))
                    ok, details = run_pip(args[:-1] + ["--user", pip_name])

                importlib.invalidate_caches()
                if ok and importlib.util.find_spec(module) is None:
                    ok = False
                    details = "pip报告成功，但当前Python仍然找不到该模块。"

                if ok:
                    succeeded = True
                    break

                errors_by_source.append(f"[{source_name}] {details}")
                if source_name == "清华 PyPI 镜像":
                    events.put((
                        "status",
                        f"清华镜像安装失败，正在切换官方 PyPI：{pip_name}…",
                    ))

            if not succeeded:
                failed.append((pip_name, required, "\n".join(errors_by_source)))

        events.put(("done", None))

    def finish():
        critical = [x for x in failed if x[1]]
        optional = [x for x in failed if not x[1]]
        message = "\n\n".join(
            f"{name} 安装失败：\n{log[-950:]}"
            for name, _, log in failed
        )
        if critical:
            return False, ("运行所需依赖安装失败。请检查网络及pip，然后重试。\n\n"
                           + message + "\n\n手动命令：\npython -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pandas baostock akshare")
        if optional:
            return True, ("AKShare自动安装失败；原有七个选股策略仍可使用，"
                          "但资金 TOP5 暂不可用。\n\n" + message
                          + "\n\n可稍后重试：python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple akshare")
        return True, ""

    # Windows .pyw 无控制台，使用轻量Tk窗口明确显示首次安装过程。
    root = None
    try:
        import tkinter as _tk
        from tkinter import ttk as _ttk, messagebox as _messagebox
        root = _tk.Tk()
    except Exception:
        root = None

    if root is None:
        # 无图形显示环境时仍可自动补装；错误输出到终端。
        install_all()
        ok, notice = finish()
        if notice:
            print(notice, file=sys.stderr)
        if not ok:
            raise SystemExit(1)
        return

    root.title("A股 MA 扫描器 · 初始化")
    root.geometry("490x180")
    root.resizable(False, False)
    root.configure(bg="#f5f5f7")
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    _ttk.Label(root, text="正在准备运行环境", font=("Segoe UI", 14, "bold"),
               background="#f5f5f7").pack(anchor="w", padx=24, pady=(22, 8))
    status = _tk.StringVar(value="检测到缺少依赖，首次安装可能需要几分钟…")
    _ttk.Label(root, textvariable=status, background="#f5f5f7",
               font=("Segoe UI", 10)).pack(anchor="w", padx=24, pady=(0, 10))
    bar = _ttk.Progressbar(root, mode="indeterminate", length=442)
    bar.pack(padx=24, fill="x")
    bar.start(14)
    _ttk.Label(root, text="仅在缺少库时安装；不会购买 API 或申请 Token。",
               background="#f5f5f7", foreground="#6e6e73",
               font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(13, 0))

    state = {"ok": True, "notice": ""}

    def poll():
        while True:
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                status.set(value)
            elif kind == "done":
                bar.stop()
                state["ok"], state["notice"] = finish()
                if state["notice"]:
                    if state["ok"]:
                        _messagebox.showwarning("部分依赖未安装", state["notice"], parent=root)
                    else:
                        _messagebox.showerror("依赖安装失败", state["notice"], parent=root)
                root.destroy()
                return
        root.after(150, poll)

    threading.Thread(target=install_all, daemon=True).start()
    root.after(150, poll)
    root.mainloop()
    if not state["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    _bootstrap_dependencies()

def _dependency_import_error(name: str, exc: Exception):
    """依赖虽然存在但导入失败时，.pyw 也必须能显示明确错误。"""
    import sys
    message = (
        f"启动失败：{name} 无法正常导入。\n"
        f"错误类型：{type(exc).__name__}\n错误详情：{exc}\n\n"
        "请检查 Python 环境，必要时使用 pip 重新安装该模块。"
    )
    try:
        import tkinter as _tk
        from tkinter import messagebox as _messagebox
        root = _tk.Tk()
        root.withdraw()
        try:
            _messagebox.showerror("A股 MA 扫描器 · 启动失败", message, parent=root)
        finally:
            root.destroy()
    except Exception:
        print(message, file=sys.stderr)
    raise SystemExit(1) from exc


try:
    import pandas as pd
except Exception as exc:
    _dependency_import_error("pandas", exc)

try:
    import baostock as bs
except Exception as exc:
    _dependency_import_error("baostock", exc)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError as exc:
    raise SystemExit(
        "当前 Python 缺少 Tkinter。\n"
        "macOS Homebrew Python 请安装对应版本的 python-tk。"
    ) from exc


# ============================================================
# 配置
# ============================================================

APP_TITLE = "A股 MA 扫描器"
APP_VERSION = "1.2.7"
RELEASE_API = "https://api.github.com/repos/Xstime/AShareMAScanner/releases/latest"
RELEASES_PAGE = "https://github.com/Xstime/AShareMAScanner/releases"

def _release_version(value: str):
    """仅比较正式发布的三段式版本号。"""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(int(part) for part in match.groups()) if match else None

def fetch_latest_release():
    """只读取本项目正式 GitHub Release，不执行远程程序。"""
    request = urllib.request.Request(RELEASE_API, headers={
        "User-Agent": "AShareMAScanner-update-checker/1.2.6",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read(128 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "尚无正式发布版本", None
        raise RuntimeError(f"GitHub 响应异常（HTTP {exc.code}）") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("无法连接 GitHub，请稍后重试") from exc
    if len(body) > 128 * 1024:
        raise RuntimeError("GitHub 返回的数据异常")
    try:
        item = json.loads(body)
        if item.get("draft") or item.get("prerelease"):
            return "尚无可用正式版本", None
        latest = _release_version(item.get("tag_name", ""))
        current = _release_version(APP_VERSION)
        if latest is None or current is None:
            raise ValueError("无效版本号")
        if latest <= current:
            return "当前已是最新版本", None
        url = str(item.get("html_url", ""))
        if not url.startswith(RELEASES_PAGE + "/tag/"):
            url = RELEASES_PAGE
        return f"发现新版本 v{'.'.join(map(str, latest))}", url
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError("GitHub 更新信息格式异常") from exc


# 新策略的固定粘合阈值：三条均线极差 / 三均线均值 <= 2%。
MA_CONVERGENCE_THRESHOLD = 0.02


def ma_convergence_up_metrics(frame: pd.DataFrame, pos: int,
                              tolerance: float = MA_CONVERGENCE_THRESHOLD):
    """首次出现 MA5/10/20 粘合后共同上行、形成多头排列并扩大间距。

    返回 (昨日粘合度%, 今日发散度%, 发散增加百分点)，不满足则返回 None。
    frame 必须按交易日期升序，三条均线必须基于有效交易日计算。
    """
    columns = ("MA5", "MA10", "MA20")
    if pos < 2 or pos >= len(frame) or not all(c in frame.columns for c in columns):
        return None

    def signal_on(index: int):
        if index < 1:
            return None
        previous = frame.iloc[index - 1]
        today = frame.iloc[index]
        try:
            older_values = [float(previous[c]) for c in columns]
            new_values = [float(today[c]) for c in columns]
        except (TypeError, ValueError, KeyError):
            return None
        if not all(math.isfinite(v) and v > 0 for v in older_values + new_values):
            return None

        old_spread = (max(older_values) - min(older_values)) / (sum(older_values) / 3)
        new_spread = (max(new_values) - min(new_values)) / (sum(new_values) / 3)
        if not (
            old_spread <= tolerance
            and all(new > old for new, old in zip(new_values, older_values))
            and new_values[0] > new_values[1] > new_values[2]
            and new_spread > old_spread
        ):
            return None
        return old_spread * 100, new_spread * 100, (new_spread - old_spread) * 100

    current = signal_on(pos)
    if current is None:
        return None
    # “刚刚形成”：连续满足时，只保留第一天。
    if signal_on(pos - 1) is not None:
        return None
    return current

MA_WINDOWS = (5, 10, 20)
VOLUME_AVG_DAYS = 5
VOLUME_RATIO = 1.5

# 为 MA20 的“昨日/今日”判断保留足够历史余量。
INITIAL_TRADING_DAYS = 45

QUERY_RETRY = 3
RETRY_WAIT = 1.5

# 全市场逐股请求做温和节流。
BATCH_SIZE = 200
BATCH_PAUSE = 2.0

# 长任务定期刷新 BaoStock 会话。
SESSION_REFRESH_SECONDS = 15 * 60

# BaoStock 行业分类官方说明为每周更新；本地缓存按7天刷新。
INDUSTRY_CACHE_DAYS = 7

# 数据库路径固定在源文件同级 data 目录，永不迁移到用户目录。
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "a_share_baostock_hfq.db"

CST = timezone(timedelta(hours=8))
ADJUST_FLAG = "1"  # 后复权

SH_PREFIXES = ("600", "601", "603", "605", "688")
SZ_PREFIXES = ("000", "001", "002", "003", "300", "301")

ProgressCallback = Callable[[float, str], None]

# 这些权重是更新器已有的步骤百分比，并非剩余时间预测。
UPDATE_PHASES = (
    ("环境与交易日", 0, 12),
    ("历史失败补抓", 12, 20),
    ("历史缓存准备", 20, 66),
    ("缺失交易日补齐", 66, 80),
    ("每日行情更新", 80, 94),
    ("换手率补齐", 94, 96),
    ("行业板块资料", 96, 98),
    ("完整性检查", 98, 100),
)


def describe_update_progress(percent: float, task: str) -> dict:
    """将后端原有真实任务事件转换为分阶段 GUI 数据，不额外访问数据库。"""
    value = min(100., max(0., float(percent)))
    task = str(task)
    # 优先根据明确的任务词识别阶段，避免范围端点落在下一阶段的误判。
    explicit = (
        (r"^(补历史失败|历史失败补抓|没有历史失败项)", 1),
        (r"^(初始化历史|历史缓存)", 2),
        (r"^没有未完整交易日", 3),
        (r"^没有新的交易日", 4),
        (r"^(补换手率|近期换手率)", 5),
        (r"^(更新行业|行业板块|板块分类)", 6),
        (r"^(校验最新交易日|数据检查完成)", 7),
    )
    index = next((idx for pattern, idx in explicit if re.search(pattern, task)), None)
    if index is None:
        # 更新 YYYY-MM-DD 可能是缺失交易日回补，也可能是增量交易日。
        if task.startswith("更新 ") or re.match(r"^\d{4}-\d\d-\d\d (更新完成|已完整)", task):
            index = 3 if value < 80 else 4
        else:
            index = next((i for i, (_, start, end) in enumerate(UPDATE_PHASES)
                          if start <= value < end), 7)
    title, start, end = UPDATE_PHASES[index]
    fraction = min(1.0, max(0.0, (value - start) / max(1, end - start)))
    match = re.search(r"\b(\d+)\s*/\s*(\d+)\b", task)
    current = total = completed = None
    stock = None
    if match:
        current = int(match.group(1))
        total = int(match.group(2))
        if total > 0 and 1 <= current <= total:
            # 后端在每只股票开始处理前报告，不能将当前股票当成已完成。
            completed = current - 1
            fraction = completed / total
            if " · " in task:
                stock = task.rsplit(" · ", 1)[-1]
        else:
            current = total = completed = None
    if task in ("没有历史失败项", "历史缓存已就绪", "没有未完整交易日",
                "没有新的交易日", "近期换手率检查完成", "板块分类缓存已就绪",
                "数据检查完成") or task.endswith(("更新完成", "补抓完成", "初始化完成")):
        fraction = 1.0
    return {
        "phase": index, "title": title, "fraction": fraction,
        "completed": completed, "current": current, "total": total,
        "stock": stock, "task": task, "overall": value,
    }


# ============================================================
# 数据结构
# ============================================================

@dataclass(frozen=True)
class RangeFilter:
    """换手率单位为百分数；区间两端均包含。"""
    volume_min: float = 1.5
    volume_max: Optional[float] = None
    turnover_min: float = 3.0
    turnover_max: Optional[float] = None

    def __post_init__(self):
        for label, low, high in (
            ("放量倍数", self.volume_min, self.volume_max),
            ("换手率", self.turnover_min, self.turnover_max),
        ):
            if not math.isfinite(low) or low < 0:
                raise ValueError(f"{label}最小值须为非负有限数字")
            if high is not None and (not math.isfinite(high) or high < low):
                raise ValueError(f"{label}最大值须为有限数字且不小于最小值")

    def matches(self, row) -> bool:
        try:
            volume = float(row["volume"])
            average = float(row["VOL5_PREV"])
            turnover = float(row["turnover"])
        except (KeyError, TypeError, ValueError):
            return False
        if not all(math.isfinite(v) for v in (volume, average, turnover)):
            return False
        if average <= 0 or volume < 0 or turnover < 0:
            return False
        ratio = volume / average
        return (self.volume_min <= ratio
                and (self.volume_max is None or ratio <= self.volume_max)
                and self.turnover_min <= turnover
                and (self.turnover_max is None or turnover <= self.turnover_max))


@dataclass
class UpdateResult:
    scan_date: str
    previous_trade_date: Optional[str]
    completeness: float
    expected: int
    saved: int
    failed: int
    today_pending: bool
    warning: str = ""


# ============================================================
# 后端
# ============================================================

class BaoStockBackend:
    HISTORY_FIELDS = "date,code,close,volume,tradestatus,isST,turn"

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._last_login_mono = 0.0
        # 同一次运行多个策略共用只读板块K线计算，避免重复全表读取。
        self._sector_chart_cache: dict[tuple[str, str], pd.DataFrame] = {}
        self._instance_lock_file = None

    # -------------------- 通用 --------------------

    @staticmethod
    def now_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def today_cn() -> str:
        return datetime.now(CST).strftime("%Y-%m-%d")

    @staticmethod
    def safe_float(value):
        try:
            if value in ("", None):
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def safe_int(value):
        try:
            if value in ("", None):
                return None
            return int(float(value))
        except Exception:
            return None

    @staticmethod
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

    @staticmethod
    def symbol_only(code: str) -> str:
        return code.split(".", 1)[1] if "." in code else code

    @staticmethod
    def pct(part: int, total: int) -> float:
        if total <= 0:
            return 1.0
        return max(0.0, min(1.0, part / total))

    @staticmethod
    def stage_progress(
        cb: ProgressCallback,
        start: float,
        end: float,
        part: int,
        total: int,
        task: str,
    ):
        fraction = BaoStockBackend.pct(part, total)
        cb(start + (end - start) * fraction, task)

    # -------------------- SQLite --------------------

    def prepare_storage(self, cb: ProgressCallback):
        """仅检查程序同级 data 文件夹，不移动、不删除现有数据库。

        SQLite 的 WAL 模式不仅要求 .db 可写，也要求 data 文件夹可创建
        -wal、-shm 文件。Windows 的“只读”属性可尝试自动移除；若受 NTFS
        权限控制，必须提示用户调整权限，不能悄悄迁移数据库。
        """
        cb(0, "检查原 data 目录的数据库写入权限")
        storage_dir = self.db_path.parent

        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"无法创建程序旁的数据目录：\n{storage_dir}\n"
                "请将整个程序文件夹放在有写入权限的位置，"
                "或在文件夹属性 → 安全中授予当前 Windows 用户修改权限。"
                f"\n原始错误：{exc}"
            ) from exc

        # Windows os.chmod() 可取消文件的“只读”属性；
        # 无法覆盖 NTFS ACL 的拒绝写入规则，出错时仍需明确提示。
        for path in (self.db_path,
                     self.db_path.with_name(self.db_path.name + "-wal"),
                     self.db_path.with_name(self.db_path.name + "-shm")):
            if not path.is_file():
                continue
            try:
                current_mode = path.stat().st_mode
                if not (current_mode & stat.S_IWUSR):
                    os.chmod(path, current_mode | stat.S_IWUSR)
            except OSError as exc:
                raise RuntimeError(
                    f"数据库文件仍是只读，且无法自动取消只读属性：\n{path}\n"
                    "请关闭其他运行中的扫描器，右键该文件 → 属性 → 取消只读；"
                    "同时检查 data 文件夹的安全权限。"
                    f"\n原始错误：{exc}"
                ) from exc

        # 真实创建临时文件来测试目录写权限，不能只用 os.access，
        # 因为 Windows NTFS ACL 与 os.access 的检测可能不一致。
        try:
            with tempfile.TemporaryFile(dir=storage_dir):
                pass
        except OSError as exc:
            raise RuntimeError(
                f"data 文件夹没有写入权限：\n{storage_dir}\n"
                "SQLite 需要在此目录创建 WAL/SHM 日志文件。"
                "请在文件夹属性 → 安全中为当前 Windows 用户启用修改权限，"
                "或将程序和 data 一起放到有写入权限的普通文件夹。"
                "不会移动或删除数据库。"
                f"\n原始错误：{exc}"
            ) from exc

        # Windows/Unix跨进程单实例锁，避免两份扫描器同时更新同一个SQLite库。
        # 锁文件仅位于原data目录；进程退出后文件句柄自动释放。
        if self._instance_lock_file is None:
            lock = None
            try:
                lock = (storage_dir / ".scanner.lock").open("a+b")
                lock.seek(0, 2)
                if lock.tell() == 0:
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._instance_lock_file = lock
            except OSError as exc:
                if lock is not None:
                    lock.close()
                raise RuntimeError(
                    "检测到另一个扫描器进程正在使用同一个data数据库，"
                    "或无法创建单实例锁。请先关闭其他扫描器，再点击重试更新。"
                    f"\n具体原因：{exc}"
                ) from exc

        # 检测已有数据库是否存在SQLite逻辑损坏，不自动清空或重建用户数据。
        if self.db_path.exists():
            try:
                with sqlite3.connect(self.db_path, timeout=30) as conn:
                    result = conn.execute("PRAGMA quick_check").fetchone()
                    if result is None or result[0] != "ok":
                        raise RuntimeError(
                            f"SQLite数据完整性检查失败：{result}。"
                            "请先备份整个data文件夹，暂时不要删除数据库。"
                        )
            except sqlite3.DatabaseError as exc:
                raise RuntimeError(
                    "SQLite数据库文件可能损坏。请先备份整个data文件夹，"
                    "不要删除或覆盖现有数据库。"
                    f"\n错误：{exc}"
                ) from exc

        # 在原数据库上验证能开启写事务；ROLLBACK 不改变用户的历史行情。
        try:
            conn = sqlite3.connect(self.db_path, timeout=12)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.rollback()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise RuntimeError(
                f"原数据库无法写入：\n{self.db_path}\n"
                "请关闭正在使用该数据库的其他程序，"
                "检查数据库文件是否为只读及 data 文件夹的 NTFS 修改权限。"
                "不会自动迁移或重建数据库。"
                f"\nSQLite 错误：{exc}"
            ) from exc

        cb(1, "原 data 文件夹可写，继续使用现有数据库")

    def init_db(self):
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            conn.execute("""
            CREATE TABLE IF NOT EXISTS daily (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                name TEXT,
                close REAL,
                volume REAL,
                trade_status INTEGER,
                is_st INTEGER,
                PRIMARY KEY (code, trade_date)
            )
            """)

            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_date
            ON daily(trade_date)
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS day_universe (
                trade_date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                trade_status INTEGER,
                PRIMARY KEY (trade_date, code)
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS day_status (
                trade_date TEXT PRIMARY KEY,
                expected_count INTEGER NOT NULL DEFAULT 0,
                saved_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'partial',
                updated_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS fetch_queue (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                name TEXT,
                reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                PRIMARY KEY (code, trade_date)
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_state (
                code TEXT PRIMARY KEY,
                name TEXT,
                history_ready INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS init_queue (
                code TEXT PRIMARY KEY,
                name TEXT,
                start_date TEXT,
                end_date TEXT,
                reason TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS industry_cache (
                code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                update_date TEXT,
                classification TEXT,
                fetched_at TEXT
            )
            """)

            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_industry_name
            ON industry_cache(industry)
            """)

            # 东方财富行业资金流排名与行业成分股代码缓存。
            # 刷新结果使用同一事务替换，避免排名和成分股错配。
            conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_top5_snapshot (
                rank INTEGER PRIMARY KEY,
                industry TEXT NOT NULL,
                net_yuan REAL NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_top5_member (
                rank INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                PRIMARY KEY(rank, stock_code)
            )
            """)
            existing={r[1] for r in conn.execute("PRAGMA table_info(fund_top5_snapshot)")}
            if "source" not in existing:
                conn.execute("ALTER TABLE fund_top5_snapshot ADD COLUMN source TEXT NOT NULL DEFAULT '东方财富'")
            conn.execute("""CREATE TABLE IF NOT EXISTS fund_source_health(
                source TEXT PRIMARY KEY, successes INTEGER NOT NULL DEFAULT 0,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                last_latency REAL, last_success TEXT, last_failure TEXT
            )""")

            conn.executescript("""
            CREATE TABLE IF NOT EXISTS signal_history (
                code TEXT NOT NULL, signal_date TEXT NOT NULL, strategy TEXT NOT NULL,
                filter_key TEXT NOT NULL, name TEXT, payload TEXT NOT NULL,
                source TEXT NOT NULL, recorded_at TEXT,
                PRIMARY KEY(code, signal_date, strategy, filter_key));
            CREATE INDEX IF NOT EXISTS idx_signal_code_date ON signal_history(code, signal_date);
            """)
            # 兼容原版数据库：旧行保留，缺失换手率以 NULL 表示。
            columns = {r[1] for r in conn.execute("PRAGMA table_info(daily)")}
            if "turnover" not in columns:
                conn.execute("ALTER TABLE daily ADD COLUMN turnover REAL")
            conn.commit()

    def upsert_daily_rows(self, conn, rows):
        if not rows:
            return

        conn.executemany("""
        INSERT OR REPLACE INTO daily
        (
            code, trade_date, name,
            close, volume, trade_status, is_st, turnover
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    def mark_history_ready(self, conn, code, name):
        conn.execute("""
        INSERT INTO stock_state
        (code, name, history_ready, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(code) DO UPDATE SET
            name=excluded.name,
            history_ready=1,
            updated_at=excluded.updated_at
        """, (code, name, self.now_text()))

        conn.execute(
            "DELETE FROM init_queue WHERE code=?",
            (code,)
        )

    def queue_init_failure(
        self,
        conn,
        code,
        name,
        start_date,
        end_date,
        reason,
    ):
        conn.execute("""
        INSERT INTO init_queue
        (
            code, name, start_date, end_date,
            reason, retry_count, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(code) DO UPDATE SET
            name=excluded.name,
            start_date=excluded.start_date,
            end_date=excluded.end_date,
            reason=excluded.reason,
            retry_count=init_queue.retry_count + 1,
            updated_at=excluded.updated_at
        """, (
            code,
            name,
            start_date,
            end_date,
            str(reason)[:500],
            self.now_text(),
        ))

    def queue_day_failure(
        self,
        conn,
        code,
        trade_date,
        name,
        reason,
    ):
        conn.execute("""
        INSERT INTO fetch_queue
        (
            code, trade_date, name,
            reason, retry_count, updated_at
        )
        VALUES (?, ?, ?, ?, 1, ?)
        ON CONFLICT(code, trade_date) DO UPDATE SET
            name=excluded.name,
            reason=excluded.reason,
            retry_count=fetch_queue.retry_count + 1,
            updated_at=excluded.updated_at
        """, (
            code,
            trade_date,
            name,
            str(reason)[:500],
            self.now_text(),
        ))

    @staticmethod
    def clear_day_failure(conn, code, trade_date):
        conn.execute("""
        DELETE FROM fetch_queue
        WHERE code=? AND trade_date=?
        """, (code, trade_date))

    def get_history_ready_codes(self) -> set[str]:
        # 四种策略中 MA20 的“昨日/今日”判断至少需要21根
        # 个股实际正常交易K线。这里直接以数据库实际行数为准，
        # 可兼容之前只为 MA10 建过较短历史的旧数据库。
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            existing = conn.execute("""
                SELECT code
                FROM daily
                WHERE trade_status=1
                GROUP BY code
                HAVING COUNT(*) >= 23
            """).fetchall()
            # IPO等不足23根有效K线的股票历史只需初始化一次，
            # 以后按每日增量更新即可，不在每次启动全量重抓。
            recorded = conn.execute("""
                SELECT code FROM stock_state WHERE history_ready=1
            """).fetchall()

        return {r[0] for r in existing} | {r[0] for r in recorded}

    def get_existing_codes_for_date(self, trade_date: str) -> set[str]:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT code
                FROM daily
                WHERE trade_date=? AND trade_status=1
                  AND close > 0 AND volume IS NOT NULL AND volume >= 0
            """, (trade_date,)).fetchall()

        return {r[0] for r in rows}

    def get_day_universe(self, trade_date: str) -> pd.DataFrame:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            return pd.read_sql_query("""
                SELECT trade_date, code, name, trade_status
                FROM day_universe
                WHERE trade_date=?
                ORDER BY code
            """, conn, params=(trade_date,))

    def get_partial_dates(self) -> list[str]:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT trade_date
                FROM day_status
                WHERE status <> 'complete'
                ORDER BY trade_date
            """).fetchall()

        return [r[0] for r in rows]

    def get_latest_processed_date(self) -> Optional[str]:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT MAX(trade_date)
                FROM day_status
            """).fetchone()

        return row[0] if row and row[0] else None

    def get_latest_daily_date(self) -> Optional[str]:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT MAX(trade_date)
                FROM daily
            """).fetchone()

        return row[0] if row and row[0] else None

    def get_day_status_info(self, trade_date: str):
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT
                    expected_count,
                    saved_count,
                    failed_count,
                    status
                FROM day_status
                WHERE trade_date=?
            """, (trade_date,)).fetchone()

        if not row:
            return None

        return {
            "expected": int(row[0]),
            "saved": int(row[1]),
            "failed": int(row[2]),
            "status": str(row[3]),
        }

    def update_day_status(self, trade_date: str):
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            expected = conn.execute("""
                SELECT COUNT(*)
                FROM day_universe
                WHERE trade_date=? AND trade_status=1
            """, (trade_date,)).fetchone()[0]

            # 仅统计“该交易日应当交易的股票”中实际下载成功的条目；
            # 旧日多余股票记录不能把完整率虚增到100%。
            saved = conn.execute("""
                SELECT COUNT(*)
                FROM day_universe AS u
                INNER JOIN daily AS d
                    ON d.code=u.code AND d.trade_date=u.trade_date
                WHERE u.trade_date=? AND u.trade_status=1
                  AND d.trade_status=1 AND d.close > 0
                  AND d.volume IS NOT NULL AND d.volume >= 0
            """, (trade_date,)).fetchone()[0]

            # 以前失败、现在已写入成功行情的项目，应自动清理队列。
            conn.execute("""
                DELETE FROM fetch_queue
                WHERE trade_date=?
                  AND EXISTS (
                    SELECT 1 FROM daily AS d
                    WHERE d.code=fetch_queue.code
                      AND d.trade_date=fetch_queue.trade_date
                      AND d.trade_status=1 AND d.close > 0
                      AND d.volume IS NOT NULL AND d.volume >= 0
                  )
            """, (trade_date,))
            failed = conn.execute("""
                SELECT COUNT(*) FROM fetch_queue
                WHERE trade_date=?
                  AND code IN (
                    SELECT code FROM day_universe
                    WHERE trade_date=? AND trade_status=1
                  )
            """, (trade_date, trade_date)).fetchone()[0]

            status = (
                "complete"
                if expected > 0 and saved >= expected and failed == 0
                else "partial"
            )

            conn.execute("""
                INSERT INTO day_status
                (
                    trade_date, expected_count,
                    saved_count, failed_count,
                    status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    expected_count=excluded.expected_count,
                    saved_count=excluded.saved_count,
                    failed_count=excluded.failed_count,
                    status=excluded.status,
                    updated_at=excluded.updated_at
            """, (
                trade_date,
                int(expected),
                int(saved),
                int(failed),
                status,
                self.now_text(),
            ))

            conn.commit()

        return {
            "expected": int(expected),
            "saved": int(saved),
            "failed": int(failed),
            "status": status,
        }

    # -------------------- BaoStock 会话 --------------------

    def login(self):
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(
                f"BaoStock连接失败：{lg.error_code} {lg.error_msg}"
            )
        self._last_login_mono = time.monotonic()

    def logout(self):
        try:
            bs.logout()
        except Exception:
            pass

    def reconnect(self):
        self.logout()
        time.sleep(0.8)
        self.login()

    def ensure_session_fresh(self):
        if (
            self._last_login_mono > 0
            and time.monotonic() - self._last_login_mono
            >= SESSION_REFRESH_SECONDS
        ):
            self.reconnect()

    @staticmethod
    def result_to_df(rs) -> pd.DataFrame:
        if rs.error_code != "0":
            raise RuntimeError(
                f"{rs.error_code} {rs.error_msg}"
            )

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        return pd.DataFrame(rows, columns=rs.fields)

    def run_query(self, query_func) -> pd.DataFrame:
        last_error = None

        for attempt in range(1, QUERY_RETRY + 1):
            try:
                self.ensure_session_fresh()
                return query_func()
            except Exception as exc:
                last_error = exc
                if attempt < QUERY_RETRY:
                    try:
                        self.reconnect()
                    except Exception:
                        pass
                    time.sleep(RETRY_WAIT * attempt)

        raise last_error

    # -------------------- BaoStock 查询 --------------------

    def query_trade_dates(self, start_date: str, end_date: str) -> pd.DataFrame:
        def q():
            rs = bs.query_trade_dates(
                start_date=start_date,
                end_date=end_date,
            )
            return self.result_to_df(rs)

        return self.run_query(q)

    def query_index_exact_day(self, trade_date: str) -> pd.DataFrame:
        def q():
            rs = bs.query_history_k_data_plus(
                "sh.000001",
                "date,code,close,volume",
                start_date=trade_date,
                end_date=trade_date,
                frequency="d",
                adjustflag="3",
            )
            return self.result_to_df(rs)

        return self.run_query(q)

    def get_recent_calendar_trade_dates(
        self,
        days_back: int = 90,
    ) -> list[str]:
        end = datetime.now(CST).date()
        start = end - timedelta(days=days_back)

        df = self.query_trade_dates(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

        if df.empty:
            raise RuntimeError("BaoStock交易日历返回空数据")

        return sorted(set(
            df.loc[
                df["is_trading_day"].astype(str) == "1",
                "calendar_date",
            ].astype(str).tolist()
        ))

    def is_today_trading_day(self) -> bool:
        today = self.today_cn()
        df = self.query_trade_dates(today, today)

        if df.empty:
            raise RuntimeError("今日交易日历返回空数据")

        return str(df.iloc[0].get("is_trading_day", "0")) == "1"

    def get_latest_available_trade_date(self) -> str:
        dates = self.get_recent_calendar_trade_dates()

        if not dates:
            raise RuntimeError("未找到最近交易日")

        # 交易日历告诉我们“应该交易”，指数K线告诉我们“数据已入库”。
        for trade_date in reversed(dates[-12:]):
            if not self.query_index_exact_day(trade_date).empty:
                return trade_date

        raise RuntimeError("最近交易日均未找到已入库日线")

    def recent_n_trade_dates(self, end_date: str, n: int) -> list[str]:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        start = end - timedelta(days=max(80, n * 3))

        df = self.query_trade_dates(
            start.strftime("%Y-%m-%d"),
            end_date,
        )

        dates = sorted(set(
            df.loc[
                df["is_trading_day"].astype(str) == "1",
                "calendar_date",
            ].astype(str).tolist()
        ))

        if len(dates) < n:
            raise RuntimeError(
                f"只找到 {len(dates)} 个交易日，少于需要的 {n} 个"
            )

        return dates[-n:]

    def get_previous_market_trade_date(
        self,
        trade_date: str,
    ) -> Optional[str]:
        end = (
            datetime.strptime(trade_date, "%Y-%m-%d").date()
            - timedelta(days=1)
        )
        start = end - timedelta(days=15)

        df = self.query_trade_dates(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

        if df.empty:
            return None

        dates = sorted(set(
            df.loc[
                df["is_trading_day"].astype(str) == "1",
                "calendar_date",
            ].astype(str).tolist()
        ))

        return dates[-1] if dates else None

    def query_all_a_stocks(self, trade_date: str) -> pd.DataFrame:
        def q():
            rs = bs.query_all_stock(day=trade_date)
            return self.result_to_df(rs)

        df = self.run_query(q)

        if df.empty:
            raise RuntimeError(f"{trade_date} 股票列表为空")

        if "code" not in df.columns:
            raise RuntimeError("股票列表缺少 code 字段")

        df = df[
            df["code"].astype(str).map(self.is_a_share_code)
        ].copy()

        if "tradeStatus" not in df.columns:
            df["tradeStatus"] = "1"

        if "code_name" not in df.columns:
            df["code_name"] = ""

        df["tradeStatus"] = (
            pd.to_numeric(df["tradeStatus"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

        return (
            df[["code", "tradeStatus", "code_name"]]
            .rename(columns={
                "tradeStatus": "trade_status",
                "code_name": "name",
            })
            .drop_duplicates("code")
            .sort_values("code")
            .reset_index(drop=True)
        )

    @staticmethod
    def normalize_industry_name(value: str) -> str:
        """
        BaoStock 常见行业值类似 J66货币金融服务、I65软件和信息技术服务。
        GUI 中去掉前面的行业编码，只保留可读名称。
        """
        value = str(value or "").strip()

        if not value or value.lower() == "nan":
            return "未分类"

        cleaned = re.sub(r"^[A-Za-z]\d+\s*", "", value).strip()
        return cleaned or value

    def query_stock_industry_all(self) -> pd.DataFrame:
        def q():
            rs = bs.query_stock_industry()
            return self.result_to_df(rs)

        return self.run_query(q)

    def get_industry_map(self) -> dict[str, str]:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT code, industry
                FROM industry_cache
            """).fetchall()

        return {
            str(code): self.normalize_industry_name(industry)
            for code, industry in rows
            if code
        }

    def _industry_cache_info(self):
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT COUNT(*), MAX(fetched_at)
                FROM industry_cache
            """).fetchone()

        count = int(row[0] or 0)
        fetched_at = row[1] if row else None

        fresh = False

        if fetched_at:
            try:
                dt = datetime.strptime(
                    fetched_at,
                    "%Y-%m-%d %H:%M:%S",
                )
                fresh = (
                    datetime.now() - dt
                    < timedelta(days=INDUSTRY_CACHE_DAYS)
                )
            except Exception:
                fresh = False

        return count, fresh

    def refresh_industry_cache(
        self,
        latest_stocks: pd.DataFrame,
        cb: ProgressCallback,
        start_p: float,
        end_p: float,
    ):
        """
        行业分类不是行情更新的硬依赖。
        若在线刷新失败但已有本地缓存，则继续使用缓存，不阻塞主程序。
        """
        cached_count, fresh = self._industry_cache_info()

        latest_codes = set(
            latest_stocks["code"].astype(str).tolist()
        )

        if latest_codes:
            cached_codes = set(self.get_industry_map().keys())
            coverage = (
                len(latest_codes & cached_codes)
                / len(latest_codes)
            )
        else:
            coverage = 0.0

        if fresh and coverage >= 0.90:
            cb(end_p, "板块分类缓存已就绪")
            return

        cb(start_p, "更新行业板块分类")

        try:
            df = self.query_stock_industry_all()

            if df is None or df.empty:
                raise RuntimeError("行业分类返回空数据")

            required = {"code", "industry"}

            if not required.issubset(df.columns):
                raise RuntimeError(
                    "行业分类返回字段不完整"
                )

            if "code_name" not in df.columns:
                df["code_name"] = ""

            if "updateDate" not in df.columns:
                df["updateDate"] = ""

            if "industryClassification" not in df.columns:
                df["industryClassification"] = ""

            df = df[
                df["code"].astype(str).map(
                    self.is_a_share_code
                )
            ].copy()

            now = self.now_text()

            rows = []

            for r in df.itertuples(index=False):
                code = str(getattr(r, "code", "") or "")
                industry = self.normalize_industry_name(
                    getattr(r, "industry", "")
                )

                if not code:
                    continue

                rows.append((
                    code,
                    str(getattr(r, "code_name", "") or ""),
                    industry,
                    str(getattr(r, "updateDate", "") or ""),
                    str(
                        getattr(
                            r,
                            "industryClassification",
                            "",
                        ) or ""
                    ),
                    now,
                ))

            if not rows:
                raise RuntimeError(
                    "行业分类没有可用A股记录"
                )

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO industry_cache
                    (
                        code, name, industry,
                        update_date, classification, fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, rows)
                conn.commit()

            cb(
                end_p,
                f"行业板块分类已更新 · {len(rows)}只",
            )

        except Exception:
            if cached_count > 0:
                cb(
                    end_p,
                    "板块分类在线更新失败，使用本地缓存",
                )
                return

            # 板块数据失败不影响四个原策略继续运行。
            cb(
                end_p,
                "板块分类暂不可用，个股扫描继续",
            )

    # -------------------- 近5日行业资金TOP5（来源自动选择） --------------------

    FUND_RANK_TIMEOUT=25
    FUND_JSON_PREFIX='__AShareMA_Fund_JSON__='
    FUND_CHILD=r"""
import sys,akshare as ak
endpoint=sys.argv[1]
if endpoint=='em_rank':
    data=ak.stock_sector_fund_flow_rank(indicator='5日',sector_type='行业资金流')
    fields=['名称','5日主力净流入-净额']
elif endpoint=='ths_rank':
    data=ak.stock_fund_flow_industry(symbol='5日排行')
    fields=['行业','净额']
else:
    raise ValueError('unknown endpoint')
if data is None or data.empty or any(x not in data.columns for x in fields):
    raise RuntimeError('empty response or missing columns')
print('__AShareMA_Fund_JSON__='+data[fields].to_json(orient='records',force_ascii=False),flush=True)
"""

    @classmethod
    def _fund_request(cls,endpoint,sector='',timeout=20):
        if endpoint not in ('em_rank','ths_rank'):
            raise ValueError('invalid fund endpoint')
        args=[sys.executable,'-c',cls.FUND_CHILD,endpoint]
        if sector: args.append(sector)
        env=os.environ.copy()
        env['PYTHONIOENCODING']='utf-8'
        try:
            done=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                encoding='utf-8',errors='replace',text=True,env=env,timeout=timeout,
                                creationflags=(subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0),check=False)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f'{endpoint} 请求超过{timeout}秒') from exc
        except OSError as exc:
            raise RuntimeError(f'资金接口子进程启动失败：{exc}') from exc
        if done.returncode:
            raise RuntimeError((done.stderr or done.stdout or '子进程错误')[-500:])
        if cls.FUND_JSON_PREFIX not in done.stdout:
            raise RuntimeError('资金接口未返回可解析数据')
        raw=done.stdout.rsplit(cls.FUND_JSON_PREFIX,1)[-1].splitlines()[0]
        try: records=json.loads(raw)
        except (ValueError,TypeError) as exc: raise RuntimeError('资金解析失败') from exc
        if not isinstance(records,list):
            raise RuntimeError('资金结果格式错误')
        return pd.DataFrame(records)


    def _fund_source_order(self):
        now=datetime.now(CST)
        with sqlite3.connect(self.db_path,timeout=10) as conn:
            history=conn.execute('SELECT source,successes,consecutive_failures,last_latency,last_success,last_failure FROM fund_source_health').fetchall()
        stats={row[0]:row[1:] for row in history}
        def score(src):
            successes,failures,latency,good,bad=stats.get(src,(0,0,None,None,None))
            cooldown=False
            if bad and failures>=2:
                try:
                    cooldown=(now-datetime.fromisoformat(bad).replace(tzinfo=CST)).total_seconds()<900
                except ValueError: pass
            return (cooldown,not bool(good),int(failures or 0),float(latency) if latency else 20.0,
                    0 if src=='东方财富' else 1)
        return sorted(('东方财富','同花顺'),key=score)

    def _fund_note_health(self,source,ok,elapsed):
        stamp=datetime.now(CST).isoformat(timespec='seconds')
        try:
            with sqlite3.connect(self.db_path,timeout=8) as conn:
                conn.execute('INSERT OR IGNORE INTO fund_source_health(source) VALUES(?)',(source,))
                if ok:
                    conn.execute('UPDATE fund_source_health SET successes=successes+1,consecutive_failures=0,last_latency=?,last_success=? WHERE source=?',(elapsed,stamp,source))
                else:
                    conn.execute('UPDATE fund_source_health SET consecutive_failures=consecutive_failures+1,last_failure=? WHERE source=?',(stamp,source))
        except sqlite3.Error:
            pass

    @staticmethod
    def _fund_stock_symbol(value) -> Optional[str]:
        """东财返回可能是 int 或 000001/交易所.000001，统一为6位代码。"""
        value = str(value or "").strip()
        if value.endswith(".0") and value[:-2].isdigit():
            value = value[:-2]
        if "." in value and value.split(".")[-1].isdigit():
            value = value.split(".")[-1]
        if not value.isdigit() or len(value) > 6:
            return None
        value = value.zfill(6)
        if value.startswith(SH_PREFIXES + SZ_PREFIXES):
            return value
        return None

    def load_fund_top5(self) -> tuple[list[dict], dict[int, set[str]]]:
        """仅查询五日资金净流入 TOP5 行业榜单。

        兼容旧调用方返回 (rows, {})，但不读取或请求成分股数据。
        """
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT rank,industry,net_yuan,fetched_at,source
                FROM fund_top5_snapshot ORDER BY rank
            """).fetchall()
        return ([dict(rank=int(rank),name=name,net_yuan=float(amount),
                      fetched_at=fetched_at,source=source)
                 for rank,name,amount,fetched_at,source in rows], {})


    def _fund_complete_snapshot(self,source,notify,now):
        """只请求行业资金排名；任何情况下都不请求行业成分股。"""
        endpoint='em_rank' if source=='东方财富' else 'ths_rank'
        notify(f'正在读取{source}近5日行业资金净流入排名…')
        ranked=self._fund_request(endpoint,timeout=self.FUND_RANK_TIMEOUT)
        name_col,amount_col=('名称','5日主力净流入-净额') if source=='东方财富' else ('行业','净额')
        if ranked.empty or not {name_col,amount_col}.issubset(ranked.columns):
            raise RuntimeError(f'{source}榜单为空或缺少必要字段')
        ranked=ranked[[name_col,amount_col]].copy()
        ranked[amount_col]=pd.to_numeric(ranked[amount_col],errors='coerce')
        ranked=ranked.dropna(subset=[name_col,amount_col])
        ranked=ranked.loc[ranked[amount_col].map(math.isfinite)]
        ranked[name_col]=ranked[name_col].astype(str).str.strip()
        ranked=ranked[ranked[name_col].ne('')].drop_duplicates(name_col)
        ranked=ranked.sort_values(amount_col,ascending=False).head(5)
        if len(ranked)!=5:
            raise RuntimeError(f'{source}有效行业少于5个')
        multiplier=1 if source=='东方财富' else 100000000
        stamp=now.strftime('%Y-%m-%d %H:%M:%S')
        rows=[(i,str(item[name_col]),float(item[amount_col])*multiplier,stamp,source)
              for i,(_,item) in enumerate(ranked.iterrows(),1)]
        notify(f'{source} · 近5日行业资金 TOP5 排名获取成功（5/5）')
        return rows


    def refresh_fund_top5(self,force=False,progress=None):
        notify=progress or (lambda _:None)
        self._fund_last_errors=[]
        previous,_=self.load_fund_top5()
        now=datetime.now(CST)
        if (not force and len(previous)==5
            and previous[0]['fetched_at'][:10]==now.strftime('%Y-%m-%d')
            and (now.hour<18 or previous[0]['fetched_at'][11:13]>='18')):
            return '已使用今日近5日资金TOP5行业榜单缓存'
        if now.weekday()<5 and now.hour<18:
            if previous:
                return '今日行情未结算，沿用本地TOP5行业榜单；18:00后可刷新'
            raise RuntimeError('交易日18:00后可获取完整的近5日行业资金榜单')
        errors=[]
        for source in self._fund_source_order():
            began=time.monotonic()
            try:
                rows=self._fund_complete_snapshot(source,notify,now)
                # 同一个事务替换榜单并清空历史遗留成分股；榜单失败不修改缓存。
                with sqlite3.connect(self.db_path,timeout=20) as conn:
                    conn.execute('DELETE FROM fund_top5_snapshot')
                    conn.execute('DELETE FROM fund_top5_member')
                    conn.executemany(
                        'INSERT INTO fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)',
                        rows)
                self._fund_note_health(source,True,time.monotonic()-began)
                return f'{source} · 近5日行业资金 TOP5 排名已更新'
            except (RuntimeError,TimeoutError,ValueError,sqlite3.Error) as exc:
                self._fund_note_health(source,False,time.monotonic()-began)
                errors.append(f'{source}: {exc}')
                self._fund_last_errors.append(dict(source=source,error=str(exc)))
                notify(f'{source}排名接口失败，切换备用来源…')
        raise RuntimeError('两个来源的行业资金排名均未获取成功，原有榜单缓存已保留。\n'
                           + '\n'.join(errors)[:2600])


    def persist_day_universe(
        self,
        trade_date: str,
        stocks: pd.DataFrame,
    ):
        rows = [
            (
                trade_date,
                str(r.code),
                str(r.name or ""),
                int(r.trade_status),
            )
            for r in stocks.itertuples(index=False)
        ]

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO day_universe
                (trade_date, code, name, trade_status)
                VALUES (?, ?, ?, ?)
            """, rows)

            active_count = sum(1 for row in rows if row[3] == 1)

            conn.execute("""
                INSERT INTO day_status
                (
                    trade_date, expected_count,
                    saved_count, failed_count,
                    status, updated_at
                )
                VALUES (?, ?, 0, 0, 'partial', ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    expected_count=excluded.expected_count,
                    updated_at=excluded.updated_at
            """, (
                trade_date,
                active_count,
                self.now_text(),
            ))

            conn.commit()

    def query_stock_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        def q():
            rs = bs.query_history_k_data_plus(
                code,
                self.HISTORY_FIELDS,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=ADJUST_FLAG,
            )
            return self.result_to_df(rs)

        return self.run_query(q)

    def dataframe_to_daily_rows(
        self,
        df: pd.DataFrame,
        name: str,
    ) -> list[tuple]:
        if df is None or df.empty:
            return []

        rows = []

        for r in df.itertuples(index=False):
            close = self.safe_float(getattr(r, "close", None))
            volume = self.safe_float(getattr(r, "volume", None))

            # NaN、inf、非法价格/成交量不得进入SQLite，避免污染均线和完整率。
            if (close is None or volume is None
                    or not math.isfinite(close) or close <= 0
                    or not math.isfinite(volume) or volume < 0):
                continue

            rows.append((
                str(getattr(r, "code")),
                str(getattr(r, "date")),
                name,
                close,
                volume,
                self.safe_int(getattr(r, "tradestatus", 1)),
                self.safe_int(getattr(r, "isST", 0)),
                self.valid_turnover(getattr(r, "turn", None)),
            ))

        return rows

    @staticmethod
    def valid_turnover(value):
        value = BaoStockBackend.safe_float(value)
        return value if value is not None and math.isfinite(value) and value >= 0 else None

    def backfill_turnover(self, end_date: str, cb: ProgressCallback) -> str:
        """仅补近期正常交易记录的缺失换手率；逐股提交，NULL 即续传标记。"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            dates = conn.execute("SELECT DISTINCT trade_date FROM daily WHERE trade_date<=? "
                                 "ORDER BY trade_date DESC LIMIT 80", (end_date,)).fetchall()
            if not dates:
                return ""
            start = dates[-1][0]
            jobs = conn.execute("SELECT code, MIN(trade_date), MAX(trade_date) FROM daily "
                                "WHERE trade_date BETWEEN ? AND ? AND trade_status=1 "
                                "AND turnover IS NULL GROUP BY code ORDER BY code",
                                (start, end_date)).fetchall()
        for idx, (code, first, last) in enumerate(jobs, 1):
            self.stage_progress(cb, 94, 96, idx-1, len(jobs),
                                f"补换手率 {idx}/{len(jobs)} · {self.symbol_only(code)}")
            try:
                data = self.query_stock_history(code, first, last)
                rows = []
                for row in data.itertuples(index=False):
                    value = self.valid_turnover(getattr(row, "turn", None))
                    if value is not None:
                        rows.append((value, code, str(row.date)))
                with sqlite3.connect(self.db_path, timeout=30) as conn:
                    conn.executemany("UPDATE daily SET turnover=? WHERE code=? AND trade_date=? "
                                     "AND turnover IS NULL", rows)
            except Exception:
                # 行情不受影响；缺失值保留，下次启动继续重试。
                pass
            if idx % BATCH_SIZE == 0:
                time.sleep(BATCH_PAUSE)
        cb(96, "近期换手率检查完成")
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            missing = conn.execute("SELECT COUNT(*) FROM daily WHERE trade_date BETWEEN ? AND ? "
                                   "AND trade_status=1 AND turnover IS NULL", (start, end_date)).fetchone()[0]
        return (f"近期有 {missing} 条换手率缺失，第5策略结果可能不完整；下次启动继续补抓。"
                if missing else "")

    # -------------------- 历史初始化 --------------------

    def retry_init_queue(
        self,
        cb: ProgressCallback,
        start_p: float,
        end_p: float,
    ):
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT code, name, start_date, end_date
                FROM init_queue
                ORDER BY code
            """).fetchall()

        if not rows:
            cb(end_p, "没有历史失败项")
            return

        total = len(rows)

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            for idx, (code, name, start_date, end_date) in enumerate(
                rows,
                start=1,
            ):
                self.stage_progress(
                    cb,
                    start_p,
                    end_p,
                    idx - 1,
                    total,
                    f"补历史失败 {idx}/{total} · {self.symbol_only(code)}",
                )

                try:
                    df = self.query_stock_history(
                        code,
                        start_date,
                        end_date,
                    )
                    data_rows = self.dataframe_to_daily_rows(
                        df,
                        name or "",
                    )

                    if not data_rows:
                        raise RuntimeError("历史补抓返回空数据")

                    self.upsert_daily_rows(conn, data_rows)
                    self.mark_history_ready(conn, code, name or "")

                except Exception as exc:
                    self.queue_init_failure(
                        conn,
                        code,
                        name or "",
                        start_date,
                        end_date,
                        exc,
                    )

                if idx % BATCH_SIZE == 0:
                    conn.commit()
                    time.sleep(BATCH_PAUSE)

            conn.commit()

        cb(end_p, "历史失败补抓完成")

    def initialize_missing_histories(
        self,
        latest_stocks: pd.DataFrame,
        latest_date: str,
        cb: ProgressCallback,
        start_p: float,
        end_p: float,
    ):
        trade_dates = self.recent_n_trade_dates(
            latest_date,
            INITIAL_TRADING_DAYS,
        )
        start_date = trade_dates[0]

        ready_codes = self.get_history_ready_codes()

        todo = latest_stocks[
            ~latest_stocks["code"].isin(ready_codes)
        ].copy()

        if todo.empty:
            cb(end_p, "历史缓存已就绪")
            return

        total = len(todo)

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            for idx, r in enumerate(
                todo.itertuples(index=False),
                start=1,
            ):
                code = str(r.code)
                name = str(r.name or "")

                self.stage_progress(
                    cb,
                    start_p,
                    end_p,
                    idx - 1,
                    total,
                    f"初始化历史 {idx}/{total} · {self.symbol_only(code)}",
                )

                try:
                    df = self.query_stock_history(
                        code,
                        start_date,
                        latest_date,
                    )
                    rows = self.dataframe_to_daily_rows(df, name)

                    if not rows:
                        raise RuntimeError("历史初始化返回空数据")

                    self.upsert_daily_rows(conn, rows)
                    self.mark_history_ready(conn, code, name)

                except Exception as exc:
                    self.queue_init_failure(
                        conn,
                        code,
                        name,
                        start_date,
                        latest_date,
                        exc,
                    )

                if idx % BATCH_SIZE == 0:
                    conn.commit()
                    time.sleep(BATCH_PAUSE)

            conn.commit()

        cb(end_p, "历史缓存初始化完成")

    # -------------------- 单日增量 --------------------

    def fetch_exact_day_for_stock(
        self,
        code: str,
        name: str,
        trade_date: str,
    ) -> list[tuple]:
        df = self.query_stock_history(
            code,
            trade_date,
            trade_date,
        )

        rows = self.dataframe_to_daily_rows(df, name)

        exact = [
            row for row in rows
            if row[1] == trade_date and row[5] == 1
        ]

        if not exact:
            raise RuntimeError("未返回目标交易日日K")

        return exact

    def process_trade_date(
        self,
        trade_date: str,
        cb: ProgressCallback,
        start_p: float,
        end_p: float,
    ):
        universe = self.get_day_universe(trade_date)

        if universe.empty:
            cb(start_p, f"读取 {trade_date} 股票列表")
            universe = self.query_all_a_stocks(trade_date)
            self.persist_day_universe(trade_date, universe)

        active = universe[
            universe["trade_status"] == 1
        ].copy()

        existing = self.get_existing_codes_for_date(trade_date)

        todo = active[
            ~active["code"].isin(existing)
        ].copy()

        if todo.empty:
            info = self.update_day_status(trade_date)
            cb(end_p, f"{trade_date} 已完整")
            return info

        total = len(todo)

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            for idx, r in enumerate(
                todo.itertuples(index=False),
                start=1,
            ):
                code = str(r.code)
                name = str(r.name or "")

                self.stage_progress(
                    cb,
                    start_p,
                    end_p,
                    idx - 1,
                    total,
                    f"更新 {trade_date} · {idx}/{total} · {self.symbol_only(code)}",
                )

                try:
                    rows = self.fetch_exact_day_for_stock(
                        code,
                        name,
                        trade_date,
                    )
                    self.upsert_daily_rows(conn, rows)
                    self.clear_day_failure(conn, code, trade_date)

                except Exception as exc:
                    self.queue_day_failure(
                        conn,
                        code,
                        trade_date,
                        name,
                        exc,
                    )

                if idx % BATCH_SIZE == 0:
                    conn.commit()
                    time.sleep(BATCH_PAUSE)

            conn.commit()

        info = self.update_day_status(trade_date)
        cb(end_p, f"{trade_date} 更新完成")
        return info

    def retry_partial_dates(
        self,
        latest_date: str,
        cb: ProgressCallback,
        start_p: float,
        end_p: float,
    ):
        dates = [
            d for d in self.get_partial_dates()
            if d <= latest_date
        ]

        if not dates:
            cb(end_p, "没有未完整交易日")
            return

        total = len(dates)

        for idx, trade_date in enumerate(dates, start=1):
            s = start_p + (end_p - start_p) * ((idx - 1) / total)
            e = start_p + (end_p - start_p) * (idx / total)

            self.process_trade_date(
                trade_date,
                cb,
                s,
                e,
            )

    def process_new_trade_dates(
        self,
        latest_available: str,
        cb: ProgressCallback,
        start_p: float,
        end_p: float,
    ):
        last_processed = self.get_latest_processed_date()
        last_daily = self.get_latest_daily_date()
        anchor = last_processed or last_daily

        if anchor is None:
            dates = [latest_available]

        elif anchor >= latest_available:
            # 首次历史建库通常已经有 latest_available，
            # 但还需要建立该日的 universe/完整率状态。
            dates = (
                [latest_available]
                if last_processed is None
                else []
            )

        else:
            start_date = (
                datetime.strptime(anchor, "%Y-%m-%d").date()
                + timedelta(days=1)
            ).strftime("%Y-%m-%d")

            df = self.query_trade_dates(
                start_date,
                latest_available,
            )

            if df.empty:
                dates = []
            else:
                dates = sorted(set(
                    df.loc[
                        df["is_trading_day"].astype(str) == "1",
                        "calendar_date",
                    ].astype(str).tolist()
                ))

        if not dates:
            cb(end_p, "没有新的交易日")
            return

        total = len(dates)

        for idx, trade_date in enumerate(dates, start=1):
            s = start_p + (end_p - start_p) * ((idx - 1) / total)
            e = start_p + (end_p - start_p) * (idx / total)

            self.process_trade_date(
                trade_date,
                cb,
                s,
                e,
            )

    # -------------------- 启动更新 --------------------

    def update_all(self, cb: ProgressCallback) -> UpdateResult:
        # 数据库位置固定在程序同级 data：启动前仅做权限检查和原地修复。
        self.prepare_storage(cb)
        self.init_db()
        self._sector_chart_cache.clear()

        cb(1, "连接 BaoStock")
        self.login()

        try:
            cb(5, "检查今天是否为交易日")
            today = self.today_cn()
            today_is_trading = self.is_today_trading_day()

            cb(8, "确认最近已更新的交易日")
            latest_available = self.get_latest_available_trade_date()

            today_pending = (
                today_is_trading
                and latest_available != today
            )

            cb(11, f"读取 {latest_available} 股票列表")
            latest_stocks = self.query_all_a_stocks(
                latest_available
            )

            # 先处理以前失败的历史初始化。
            self.retry_init_queue(
                cb,
                12,
                20,
            )

            # 首次或有新上市股票时补历史。
            self.initialize_missing_histories(
                latest_stocks,
                latest_available,
                cb,
                20,
                66,
            )

            # 以前中途失败的交易日优先补齐。
            self.retry_partial_dates(
                latest_available,
                cb,
                66,
                80,
            )

            # 数据库断点之后的新交易日。
            self.process_new_trade_dates(
                latest_available,
                cb,
                80,
                94,
            )

            turnover_warning = self.backfill_turnover(latest_available, cb)

            # 行业分类用于全部策略的板块联动。
            self.refresh_industry_cache(
                latest_stocks,
                cb,
                96,
                97,
            )

            cb(98, "校验最新交易日完整性")

            # 确保 latest_available 至少建立 day_status。
            universe = self.get_day_universe(latest_available)

            if universe.empty:
                self.process_trade_date(
                    latest_available,
                    cb,
                    98,
                    99,
                )

            status = self.update_day_status(
                latest_available
            )

            previous_date = self.get_previous_market_trade_date(
                latest_available
            )

            expected = status["expected"]
            saved = status["saved"]
            completeness = (
                saved / expected * 100
                if expected
                else 0.0
            )

            warning_parts = [turnover_warning] if turnover_warning else []

            if today_pending:
                warning_parts.append(
                    "今日数据未更新，请在18:00后尝试更新；"
                    f"当前显示 {latest_available}。"
                )

            if status["status"] != "complete":
                warning_parts.append(
                    f"{latest_available} 数据完整率 "
                    f"{completeness:.2f}%，结果可能不完整。"
                )

            cb(100, "数据检查完成")

            return UpdateResult(
                scan_date=latest_available,
                previous_trade_date=previous_date,
                completeness=completeness,
                expected=expected,
                saved=saved,
                failed=status["failed"],
                today_pending=today_pending,
                warning=" ".join(warning_parts),
            )

        finally:
            self.logout()

    @staticmethod
    def filter_key(strategy: str, filters: Optional[RangeFilter] = None) -> str:
        if strategy != "volume_turnover":
            return "固定规则"
        f = filters or RangeFilter()
        return json.dumps([float(f.volume_min), float(f.volume_max) if f.volume_max is not None else None,
                           float(f.turnover_min), float(f.turnover_max) if f.turnover_max is not None else None],
                          ensure_ascii=False, separators=(",", ":"))

    def record_signals(self, strategy: str, data: pd.DataFrame,
                       filters: Optional[RangeFilter] = None, source: str = "扫描"):
        if data.empty:
            return
        rows = []
        key = self.filter_key(strategy, filters)
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            for item in data.to_dict("records"):
                payload = {k: (None if pd.isna(v) else v) for k, v in item.items()}
                code, day = str(item["_code_full"]), str(item["触发日"])
                # 保存扫描当日的成交指标，便于以后查看当时的信号。
                bar = conn.execute("SELECT volume,turnover FROM daily WHERE code=? AND trade_date=?",
                                   (code, day)).fetchone()
                if bar:
                    payload.setdefault("换手率%", bar[1])
                    if "放量倍数" not in payload:
                        volumes = conn.execute("SELECT volume FROM daily WHERE code=? AND trade_date<? "
                                               "AND trade_status=1 AND close IS NOT NULL AND volume IS NOT NULL "
                                               "ORDER BY trade_date DESC LIMIT 5", (code, day)).fetchall()
                        average = sum(v[0] for v in volumes)/5 if len(volumes)==5 else 0
                        payload["放量倍数"] = bar[0]/average if average>0 else None
                rows.append((code, day, strategy, key, str(item.get("名称", "")),
                             json.dumps(payload, ensure_ascii=False, allow_nan=False), source, self.now_text()))
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.executemany("""
                INSERT INTO signal_history VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(code,signal_date,strategy,filter_key) DO UPDATE SET
                    name=excluded.name,payload=CASE WHEN signal_history.source='扫描' AND excluded.source='本地回算'
                    THEN signal_history.payload ELSE excluded.payload END,
                    source=CASE WHEN signal_history.source='扫描' THEN '扫描' ELSE excluded.source END,
                    recorded_at=excluded.recorded_at
            """, rows)

    def get_signal_history(self, code: str, end_date: str,
                           filters: Optional[RangeFilter] = None) -> pd.DataFrame:
        """回算这只股票的本地全部历史；保留已扫描过的其他参数方案。"""
        filters = filters or RangeFilter()
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            raw = pd.read_sql_query("SELECT * FROM daily WHERE code=? AND trade_date<=? ORDER BY trade_date",
                                    conn, params=(code, end_date))
        if not raw.empty:
            g = self._prepare_group(raw)
            results = {k: [] for k in StockScannerApp.STRATEGIES.values()}
            for pos in range(1, len(g)):
                row, prev = g.iloc[pos], g.iloc[pos-1]
                name_on_day = str(row.get("name", "") or "").strip().upper()
                if (self.safe_int(row["is_st"]) == 1
                        or name_on_day.lstrip("*").startswith("ST")):
                    continue
                for strategy in results:
                    match = False
                    if strategy == "volume_turnover":
                        match = pos >= 5 and filters.matches(row)
                    elif strategy == "ma5_turn_up":
                        # MA5(t-2)要求至少7根有效K线（pos从0开始）。
                        if pos >= 6:
                            before = g.iloc[pos - 2]
                            match = (
                                pd.notna(row["MA5"])
                                and pd.notna(prev["MA5"])
                                and pd.notna(before["MA5"])
                                and row["MA5"] > prev["MA5"]
                                and prev["MA5"] <= before["MA5"]
                            )
                    elif strategy == "ma_convergence_up":
                        match = pos >= 22 and ma_convergence_up_metrics(g, pos) is not None
                    elif pos >= 20 and prev["close"] > 0:
                        if strategy.startswith("breakout_ma"):
                            ma = 'MA' + strategy.replace('breakout_ma', '')
                            match = (pd.notna(row[ma]) and pd.notna(prev[ma]) and row[ma] > 0
                                     and pd.notna(row["VOL5_PREV"]) and row["VOL5_PREV"] > 0
                                     and row["close"] > row[ma] and prev["close"] <= prev[ma]
                                     and row["volume"] >= row["VOL5_PREV"] * VOLUME_RATIO)
                        elif strategy == "ma5_cross_ma10":
                            match = (pd.notna(prev["MA10"]) and row["MA10"] > 0
                                     and row["MA5"] > row["MA10"] and prev["MA5"] <= prev["MA10"])
                    if match:
                        average = row["VOL5_PREV"]
                        ratio = row["volume"] / average if pd.notna(average) and average > 0 else None
                        payload = {"_code_full": code, "代码": self.symbol_only(code),
                            "名称": row["name"], "触发日": row["trade_date"], "收盘价": row["close"],
                            "放量倍数": ratio, "换手率%": row.get("turnover")}
                        if strategy == "ma_convergence_up":
                            old_gap, new_gap, gain = ma_convergence_up_metrics(g, pos)
                            payload.update({"昨日粘合度%": round(old_gap, 3),
                                            "今日发散度%": round(new_gap, 3),
                                            "发散增加百分点": round(gain, 3)})
                        results[strategy].append(payload)
            for strategy, rows in results.items():
                self.record_signals(strategy, pd.DataFrame(rows), filters, "本地回算")
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            history = pd.read_sql_query("SELECT * FROM signal_history WHERE code=? AND signal_date<=? "
                                        "ORDER BY signal_date DESC,strategy,filter_key", conn, params=(code,end_date))
            days = [r[0] for r in conn.execute("SELECT DISTINCT trade_date FROM daily WHERE trade_date<=? ORDER BY trade_date",
                                             (end_date,))]
        history["streak"] = 1
        order = {day: i for i, day in enumerate(days)}
        for _, group in history.groupby(["strategy", "filter_key"]):
            last, streak = None, 0
            for idx, row in group.sort_values("signal_date").iterrows():
                position = order.get(row.signal_date)
                streak = streak+1 if last is not None and position is not None and position==last+1 else 1
                history.loc[idx,"streak"] = streak
                last = position
        return history

    @staticmethod
    def filter_results(data: pd.DataFrame, search: str = "", market: str = "全部市场",
                       industry: str = "全部行业", low=None, high=None, sector=None) -> pd.DataFrame:
        """快捷过滤只作用于当前策略的结果，不重新联网或改变信号。"""
        if data.empty:
            return data.copy()
        mask = pd.Series(True, index=data.index)
        if search.strip():
            text = search.strip().casefold()
            mask &= (data["代码"].astype(str).str.casefold().str.contains(text, regex=False)
                     | data["名称"].astype(str).str.casefold().str.contains(text, regex=False))
        codes = data["代码"].astype(str).str.zfill(6)
        if market == "创业板":
            mask &= codes.str.startswith(("300", "301"))
        elif market == "科创板":
            mask &= codes.str.startswith("688")
        elif market == "主板":
            mask &= ~codes.str.startswith(("300", "301", "688"))
        if industry != "全部行业":
            mask &= data["板块"].astype(str).eq(industry)
        if sector:
            mask &= data["板块"].astype(str).eq(sector)
        change = pd.to_numeric(data["当日涨幅%"], errors="coerce")
        if low is not None:
            mask &= change >= low
        if high is not None:
            mask &= change <= high
        return data.loc[mask].copy()

    # -------------------- 扫描 --------------------

    def _load_scan_data(
        self,
        end_date: str,
        distinct_days: int = 80,
    ) -> pd.DataFrame:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            dates = conn.execute("""
                SELECT DISTINCT trade_date
                FROM daily
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
            """, (
                end_date,
                distinct_days,
            )).fetchall()

            if not dates:
                return pd.DataFrame()

            oldest = dates[-1][0]

            return pd.read_sql_query("""
                SELECT
                    code,
                    trade_date,
                    name,
                    close,
                    volume,
                    trade_status,
                    is_st,
                    turnover
                FROM daily
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY code, trade_date
            """, conn, params=(oldest, end_date))

    @staticmethod
    def _prepare_group(g: pd.DataFrame) -> pd.DataFrame:
        g = g.copy()

        g["close"] = pd.to_numeric(
            g["close"],
            errors="coerce",
        )
        g["volume"] = pd.to_numeric(
            g["volume"],
            errors="coerce",
        )
        g["trade_status"] = pd.to_numeric(
            g["trade_status"],
            errors="coerce",
        )
        g["is_st"] = pd.to_numeric(
            g["is_st"],
            errors="coerce",
        )
        if "turnover" not in g.columns:
            g["turnover"] = float("nan")
        g["turnover"] = pd.to_numeric(
            g["turnover"],
            errors="coerce",
        )

        # 排除无效行情（含旧版本遗留的0价、inf、异常负成交量）。
        g[["close", "volume"]] = g[["close", "volume"]].replace(
            [float("inf"), float("-inf")], float("nan")
        )
        g = (
            g.dropna(subset=["close", "volume"])
            .loc[lambda x: (x["trade_status"] == 1)
                 & (x["close"] > 0) & (x["volume"] >= 0)]
            .sort_values("trade_date")
            .copy()
        )

        if g.empty:
            return g

        for window in MA_WINDOWS:
            g[f"MA{window}"] = (
                g["close"]
                .rolling(window)
                .mean()
            )

        g["VOL5_PREV"] = (
            g["volume"]
            .shift(1)
            .rolling(VOLUME_AVG_DAYS)
            .mean()
        )

        return g

    def scan_strategy(
        self,
        strategy: str,
        target_date: str,
        include_previous: bool,
        previous_trade_date: Optional[str],
        filters: Optional[RangeFilter] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> pd.DataFrame:
        # 第5策略才使用用户输入的区间；其他策略保持各自固定规则。
        active_filters = filters if strategy == "volume_turnover" else None
        filters = active_filters or RangeFilter()

        def cancelled() -> bool:
            return bool(cancel_event and cancel_event.is_set())
        scan_dates = [target_date]

        if include_previous and previous_trade_date:
            scan_dates.append(previous_trade_date)

        earliest_needed = min(scan_dates)
        df = self._load_scan_data(target_date)

        if df.empty:
            return pd.DataFrame()

        result = []
        daily_metrics = {}

        # 七个策略都附带行业板块，板块区始终只展示当前选中的策略。
        industry_map = self.get_industry_map()

        for code, raw in df.groupby("code", sort=False):
            if cancelled():
                return pd.DataFrame()
            g = self._prepare_group(raw)

            if g.empty:
                continue

            for signal_date in scan_dates:
                positions = g.index[
                    g["trade_date"].astype(str) == signal_date
                ].tolist()

                if not positions:
                    continue

                # positions 里拿到的是原 DataFrame index，因此用布尔定位后再取位置。
                sub = g[
                    g["trade_date"].astype(str) <= signal_date
                ]

                if sub.empty or str(sub.iloc[-1]["trade_date"]) != signal_date:
                    continue

                today = sub.iloc[-1]
                average = today["VOL5_PREV"]
                ratio = (float(today["volume"] / average)
                         if pd.notna(average) and average > 0 else None)
                turnover = self.valid_turnover(today.get("turnover"))
                daily_metrics[(code, signal_date)] = (ratio, turnover)

                name_today = str(today.get("name", "") or "").strip().upper()
                if (self.safe_int(today["is_st"]) == 1
                        or name_today.lstrip("*").startswith("ST")):
                    continue

                minimum_bars = (
                    6 if strategy == "volume_turnover"
                    else 7 if strategy == "ma5_turn_up"
                    else 23 if strategy == "ma_convergence_up"
                    else 21
                )
                if len(sub) < minimum_bars:
                    continue

                prev = sub.iloc[-2]

                if strategy == "volume_turnover":
                    if not filters.matches(today):
                        continue
                    change = ((today["close"] / prev["close"] - 1) * 100
                              if prev["close"] > 0 else float("nan"))
                    result.append({
                        "代码": self.symbol_only(code), "名称": str(today["name"] or ""),
                        "板块": industry_map.get(code, "未分类"), "触发日": signal_date,
                        "收盘价": round(float(today["close"]), 2),
                        "当日涨幅%": round(float(change), 2),
                        "放量倍数": round(float(today["volume"] / today["VOL5_PREV"]), 2),
                        "换手率%": round(float(today["turnover"]), 3), "_code_full": code,
                    })

                elif strategy.startswith("breakout_ma"):
                    ma_n = int(strategy.replace("breakout_ma", ""))
                    ma_col = f"MA{ma_n}"

                    if (
                        pd.isna(today[ma_col])
                        or pd.isna(prev[ma_col])
                        or pd.isna(today["VOL5_PREV"])
                        or today["VOL5_PREV"] <= 0
                        or prev["close"] <= 0
                        or today[ma_col] <= 0
                    ):
                        continue

                    triggered = (
                        today["close"] > today[ma_col]
                        and prev["close"] <= prev[ma_col]
                        and today["volume"]
                        >= today["VOL5_PREV"] * VOLUME_RATIO
                    )

                    if not triggered:
                        continue

                    daily_change = (
                        today["close"] / prev["close"] - 1
                    ) * 100

                    breakout_pct = (
                        today["close"] / today[ma_col] - 1
                    ) * 100

                    volume_ratio = (
                        today["volume"] / today["VOL5_PREV"]
                    )

                    result.append({
                        "代码": self.symbol_only(code),
                        "名称": str(today["name"] or ""),
                        "板块": industry_map.get(
                            code,
                            "未分类",
                        ),
                        "触发日": signal_date,
                        "收盘价": round(float(today["close"]), 2),
                        "当日涨幅%": round(float(daily_change), 2),
                        f"MA{ma_n}": round(float(today[ma_col]), 2),
                        f"突破MA{ma_n}幅度%": round(
                            float(breakout_pct),
                            3,
                        ),
                        "放量倍数": round(float(volume_ratio), 2),
                        "_code_full": code,
                    })

                elif strategy == "ma5_turn_up":
                    # 严格的一次性向上转折：昨日走平/下行，今天首次转升。
                    before = sub.iloc[-3]
                    if (
                        pd.isna(today["MA5"])
                        or pd.isna(prev["MA5"])
                        or pd.isna(before["MA5"])
                        or prev["close"] <= 0
                        or prev["MA5"] <= 0
                        or not (
                            today["MA5"] > prev["MA5"]
                            and prev["MA5"] <= before["MA5"]
                        )
                    ):
                        continue

                    change = (today["close"] / prev["close"] - 1) * 100
                    turn_pct = (today["MA5"] / prev["MA5"] - 1) * 100
                    result.append({
                        "代码": self.symbol_only(code),
                        "名称": str(today["name"] or ""),
                        "板块": industry_map.get(code, "未分类"),
                        "触发日": signal_date,
                        "收盘价": round(float(today["close"]), 2),
                        "当日涨幅%": round(float(change), 2),
                        "MA5": round(float(today["MA5"]), 3),
                        "昨日MA5": round(float(prev["MA5"]), 3),
                        "MA5上拐幅度%": round(float(turn_pct), 3),
                        "_code_full": code,
                    })

                elif strategy == "ma_convergence_up":
                    # 先验证昨日粘合、今日三均线上升并多头排列、间距扩大；再排除连续触发。
                    metrics = ma_convergence_up_metrics(sub, len(sub) - 1)
                    if metrics is None or prev["close"] <= 0:
                        continue
                    old_gap, new_gap, gap_gain = metrics
                    change = (today["close"] / prev["close"] - 1) * 100
                    result.append({
                        "代码": self.symbol_only(code),
                        "名称": str(today["name"] or ""),
                        "板块": industry_map.get(code, "未分类"),
                        "触发日": signal_date,
                        "收盘价": round(float(today["close"]), 2),
                        "当日涨幅%": round(float(change), 2),
                        "MA5": round(float(today["MA5"]), 3),
                        "MA10": round(float(today["MA10"]), 3),
                        "MA20": round(float(today["MA20"]), 3),
                        "昨日粘合度%": round(old_gap, 3),
                        "今日发散度%": round(new_gap, 3),
                        "发散增加百分点": round(gap_gain, 3),
                        "_code_full": code,
                    })

                elif strategy == "ma5_cross_ma10":
                    if (
                        pd.isna(today["MA5"])
                        or pd.isna(today["MA10"])
                        or pd.isna(prev["MA5"])
                        or pd.isna(prev["MA10"])
                        or prev["close"] <= 0
                        or today["MA10"] <= 0
                    ):
                        continue

                    triggered = (
                        today["MA5"] > today["MA10"]
                        and prev["MA5"] <= prev["MA10"]
                    )

                    if not triggered:
                        continue

                    daily_change = (
                        today["close"] / prev["close"] - 1
                    ) * 100

                    spread_pct = (
                        today["MA5"] / today["MA10"] - 1
                    ) * 100

                    result.append({
                        "代码": self.symbol_only(code),
                        "名称": str(today["name"] or ""),
                        "板块": industry_map.get(
                            code,
                            "未分类",
                        ),
                        "触发日": signal_date,
                        "收盘价": round(float(today["close"]), 2),
                        "当日涨幅%": round(float(daily_change), 2),
                        "MA5": round(float(today["MA5"]), 2),
                        "MA10": round(float(today["MA10"]), 2),
                        "MA5高于MA10%": round(
                            float(spread_pct),
                            3,
                        ),
                        "_code_full": code,
                    })

        out = pd.DataFrame(result)

        if out.empty:
            return out

        # 七个策略统一显示触发当天的成交指标，缺失值不冒充零。
        metrics = [daily_metrics[(str(row["_code_full"]), str(row["触发日"]))]
                   for row in out.to_dict("records")]
        volume_digits = 6 if strategy == "volume_turnover" else 2
        turnover_digits = 6 if strategy == "volume_turnover" else 3
        out["放量倍数"] = [round(pair[0], volume_digits) if pair[0] is not None else float("nan") for pair in metrics]
        out["换手率%"] = [round(pair[1], turnover_digits) if pair[1] is not None else float("nan") for pair in metrics]

        # 第5策略的精准区间判定已经由 RangeFilter.matches(today) 在原始数据上完成。
        # 不得对显示用的两/三位小数再筛一次，否则临界值会被错误剔除。

        # 板块本身也只按当前选中的策略判断。
        sector_status = {}

        if "板块" in out.columns:
            for sector_name in (
                out["板块"]
                .fillna("未分类")
                .astype(str)
                .drop_duplicates()
                .tolist()
            ):
                if cancelled():
                    return pd.DataFrame()
                if sector_name == "未分类":
                    sector_status[sector_name] = "未分类"
                    continue

                sector_status[sector_name] = (
                    self.get_sector_strategy_status(
                        sector_name=sector_name,
                        strategy=strategy,
                        target_date=target_date,
                        include_previous=include_previous,
                        previous_trade_date=previous_trade_date,
                        filters=filters,
                    )
                )

            out["板块信号"] = (
                out["板块"]
                .fillna("未分类")
                .astype(str)
                .map(sector_status)
                .fillna("未分类")
            )

        # 最新触发日在前；同日内优先显示信号强度较大的股票。
        if strategy.startswith("breakout_ma"):
            ma_n = int(strategy.replace("breakout_ma", ""))
            out = out.sort_values(
                ["触发日", "放量倍数", f"突破MA{ma_n}幅度%"],
                ascending=[False, False, False],
            )
        elif strategy == "volume_turnover":
            out = out.sort_values(["触发日", "放量倍数", "换手率%"], ascending=[False, False, False])
        elif strategy == "ma5_turn_up":
            out = out.sort_values(
                ["触发日", "MA5上拐幅度%", "当日涨幅%"],
                ascending=[False, False, False],
            )
        elif strategy == "ma_convergence_up":
            out = out.sort_values(
                ["触发日", "发散增加百分点", "当日涨幅%"],
                ascending=[False, False, False],
            )
        else:
            out = out.sort_values(
                ["触发日", "MA5高于MA10%", "当日涨幅%"],
                ascending=[False, False, False],
            )

        if cancelled():
            return pd.DataFrame()

        self.record_signals(strategy, out, active_filters)
        return out.reset_index(drop=True)

    # -------------------- 图表数据 --------------------

    def get_chart_data(self, code_full: str, end_date: str) -> pd.DataFrame:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            df = pd.read_sql_query("SELECT * FROM daily WHERE code=? AND trade_date<=? "
                                   "AND trade_status=1 ORDER BY trade_date DESC LIMIT 80",
                                   conn, params=(code_full, end_date))
        if df.empty:
            return df
        df = self._prepare_group(df)
        df["放量倍数"] = df["volume"] / df["VOL5_PREV"].where(df["VOL5_PREV"] > 0)
        df["turnover"] = df["turnover"].map(self.valid_turnover)
        return df.tail(30).reset_index(drop=True)

    def get_sector_chart_data(
        self,
        sector_name: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        板块走势图：
        - 取行业板块全部成分股；
        - 每只股票后复权收盘价先归一化到100，再做等权平均；
        - 板块成交量用当日全部有效成分股成交量求和；
        - 在板块等权指数上计算 MA5 / MA10 / MA20；
        - 同时计算板块前5个交易日平均成交量，供“放量突破”策略判断。
        """
        cache_key = (str(sector_name), str(end_date))
        cached = self._sector_chart_cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        # SQLite窗口函数：先从行业成员中检索各股最近70根K线，
        # 不再将该板块历年全部日线读入内存，也不受IN列表绑定参数数量限制。
        sql = """
            WITH recent AS (
                SELECT d.code,d.trade_date,d.close,d.volume,
                       d.trade_status,d.turnover,
                       ROW_NUMBER() OVER (
                           PARTITION BY d.code ORDER BY d.trade_date DESC
                       ) AS rn
                FROM daily AS d
                INNER JOIN industry_cache AS i ON i.code=d.code
                WHERE i.industry=? AND d.trade_date<=?
                  AND d.trade_status=1 AND d.close>0
                  AND d.volume IS NOT NULL AND d.volume>=0
            )
            SELECT code,trade_date,close,volume,trade_status,turnover
            FROM recent WHERE rn<=70 ORDER BY code,trade_date DESC
        """
        with sqlite3.connect(self.db_path, timeout=20) as conn:
            raw = pd.read_sql_query(sql, conn, params=(sector_name, end_date))

        if raw.empty:
            return pd.DataFrame()

        raw["close"] = pd.to_numeric(
            raw["close"],
            errors="coerce",
        )
        raw["volume"] = pd.to_numeric(
            raw["volume"],
            errors="coerce",
        )
        raw["trade_status"] = pd.to_numeric(
            raw["trade_status"],
            errors="coerce",
        )

        raw[["close", "volume"]] = raw[["close", "volume"]].replace(
            [float("inf"), float("-inf")], float("nan")
        )
        raw = (
            raw.dropna(subset=["close", "volume"])
            .loc[lambda x: (x["trade_status"] == 1)
                 & (x["close"] > 0) & (x["volume"] >= 0)]
            .copy()
        )

        if raw.empty:
            return pd.DataFrame()

        raw["turnover"] = raw["turnover"].map(self.valid_turnover)

        # 每只股票保留最近约70个有效交易日。
        raw = (
            raw.groupby("code", group_keys=False)
            .head(70)
            .sort_values(["code", "trade_date"])
            .copy()
        )

        normalized_rows = []

        for code, g in raw.groupby("code", sort=False):
            if g.empty:
                continue

            base = float(g.iloc[0]["close"])

            if base <= 0:
                continue

            g = g.copy()
            g["norm_close"] = (
                g["close"] / base * 100.0
            )

            normalized_rows.append(
                g[
                    [
                        "trade_date",
                        "norm_close",
                        "volume",
                        "turnover",
                    ]
                ]
            )

        if not normalized_rows:
            return pd.DataFrame()

        merged = pd.concat(
            normalized_rows,
            ignore_index=True,
        )

        sector = (
            merged.groupby("trade_date", as_index=False)
            .agg(
                close=("norm_close", "mean"),
                volume=("volume", "sum"),
                turnover=("turnover", "mean"),
                turnover_members=("turnover", "count"),
                members=("norm_close", "count"),
            )
            .sort_values("trade_date")
            .reset_index(drop=True)
        )

        for window in MA_WINDOWS:
            sector[f"MA{window}"] = (
                sector["close"]
                .rolling(window)
                .mean()
            )

        sector["VOL5_PREV"] = (
            sector["volume"]
            .shift(1)
            .rolling(VOLUME_AVG_DAYS)
            .mean()
        )

        sector["放量倍数"] = sector["volume"] / sector["VOL5_PREV"].where(sector["VOL5_PREV"] > 0)
        result = sector.tail(40).reset_index(drop=True)
        # 有上限的轻量缓存，避免大量策略来回切换时内存无限增长。
        if len(self._sector_chart_cache) >= 120:
            self._sector_chart_cache.clear()
        self._sector_chart_cache[cache_key] = result.copy()
        return result

    @staticmethod
    def _sector_strategy_triggered(
        data: pd.DataFrame,
        strategy: str,
        signal_date: str,
        filters: Optional[RangeFilter] = None,
    ) -> bool:
        if data is None or data.empty:
            return False

        sub = data[
            data["trade_date"].astype(str)
            <= str(signal_date)
        ]

        if (
            sub.empty
            or str(sub.iloc[-1]["trade_date"])
            != str(signal_date)
            or len(sub) < 2
        ):
            return False

        today = sub.iloc[-1]
        prev = sub.iloc[-2]

        if strategy == "volume_turnover":
            return (filters or RangeFilter()).matches(today)

        if strategy.startswith("breakout_ma"):
            ma_n = int(
                strategy.replace(
                    "breakout_ma",
                    "",
                )
            )
            ma_col = f"MA{ma_n}"

            if (
                ma_col not in sub.columns
                or pd.isna(today[ma_col])
                or pd.isna(prev[ma_col])
                or pd.isna(today["VOL5_PREV"])
                or today["VOL5_PREV"] <= 0
            ):
                return False

            return bool(
                today["close"] > today[ma_col]
                and prev["close"] <= prev[ma_col]
                and today["volume"]
                >= today["VOL5_PREV"] * VOLUME_RATIO
            )

        if strategy == "ma5_turn_up":
            if len(sub) < 3 or "MA5" not in sub.columns:
                return False
            before = sub.iloc[-3]
            if any(pd.isna(bar["MA5"]) for bar in (today, prev, before)):
                return False
            return bool(
                today["MA5"] > prev["MA5"]
                and prev["MA5"] <= before["MA5"]
            )

        if strategy == "ma_convergence_up":
            return ma_convergence_up_metrics(sub, len(sub) - 1) is not None

        if strategy == "ma5_cross_ma10":
            if (
                pd.isna(today["MA5"])
                or pd.isna(today["MA10"])
                or pd.isna(prev["MA5"])
                or pd.isna(prev["MA10"])
            ):
                return False

            return bool(
                today["MA5"] > today["MA10"]
                and prev["MA5"] <= prev["MA10"]
            )

        return False

    def get_sector_strategy_status(
        self,
        sector_name: str,
        strategy: str,
        target_date: str,
        include_previous: bool,
        previous_trade_date: Optional[str],
        filters: Optional[RangeFilter] = None,
    ) -> str:
        data = self.get_sector_chart_data(
            sector_name,
            target_date,
        )

        if self._sector_strategy_triggered(
            data,
            strategy,
            target_date,
            filters,
        ):
            return "今日触发"

        if (
            include_previous
            and previous_trade_date
            and self._sector_strategy_triggered(
                data,
                strategy,
                previous_trade_date,
                filters,
            )
        ):
            return "昨日触发"

        return "未触发"


# ============================================================
# GUI
# ============================================================

class HoverTip:
    """轻量提示框：不抢焦点，离开控件或销毁窗口时立即关闭。"""
    def __init__(self, owner):
        self.owner = owner
        self.window = None
        self.text = ""
        owner.bind("<Destroy>", lambda event: self.hide() if event.widget == owner else None, add="+")

    def hide(self):
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
        self.text = ""

    def show(self, text, x, y):
        if not text:
            self.hide()
            return
        if self.window is None:
            self.window = tk.Toplevel(self.owner)
            self.window.withdraw()
            self.window.overrideredirect(True)
            self.window.attributes("-topmost", True)
            self.label = tk.Label(self.window, text=text, justify="left", anchor="w",
                                  background="#ffffff", foreground="#1d1d1f", font=("Segoe UI", 10),
                                  padx=10, pady=7, relief="solid", borderwidth=1, wraplength=420)
            self.label.pack()
        if text != self.text:
            self.label.configure(text=text)
            self.text = text
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        screen_w, screen_h = self.owner.winfo_screenwidth(), self.owner.winfo_screenheight()
        x = max(4, min(int(x) + 16, screen_w - width - 4))
        y = int(y) + 18
        if y + height > screen_h - 4:
            y = max(4, int(y) - height - 12)
        self.window.geometry(f"+{x}+{y}")
        self.window.deiconify()


def attach_sector_tip(tree):
    """个股及板块表的板块名称悬停提示；延迟出现，避免扫过时闪烁。"""
    tip = HoverTip(tree)
    state = {"key": None, "timer": None, "position": None}
    def hide(_event=None):
        if state["timer"]:
            try:
                tree.after_cancel(state["timer"])
            except tk.TclError:
                pass
        state.update(key=None, timer=None, position=None)
        tip.hide()
    def motion(event):
        columns = list(tree["columns"])
        row = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        if not row or not column or tree.identify_region(event.x, event.y) != "cell":
            hide()
            return
        index = int(column[1:]) - 1
        if index < 0 or index >= len(columns) or columns[index] != "板块":
            hide()
            return
        name = tree.set(row, "板块")
        key = (row, name)
        if not name or name == "全部板块":
            hide()
            return
        state["position"] = (event.x, event.y, event.x_root, event.y_root)
        if key == state["key"]:
            return
        hide()
        state["key"] = key
        state["position"] = (event.x, event.y, event.x_root, event.y_root)
        def show():
            state["timer"] = None
            if state["key"] != key or not tree.winfo_exists():
                return
            x, y, root_x, root_y = state["position"]
            if tree.exists(row) and tree.identify_row(y) == row and tree.set(row, "板块") == name:
                tip.show(name, root_x, root_y)
        state["timer"] = tree.after(350, show)
    tree.bind("<Motion>", motion, add="+")
    for event in ("<Leave>", "<ButtonPress>", "<MouseWheel>", "<Button-4>", "<Button-5>", "<Configure>", "<Unmap>", "<Destroy>"):
        tree.bind(event, hide, add="+")
    tree._sector_tip = tip


def attach_chart_hover(canvas):
    """所有图表共用同一读数逻辑，按日期就近吸附，提示完整成交信息。"""
    if hasattr(canvas, "_hover_tip"):
        return
    canvas._hover_tip = HoverTip(canvas)
    def hide(_event=None):
        canvas._hover_tip.hide()
        if canvas.winfo_exists():
            canvas.delete("hover_cursor")
    def motion(event):
        state = getattr(canvas, "_chart_state", None)
        if not state:
            hide()
            return
        frame, series, left, top, plot_w, plot_h, ymin, ymax = state
        if not (left <= event.x <= left + plot_w and top <= event.y <= top + plot_h):
            hide()
            return
        count = len(frame)
        index = 0 if count == 1 else max(0, min(count-1, round((event.x-left)/plot_w*(count-1))))
        row = frame.iloc[index]
        x = left + plot_w/2 if count == 1 else left + plot_w*index/(count-1)
        canvas.delete("hover_cursor")
        canvas.create_line(x, top, x, top+plot_h, fill="#6e6e73", dash=(3,3), tags="hover_cursor")
        for column, color in series.items():
            value = BaoStockBackend.safe_float(row.get(column))
            if value is not None and math.isfinite(value):
                y = top + plot_h*(ymax-value)/(ymax-ymin)
                canvas.create_oval(x-3,y-3,x+3,y+3,fill=color,outline="white",tags="hover_cursor")
        def number(column, suffix="", volume=False):
            value = BaoStockBackend.safe_float(row.get(column))
            if value is None or not math.isfinite(value):
                return "缺失"
            return (f"{value:,.0f}" if volume else f"{value:.3f}") + suffix
        sector = "members" in frame.columns
        text = [str(row["trade_date"]),
                ("板块等权指数：" if sector else "收盘价：") + number("close"),
                ("成交量总和：" if sector else "成交量：") + number("volume", " 股", True),
                "放量倍数：" + number("放量倍数", " 倍"),
                ("等权换手率：" if sector else "换手率：") + number("turnover", "%")]
        for column in series:
            if column.startswith("MA"):
                text.append(column + "：" + number(column))
        canvas._hover_index = index
        canvas._hover_tip.show("\n".join(text), event.x_root, event.y_root)
    canvas.bind("<Motion>", motion, add="+")
    for event in ("<Leave>", "<Unmap>"):
        canvas.bind(event, hide, add="+")
    canvas._hover_hide = hide


class StockScannerApp:
    STRATEGIES = {
        "放量突破 MA5": "breakout_ma5",
        "放量突破 MA10": "breakout_ma10",
        "放量突破 MA20": "breakout_ma20",
        "MA5 上穿 MA10": "ma5_cross_ma10",
        "放量 + 换手率筛选": "volume_turnover",
        "MA5 拐头向上": "ma5_turn_up",
        "均线粘合向上": "ma_convergence_up",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        # 启动期间隐藏主界面；所有行情加载步骤在独立进度窗口显示。
        self.root.withdraw()
        self._startup_loading = True
        self._startup_started_at = time.monotonic()
        self.splash_window = None
        self.root.title(APP_TITLE)
        self.root.geometry("1080x810")  # 4:3 默认窗口
        self.root.minsize(960, 720)

        self.backend = BaoStockBackend(DB_PATH)
        self.events: queue.Queue = queue.Queue()

        self.update_result: Optional[UpdateResult] = None
        self.current_strategy_key: Optional[str] = None
        self.current_strategy_label: str = ""
        self.current_df = pd.DataFrame()
        self.current_sort_column: Optional[str] = None
        self.current_sort_reverse = False
        self.current_sector_filter: Optional[str] = None

        self.progress_var = tk.DoubleVar(value=0)
        self.task_var = tk.StringVar(value="准备检查数据…")
        self.date_var = tk.StringVar(value="数据日期：—")
        self.complete_var = tk.StringVar(value="完整率：—")
        self.summary_var = tk.StringVar(value="请选择策略")
        self.warning_var = tk.StringVar(value="")
        self.filter_vars = [tk.StringVar(value=v) for v in ("1.5", "", "3", "")]
        self.parameter_status_var = tk.StringVar(value="仅第5策略使用以上参数 · 最大值留空为无上限 · 修改后重新点击筛选按钮")
        self.current_filters = RangeFilter()
        self.search_var = tk.StringVar()
        self.market_var = tk.StringVar(value="全部市场")
        self.industry_var = tk.StringVar(value="全部行业")
        self.change_min_var, self.change_max_var = tk.StringVar(), tk.StringVar()
        self.quick_change_range = (None, None)
        self.visible_df = pd.DataFrame()
        self._quick_after = None
        self._history_windows = {}
        self.update_status_var = tk.StringVar(value="")
        self._update_check_busy = False
        self._latest_release_url = None

        # 资金TOP5只供查看，不关联股票过滤或行业成分股。
        self.fund_status_var = tk.StringVar(value="等待行情检查完成…")
        self._fund_rows: list[dict] = []
        self._fund_fetch_in_progress = False

        # 数据更新与策略扫描分离管理。
        # 启动数据更新时仍锁定操作；策略扫描时允许立即切换到另一个策略。
        self._scan_seq = 0
        self._active_scan_id = 0
        self._scan_cancel_event: Optional[threading.Event] = None
        self._scan_in_progress = False

        self._setup_styles()
        self._build_ui()
        self._set_actions_enabled(False)
        self._build_startup_splash()

        self.root.after(120, self._poll_events)
        self.root.after(250, self.start_update)

    # -------------------- UI --------------------

    def _setup_styles(self):
        # 轻量 Apple 风格：浅灰背景、白色内容区、弱边框、充足留白。
        self.root.configure(bg="#f5f5f7")

        style = ttk.Style(self.root)

        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "TFrame",
            background="#f5f5f7",
        )
        style.configure(
            "TLabel",
            background="#f5f5f7",
            foreground="#1d1d1f",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Headline.TLabel",
            background="#f5f5f7",
            foreground="#1d1d1f",
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Subtle.TLabel",
            background="#f5f5f7",
            foreground="#6e6e73",
            font=("Segoe UI", 9),
        )
        style.configure(
            "TButton",
            padding=(11, 6),
            font=("Segoe UI", 10),
        )
        style.configure('SelectedStrategy.TButton', background='#dbeafe', foreground='#074fa0',
                        padding=(11, 6), font=('Segoe UI',10,'bold'))
        style.map('SelectedStrategy.TButton', background=[('active','#c8dfff'),('disabled','#dbeafe')])
        style.map(
            "TButton",
            foreground=[
                ("disabled", "#9ca3af"),
                ("active", "#111827"),
            ],
        )
        style.configure(
            "TCheckbutton",
            background="#f5f5f7",
            foreground="#1d1d1f",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#e5e7eb",
            background="#0071e3",
            bordercolor="#e5e7eb",
            lightcolor="#0071e3",
            darkcolor="#0071e3",
        )
        style.configure("Sidebar.TFrame", background="#eff2f7")
        style.configure("Inspector.TFrame", background="#ffffff")
        style.configure("SidebarHeading.TLabel", background="#eff2f7",
                        foreground="#1d2735", font=("Segoe UI", 11, "bold"))
        style.configure("SidebarSubtle.TLabel", background="#eff2f7",
                        foreground="#748297", font=("Segoe UI", 9))
        style.configure("InspectorTitle.TLabel", background="#ffffff",
                        foreground="#1d2735", font=("Segoe UI", 13, "bold"))
        style.configure("InspectorSubtle.TLabel", background="#ffffff",
                        foreground="#758196", font=("Segoe UI", 9))
        style.configure("Nav.TButton", background="#eff2f7", foreground="#334155",
                        anchor="w", padding=(9, 9), borderwidth=0,
                        font=("Segoe UI", 10))
        style.map("Nav.TButton", background=[("active", "#e5ecf7")])
        style.configure("SelectedNav.TButton", background="#dceaff",
                        foreground="#075bbd", anchor="w",
                        padding=(9, 9), borderwidth=0,
                        font=("Segoe UI", 10, "bold"))
        style.map("SelectedNav.TButton", background=[("active", "#cce2fc")])
        style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1d1d1f",
            borderwidth=0,
            rowheight=30,
            font=("Segoe UI", 10),
        )
        style.map(
            "Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", "#111827")],
        )
        style.configure(
            "Treeview.Heading",
            background="#f5f5f7",
            foreground="#1d1d1f",
            relief="flat",
            borderwidth=0,
            padding=(8, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#eceef2")],
        )

    def _build_startup_splash(self):
        """启动流程独立可视化；主界面仅在行情完成后显示。"""
        splash = tk.Toplevel(self.root)
        self.splash_window = splash
        splash.title(f"{APP_TITLE} · 行情加载")
        splash.configure(bg="#f5f5f7")
        splash.resizable(False, False)
        width, height = 580, 490
        x = max(0, (splash.winfo_screenwidth() - width) // 2)
        y = max(0, (splash.winfo_screenheight() - height) // 2)
        splash.geometry(f"{width}x{height}+{x}+{y}")
        splash.protocol("WM_DELETE_WINDOW", self.root.destroy)

        card = tk.Frame(splash, bg="#ffffff", highlightbackground="#e5e5ea",
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)
        header = tk.Frame(card, bg="#ffffff")
        header.pack(fill="x", padx=24, pady=(21, 0))
        tk.Label(header, text="MA", bg="#0071e3", fg="#ffffff",
                 font=("Segoe UI", 13, "bold"), width=4, height=2).pack(side="left")
        text_area = tk.Frame(header, bg="#ffffff")
        text_area.pack(side="left", padx=(12, 0))
        tk.Label(text_area, text="A股 MA 扫描器", bg="#ffffff", fg="#1d1d1f",
                 font=("Segoe UI", 16, "bold"), anchor="w").pack(anchor="w")
        tk.Label(text_area, text="每日行情准备 · 完成后自动进入", bg="#ffffff",
                 fg="#8e8e93", font=("Segoe UI", 9)).pack(anchor="w")
        self.splash_elapsed_var = tk.StringVar(value="已用时 00:00")
        tk.Label(header, textvariable=self.splash_elapsed_var,
                 font=("Segoe UI", 9), bg="#ffffff", fg="#6e6e73"
                 ).pack(side="right", anchor="n")

        heading = tk.Frame(card, bg="#ffffff")
        heading.pack(fill="x", padx=24, pady=(22, 6))
        self.splash_stage_var = tk.StringVar(value="准备连接行情")
        tk.Label(heading, textvariable=self.splash_stage_var,
                 font=("Segoe UI", 13, "bold"), bg="#ffffff", fg="#1d1d1f"
                 ).pack(side="left")
        self.splash_step_var = tk.StringVar(value="第 1 / 8 阶段")
        tk.Label(heading, textvariable=self.splash_step_var,
                 bg="#ffffff", fg="#8e8e93",
                 font=("Segoe UI", 9)).pack(side="right")

        self.splash_message_var = tk.StringVar(value="正在检查本地行情…")
        tk.Label(card, textvariable=self.splash_message_var, bg="#ffffff",
                 fg="#6e6e73", font=("Segoe UI", 10), anchor="w",
                 justify="left", wraplength=490).pack(
                     fill="x", padx=24, pady=(0, 11))
        self.splash_count_var = tk.StringVar(value="正在准备")
        tk.Label(card, textvariable=self.splash_count_var, bg="#ffffff",
                 fg="#1d1d1f", font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", padx=24)

        self.splash_stage_progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(card, mode="determinate", maximum=100,
                        variable=self.splash_stage_progress_var).pack(
                            fill="x", padx=24, pady=(6, 14))

        overall_line = tk.Frame(card, bg="#ffffff")
        overall_line.pack(fill="x", padx=24)
        tk.Label(overall_line, text="总体流程进度", bg="#ffffff",
                 fg="#6e6e73", font=("Segoe UI", 9)).pack(side="left")
        self.splash_percent_label = tk.Label(
            overall_line, text="0%", bg="#ffffff", fg="#0071e3",
            font=("Segoe UI", 10, "bold"))
        self.splash_percent_label.pack(side="right")
        ttk.Progressbar(card, mode="determinate", maximum=100,
                        variable=self.progress_var).pack(
                            fill="x", padx=24, pady=(5, 5))
        tk.Label(card, text="百分比表示流程步骤，不代表剩余时间",
                 bg="#ffffff", fg="#a1a1a6",
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=24)

        divider = tk.Frame(card, bg="#e5e5ea", height=1)
        divider.pack(fill="x", padx=24, pady=(17, 11))
        tk.Label(card, text="更新步骤", bg="#ffffff", fg="#6e6e73",
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=24)
        phase_frame = tk.Frame(card, bg="#ffffff")
        phase_frame.pack(fill="x", padx=24, pady=(5, 11))
        self.splash_phase_labels = []
        for idx, (title, _, _) in enumerate(UPDATE_PHASES):
            label = tk.Label(phase_frame, text=f"○  {title}",
                             anchor="w", bg="#ffffff", fg="#9898a0",
                             font=("Segoe UI", 9))
            label.grid(row=idx % 4, column=idx // 4, sticky="w", pady=4)
            self.splash_phase_labels.append(label)
        phase_frame.grid_columnconfigure(0, weight=1)
        phase_frame.grid_columnconfigure(1, weight=1)

        footer = tk.Frame(card, bg="#ffffff")
        footer.pack(fill="x", padx=24, pady=(2, 17))
        self.splash_phase_var = tk.StringVar(value="更新完成后自动进入扫描器")
        tk.Label(footer, textvariable=self.splash_phase_var,
                 fg="#8e8e93", bg="#ffffff",
                 font=("Segoe UI", 9), wraplength=280,
                 justify="left").pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="退出", command=self.root.destroy).pack(side="right")
        self.splash_retry_button = ttk.Button(
            footer, text="重试更新", command=self.start_update)
        self.splash_retry_button.pack(side="right", padx=(0, 8))
        self.splash_retry_button.pack_forget()
        self._update_splash_progress(0, "准备检查数据")
        self.root.after(1000, self._tick_splash_clock)

    def _tick_splash_clock(self):
        if not self._startup_loading or not self.splash_window:
            return
        elapsed = max(0, int(time.monotonic() - self._startup_started_at))
        minutes, seconds = divmod(elapsed, 60)
        self.splash_elapsed_var.set(f"已用时 {minutes:02d}:{seconds:02d}")
        self.root.after(1000, self._tick_splash_clock)

    def _update_splash_progress(self, percent: float, task: str):
        if not self._startup_loading or self.splash_window is None:
            return
        info = describe_update_progress(percent, task)
        index = info["phase"]
        self.splash_step_var.set(f"第 {index + 1} / {len(UPDATE_PHASES)} 阶段")
        self.splash_stage_var.set(info["title"])
        self.splash_message_var.set(info["task"])
        self.splash_percent_label.configure(text=f'{info["overall"]:.0f}%')
        self.splash_stage_progress_var.set(info["fraction"] * 100)
        if info["total"] is not None:
            self.splash_count_var.set(
                f'已处理 {info["completed"]:,} / {info["total"]:,} 只'
                + (f' · 当前 {info["stock"]}' if info["stock"] else ""))
        elif info["fraction"] >= 1:
            self.splash_count_var.set("该阶段已完成")
        else:
            self.splash_count_var.set("正在检查，请稍候…")
        for i, label in enumerate(self.splash_phase_labels):
            if i < index:
                symbol, color = "✓", "#159b79"
            elif i == index:
                symbol, color = "●", "#0071e3"
            else:
                symbol, color = "○", "#9898a0"
            label.configure(text=f"{symbol}  {UPDATE_PHASES[i][0]}", fg=color,
                            font=("Segoe UI", 9, "bold" if i == index else "normal"))

    def _enter_scanner(self):
        """行情更新成功后关闭加载窗口，显示完整主窗口。"""
        if not self._startup_loading:
            return
        self._startup_loading = False
        if self.splash_window is not None and self.splash_window.winfo_exists():
            self.splash_window.destroy()
        self.splash_window = None
        self.root.deiconify()
        self.root.lift()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.workspace = ttk.Frame(self.root, style="TFrame")
        self.workspace.grid(row=1, column=0, sticky="nsew")
        self.workspace.rowconfigure(0, weight=1)
        self.workspace.columnconfigure(0, weight=0, minsize=168)
        self.workspace.columnconfigure(1, weight=1)
        self.workspace.columnconfigure(2, weight=0, minsize=242)
        self.center_panel = ttk.Frame(self.workspace)
        self.center_panel.grid(row=0, column=1, sticky="nsew")
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(4, weight=1)
        self.inspector_panel = ttk.Frame(self.workspace, style="Inspector.TFrame",
                                         padding=(13, 16, 13, 13))
        self.inspector_panel.grid(row=0, column=2, sticky="nsew")
        self.workspace_separator = ttk.Separator(self.workspace, orient="vertical")
        # 从左到右依次为策略导航、选股列表、走势图详情；不创建第二个弹窗做详情。

        top = ttk.Frame(self.root, padding=(16, 10, 16, 2))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        status_left = ttk.Frame(top)
        status_left.grid(row=0, column=0, sticky="w")
        ttk.Label(status_left, text="A股 MA 扫描器",
                  style="Headline.TLabel",
                  font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 18))
        ttk.Label(status_left, textvariable=self.date_var,
                  style="Subtle.TLabel").pack(side="left", padx=(0, 12))
        ttk.Label(status_left, textvariable=self.complete_var,
                  style="Subtle.TLabel").pack(side="left")

        update_controls = ttk.Frame(top)
        update_controls.grid(row=0, column=1, sticky="e")
        ttk.Label(update_controls, textvariable=self.update_status_var,
                  style="Subtle.TLabel").pack(side="left", padx=(0, 8))
        self.update_check_button = ttk.Button(update_controls, text="检查更新",
                                              command=self._start_update_check)
        self.update_check_button.pack(side="left")
        self.update_download_button = ttk.Button(update_controls, text="查看新版本",
                                                 command=self._open_latest_release)
        self.update_download_button.pack(side="left", padx=(8, 0))
        self.update_download_button.pack_forget()

        progress_box = ttk.Frame(
            self.center_panel,
            padding=(16, 4, 16, 6),
        )
        progress_box.grid(row=0, column=0, sticky="ew")
        self.progress_box=progress_box
        progress_box.columnconfigure(0, weight=1)

        task_line = ttk.Frame(progress_box)
        task_line.grid(row=0, column=0, sticky="ew")
        task_line.columnconfigure(0, weight=1)

        ttk.Label(
            task_line,
            textvariable=self.task_var,
        ).grid(row=0, column=0, sticky="w")

        self.progress_percent_label = ttk.Label(
            task_line,
            text="0%",
            width=6,
            anchor="e",
        )
        self.progress_percent_label.grid(
            row=0,
            column=1,
            sticky="e",
        )

        # 网络或SQLite权限故障后不用退出软件，可原地重试更新。
        self.retry_button = ttk.Button(
            task_line, text="重试更新", command=self.start_update,
        )
        self.retry_button.grid(row=0, column=2, padx=(12, 0))
        self.retry_button.grid_remove()

        self.progress = ttk.Progressbar(
            progress_box,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(5, 0),
        )

        action_box = ttk.Frame(
            self.workspace, style="Sidebar.TFrame",
            padding=(9, 16, 9, 12),
        )
        action_box.grid(row=0, column=0, sticky="nsew")
        ttk.Label(action_box, text="选股策略", style="SidebarHeading.TLabel"
                  ).pack(anchor="w", padx=6, pady=(1, 9))

        button_row = ttk.Frame(action_box, style="Sidebar.TFrame")
        button_row.pack(fill="x")
        self.strategy_buttons = []
        self.strategy_button_by_key = {}
        entries = list(self.STRATEGIES.items())
        for heading, ids in (("均线突破", (0, 1, 2)),
                             ("趋势信号", (3, 5, 6)),
                             ("量价分析", (4,))):
            ttk.Label(button_row, text=heading, style="SidebarSubtle.TLabel"
                      ).pack(fill="x", padx=6, pady=(10, 3))
            for i in ids:
                label, strategy_key = entries[i]
                btn = ttk.Button(
                    button_row, text=label, style="Nav.TButton",
                    command=lambda k=strategy_key, l=label: self.start_scan(k, l),
                )
                btn.pack(fill="x", pady=2)
                self.strategy_buttons.append(btn)
                self.strategy_button_by_key[strategy_key] = btn

        self.parameter_row = ttk.Frame(action_box)
        parameter_row = self.parameter_row
        parameter_row.pack(fill="x", pady=(4, 2))
        self.filter_entries = []
        for label, variable in zip(("放量下限", "放量上限", "换手率下限%", "换手率上限%"), self.filter_vars):
            line = ttk.Frame(parameter_row, style="Sidebar.TFrame")
            line.pack(fill="x", pady=3)
            ttk.Label(line, text=label, style="SidebarSubtle.TLabel"
                      ).pack(side="left")
            entry = ttk.Entry(line, textvariable=variable, width=6)
            entry.pack(side="right")
            self.filter_entries.append(entry)
        self.parameter_help = ttk.Label(action_box, textvariable=self.parameter_status_var,
                                       style="Subtle.TLabel")
        self.parameter_help.pack(anchor="w", pady=(2, 0))
        self.parameter_row.pack_forget()
        self.parameter_help.pack_forget()

        info_box = ttk.Frame(
            self.center_panel,
            padding=(16, 3, 16, 6),
        )
        info_box.grid(row=2, column=0, sticky="ew")
        info_box.columnconfigure(0, weight=1)

        ttk.Label(
            info_box,
            textvariable=self.summary_var,
            style="Headline.TLabel",
        ).grid(row=0, column=0, sticky="w")

        self.warning_label = ttk.Label(
            info_box,
            textvariable=self.warning_var,
            style="Subtle.TLabel",
        )
        self.warning_label.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(3, 0),
        )

        quick_box = ttk.Frame(info_box)
        quick_box.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        quick_row = ttk.Frame(quick_box)
        quick_row.pack(fill="x")
        ttk.Label(quick_row, text="搜索").pack(side="left")
        ttk.Entry(quick_row, textvariable=self.search_var, width=15
                  ).pack(side="left", fill="x", expand=True, padx=(5, 7))
        self.market_combo = ttk.Combobox(quick_row, textvariable=self.market_var, width=9,
                                        state="readonly",
                                        values=("全部市场", "主板", "创业板", "科创板"))
        self.market_combo.pack(side="left", padx=(0, 6))
        self.industry_combo = ttk.Combobox(quick_row, textvariable=self.industry_var,
                                          width=13, state="readonly",
                                          values=("全部行业",))
        self.industry_combo.pack(side="left")
        range_row = ttk.Frame(quick_box)
        range_row.pack(fill="x", pady=(4, 0))
        ttk.Label(range_row, text="涨幅范围%").pack(side="left")
        for variable in (self.change_min_var, self.change_max_var):
            ttk.Entry(range_row, textvariable=variable, width=7
                      ).pack(side="left", padx=(6, 3))
        ttk.Button(range_row, text="重置筛选",
                   command=self._reset_quick_filters).pack(side="right")
        for variable in (self.search_var, self.market_var, self.industry_var,
                         self.change_min_var, self.change_max_var):
            variable.trace_add("write", self._schedule_quick_filter)
        tools_row = ttk.Frame(quick_box)
        tools_row.pack(fill="x", pady=(5, 0))
        self.history_button = ttk.Button(tools_row, text="信号历史", command=self._open_selected_history)
        self.history_button.pack(side="left")
        ttk.Label(tools_row, text="双击查看走势 · 右键查看操作",
                  style="Subtle.TLabel").pack(side="left", padx=(8, 0))

        # 资金榜单是高度固定的小模块，不影响个股表的自适应高度。
        self.fund_box = ttk.Frame(self.center_panel, padding=(12, 7, 12, 5))
        self.fund_box.grid(row=1, column=0, sticky="ew")
        self.fund_box.columnconfigure(0, weight=1)
        fund_heading = ttk.Frame(self.fund_box)
        fund_heading.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        fund_heading.columnconfigure(0, weight=1)
        ttk.Label(fund_heading, text="近5日 · 行业资金净流入 TOP5",
                  style="Headline.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(fund_heading, textvariable=self.fund_status_var,
                  style="Subtle.TLabel").grid(row=0, column=1, sticky="e", padx=(8, 10))
        self.fund_refresh_button = ttk.Button(fund_heading, text="刷新", command=lambda: self._start_fund_refresh(True))
        self.fund_refresh_button.grid(row=0, column=3, sticky="e", padx=(10, 0))

        self.fund_cards_frame = tk.Frame(self.fund_box, bg="#f5f5f7")
        self.fund_cards_frame.grid(row=1, column=0, sticky="ew")
        self._fund_card_labels = []
        for idx in range(5):
            self.fund_cards_frame.grid_columnconfigure(idx, weight=1, uniform="fund", minsize=82)
            tile = tk.Frame(self.fund_cards_frame, bg="#ffffff", highlightbackground="#e5e5ea",
                            highlightcolor="#e5e5ea", highlightthickness=1)
            tile.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 4, 0 if idx == 4 else 4))
            lbl = tk.Label(tile, bg="#ffffff", fg="#6e6e73", anchor="w",
                           font=("Segoe UI", 9), text=f"#{idx+1}  等待数据")
            lbl.pack(fill="x", padx=10, pady=(5,0))
            val = tk.Label(tile, bg="#ffffff", fg="#6e6e73", anchor="w",
                           font=("Segoe UI", 12, "bold"), text="—")
            val.pack(fill="x", padx=10, pady=(0,5))
            self._fund_card_labels.append((lbl, val))

        # 五个策略共用：板块与板块自身信号视图。
        # 不是额外下拉框，而是在结果上方直接列出触发板块。
        self.sector_box = ttk.Frame(
            self.center_panel,
            padding=(16, 1, 16, 3),
        )
        self.sector_box.grid(
            row=3,
            column=0,
            sticky="ew",
        )
        self.sector_box.columnconfigure(0, weight=1)

        sector_head = ttk.Frame(self.sector_box)
        sector_head.grid(row=0, column=0, sticky="ew")
        sector_head.columnconfigure(0, weight=1)

        self.sector_title_var = tk.StringVar(value="板块信号 · 今日")

        ttk.Label(
            sector_head,
            textvariable=self.sector_title_var,
            style="Headline.TLabel",
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            sector_head,
            text="单击过滤，双击看走势及历史",
            style="Subtle.TLabel",
        ).grid(row=0, column=1, sticky="e")
        self.sector_expanded = False
        self.sector_toggle_button = ttk.Button(
            sector_head, text="展开板块", command=self._toggle_sector_table)
        self.sector_toggle_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

        self.sector_tree = ttk.Treeview(
            self.sector_box,
            columns=(
                "板块",
                "今日触发",
                "板块信号",
            ),
            show="headings",
            height=3,
            selectmode="browse",
        )
        self.sector_tree.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(5, 0),
        )
        self.sector_tree.grid_remove()

        sector_widths = {
            "板块": 220,
            "今日触发": 105,
            "板块信号": 140,
        }

        for col in self.sector_tree["columns"]:
            self.sector_tree.heading(col, text=col)
            self.sector_tree.column(
                col,
                width=sector_widths.get(col, 90),
                minwidth=60,
                anchor="w" if col == "板块" else "center",
                stretch=True,
            )

        self.sector_tree.tag_configure(
            "signal_breakout",
            foreground="#d11a2a",
        )
        self.sector_tree.tag_configure(
            "signal_no_breakout",
            foreground="#16a34a",
        )
        self.sector_tree.tag_configure(
            "signal_neutral",
            foreground="#6b7280",
        )

        self.sector_tree.bind(
            "<<TreeviewSelect>>",
            self._on_sector_select,
        )
        self.sector_tree.bind(
            "<Double-1>",
            self._open_selected_sector_chart,
        )

        # 启动时先隐藏；选择任一策略后显示。
        self.sector_box.grid_remove()

        table_box = ttk.Frame(
            self.center_panel,
            padding=(16, 0, 16, 16),
        )
        table_box.grid(
            row=4,
            column=0,
            sticky="nsew",
        )
        table_box.columnconfigure(0, weight=1)
        table_box.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_box,
            show="headings",
            selectmode="browse",
        )
        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        yscroll = ttk.Scrollbar(
            table_box,
            orient="vertical",
            command=self.tree.yview,
        )
        yscroll.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        xscroll = ttk.Scrollbar(
            table_box,
            orient="horizontal",
            command=self.tree.xview,
        )
        xscroll.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        self.tree.configure(
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set,
        )

        self.tree.bind(
            "<Double-1>",
            self._open_selected_chart,
        )

        self.result_menu = tk.Menu(self.root, tearoff=False)
        self.result_menu.add_command(label="信号历史", command=self._open_selected_history)
        self.result_menu.add_command(label="走势图", command=self._open_selected_chart)
        self.tree.bind("<Button-3>", self._result_context_menu)
        self.tree.bind("<Control-Button-1>", self._result_context_menu)
        self.tree.bind("<<TreeviewSelect>>", self._on_stock_selection)
        self._build_stock_inspector()
        attach_sector_tip(self.tree)
        attach_sector_tip(self.sector_tree)

    def _build_stock_inspector(self):
        """右侧真实股票信息面板，与实际 Treeview 选择和本地日线数据联动。"""
        side = self.inspector_panel
        self._inspector_seq = 0
        self._inspector_frame = pd.DataFrame()
        self._inspector_signal_date = None
        ttk.Label(side, text="股票详情", style="InspectorSubtle.TLabel"
                  ).pack(fill="x")
        self.inspector_name_var = tk.StringVar(value="请选择股票")
        self.inspector_code_var = tk.StringVar(value="选择列表行即可查看走势图")
        self.inspector_price_var = tk.StringVar(value="—")
        self.inspector_change_var = tk.StringVar(value="")
        ttk.Label(side, textvariable=self.inspector_name_var,
                  style="InspectorTitle.TLabel", wraplength=220,
                  ).pack(fill="x", pady=(10, 2))
        ttk.Label(side, textvariable=self.inspector_code_var,
                  style="InspectorSubtle.TLabel", wraplength=220,
                  ).pack(fill="x")
        tk.Label(side, textvariable=self.inspector_price_var,
                 font=("Segoe UI", 22, "bold"), bg="#ffffff",
                 fg="#1d2735", anchor="w").pack(fill="x", pady=(16, 2))
        tk.Label(side, textvariable=self.inspector_change_var,
                 font=("Segoe UI", 11, "bold"), bg="#ffffff",
                 fg="#dc4b5a", anchor="w").pack(fill="x")

        ttk.Separator(side).pack(fill="x", pady=(14, 10))
        ttk.Label(side, text="最近 30 个有效交易日",
                  style="InspectorSubtle.TLabel").pack(fill="x")
        self.inspector_chart = tk.Canvas(side, height=215, bg="#ffffff",
                                         highlightthickness=0)
        self.inspector_chart.pack(fill="x", pady=(7, 4))
        self.inspector_chart.bind("<Configure>", self._redraw_inspector_chart)
        legend = ttk.Frame(side, style="Inspector.TFrame")
        legend.pack(fill="x", pady=(0, 17))
        for title, color in (("● 收盘", "#1d2735"), ("● MA5", "#2f6fed"),
                             ("● MA10", "#d17b00"), ("● MA20", "#7b4ab5")):
            tk.Label(legend, text=title, fg=color, bg="#ffffff",
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
        ttk.Label(side, text="策略指标", style="InspectorTitle.TLabel"
                  ).pack(fill="x", pady=(0, 9))
        self.inspector_metric_vars = []
        for title in ("放量倍数", "换手率", "触发日"):
            metric = tk.StringVar(value="—")
            line = ttk.Frame(side, style="Inspector.TFrame")
            line.pack(fill="x", pady=5)
            tk.Label(line, text=title, bg="#ffffff", fg="#758196",
                     font=("Segoe UI", 10)).pack(side="left")
            tk.Label(line, textvariable=metric, bg="#ffffff", fg="#1d2735",
                     font=("Segoe UI", 10, "bold")).pack(side="right")
            self.inspector_metric_vars.append(metric)
        ttk.Separator(side).pack(fill="x", pady=(14, 11))
        ttk.Button(side, text="查看完整走势图", command=self._open_selected_chart
                   ).pack(fill="x", pady=(0, 7))
        ttk.Button(side, text="信号历史", command=self._open_selected_history
                   ).pack(fill="x")
        self.inspector_status_var = tk.StringVar(value="数据来自本地 SQLite")
        ttk.Label(side, textvariable=self.inspector_status_var,
                  style="InspectorSubtle.TLabel", wraplength=220
                  ).pack(fill="x", pady=(13, 0))

    def _on_stock_selection(self, _event=None):
        """用户换股后异步查询本地走势图，避免阻塞列表滚动和策略切换。"""
        selected = self.tree.selection()
        self._inspector_seq += 1
        token = self._inspector_seq
        self._inspector_frame = pd.DataFrame()
        if not selected:
            self.inspector_name_var.set("请选择股票")
            self.inspector_code_var.set("选择列表行即可查看走势图")
            self.inspector_price_var.set("—")
            self.inspector_change_var.set("")
            for var in self.inspector_metric_vars:
                var.set("—")
            self.inspector_status_var.set("数据来自本地 SQLite")
            self._redraw_inspector_chart()
            return
        iid = selected[0]
        tags = self.tree.item(iid, "tags")
        if not tags:
            return
        code_full = str(tags[0])
        name = str(self.tree.set(iid, "名称"))
        code = str(self.tree.set(iid, "代码"))
        trigger_date = str(self.tree.set(iid, "触发日"))
        price = str(self.tree.set(iid, "收盘价"))
        change = str(self.tree.set(iid, "当日涨幅%"))
        volume = str(self.tree.set(iid, "放量倍数"))
        turnover = str(self.tree.set(iid, "换手率%"))
        self.inspector_name_var.set(name)
        self.inspector_code_var.set(f"{code} · {self.tree.set(iid, '板块')}")
        self.inspector_price_var.set(price)
        self.inspector_change_var.set(f"涨幅 {change}%")
        for var, value in zip(self.inspector_metric_vars,
                              (f"{volume}×", f"{turnover}%", trigger_date)):
            var.set(value)
        self._inspector_signal_date = trigger_date
        self.inspector_status_var.set("正在读取本地走势图…")
        self._redraw_inspector_chart()
        end = self.update_result.scan_date if self.update_result else trigger_date

        def worker():
            try:
                data = self.backend.get_chart_data(code_full, end)
                self.events.put(("inspector_done", token, data, ""))
            except Exception as exc:
                self.events.put(("inspector_done", token, pd.DataFrame(), str(exc)))
        threading.Thread(target=worker, name="stock-inspector",
                         daemon=True).start()

    def _handle_inspector_done(self, token, data, error):
        if token != self._inspector_seq:
            return
        self._inspector_frame = data
        self.inspector_status_var.set(
            f"走势图读取失败：{error[:90]}" if error else
            ("本地暂无可绘制行情" if data.empty else "价格与均线 · 本地行情"))
        self._redraw_inspector_chart()

    def _redraw_inspector_chart(self, _event=None):
        if not hasattr(self, "inspector_chart"):
            return
        canvas = self.inspector_chart
        if self._inspector_frame.empty:
            canvas.delete("all")
            canvas.create_text(max(canvas.winfo_width(), 220)/2, 100,
                               text="选择股票查看走势图", fill="#9ca3af",
                               font=("Segoe UI", 9))
            return
        self._draw_series_chart(
            canvas, self._inspector_frame,
            {"close": "#1d2735", "MA5": "#2f6fed",
             "MA10": "#d17b00", "MA20": "#7b4ab5"},
            signal_date=self._inspector_signal_date,
        )

    def _refresh_strategy_selection(self):
        for key, btn in self.strategy_button_by_key.items():
            btn.configure(style='SelectedNav.TButton' if key == self.current_strategy_key else 'Nav.TButton')
        if self.current_strategy_key == 'volume_turnover':
            self.parameter_row.pack(fill='x', pady=(4,2))
            self.parameter_help.pack(anchor='w', pady=(2,0))
        else:
            self.parameter_row.pack_forget()
            self.parameter_help.pack_forget()

    def _set_actions_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"

        for btn in self.strategy_buttons:
            btn.configure(state=state)

        for entry in self.filter_entries:
            entry.configure(state=state)
        for button in (self.history_button,):
            button.configure(state=state)

        self.fund_refresh_button.configure(
            state="normal" if enabled and not self._fund_fetch_in_progress else "disabled")

    def _set_progress(self, percent: float, task: str):
        value = max(0.0, min(100.0, float(percent)))
        self.progress_var.set(value)
        self.progress_percent_label.configure(
            text=f"{value:.0f}%"
        )
        self.task_var.set(task)
        if self._startup_loading and self.splash_window is not None:
            self._update_splash_progress(value, task)

    # -------------------- GitHub 版本检查（不干扰行情任务） --------------------

    def _start_update_check(self):
        if self._update_check_busy:
            return
        self._update_check_busy = True
        self.update_check_button.configure(state="disabled")
        self.update_status_var.set("正在检查…")
        def worker():
            try:
                status, url = fetch_latest_release()
            except Exception as exc:
                status, url = f"检查失败：{exc}", None
            self.events.put(("version_check_done", status, url))
        threading.Thread(target=worker, name="github-release-check", daemon=True).start()

    def _open_latest_release(self):
        if self._latest_release_url:
            webbrowser.open(self._latest_release_url)

    # -------------------- 线程/事件 --------------------

    def start_update(self):
        if getattr(self, "_busy", False) or self._scan_in_progress:
            return

        self.retry_button.grid_remove()
        self._busy = True
        if self._startup_loading and self.splash_window is not None:
            self._startup_started_at = time.monotonic()
            self.splash_elapsed_var.set("已用时 00:00")
            self.splash_retry_button.pack_forget()
            self.splash_phase_var.set("更新完成后会自动进入扫描器")
        self._set_actions_enabled(False)
        self.progress_box.grid()
        self._set_progress(0, "开始检查数据")
        self.summary_var.set("正在检查并更新数据…")
        self.warning_var.set("")

        thread = threading.Thread(
            target=self._update_worker,
            daemon=True,
        )
        thread.start()

    def _update_worker(self):
        try:
            def cb(percent, task):
                self.events.put(
                    ("progress", float(percent), str(task))
                )

            result = self.backend.update_all(cb)
            self.events.put(("update_done", result))

        except Exception as exc:
            self.events.put((
                "error",
                f"{type(exc).__name__}: {exc}",
                traceback.format_exc(),
            ))

    def _read_filters(self) -> RangeFilter:
        values = [v.get().strip() for v in self.filter_vars]
        try:
            return RangeFilter(float(values[0]), float(values[1]) if values[1] else None,
                               float(values[2]), float(values[3]) if values[3] else None)
        except (ValueError, OverflowError) as exc:
            raise ValueError("请填写有效的最小值和最大值；最小值不能留空。" + str(exc)) from exc

    def start_scan(
        self,
        strategy_key: str,
        strategy_label: str,
    ):
        # _busy 只代表启动数据更新等不可并行任务。
        if getattr(self, "_busy", False):
            return

        if not self.update_result:
            return

        filters = None
        if strategy_key == "volume_turnover":
            try:
                filters = self._read_filters()
            except ValueError as exc:
                messagebox.showerror(APP_TITLE, str(exc))
                return
            self.current_filters = filters

        # 用户在旧策略尚未算完时点击新策略：取消旧扫描，立即启动最新请求。
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()

        self._scan_seq += 1
        scan_id = self._scan_seq
        self._active_scan_id = scan_id
        cancel_event = threading.Event()
        self._scan_cancel_event = cancel_event
        self._scan_in_progress = True

        # 切换策略时绝不能继续显示上一个策略的板块选择和个股结果。
        self.current_strategy_key = strategy_key
        self.current_strategy_label = strategy_label
        self._refresh_strategy_selection()
        self.current_sector_filter = None
        self.current_df = pd.DataFrame()
        self.visible_df = pd.DataFrame()
        self.current_sort_column = None
        self.current_sort_reverse = False

        self.sector_tree.delete(*self.sector_tree.get_children())
        self.sector_box.grid_remove()
        self._populate_tree(strategy_key, pd.DataFrame())

        self.progress_box.grid()
        self._set_progress(
            0,
            f"计算 {strategy_label}",
        )
        self.summary_var.set(
            f"正在计算：{strategy_label}"
        )

        # 策略扫描期间保持策略按钮和第5策略参数可编辑。
        # 新点击会取消旧扫描，以最后一次点击为准。
        self._set_actions_enabled(True)

        include_previous = False  # 个股结果始终只展示最新市场交易日。

        thread = threading.Thread(
            target=self._scan_worker,
            args=(
                scan_id,
                cancel_event,
                strategy_key,
                strategy_label,
                include_previous,
                filters,
            ),
            daemon=True,
        )
        thread.start()

    def _scan_worker(
        self,
        scan_id: int,
        cancel_event: threading.Event,
        strategy_key: str,
        strategy_label: str,
        include_previous: bool,
        filters: Optional[RangeFilter] = None,
    ):
        try:
            self.events.put(
                ("scan_progress", scan_id, 20.0, f"读取本地行情 · {strategy_label}")
            )

            df = self.backend.scan_strategy(
                strategy=strategy_key,
                target_date=self.update_result.scan_date,
                include_previous=include_previous,
                previous_trade_date=(
                    self.update_result.previous_trade_date
                ),
                filters=filters,
                cancel_event=cancel_event,
            )

            if cancel_event.is_set():
                return

            self.events.put(
                ("scan_progress", scan_id, 90.0, "整理结果")
            )
            self.events.put((
                "scan_done",
                scan_id,
                strategy_key,
                strategy_label,
                include_previous,
                df,
            ))

        except Exception as exc:
            if cancel_event.is_set():
                return
            self.events.put((
                "scan_error",
                scan_id,
                f"{type(exc).__name__}: {exc}",
                traceback.format_exc(),
            ))

    def _poll_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            try:
                kind = event[0]

                if kind == "version_check_done":
                    _, status, url = event
                    self._update_check_busy = False
                    self._latest_release_url = url
                    self.update_status_var.set(status)
                    self.update_check_button.configure(state="normal")
                    if url:
                        self.update_download_button.pack(side="left", padx=(8, 0))
                    else:
                        self.update_download_button.pack_forget()

                elif kind == "progress":
                    _, percent, task = event
                    self._set_progress(
                        percent,
                        task,
                    )

                elif kind == "scan_progress":
                    _, scan_id, percent, task = event
                    if scan_id == self._active_scan_id:
                        self._set_progress(percent, task)

                elif kind == "update_done":
                    _, result = event
                    self._handle_update_done(result)

                elif kind == "scan_done":
                    (
                        _,
                        scan_id,
                        strategy_key,
                        strategy_label,
                        include_previous,
                        df,
                    ) = event
                    if scan_id == self._active_scan_id:
                        self._scan_in_progress = False
                        self._scan_cancel_event = None
                        self._handle_scan_done(
                            strategy_key,
                            strategy_label,
                            include_previous,
                            df,
                        )

                elif kind == "fund_progress":
                    _, progress_message = event
                    if self._fund_fetch_in_progress:
                        self.fund_status_var.set(progress_message)

                elif kind == "fund_done":
                    _, message = event
                    self._fund_fetch_in_progress = False
                    self._display_fund_top5(message)

                elif kind == "inspector_done":
                    _, token, data, error = event
                    self._handle_inspector_done(token, data, error)

                elif kind == "history_done":
                    _, token, frame, error = event
                    callback = self._history_windows.pop(token, None)
                    if callback:
                        callback(frame, error)

                elif kind == "scan_error":
                    _, scan_id, message, details = event
                    if scan_id == self._active_scan_id:
                        self._scan_in_progress = False
                        self._scan_cancel_event = None
                        self._handle_error(
                            message,
                            details,
                        )

                elif kind == "error":
                    _, message, details = event
                    self._handle_error(
                        message,
                        details,
                    )

            except Exception as exc:
                # GUI事件处理自身出错也不能中断 after 轮询，否则界面会永久卡死。
                self._scan_in_progress = False
                self._scan_cancel_event = None
                self._busy = False
                self._set_actions_enabled(
                    self.update_result is not None
                )
                details = traceback.format_exc()
                self.warning_var.set(
                    f"{type(exc).__name__}: {exc}"
                )
                try:
                    messagebox.showerror(
                        APP_TITLE,
                        f"界面处理错误：{type(exc).__name__}: {exc}",
                    )
                except Exception:
                    pass
                print(details)

        self.root.after(
            120,
            self._poll_events,
        )

    # -------------------- 完成/错误 --------------------

    def _handle_update_done(
        self,
        result: UpdateResult,
    ):
        self.retry_button.grid_remove()
        self.update_result = result
        self._busy = False

        self.date_var.set(
            f"数据日期：{result.scan_date}"
        )
        self.complete_var.set(
            f"完整率：{result.completeness:.2f}% "
            f"({result.saved}/{result.expected})"
        )

        self._set_progress(
            100,
            "数据检查完成",
        )
        self.progress_box.grid_remove()

        if result.warning:
            self.warning_var.set(
                result.warning
            )
        else:
            self.warning_var.set("")

        self.summary_var.set(
            "数据已就绪，请选择策略"
        )
        self._set_actions_enabled(True)
        self._enter_scanner()
        # 独立线程获取资金TOP5，行情完成即可使用全部策略。
        self._display_fund_top5("")
        self._start_fund_refresh(False)

    def _handle_scan_done(
        self,
        strategy_key: str,
        strategy_label: str,
        include_previous: bool,
        df: pd.DataFrame,
    ):
        self._scan_in_progress = False
        self.current_df = df.copy()
        self.current_sort_column = None
        self.current_sort_reverse = False

        self.current_sector_filter = None

        self.sector_title_var.set(f"板块信号 · 今日 · {strategy_label}")
        self._populate_sector_tree(df)
        self.sector_box.grid()

        self._populate_tree(
            strategy_key,
            df,
        )

        suffix = (
            "（含昨日触发）"
            if include_previous
            else ""
        )

        self.summary_var.set(
            f"{strategy_label}{suffix} · 命中 {len(df)} 只"
        )

        self._set_progress(
            100,
            f"{strategy_label} 计算完成",
        )
        self.progress_box.grid_remove()
        self._set_actions_enabled(True)
        industries = sorted(df["板块"].dropna().astype(str).unique()) if not df.empty else []
        self.industry_combo.configure(values=["全部行业"] + industries)
        if self.industry_var.get() not in ["全部行业"] + industries:
            self.industry_var.set("全部行业")
        self._apply_quick_filters(silent=True)

    def _handle_error(
        self,
        message: str,
        details: str,
    ):
        was_update_error = bool(self._busy)
        self._busy = False
        if was_update_error:
            self.retry_button.grid()
        self._scan_in_progress = False
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        self._scan_cancel_event = None
        self._set_actions_enabled(
            self.update_result is not None
        )

        self._set_progress(self.progress_var.get(), "发生错误")
        self.progress_box.grid_remove()
        self.warning_var.set("操作失败：" + message[:240])
        if was_update_error and self._startup_loading and self.splash_window is not None:
            self.splash_phase_var.set("启动行情更新失败 · 可以重试或退出")
            self.splash_message_var.set(message[:180])
            self.splash_count_var.set("当前任务未完成，保留已保存的本地行情")
            self.splash_retry_button.pack(side="right", padx=(0, 8))
        # 报错详情保存至data文件夹；权限受限时回退终端，不影响GUI。
        try:
            log_file = DATA_DIR / "scanner_error.log"
            with log_file.open("a", encoding="utf-8") as log:
                log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {message}\n{details}\n")
        except OSError:
            print(details)

    # -------------------- 表格 --------------------

    def _columns_for_strategy(
        self,
        strategy_key: str,
    ) -> list[str]:
        if strategy_key == "volume_turnover":
            return ["代码", "名称", "板块", "触发日", "收盘价", "当日涨幅%", "放量倍数", "换手率%"]
        if strategy_key == "ma5_turn_up":
            return [
                "代码", "名称", "板块", "触发日", "收盘价", "当日涨幅%",
                "MA5", "昨日MA5", "MA5上拐幅度%", "放量倍数", "换手率%",
            ]
        if strategy_key == "ma_convergence_up":
            return [
                "代码", "名称", "板块", "触发日", "收盘价", "当日涨幅%",
                "MA5", "MA10", "MA20", "昨日粘合度%", "今日发散度%",
                "发散增加百分点", "放量倍数", "换手率%",
            ]
        if strategy_key.startswith("breakout_ma"):
            ma_n = int(
                strategy_key.replace(
                    "breakout_ma",
                    "",
                )
            )
            return [
                "代码",
                "名称",
                "板块",
                "触发日",
                "收盘价",
                "当日涨幅%",
                f"MA{ma_n}",
                f"突破MA{ma_n}幅度%",
                "放量倍数",
                "换手率%",
            ]

        return [
            "代码",
            "名称",
            "板块",
            "触发日",
            "收盘价",
            "当日涨幅%",
            "MA5",
            "MA10",
            "MA5高于MA10%",
            "放量倍数",
            "换手率%",
        ]

    def _populate_tree(
        self,
        strategy_key: str,
        df: pd.DataFrame,
    ):
        self.tree.delete(
            *self.tree.get_children()
        )

        columns = self._columns_for_strategy(
            strategy_key
        )

        self.tree.configure(
            columns=columns
        )

        width_map = {
            "代码": 85,
            "名称": 110,
            "板块": 105,
            "触发日": 105,
            "收盘价": 90,
            "当日涨幅%": 95,
            "MA5": 90,
            "MA10": 90,
            "MA20": 90,
            "突破MA5幅度%": 120,
            "突破MA10幅度%": 125,
            "突破MA20幅度%": 125,
            "放量倍数": 95,
            "换手率%": 100,
            "MA5高于MA10%": 125,
            "昨日MA5": 95,
            "MA5上拐幅度%": 122,
            "昨日粘合度%": 112,
            "今日发散度%": 112,
            "发散增加百分点": 128,
        }

        for col in columns:
            self.tree.heading(
                col,
                text=col,
                command=lambda c=col: self._sort_tree(c),
            )

            anchor = (
                "w"
                if col in ("名称", "板块")
                else "center"
            )

            self.tree.column(
                col,
                width=width_map.get(col, 100),
                minwidth=70,
                anchor=anchor,
                stretch=(col != "板块"),
            )

        if df.empty:
            return

        for idx, row in df.iterrows():
            values = [
                "—" if pd.isna(row.get(col, "")) else row.get(col, "")
                for col in columns
            ]

            full_code = str(
                row.get("_code_full", "")
            )

            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=values,
                tags=(full_code,),
            )
        if self.current_sort_column in columns:
            self._apply_saved_sort()

    def _populate_sector_tree(
        self,
        df: pd.DataFrame,
    ):
        self.sector_tree.delete(
            *self.sector_tree.get_children()
        )

        if df.empty or "板块" not in df.columns:
            return

        target_date = (
            self.update_result.scan_date
            if self.update_result
            else ""
        )
        rows = []

        for sector, g in df.groupby("板块", dropna=False):
            sector = str(sector or "未分类")

            today_count = int(
                (
                    g["触发日"].astype(str)
                    == str(target_date)
                ).sum()
            )

            sector_signal = (
                str(g["板块信号"].iloc[0])
                if "板块信号" in g.columns
                and not g.empty
                else "未触发"
            )

            rows.append({
                "板块": sector,
                "今日触发": today_count,
                "板块信号": sector_signal,
            })

        rows.sort(
            key=lambda r: (
                r["板块信号"] == "今日触发",
                r["今日触发"],
                r["板块"],
            ),
            reverse=True,
        )

        self.sector_tree.insert(
            "",
            "end",
            iid="__ALL__",
            values=(
                "全部板块",
                len(df),
                "",
            ),
            tags=("signal_neutral",),
        )

        for idx, row in enumerate(rows):
            signal = str(row["板块信号"])

            if signal in ("今日触发", "昨日触发"):
                tag = "signal_breakout"
            elif signal == "未触发":
                tag = "signal_no_breakout"
            else:
                tag = "signal_neutral"

            self.sector_tree.insert(
                "",
                "end",
                iid=f"sector_{idx}",
                values=(
                    row["板块"],
                    row["今日触发"],
                    row["板块信号"],
                ),
                tags=(tag,),
            )

        if self.current_sector_filter:
            for iid in self.sector_tree.get_children(''):
                if str(self.sector_tree.set(iid,'板块'))==self.current_sector_filter:
                    self.sector_tree.selection_set(iid)
                    break
        else:
            self.sector_tree.selection_set('__ALL__')

    def _on_sector_select(self, _event=None):
        if not self.current_strategy_key:
            return

        selected = self.sector_tree.selection()

        if not selected:
            return

        values = self.sector_tree.item(
            selected[0],
            "values",
        )

        if not values:
            return

        sector = str(values[0])

        self.current_sector_filter = None if sector == "全部板块" else sector
        self._apply_quick_filters(silent=True)

    def _toggle_sector_table(self):
        if self.sector_expanded:
            self.sector_tree.grid_remove()
            self.sector_toggle_button.configure(text="展开板块表")
        else:
            self.sector_tree.grid()
            self.sector_toggle_button.configure(text="收起板块表")
        self.sector_expanded = not self.sector_expanded

    # -------------------- 近5日行业资金 TOP5（仅显示） --------------------

    def _display_fund_top5(self, message: str):
        try:
            rows,_ = self.backend.load_fund_top5()
        except Exception as exc:
            rows=[]
            message=str(exc)
        self._fund_rows=rows
        for i,(lbl,val) in enumerate(self._fund_card_labels):
            if i<len(rows):
                item=rows[i]
                name=item['name']
                lbl.configure(text=f"#{i+1}  {name[:10]+'…' if len(name)>11 else name}")
                amount=item['net_yuan']/100000000
                val.configure(text=f"{amount:+.2f} 亿",
                              fg="#d11a2a" if amount>=0 else "#16a34a")
            else:
                lbl.configure(text=f"#{i+1}  暂无数据")
                val.configure(text="—",fg="#6e6e73")
        if rows:
            stamp=rows[0]['fetched_at'][5:16]
            source=rows[0].get('source','未知来源')
            suffix=' · 更新失败，展示旧缓存' if message and ('失败' in message or '异常' in message) else ''
            self.fund_status_var.set(f'{source} · 抓取 {stamp} · 仅展示排名{suffix}')
        else:
            info=message or '暂无资金TOP5行业榜单'
            self.fund_status_var.set(info[:72] + ('…' if len(info)>72 else ''))
        self._set_actions_enabled(not getattr(self,'_busy',False))


    def _start_fund_refresh(self, force: bool = False):
        if self._fund_fetch_in_progress or getattr(self, '_busy', False):
            return
        self._fund_fetch_in_progress = True
        self.fund_status_var.set('正在获取近5日行业资金TOP5排名…')
        self._set_actions_enabled(True)
        def worker():
            try:
                def progress(notice):self.events.put(('fund_progress',notice))
                message = self.backend.refresh_fund_top5(force=force,progress=progress)
            except Exception as exc:
                message = f'更新失败：{exc}；不会影响原有策略'
            self.events.put(('fund_done', message))
        threading.Thread(target=worker, daemon=True).start()

    def _schedule_quick_filter(self, *_args):
        if self._quick_after:
            self.root.after_cancel(self._quick_after)
        self._quick_after = self.root.after(200, lambda: self._apply_quick_filters(silent=True))

    def _apply_quick_filters(self, silent=False):
        if self._quick_after:
            self.root.after_cancel(self._quick_after)
        self._quick_after = None

        # 新策略计算过程中 current_df 已清空；不要让旧筛选状态把旧结果重新画回来。
        if self._scan_in_progress and self.current_df.empty:
            return

        try:
            text = [self.change_min_var.get().strip(), self.change_max_var.get().strip()]
            low, high = [float(v) if v else None for v in text]
            if any(v is not None and not math.isfinite(v) for v in (low, high)):
                raise ValueError("涨幅范围须为有限数字")
            if low is not None and high is not None and low > high:
                raise ValueError("涨幅最小值不能大于最大值")
        except ValueError as exc:
            if not silent:
                messagebox.showerror(APP_TITLE, str(exc))
            return
        self.quick_change_range = (low, high)
        filtered = self.backend.filter_results(self.current_df, self.search_var.get(), self.market_var.get(),
                                              self.industry_var.get(), low, high, self.current_sector_filter)
        self.visible_df = filtered
        if self.current_strategy_key:
            self._populate_tree(self.current_strategy_key, filtered)
            suffix = f" · {self.current_sector_filter}" if self.current_sector_filter else ""
            self.summary_var.set(f"{self.current_strategy_label}{suffix} · 显示 {len(filtered)} 条 / 原始 {len(self.current_df)} 条")

    def _reset_quick_filters(self):
        self.search_var.set("")
        self.market_var.set("全部市场")
        self.industry_var.set("全部行业")
        self.change_min_var.set("")
        self.change_max_var.set("")
        self.current_sector_filter = None
        if self.sector_tree.exists("__ALL__"):
            self.sector_tree.selection_set("__ALL__")
        self._apply_quick_filters()

    def _selected_stock(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "请先选择一只个股。")
            return None
        tags = self.tree.item(selected[0], "tags")
        if not tags:
            return None
        return str(tags[0]), str(self.tree.set(selected[0], "名称"))

    def _result_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.result_menu.tk_popup(event.x_root, event.y_root)
            self.result_menu.grab_release()

    def _open_selected_history(self):
        if getattr(self, "_busy", False):
            return
        stock = self._selected_stock()
        if stock:
            self._open_history_window(*stock)

    def _aux_table(self, parent, columns, widths):
        box = ttk.Frame(parent)
        box.pack(fill="both", expand=True)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        tree = ttk.Treeview(box, columns=columns, show="headings", selectmode="browse")
        tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(box, orient="horizontal", command=tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        directions = {}
        def sort(column):
            reverse = not directions.get(column, True)
            directions[column] = reverse
            items = sorted(tree.get_children(), key=lambda iid: self._sort_value(tree.set(iid, column)), reverse=reverse)
            for position, iid in enumerate(items):
                tree.move(iid, "", position)
        for column, width in zip(columns, widths):
            tree.heading(column, text=column, command=lambda c=column: sort(c))
            tree.column(column, width=width, minwidth=65, stretch=True, anchor="w")
        return tree

    def _open_code_chart(self, code, name, trigger_date=None):
        end = self.update_result.scan_date if self.update_result else self.backend.get_latest_daily_date()
        end = trigger_date or end
        if not end:
            messagebox.showinfo(APP_TITLE, "没有本地行情。")
            return
        data = self.backend.get_chart_data(code, end)
        if data.empty:
            messagebox.showinfo(APP_TITLE, "这只股票没有可用的本地行情。")
            return
        self._show_chart_window(self.backend.symbol_only(code), name, trigger_date or "—", data)

    def _open_history_window(self, code, name):
        # 不受第5策略输入框尚未应用的内容影响。
        filters = self.current_filters
        end = self.update_result.scan_date if self.update_result else self.backend.get_latest_daily_date()
        if not end:
            return
        win = tk.Toplevel(self.root)
        win.title(f"{self.backend.symbol_only(code)} {name} · 信号历史")
        win.geometry("1180x650")
        win.minsize(850, 500)
        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"{self.backend.symbol_only(code)}  {name} · 信号历史", style="Headline.TLabel").pack(anchor="w")
        text = tk.StringVar(value="正在读取本地历史…")
        ttk.Label(body, textvariable=text, style="Subtle.TLabel", wraplength=1000).pack(anchor="w", pady=(5, 8))
        tree = self._aux_table(body, ("触发日", "策略", "连续日数", "收盘价", "放量倍数", "换手率%", "参数", "来源"),
                               (110,170,80,85,85,90,260,100))
        rows = {}
        labels = {v:k for k,v in self.STRATEGIES.items()}
        def number(value):
            return "—" if value is None else f"{float(value):.3f}"
        def receive(frame, error):
            if not win.winfo_exists():
                return
            if error:
                text.set("历史读取失败：" + error)
                return
            if frame.empty:
                text.set("本地缓存中尚无符合条件的信号；历史仅覆盖已有行情。")
                return
            for idx, row in enumerate(frame.to_dict("records")):
                payload = json.loads(row["payload"])
                key = row["filter_key"]
                if key != "固定规则":
                    lo, hi, tlo, thi = json.loads(key)
                    key = f"放量 {lo:g}～{hi if hi is not None else '不限'}；换手 {tlo:g}～{thi if thi is not None else '不限'}%"
                rows[str(idx)] = row
                tree.insert("", "end", iid=str(idx), values=(row["signal_date"], labels.get(row["strategy"],row["strategy"]), row["streak"],
                    number(payload.get("收盘价")), number(payload.get("放量倍数")), number(payload.get("换手率%")), key,row["source"]))
            current = frame[(frame.strategy=='volume_turnover') & (frame.filter_key==self.backend.filter_key('volume_turnover',filters))]
            dates = sorted(current.signal_date.unique())
            repeat = ""
            if dates:
                repeat = f" 当前第5策略本地最早触发 {dates[0]}，共有 {len(dates)} 个触发日。"
            text.set(f"共 {len(frame)} 条信号；历史仅覆盖本地缓存。第5策略按当前输入参数回算，其他已扫描参数另行保留。"
                     + repeat + " 连续日数按本地市场交易日计；双击记录查看该触发日走势图。")
        def open_record(_event=None):
            items = tree.selection()
            if items:
                self._open_code_chart(code,name,rows[items[0]]["signal_date"])
        tree.bind("<Double-1>",open_record)
        win.history_tree = tree
        token = time.monotonic_ns()
        self._history_windows[token] = receive
        def worker():
            try:
                frame = self.backend.get_signal_history(code,end,filters)
                self.events.put(("history_done",token,frame,""))
            except Exception as exc:
                self.events.put(("history_done",token,pd.DataFrame(),str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    @staticmethod
    def _sort_value(value):
        if value is None:
            return (2, "")

        text = str(value).strip()

        if not text:
            return (2, "")

        try:
            return (0, float(text))
        except Exception:
            return (1, text)

    def _apply_saved_sort(self):
        column=self.current_sort_column
        if column is None:return
        items=[(self._sort_value(self.tree.set(iid,column)),iid)
               for iid in self.tree.get_children('')]
        items.sort(key=lambda pair:pair[0],reverse=self.current_sort_reverse)
        for pos,(_,iid) in enumerate(items):
            self.tree.move(iid,'',pos)

    def _sort_tree(self,column:str):
        self.current_sort_reverse=(not self.current_sort_reverse
                                   if self.current_sort_column==column else False)
        self.current_sort_column=column
        self._apply_saved_sort()

    def _open_selected_sector_chart(self, _event=None):
        if not self.current_strategy_key:
            return

        selected = self.sector_tree.selection()

        if not selected:
            return

        values = self.sector_tree.item(
            selected[0],
            "values",
        )

        if not values:
            return

        sector = str(values[0])

        if sector == "全部板块":
            return

        # 板块信号在精简摘要第3列。
        sector_signal = (
            str(values[2])
            if len(values) > 2
            else ""
        )

        end_date = (
            self.update_result.scan_date
            if self.update_result
            else ""
        )

        try:
            df = self.backend.get_sector_chart_data(
                sector,
                end_date,
            )

            if df.empty:
                messagebox.showinfo(
                    APP_TITLE,
                    "没有足够的板块走势图数据。",
                )
                return

            self._show_sector_chart_window(
                sector,
                end_date,
                df,
                self.current_strategy_key,
                self.current_strategy_label,
                sector_signal,
            )

        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"读取板块走势图失败：{exc}",
            )

    def _show_sector_chart_window(
        self,
        sector: str,
        end_date: str,
        df: pd.DataFrame,
        strategy_key: str,
        strategy_label: str,
        sector_signal: str,
    ):
        win = tk.Toplevel(self.root)
        win.title(
            f"{sector} · {strategy_label}"
        )
        win.geometry("920x760" if strategy_key == "volume_turnover" else "920x520")
        win.minsize(680, 400)

        header = ttk.Frame(
            win,
            padding=(14, 12, 14, 5),
        )
        header.pack(fill="x")

        ttk.Label(
            header,
            text=f"{sector}（板块等权指数）",
            font=("", 13, "bold"),
        ).pack(side="left")

        ttk.Label(
            header,
            text=f"截至：{end_date}",
        ).pack(side="right")

        desc = ttk.Frame(
            win,
            padding=(14, 0, 14, 5),
        )
        desc.pack(fill="x")

        ttk.Label(
            desc,
            text=(
                f"当前策略：{strategy_label}    "
                f"板块信号：{sector_signal}"
            ),
            font=("", 10, "bold"),
        ).pack(side="left")

        ttk.Label(
            desc,
            text="  ·  成分股后复权收盘价归一化后等权平均",
        ).pack(side="left")
        # 板块列表只显示当日信号；历史信号在走势详情中按同一策略回算。
        dates=df.get('trade_date',pd.Series(dtype=str)).astype(str).tolist()
        history=[d for d in dates if self.backend._sector_strategy_triggered(
            df,strategy_key,d,self.current_filters) and d!=end_date]
        status=('历史信号：'+'、'.join(history[-5:][::-1]) if history
                else '历史信号：本地图表范围内暂无其他触发')
        ttk.Label(win,text=status,style='Subtle.TLabel').pack(anchor='w',padx=14,pady=(0,4))

        legend = ttk.Frame(
            win,
            padding=(14, 0, 14, 5),
        )
        legend.pack(fill="x")

        series = {
            "close": "#202020",
        }

        labels = [
            ("close", "板块等权指数", "#202020"),
        ]

        if strategy_key.startswith("breakout_ma"):
            ma_n = int(
                strategy_key.replace(
                    "breakout_ma",
                    "",
                )
            )
            color_map = {
                5: "#2f6fed",
                10: "#d17b00",
                20: "#7b4ab5",
            }
            color = color_map[ma_n]
            series[f"MA{ma_n}"] = color
            labels.append(
                (f"MA{ma_n}", f"MA{ma_n}", color)
            )

        elif strategy_key == "ma5_turn_up":
            # 拐头策略只显示板块等权指数和其MA5，不混入MA10/20。
            series["MA5"] = "#2f6fed"
            labels.append(("MA5", "MA5", "#2f6fed"))

        elif strategy_key == "ma_convergence_up":
            # 粘合/发散需要同时观察MA5、MA10、MA20三条均线。
            for ma, color in (("MA5", "#2f6fed"),
                              ("MA10", "#d17b00"),
                              ("MA20", "#7b4ab5")):
                series[ma] = color
                labels.append((ma, ma, color))

        elif strategy_key == "ma5_cross_ma10":
            series["MA5"] = "#2f6fed"
            series["MA10"] = "#d17b00"
            labels.extend([
                ("MA5", "MA5", "#2f6fed"),
                ("MA10", "MA10", "#d17b00"),
            ])

        if strategy_key == "volume_turnover":
            latest = df.iloc[-1]
            ratio = latest.get("放量倍数", float("nan"))
            turnover = latest.get("turnover", float("nan"))
            def metric(value):
                return f"{value:.3f}" if pd.notna(value) and math.isfinite(float(value)) else "缺失"
            ttk.Label(legend, text=f"板块放量：{metric(ratio)} 倍    板块换手率：{metric(turnover)}%",
                      style="Subtle.TLabel").pack(side="right")

        for _, label, color in labels:
            tk.Label(
                legend,
                text=f"● {label}",
                fg=color,
            ).pack(
                side="left",
                padx=(0, 14),
            )

        metric_canvases = []
        if strategy_key == "volume_turnover":
            for column, label, color in (("放量倍数", "板块放量倍数", "#0071e3"),
                                         ("turnover", "板块等权换手率%", "#d17b00")):
                ttk.Label(win, text=label, style="Subtle.TLabel").pack(anchor="w", padx=14)
                metric_canvas = tk.Canvas(win, background="white", height=155, highlightthickness=0)
                metric_canvas.pack(fill="x", padx=14, pady=(0, 5))
                metric_canvases.append((metric_canvas, column, color))

        canvas = tk.Canvas(
            win,
            background="white",
            highlightthickness=1,
            highlightbackground="#d0d0d0",
        )
        canvas.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(0, 14),
        )

        def redraw(_event=None):
            self._draw_series_chart(canvas, df, series=series)
            for metric_canvas, column, color in metric_canvases:
                self._draw_series_chart(metric_canvas, df, series={column: color})

        canvas.bind(
            "<Configure>",
            redraw,
        )

        win.after(
            100,
            redraw,
        )

    # -------------------- 走势图 --------------------

    def _open_selected_chart(self, _event=None):
        selected = self.tree.selection()

        if not selected:
            return

        iid = selected[0]
        tags = self.tree.item(
            iid,
            "tags",
        )

        if not tags:
            return

        code_full = tags[0]
        values = self.tree.item(
            iid,
            "values",
        )

        if not values:
            return

        code = str(values[0])
        name = str(values[1])
        trigger_date = str(self.tree.set(iid, "触发日"))

        try:
            df = self.backend.get_chart_data(
                code_full,
                self.update_result.scan_date if self.update_result else trigger_date,
            )

            if df.empty:
                messagebox.showinfo(
                    APP_TITLE,
                    "没有足够的本地走势图数据。",
                )
                return

            self._show_chart_window(
                code,
                name,
                trigger_date,
                df,
            )

        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"读取走势图失败：{exc}",
            )

    def _show_chart_window(
        self,
        code: str,
        name: str,
        trigger_date: str,
        df: pd.DataFrame,
    ):
        win = tk.Toplevel(self.root)
        win.title(
            f"{code} {name} · 最近30个有效交易日"
        )
        win.geometry("940x840")
        win.minsize(720, 650)

        header = ttk.Frame(
            win,
            padding=(14, 12, 14, 5),
        )
        header.pack(
            fill="x"
        )

        ttk.Label(
            header,
            text=f"{code}  {name}",
            font=("", 13, "bold"),
        ).pack(side="left")

        ttk.Label(
            header,
            text=f"触发日：{trigger_date}",
        ).pack(side="right")

        legend = ttk.Frame(
            win,
            padding=(14, 0, 14, 5),
        )
        legend.pack(fill="x")

        # 图例使用文字颜色；Canvas 曲线颜色固定，便于辨识。
        tk.Label(
            legend,
            text="● 收盘价",
            fg="#202020",
        ).pack(side="left", padx=(0, 14))

        tk.Label(
            legend,
            text="● MA5",
            fg="#2f6fed",
        ).pack(side="left", padx=(0, 14))

        tk.Label(
            legend,
            text="● MA10",
            fg="#d17b00",
        ).pack(side="left", padx=(0, 14))

        tk.Label(
            legend,
            text="● MA20",
            fg="#7b4ab5",
        ).pack(side="left")

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        price_page, metrics_page = ttk.Frame(notebook), ttk.Frame(notebook)
        notebook.add(price_page, text="价格与均线")
        notebook.add(metrics_page, text="成交量 · 放量 · 换手率")
        canvas = tk.Canvas(price_page, background="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        metrics = []
        for column, label, color in (("volume", "成交量（股）", "#0071e3"),
                                      ("放量倍数", "放量倍数（前5个有效交易日，不含当日）", "#7b4ab5"),
                                      ("turnover", "换手率%（缺失值不绘制）", "#d17b00")):
            ttk.Label(metrics_page, text=label, style="Subtle.TLabel").pack(anchor="w", pady=(5, 0))
            chart = tk.Canvas(metrics_page, background="white", height=150, highlightthickness=0)
            chart.pack(fill="both", expand=True)
            metrics.append((chart, column, color))
        def redraw(_event=None):
            self._draw_series_chart(canvas, df,
                series={"close": "#202020", "MA5": "#2f6fed", "MA10": "#d17b00", "MA20": "#7b4ab5"},
                signal_date=trigger_date)
            for chart, column, color in metrics:
                self._draw_series_chart(chart, df, {column: color}, signal_date=trigger_date)
        canvas.bind("<Configure>", redraw)
        for chart, _, _ in metrics:
            chart.bind("<Configure>", redraw)
        notebook.bind("<<NotebookTabChanged>>", lambda e: win.after_idle(redraw))
        win.after(100, redraw)

    @staticmethod
    def _draw_series_chart(
        canvas: tk.Canvas,
        df: pd.DataFrame,
        series: dict,
        signal_date: Optional[str] = None,
    ):
        attach_chart_hover(canvas)
        canvas._hover_hide()
        canvas._chart_state = None
        canvas.delete("all")

        width = max(
            canvas.winfo_width(),
            200,
        )
        height = max(
            canvas.winfo_height(),
            120,
        )

        left = 62
        right = 18
        top = 22
        bottom = 50

        plot_w = max(
            width - left - right,
            10,
        )
        plot_h = max(
            height - top - bottom,
            10,
        )

        values = []

        for col in series:
            if col in df.columns:
                vals = pd.to_numeric(
                    df[col],
                    errors="coerce",
                ).dropna().tolist()
                values.extend(vals)

        if not values:
            canvas.create_text(
                width / 2,
                height / 2,
                text="无可绘制数据",
            )
            return

        ymin = min(values)
        ymax = max(values)

        if math.isclose(ymin, ymax):
            pad = max(
                abs(ymin) * 0.02,
                1.0,
            )
            ymin -= pad
            ymax += pad
        else:
            pad = (
                ymax - ymin
            ) * 0.08
            ymin -= pad
            ymax += pad

        n = len(df)
        canvas._chart_state = (df, dict(series), left, top, plot_w, plot_h, ymin, ymax)

        def x_of(i):
            if n <= 1:
                return left + plot_w / 2
            return left + plot_w * i / (n - 1)

        def y_of(value):
            return (
                top
                + plot_h
                * (ymax - value)
                / (ymax - ymin)
            )

        # 横向网格与数值。
        grid_lines = 5

        for i in range(grid_lines):
            frac = i / (grid_lines - 1)
            y = top + plot_h * frac
            price = ymax - (ymax - ymin) * frac

            canvas.create_line(
                left,
                y,
                width - right,
                y,
                fill="#e8e8e8",
            )

            canvas.create_text(
                left - 8,
                y,
                text=f"{price:.2f}",
                anchor="e",
                fill="#666666",
                font=("", 9),
            )

        # X轴日期标签，最多6个。
        label_count = min(6, n)
        if label_count > 1:
            positions = sorted(set(
                round(
                    i * (n - 1)
                    / (label_count - 1)
                )
                for i in range(label_count)
            ))
        else:
            positions = [0]

        for i in positions:
            date_text = str(
                df.iloc[i]["trade_date"]
            )
            x = x_of(i)

            canvas.create_line(
                x,
                top + plot_h,
                x,
                top + plot_h + 4,
                fill="#888888",
            )

            canvas.create_text(
                x,
                top + plot_h + 18,
                text=date_text[5:],
                fill="#666666",
                font=("", 9),
            )

        # 纵轴和横轴。
        canvas.create_line(
            left,
            top,
            left,
            top + plot_h,
            fill="#999999",
        )
        canvas.create_line(
            left,
            top + plot_h,
            width - right,
            top + plot_h,
            fill="#999999",
        )

        if signal_date:
            positions = [i for i, day in enumerate(df["trade_date"].astype(str)) if day == signal_date]
            for i in positions:
                x = x_of(i)
                canvas.create_line(x, top, x, top + plot_h, fill="#d11a2a", dash=(4, 3), tags="signal_marker")
                canvas.create_text(x, top - 9, text="触发", fill="#d11a2a", tags="signal_marker")

        # 各曲线。
        for col, color in series.items():
            if col not in df.columns:
                continue

            points = []
            vals = pd.to_numeric(
                df[col],
                errors="coerce",
            )

            for i, value in enumerate(vals):
                if pd.isna(value):
                    # 遇到均线尚未形成时，不连接跨越空值的线段。
                    if len(points) >= 4:
                        canvas.create_line(
                            *points,
                            fill=color,
                            width=2,
                            smooth=False,
                        )
                    points = []
                    continue

                points.extend([
                    x_of(i),
                    y_of(float(value)),
                ])

            if len(points) >= 4:
                canvas.create_line(
                    *points,
                    fill=color,
                    width=2,
                    smooth=False,
                )


# ============================================================
# 主程序
# ============================================================

def main():
    root = tk.Tk()

    try:
        style = ttk.Style()
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
    except Exception:
        pass

    StockScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
