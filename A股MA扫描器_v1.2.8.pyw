# -*- coding: utf-8 -*-
"""A股 MA 扫描器 1.2.8 · Tkinter 环境准备 → Tkinter 行情抓取 → PySide6 4:3 工作台。
单文件 .pyw 便携源码；七种策略；同花顺近5日行业资金 TOP5 仅展示板块。
第三方 Python 库缺失时自动尝试安装，不内置大型二进制库。
"""
from __future__ import annotations
import argparse, importlib, importlib.util, math, json, os, stat, tempfile, queue, re
import sqlite3, threading, time, traceback, urllib.request, urllib.error, webbrowser
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Callable,Optional

def stage1_dependencies():
    """1/3：Tkinter 显示库检查及缺失自动安装。"""
    import tkinter as tk
    from tkinter import ttk,messagebox
    root=tk.Tk()
    root.title("A股 MA 扫描器 · 1/3 Python库检查")
    root.geometry("520x255")
    root.resizable(False,False)
    root.protocol("WM_DELETE_WINDOW",lambda:None)
    container=ttk.Frame(root,padding=24)
    container.pack(fill="both",expand=True)
    ttk.Label(container,text="1 / 3 · Python 运行环境",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(4,12))
    status=tk.StringVar(value="检查必要 Python 库…")
    ttk.Label(container,textvariable=status,wraplength=450).pack(anchor="w",pady=(0,15))
    bar=ttk.Progressbar(container,maximum=4,length=455)
    bar.pack(fill="x")
    detail=tk.StringVar(value="缺少的库将从清华镜像自动安装，失败后切换官方 PyPI。")
    ttk.Label(container,textvariable=detail,wraplength=450).pack(anchor="w",pady=16)
    events=queue.Queue()
    state={"ok":False}
    required=[("pandas","pandas",True),("baostock","baostock",True),
              ("akshare","akshare",False),("PySide6","PySide6",True)]
    def install():
        failed=[]
        for n,(mod,package,critical) in enumerate(required,1):
            events.put(("status",f"正在检查 {mod}（{n}/4）"))
            try:found=importlib.util.find_spec(mod) is not None
            except (ValueError,ImportError):found=False
            if not found:
                details=[]
                for label,url in (("清华镜像","https://pypi.tuna.tsinghua.edu.cn/simple"),
                                  ("官方 PyPI","https://pypi.org/simple")):
                    events.put(("status",f"正在用{label}安装 {package}（{n}/4）"))
                    try:
                        cp=subprocess.run([sys.executable,"-m","pip","install",
                            "--disable-pip-version-check","--no-input","--timeout","20",
                            "--retries","1","-i",url,package],
                            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                            encoding="utf-8",errors="replace",check=False,timeout=600,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
                        importlib.invalidate_caches()
                        found=(cp.returncode==0 and importlib.util.find_spec(mod) is not None)
                        if found:break
                        details.append(f"{label}: {(cp.stdout or '')[-650:]}")
                    except (OSError,subprocess.TimeoutExpired) as exc:
                        details.append(f"{label}: {exc}")
                if not found:failed.append((package,critical,"\n".join(details)))
            events.put(("step",n))
        events.put(("done",failed))

    def poll():
        while True:
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=="status":status.set(value)
            elif kind=="step":
                bar["value"]=value
                detail.set(f"环境检查 {value}/4")
            elif kind=="done":
                important=[f for f in value if f[1]]
                state["ok"]=not important
                if value:
                    msg="\n\n".join(f"{name}: {detail[-650:]}" for name,_,detail in value)
                    if important:messagebox.showerror("依赖安装失败",msg,parent=root)
                    else:messagebox.showwarning("TOP5 暂不可用","AKShare 未安装，七种策略仍可使用。\n\n"+msg,parent=root)
                root.destroy()
                return
        root.after(90,poll)
    threading.Thread(target=install,daemon=True).start()
    root.after(90,poll)
    root.mainloop()
    if not state["ok"]:raise SystemExit(1)

if __name__=="__main__" and not any(a in sys.argv for a in ("-h","--help")):
    stage1_dependencies()
try:
    import pandas as pd
    import baostock as bs
except Exception as exc:
    raise SystemExit("pandas / BaoStock 无法导入: "+str(exc)) from exc
import tkinter as tk
from tkinter import ttk,messagebox

# ============================================================
# 配置
# ============================================================

APP_TITLE = "A股 MA 扫描器"
APP_VERSION = "1.2.8"
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
if endpoint=='ths_rank':
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
        if endpoint != 'ths_rank':
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
        return ['同花顺']

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
                FROM fund_top5_snapshot WHERE source='同花顺' ORDER BY rank
            """).fetchall()
        return ([dict(rank=int(rank),name=name,net_yuan=float(amount),
                      fetched_at=fetched_at,source=source)
                 for rank,name,amount,fetched_at,source in rows], {})


    def _fund_complete_snapshot(self,source,notify,now):
        """只请求行业资金排名；任何情况下都不请求行业成分股。"""
        if source != '同花顺':
            raise ValueError('仅支持同花顺资金排名')
        notify('正在读取同花顺近5日行业资金净流入排名…')
        ranked=self._fund_request('ths_rank',timeout=self.FUND_RANK_TIMEOUT)
        name_col,amount_col='行业','净额'
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
        multiplier=100000000
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
        raise RuntimeError('同花顺行业资金排名获取失败，原有同花顺榜单缓存已保留。\n'
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



# 旧策略的历史信号回算仅使用此常量；不构造旧版 Tk 主窗口。
class StockScannerApp:
    STRATEGIES={
        "放量突破 MA5":"breakout_ma5",
        "放量突破 MA10":"breakout_ma10",
        "放量突破 MA20":"breakout_ma20",
        "MA5 上穿 MA10":"ma5_cross_ma10",
        "放量 + 换手率筛选":"volume_turnover",
        "MA5 拐头向上":"ma5_turn_up",
        "均线粘合向上":"ma_convergence_up",
    }

def stage2_update_market(*,demo=False):
    """2/3：真实八阶段 BaoStock 抓取和本地 SQLite 维护。"""
    from tkinter.scrolledtext import ScrolledText
    root=tk.Tk()
    root.title("A股 MA 扫描器 · 2/3 行情抓取")
    root.geometry("620x495")
    root.minsize(620,495)
    root.protocol("WM_DELETE_WINDOW",lambda:None)
    wrap=ttk.Frame(root,padding=22)
    wrap.pack(fill="both",expand=True)
    ttk.Label(wrap,text="2 / 3 · 数据抓取与校验",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,10))
    label=tk.StringVar(value="正在准备数据源")
    status=tk.StringVar(value="等待数据库初始化")
    elapsed=tk.StringVar(value="已用时 00:00")
    percent=tk.StringVar(value="0%")
    ttk.Label(wrap,textvariable=label,font=("Segoe UI",11,"bold")).pack(anchor="w")
    ttk.Label(wrap,textvariable=status,wraplength=560).pack(anchor="w",pady=(6,10))
    bar=ttk.Progressbar(wrap,maximum=100)
    bar.pack(fill="x")
    info=ttk.Frame(wrap)
    info.pack(fill="x",pady=(5,8))
    ttk.Label(info,textvariable=elapsed).pack(side="left")
    ttk.Label(info,textvariable=percent).pack(side="right")
    ttk.Label(wrap,text="按实际任务阶段更新，不代表剩余时间",foreground="#777777").pack(anchor="w")
    stages=ttk.Frame(wrap)
    stages.pack(fill="x",pady=10)
    names=[]
    for i,(name,_,_) in enumerate(UPDATE_PHASES):
        w=ttk.Label(stages,text="○ "+name)
        w.grid(row=i%4,column=i//4,sticky="w",padx=(0,25),pady=4)
        names.append(w)
    ttk.Separator(wrap).pack(fill="x",pady=6)
    log=ScrolledText(wrap,height=7,state="disabled",wrap="word")
    log.pack(fill="both",expand=True,pady=(10,5))
    actions=ttk.Frame(wrap)
    actions.pack(fill="x")
    retry=ttk.Button(actions,text="重试",state="disabled")
    retry.pack(side="right")
    leave=ttk.Button(actions,text="退出")
    leave.pack(side="right",padx=10)
    state={"result":None,"busy":False}
    events=queue.Queue()
    backend=None if demo else BaoStockBackend(DB_PATH)
    started=time.monotonic()

    def add(text):
        log.configure(state="normal")
        log.insert("end",text+"\n")
        log.see("end")
        log.configure(state="disabled")

    def run():
        try:
            def progress(p,text):
                events.put(("progress",(float(p),str(text))))
            if demo:
                for name,low,high in UPDATE_PHASES:
                    progress(low,"演示 · "+name)
                    time.sleep(.09)
                    progress(high,"演示 · "+name+" 已完成")
                result=UpdateResult("2026-10-29","2026-10-28",100.,5000,5000,0,False,"")
            else:
                result=backend.update_all(progress)
            events.put(("done",result))
        except Exception:
            events.put(("error",traceback.format_exc()))

    def launch():
        if state["busy"]:return
        state["busy"]=True
        retry.configure(state="disabled")
        add("开始数据更新"+("（演示）" if demo else ""))
        threading.Thread(target=run,daemon=True).start()

    def close():
        if state["busy"]:
            messagebox.showinfo("数据更新中","为避免中断数据库写入，请等待当前更新结束。",parent=root)
        else:
            root.destroy()

    def poll():
        while True:
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=="progress":
                p,task=value
                bar["value"]=max(0,min(100,p))
                percent.set(f"{p:.0f}%")
                parsed=describe_update_progress(p,task)
                phase=parsed["phase"]
                label.set(f"第 {phase+1}/8 阶段 · {parsed['title']}")
                status.set(task)
                for idx,widget in enumerate(names):
                    prefix="✓ " if idx<phase else "● " if idx==phase else "○ "
                    widget.configure(text=prefix+UPDATE_PHASES[idx][0])
                add(f"{p:.1f}%  {task}")
            elif kind=="error":
                state["busy"]=False
                retry.configure(state="normal")
                add(value)
                label.set("抓取失败，可重试")
                messagebox.showerror("行情更新失败",value[-2400:],parent=root)
            elif kind=="done":
                state["busy"]=False
                state["result"]=value
                bar["value"]=100
                percent.set("100%")
                add("已完成 · 准备切换 PySide6 主界面")
                root.after(130,root.destroy)
                return
        if root.winfo_exists():
            secs=int(time.monotonic()-started)
            elapsed.set(f"已用时 {secs//60:02d}:{secs%60:02d}")
            root.after(100,poll)
    retry.configure(command=launch)
    leave.configure(command=close)
    root.after(120,launch)
    root.after(120,poll)
    root.mainloop()
    if state["result"] is None:raise SystemExit(1)
    return backend,state["result"]

_backend_prepared=None
_result_prepared=None
if __name__=="__main__" and not any(a in sys.argv for a in ("-h","--help")):
    _backend_prepared,_result_prepared=stage2_update_market(demo="--demo" in sys.argv)


from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

STRATEGIES = [
    ("breakout_ma5", "突破 MA5", "均线突破"),
    ("breakout_ma10", "突破 MA10", "均线突破"),
    ("breakout_ma20", "突破 MA20", "均线突破"),
    ("ma5_cross_ma10", "MA5 上穿 MA10", "趋势信号"),
    ("ma5_turn_up", "MA5 拐头向上", "趋势信号"),
    ("ma_convergence_up", "均线粘合向上", "趋势信号"),
    ("volume_turnover", "放量 + 换手率", "量价分析"),
]
class ScanWorker(QThread):
    success = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, backend, request_id, strategy, date, previous, filters):
        super().__init__()
        self.backend = backend
        self.request_id = request_id
        self.strategy = strategy
        self.date = date
        self.previous = previous
        self.filters = filters

    def run(self):
        try:
            frame = self.backend.scan_strategy(
                self.strategy, self.date, False, self.previous, self.filters
            )
            self.success.emit(self.request_id, frame)
        except Exception:
            self.failed.emit(self.request_id, traceback.format_exc())


class FundWorker(QThread):
    notice = Signal(str)
    success = Signal(str, object, object)
    failed = Signal(str, str, object, object)

    def __init__(self, backend):
        super().__init__()
        self.backend = backend

    def run(self):
        notices = []
        try:
            message = self.backend.refresh_fund_top5(
                force=True, progress=lambda t: (notices.append(str(t)), self.notice.emit(str(t)))
            )
            rows, members = self.backend.load_fund_top5()
            self.success.emit(message, rows, members)
        except Exception:
            error = traceback.format_exc()
            try:
                rows, members = self.backend.load_fund_top5()
            except Exception:
                rows, members = [], {}
            self.failed.emit(error, "\n".join(notices[-35:]), rows, members)


class ChartWorker(QThread):
    success = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, backend, token, full_code, date):
        super().__init__()
        self.backend, self.token, self.full_code, self.date = backend, token, full_code, date

    def run(self):
        try:
            self.success.emit(self.token, self.backend.get_chart_data(self.full_code, self.date))
        except Exception:
            self.failed.emit(self.token, traceback.format_exc())


class PriceChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = pd.DataFrame()
        self.setMinimumHeight(164)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_frame(self, data):
        self.data = data if data is not None else pd.DataFrame()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))
        left, top, right, bottom = 28, 14, rect.width() - 10, rect.height() - 25
        if self.data.empty or bottom - top < 30:
            painter.setPen(QColor("#9ca3b0"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "选择股票后显示本地均线走势图")
            return
        df = self.data
        curves = [("close", "#222938", 2.3), ("MA5", "#347df4", 1.5),
                  ("MA10", "#e6a24b", 1.5), ("MA20", "#a487dc", 1.5)]
        valid = []
        for field, _, _ in curves:
            if field in df:
                valid += pd.to_numeric(df[field], errors="coerce").dropna().tolist()
        if not valid:
            return
        low, high = min(valid), max(valid)
        if high <= low:
            high, low = high + 1, low - 1
        span = high - low
        low -= span * .08
        high += span * .08
        for k in range(4):
            y = top + (bottom - top) * k / 3
            painter.setPen(QPen(QColor("#edf0f5"), 1))
            painter.drawLine(left, int(y), right, int(y))
        n = len(df)
        def coordinate(index, val):
            x = left + ((right - left) * index / max(1, n - 1))
            y = bottom - ((float(val) - low) / (high - low)) * (bottom - top)
            return int(x), int(y)
        for field, color, thickness in curves:
            if field not in df:
                continue
            vals = pd.to_numeric(df[field], errors="coerce")
            painter.setPen(QPen(QColor(color), thickness))
            previous = None
            for i, v in enumerate(vals):
                if pd.isna(v) or not math.isfinite(float(v)):
                    previous = None
                    continue
                point = coordinate(i, v)
                if previous is not None:
                    painter.drawLine(*previous, *point)
                previous = point
        painter.setPen(QColor("#9199a9"))
        if "trade_date" in df.columns and n:
            painter.drawText(left, rect.height() - 6, str(df.iloc[0]["trade_date"])[5:])
            text = str(df.iloc[-1]["trade_date"])[5:]
            painter.drawText(right - 42, rect.height() - 6, text)
        painter.end()


def value_text(raw):
    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        return "—"
    try:
        return f"{float(raw):.2f}"
    except (ValueError, TypeError):
        return str(raw)


def sample_data(strategy):
    # Used only in explicit --demo mode: all stock names and values are imaginary.
    examples = [
        ("sh.600101", "演示科技", "电子", 21.38, 4.83, 2.14, 6.8),
        ("sz.300271", "演示智联", "计算机", 43.57, 3.31, 1.98, 8.1),
        ("sh.688117", "演示通讯", "通信", 73.26, 6.12, 3.02, 10.2),
        ("sz.002681", "演示能源", "电力设备", 17.12, 2.56, 1.76, 4.5),
        ("sh.600688", "演示汽车", "汽车", 27.81, -1.35, 1.65, 3.2),
        ("sh.600234", "演示计算", "计算机", 51.08, 4.26, 2.31, 6.2),
        ("sz.300775", "演示芯片", "电子", 89.62, 7.66, 3.27, 12.1),
        ("sh.688666", "演示智能", "通信", 63.91, 2.71, 1.80, 5.6),
    ]
    rows = []
    offset = next((i for i, (key, _, _) in enumerate(STRATEGIES) if key == strategy), 0)
    for i, (code, name, industry, price, pct, vol, turnover) in enumerate(examples):
        if (i + offset) % 5 == 4:
            continue
        rows.append({
            "_code_full": code, "代码": code.split(".")[-1], "名称": name,
            "板块": industry, "收盘价": price, "当日涨幅%": pct,
            "放量倍数": vol, "换手率%": turnover, "触发日": "2026-10-29",
        })
    return pd.DataFrame(rows)


def sample_chart(price, seed=1):
    dates = pd.date_range("2026-09-10", periods=32, freq="B")
    vals = [price * (.88 + .0034 * i + .013 * math.sin(i * .64 + seed)
                     + .008 * math.cos(i * .22 + seed)) for i in range(32)]
    f = pd.DataFrame({"trade_date": [x.strftime("%Y-%m-%d") for x in dates],
                      "close": vals})
    for n in (5, 10, 20):
        f[f"MA{n}"] = f.close.rolling(n).mean()
    return f


STYLE = """
QMainWindow, QWidget#appRoot { background: #f6f7fa; color: #222938; }
QLabel { color: #222938; background: transparent; }
QFrame#nav { background: #edf1f7; border-right: 1px solid #e4e8f0; }
QFrame#right { background: white; border-left: 1px solid #e5e9f0; }
QFrame#card { background: white; border: 1px solid #e6eaf2; border-radius: 12px; }
QLabel#small { color: #8791a1; font-size: 11px; }
QLabel#section { font-size: 12px; font-weight: 700; }
QLabel#brand { font-size: 18px; font-weight: 760; }
QLabel#symbolName { font-size: 18px; font-weight: 700; }
QLabel#price { font-size: 28px; font-weight: 750; }
QPushButton { background: white; border: 1px solid #e2e7ef; border-radius: 8px;
              padding: 7px 12px; color: #344054; }
QPushButton:hover { border-color: #82b6f2; background: #f8fbff; }
QPushButton:disabled { color: #b2bac7; background: #f5f6f8; }
QPushButton#navButton { text-align: left; background: transparent; border: none;
                       border-radius: 8px; padding: 11px 12px; }
QPushButton#navButton:hover { background: #e2eafa; }
QPushButton#navButton:checked { background: #dceafe; color: #1261be; font-weight: 700; }
QLabel#fundCard { text-align: left; background: #ffffff; border: 1px solid #e1e7f0;
                   border-radius: 11px; padding: 11px 8px; color: #354155; }
QLineEdit, QComboBox { background: white; border: 1px solid #e0e5ee; border-radius: 8px;
                        padding: 7px 9px; min-height: 18px; color: #293344; }
QLineEdit:focus, QComboBox:focus { border-color: #4c99e8; }
QTableWidget { background: white; border: 1px solid #e4e8f0; border-radius: 10px;
               gridline-color: #edf0f5; alternate-background-color: #fafbfd;
               selection-background-color: #e5f1ff; selection-color: #185eae; }
QHeaderView::section { background: #f4f6f9; color: #738093; border: none;
                       border-bottom: 1px solid #e3e8ef; padding: 10px 8px; }
QProgressBar { border: none; background: #edf1f6; border-radius: 5px;
               text-align: center; min-height: 9px; max-height: 9px; }
QProgressBar::chunk { background: #2885e9; border-radius: 5px; }
QCheckBox { spacing: 5px; }
"""


class ScannerWindow(QMainWindow):
    def __init__(self, demo=False, backend=None, update_result=None):
        super().__init__()
        self.demo = demo
        self.engine = sys.modules[__name__]
        self.backend = backend
        self.update_result = None
        self._restart_requested = False
        self.frame = pd.DataFrame()
        self.filtered = pd.DataFrame()
        self.funds = []
        self.fund_source = ""
        self.fund_error_details = ""
        self.current_key = STRATEGIES[5][0]
        self.workers = []
        self.scan_token = 0
        self.chart_token = 0
        self.setWindowTitle("A股 MA 扫描器 v1.2.8 · PySide6")
        self.resize(1120, 840)
        self.setMinimumSize(980, 735)
        self.setStyleSheet(STYLE)
        shell = QWidget()
        shell.setObjectName("appRoot")
        self.setCentralWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.page = QStackedWidget()
        root.addWidget(self.page)
        self._make_workspace()
        if demo:
            self._load_demo()
        elif backend is not None and update_result is not None:
            QTimer.singleShot(40,lambda:self._on_update_ready(update_result))
        else:
            raise RuntimeError('行情抓取阶段尚未完成')

    def _text(self, value, role=None, parent=None):
        label = QLabel(value, parent)
        if role:
            label.setObjectName(role)
        return label

    def _make_workspace(self):
        page = QWidget()
        whole = QVBoxLayout(page)
        whole.setContentsMargins(0, 0, 0, 0)
        whole.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("QFrame{background:white;border-bottom:1px solid #e6eaf1}")
        line = QHBoxLayout(header)
        line.setContentsMargins(19, 12, 19, 12)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(self._text("A股 MA 扫描器", "brand"))
        self.header_status = self._text("v1.2.8 · PySide6 · 4:3 工作台", "small")
        brand.addWidget(self.header_status)
        line.addLayout(brand)
        line.addStretch(1)
        self.refresh_market = QPushButton("更新行情")
        self.refresh_market.clicked.connect(self.restart_pipeline)
        self.refresh_market.setEnabled(not self.demo)
        line.addWidget(self.refresh_market)
        release = QPushButton("检查更新")
        release.clicked.connect(self._show_release_info)
        line.addWidget(release)
        whole.addWidget(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(1)
        whole.addWidget(split, 1)

        nav = QFrame()
        nav.setObjectName("nav")
        nav_l = QVBoxLayout(nav)
        nav_l.setContentsMargins(12, 20, 12, 18)
        nav_l.setSpacing(4)
        nav_l.addWidget(self._text("扫描策略", "section"))
        nav_l.addSpacing(9)
        self.buttons = {}
        self.strategy_group = QButtonGroup(self)
        self.strategy_group.setExclusive(True)
        last_group = None
        for key, name, group in STRATEGIES:
            if group != last_group:
                nav_l.addSpacing(10)
                nav_l.addWidget(self._text(group, "small"))
                last_group = group
            button = QPushButton("  " + name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setChecked(key == self.current_key)
            button.clicked.connect(lambda checked=False, k=key:self._select_strategy(k))
            self.strategy_group.addButton(button)
            self.buttons[key] = button
            nav_l.addWidget(button)
        self.volume_options = QFrame()
        opt = QVBoxLayout(self.volume_options)
        opt.setContentsMargins(0, 8, 0, 0)
        self.volume_min = QLineEdit("1.5")
        self.volume_min.setPlaceholderText("放量下限")
        self.turnover_min = QLineEdit("3")
        self.turnover_min.setPlaceholderText("换手率下限")
        opt.addWidget(self._text("放量倍数 ≥", "small"))
        opt.addWidget(self.volume_min)
        opt.addWidget(self._text("换手率 ≥ (%)", "small"))
        opt.addWidget(self.turnover_min)
        apply = QPushButton("重新筛选")
        apply.clicked.connect(self._rerun_strategy)
        opt.addWidget(apply)
        nav_l.addWidget(self.volume_options)
        self.volume_options.hide()
        nav_l.addStretch(1)
        nav_l.addWidget(self._text("数据：本地 SQLite / BaoStock", "small"))
        split.addWidget(nav)

        middle = QWidget()
        mid = QVBoxLayout(middle)
        mid.setContentsMargins(16, 15, 16, 16)
        mid.setSpacing(11)
        head = QHBoxLayout()
        self.strategy_title = self._text("均线粘合向上", "section")
        head.addWidget(self.strategy_title)
        head.addStretch()
        self.hit_count = self._text("命中 — 只", "small")
        head.addWidget(self.hit_count)
        mid.addLayout(head)

        fund_head = QHBoxLayout()
        fund_head.addWidget(self._text("近5日 · 行业资金 TOP5", "section"))
        fund_head.addStretch()
        self.fund_source_label = self._text("未刷新", "small")
        fund_head.addWidget(self.fund_source_label)
        self.fund_refresh = QPushButton("刷新")
        self.fund_refresh.clicked.connect(self.start_fund_refresh)
        fund_head.addWidget(self.fund_refresh)
        mid.addLayout(fund_head)
        cards = QHBoxLayout()
        cards.setSpacing(6)
        self.fund_cards = []
        for i in range(5):
            card = QLabel(f"TOP {i + 1:02d}\n等待数据\n—")
            card.setObjectName("fundCard")
            card.setMinimumHeight(67)
            card.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            cards.addWidget(card, 1)
            self.fund_cards.append(card)
        mid.addLayout(cards)

        search = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("搜索股票代码 / 名称")
        self.query.textChanged.connect(self.apply_filters)
        search.addWidget(self.query, 3)
        self.market = QComboBox()
        self.market.addItems(["全部市场", "主板", "创业板", "科创板"])
        self.market.currentIndexChanged.connect(self.apply_filters)
        search.addWidget(self.market, 2)
        self.industry = QComboBox()
        self.industry.addItem("全部行业")
        self.industry.currentIndexChanged.connect(self.apply_filters)
        search.addWidget(self.industry, 2)
        mid.addLayout(search)
        results = QHBoxLayout()
        results.addWidget(self._text("选股结果", "section"))
        results.addStretch(1)
        clear = QPushButton("重置条件")
        clear.clicked.connect(self.clear_filters)
        results.addWidget(clear)
        mid.addLayout(results)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["代码", "名称", "板块", "收盘价", "涨幅%", "放量", "换手率%"]
        )
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._stock_selected)
        self.table.horizontalHeader().setStretchLastSection(True)
        mid.addWidget(self.table, 1)
        self.result_info = self._text("选择策略后开始扫描", "small")
        self.result_info.setWordWrap(True)
        mid.addWidget(self.result_info)
        split.addWidget(middle)

        right = QFrame()
        right.setObjectName("right")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 21, 16, 18)
        rl.setSpacing(8)
        rl.addWidget(self._text("股票详情", "small"))
        self.stock_name = self._text("请选择股票", "symbolName")
        rl.addWidget(self.stock_name)
        self.stock_code = self._text("点击中间列表查看", "small")
        rl.addWidget(self.stock_code)
        rl.addSpacing(8)
        self.stock_price = self._text("—", "price")
        rl.addWidget(self.stock_price)
        self.stock_change = self._text("", "section")
        rl.addWidget(self.stock_change)
        rl.addSpacing(12)
        rl.addWidget(self._text("收盘价 / MA5 / MA10 / MA20", "small"))
        self.chart = PriceChart()
        rl.addWidget(self.chart, 1)
        legend = self._text("● 收盘   ● MA5   ● MA10   ● MA20", "small")
        legend.setStyleSheet("color:#64748b;font-size:10px")
        rl.addWidget(legend)
        rl.addSpacing(12)
        rl.addWidget(self._text("信号指标", "section"))
        self.metrics = self._text("放量倍数   —\n\n换手率        —\n\n触发日期    —", "small")
        rl.addWidget(self.metrics)
        rl.addStretch(1)
        chart_button = QPushButton("打开完整走势图")
        chart_button.clicked.connect(self._full_chart_dialog)
        rl.addWidget(chart_button)
        history = QPushButton("查看信号历史")
        history.clicked.connect(self._history_dialog)
        rl.addWidget(history)
        self.chart_status = self._text("本地历史缓存", "small")
        self.chart_status.setWordWrap(True)
        rl.addWidget(self.chart_status)
        split.addWidget(right)
        split.setSizes([194, 652, 274])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        self.page.addWidget(page)

        footer = self.statusBar()
        footer.showMessage("三阶段启动完成 · PySide6 4:3 工作台 · SQLite 数据原位保留")

    def _load_demo(self):
        self.demo = True
        self.update_result = type("DemoResult", (), {
            "scan_date": "2026-10-29", "previous_trade_date": "2026-10-28",
            "completeness": 100., "expected": 5000, "saved": 5000,
            "warning": "",
        })()
        self.header_status.setText("演示模式 · 全部数据为虚构，仅展示交互")
        self.fund_source_label.setText("演示资金榜单 · 模拟数据")
        self.funds = [
            {"name": name, "net_yuan": net * 1e8, "source": "演示"}
            for name, net in (("电子", 28.6), ("计算机", 22.1),
                              ("通信", 16.8), ("电力设备", 14.4), ("汽车", 11.2))
        ]
        self.refresh_market.setEnabled(False)
        self.fund_refresh.setEnabled(False)
        self._render_funds()
        self.page.setCurrentIndex(0)
        self._select_strategy(self.current_key)

    def restart_pipeline(self):
        """Exit Qt first, then restart the full three-stage .pyw."""
        self._restart_requested = True
        QApplication.instance().quit()

    def _on_update_ready(self, result):
        self.update_result = result
        self.header_status.setText(
            f"行情日期 {result.scan_date} · 完整率 {result.completeness:.2f}%"
        )
        self.page.setCurrentIndex(0)
        self.statusBar().showMessage(
            result.warning or f"{result.scan_date} 本地日线已就绪"
        )
        self._select_strategy(self.current_key)
        self._load_funds_from_cache()
        self.start_fund_refresh()

    def _remember(self, worker):
        self.workers.append(worker)
        worker.finished.connect(lambda: self._forget_worker(worker))

    def _forget_worker(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)

    def _select_strategy(self, key):
        self.current_key = key
        self.buttons[key].setChecked(True)
        self.strategy_title.setText(
            next(name for k, name, _ in STRATEGIES if k == key)
        )
        self.volume_options.setVisible(key == "volume_turnover")
        self._rerun_strategy()

    def _rerun_strategy(self):
        if self.update_result is None:
            return
        self.scan_token += 1
        self.frame = pd.DataFrame()
        self.apply_filters()
        if self.demo:
            self.frame = sample_data(self.current_key)
            self.apply_filters()
            return
        try:
            filters = None
            if self.current_key == "volume_turnover":
                filters = self.engine.RangeFilter(
                    float(self.volume_min.text()), None,
                    float(self.turnover_min.text()), None,
                )
        except ValueError:
            self.result_info.setText("请输入有效的放量倍数和换手率")
            return
        self.result_info.setText("正在读取本地行情并计算策略…")
        worker = ScanWorker(self.backend, self.scan_token, self.current_key,
                            self.update_result.scan_date,
                            self.update_result.previous_trade_date, filters)
        worker.success.connect(self._scan_ready)
        worker.failed.connect(self._scan_failed)
        self._remember(worker)
        worker.start()

    def _scan_ready(self, token, frame):
        if token != self.scan_token:
            return
        self.frame = frame
        self._update_industry_filter()
        self.apply_filters()

    def _scan_failed(self, token, detail):
        if token != self.scan_token:
            return
        self.result_info.setText("策略执行失败，点击查看错误信息")
        self._show_error("策略执行失败", detail)

    def _update_industry_filter(self):
        current = self.industry.currentText()
        self.industry.blockSignals(True)
        self.industry.clear()
        self.industry.addItem("全部行业")
        if not self.frame.empty and "板块" in self.frame:
            self.industry.addItems(sorted(set(self.frame["板块"].dropna().astype(str))))
        index = self.industry.findText(current)
        self.industry.setCurrentIndex(max(0, index))
        self.industry.blockSignals(False)

    def clear_filters(self):
        self.query.clear()
        self.market.setCurrentIndex(0)
        self.industry.setCurrentIndex(0)
        self._render_funds()
        self.apply_filters()

    def apply_filters(self):
        if self.frame.empty:
            self.filtered = pd.DataFrame()
        else:
            text = self.query.text().strip().casefold()
            frame = self.frame
            if text:
                frame = frame.loc[
                    frame["名称"].astype(str).str.casefold().str.contains(text, regex=False)
                    | frame["代码"].astype(str).str.casefold().str.contains(text, regex=False)
                ]
            market = self.market.currentText()
            codes = frame["代码"].astype(str).str.zfill(6)
            if market == "创业板":
                frame = frame.loc[codes.str.startswith(("300", "301"))]
            elif market == "科创板":
                frame = frame.loc[codes.str.startswith("688")]
            elif market == "主板":
                frame = frame.loc[~codes.str.startswith(("300", "301", "688"))]
            sector = self.industry.currentText()
            if sector and sector != "全部行业":
                frame = frame.loc[frame["板块"].astype(str).eq(sector)]
            self.filtered = frame.copy()
        self._draw_table()
        self.hit_count.setText(f"命中 {len(self.filtered)} 只")
        self.result_info.setText(
            "模拟数据 · 非真实行情" if self.demo else
            f"股票结果 {len(self.filtered)} 只 · {self.update_result.scan_date if self.update_result else '—'}"
        )

    def _draw_table(self):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0 if self.filtered.empty else len(self.filtered))
        for row_number, (_, record) in enumerate(self.filtered.iterrows()):
            for column, key in enumerate(
                ("代码", "名称", "板块", "收盘价", "当日涨幅%", "放量倍数", "换手率%")
            ):
                raw = record.get(key, None)
                value = value_text(raw) if column >= 3 else str(raw or "—")
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(record.get("_code_full", "")))
                if column >= 3:
                    try:
                        item.setData(Qt.ItemDataRole.EditRole, float(raw))
                    except (ValueError, TypeError):
                        pass
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key == "当日涨幅%" and pd.notna(raw):
                    item.setForeground(QColor("#db5263" if float(raw) >= 0 else "#139b74"))
                self.table.setItem(row_number, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)
        if self.table.rowCount():
            self.table.selectRow(0)
            # Populating the table temporarily blocks Qt signals; explicitly
            # synchronize the inspector with the newly selected first row.
            self._stock_selected()
        else:
            self._clear_stock()

    def _render_funds(self):
        """TOP5 五个板块只展示排名及净流入金额，不支持点击筛选。"""
        for idx, card in enumerate(self.fund_cards):
            if idx < len(self.funds):
                record = self.funds[idx]
                net = float(record["net_yuan"]) / 1e8
                card.setText(f'TOP {idx + 1:02d}\n{record["name"]}\n{net:+.2f} 亿')
            else:
                card.setText(f"TOP {idx + 1:02d}\n暂无数据\n—")


    def _load_funds_from_cache(self):
        try:
            rows, _ = self.backend.load_fund_top5()
            self.funds = rows
            self._check_fund_freshness()
            self._render_funds()
        except Exception as exc:
            self.fund_error_details = str(exc)


    def _check_fund_freshness(self):
        """缓存允许查看，但必须显示真实抓取时间，不暗示等同当日实时排名。"""
        rows = self.funds
        self.fund_source = rows[0].get("source", "未知来源") if rows else ""
        if self.demo:
            return
        if rows:
            stamp = str(rows[0].get("fetched_at", "未知时间"))[:16]
            self.fund_source_label.setText(f"{self.fund_source} · 抓取 {stamp}")
        else:
            self.fund_source_label.setText("暂无资金榜单")


    def start_fund_refresh(self):
        if self.demo:
            return
        if self.backend is None or any(isinstance(w, FundWorker) and w.isRunning() for w in self.workers):
            return
        self.fund_error_details = ""
        self.fund_refresh.setEnabled(False)
        self.fund_source_label.setText("正在获取近5日行业资金TOP5排名…")
        worker = FundWorker(self.backend)
        worker.notice.connect(self.fund_source_label.setText)
        worker.success.connect(self._fund_ready)
        worker.failed.connect(self._fund_failed)
        worker.finished.connect(lambda: self.fund_refresh.setEnabled(True))
        self._remember(worker)
        worker.start()

    def _fund_ready(self, message, rows, members):
        self.funds = rows
        self._check_fund_freshness()
        self._render_funds()
        self.statusBar().showMessage(message)


    def _fund_failed(self, detail, notices, rows, members):
        self.fund_error_details = detail + "\n\n请求步骤：\n" + notices
        self.funds = rows
        self._check_fund_freshness()
        self._render_funds()
        self.fund_source_label.setText(
            f"{self.fund_source} · 更新失败，显示旧缓存" if rows
            else "同花顺资金排名失败 · 查看原因"
        )
        self._show_error(
            "TOP5 排名刷新失败",
            "同花顺资金排名获取失败；原有同花顺榜单缓存未被覆盖。\n\n"
            + self.fund_error_details,
        )


    def _stock_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < 0:
            return
        code_item = self.table.item(row, 0)
        if code_item is None:
            return
        full_code = code_item.data(Qt.ItemDataRole.UserRole)
        matching = self.filtered.loc[self.filtered["_code_full"].astype(str) == full_code]
        if matching.empty:
            return
        record = matching.iloc[0]
        self.selected_stock = record
        self.stock_name.setText(str(record.get("名称", "")))
        self.stock_code.setText(f'{record.get("代码", "")} · {record.get("板块", "")}')
        self.stock_price.setText(value_text(record.get("收盘价")))
        change = float(record.get("当日涨幅%", 0))
        self.stock_change.setText(f'{change:+.2f}%')
        self.stock_change.setStyleSheet(
            "color:#dd4d5f" if change >= 0 else "color:#149b78"
        )
        self.metrics.setText(
            f'放量倍数     {value_text(record.get("放量倍数"))} 倍\n\n'
            f'换手率          {value_text(record.get("换手率%"))}%\n\n'
            f'触发日期     {record.get("触发日", "—")}'
        )
        self.chart_token += 1
        if self.demo:
            self.chart.set_frame(sample_chart(float(record.get("收盘价", 20)), row + 1))
            self.chart_status.setText("演示价格曲线，非真实交易数据")
            return
        self.chart_status.setText("正在读取本地走势图…")
        token = self.chart_token
        worker = ChartWorker(self.backend, token, full_code, self.update_result.scan_date)
        worker.success.connect(self._chart_ready)
        worker.failed.connect(self._chart_failed)
        self._remember(worker)
        worker.start()

    def _clear_stock(self):
        self.stock_name.setText("请选择股票")
        self.stock_code.setText("点击列表行查看")
        self.stock_price.setText("—")
        self.stock_change.setText("")
        self.metrics.setText("放量倍数   —\n\n换手率        —\n\n触发日期     —")
        self.chart.set_frame(pd.DataFrame())

    def _chart_ready(self, token, frame):
        if token == self.chart_token:
            self.chart.set_frame(frame)
            self.chart_status.setText("历史日线 · 来源：本地 SQLite")

    def _chart_failed(self, token, detail):
        if token == self.chart_token:
            self.chart_status.setText("走势图读取失败")
            self.fund_error_details = detail

    def _full_chart_dialog(self):
        record = getattr(self, "selected_stock", None)
        if record is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f'{record.get("名称")} · 30日走势图')
        dialog.resize(900, 590)
        layout = QVBoxLayout(dialog)
        layout.addWidget(self._text(str(record.get("名称")), "brand"))
        chart = PriceChart()
        chart.set_frame(self.chart.data)
        layout.addWidget(chart)
        dialog.exec()

    def _history_dialog(self):
        record = getattr(self, "selected_stock", None)
        if record is None:
            return
        if self.demo:
            QMessageBox.information(self, "信号历史", "演示模式不提供真实信号历史。")
            return
        # Read-only query to keep the PySide6 preview independent of the old Tkinter dialogs.
        try:
            f = self.backend.get_signal_history(
                str(record["_code_full"]), self.update_result.scan_date,
                self.engine.RangeFilter()
            )
            text = "暂无历史触发信号" if f.empty else "\n".join(
                f'{r["signal_date"]} · {r["strategy"]}'
                for r in f.head(35).to_dict("records")
            )
            self._show_error("本地信号历史", text)
        except Exception:
            self._show_error("历史读取失败", traceback.format_exc())

    def _show_release_info(self):
        QMessageBox.information(
            self, "检查更新",
            "当前为三阶段 .pyw 开发版，尚未发布正式 Release。\n"
            "请到 github.com/Xstime/AShareMAScanner/releases 查看正式版本。"
        )

    def _show_error(self, title, details):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(710, 410)
        layout = QVBoxLayout(dialog)
        summary = QLabel("接口错误详情 / traceback（可复制用于排查）")
        layout.addWidget(summary)
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(details)
        layout.addWidget(txt, 1)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()


def main():
    parser=argparse.ArgumentParser(description="A股 MA 扫描器三阶段 PySide6 单文件 .pyw")
    parser.add_argument("--demo",action="store_true",help="依次演示三个界面；不用真实网络行情")
    parser.add_argument("--screenshot",default="",help="在第三界面保存 Qt 实际截图")
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    app.setFont(QFont("Segoe UI",10))
    win=ScannerWindow(demo=args.demo,backend=_backend_prepared,update_result=_result_prepared)
    win.show()
    if args.screenshot:
        def capture():
            if not win.grab().save(args.screenshot):
                print("Qt截图保存失败",file=sys.stderr)
            app.quit()
        QTimer.singleShot(1000,capture)
    exitcode=app.exec()
    if win._restart_requested:
        # Restart after Qt's event loop has ended; Tk and Qt must not coexist.
        subprocess.Popen([sys.executable,str(Path(__file__).resolve())],
                         cwd=str(BASE_DIR),
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    return exitcode

if __name__=="__main__":
    raise SystemExit(main())
