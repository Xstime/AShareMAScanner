# -*- coding: utf-8 -*-
"""
A股 MA 扫描器（单文件 Tkinter .pyw · BaoStock + 同花顺资金 TOP5 · v1.3.0）
=====================================

功能
----
- Tkinter 依赖检测与行情更新，PySide6 4:3 三栏主界面。
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
- 七种策略支持行业板块同规则判断、单击板块筛选、双击查看当前策略的板块走势及历史信号。
- PySide6 主界面采用左侧七策略、中央筛选与结果、右侧个股详情三栏布局。
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
- 近5日同花顺行业资金净流入 TOP5 仅展示行业排名与金额，不抓成分股、不按榜单筛选股票。
- 资金排名仅通过 AKShare 的同花顺五日行业排行获取；保留失败前的同花顺缓存。
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
正常直接运行：python A股MA扫描器_v1.3.0.pyw
首次运行自动补装缺少的第三方库（需要联网，不需要任何付费API）。
若安装失败，可手动运行：python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple baostock pandas akshare

macOS 若使用 Homebrew Python 且缺少 Tkinter，可安装对应版本的 python-tk。
"""

from __future__ import annotations

import math
import json
import multiprocessing
import hashlib
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
import urllib.parse
import webbrowser
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
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
        "PySide6": ("PySide6", True),
    }
    missing = [(module, pip_name, required)
               for module, (pip_name, required) in packages.items()
               if importlib.util.find_spec(module) is None]
    if not missing:
        # 阶段1：环境检查成功也短暂显示独立的 Tkinter 窗口。
        # 无桌面 DISPLAY 的 CI 环境自动跳过，不阻断非 GUI 测试。
        try:
            import tkinter as _tk
            root = _tk.Tk()
            root.title("A股 MA 扫描器 · 1/3 环境检查")
            root.geometry("500x165")
            root.configure(bg="#f5f6fa")
            _tk.Label(root,text="运行环境检查",font=("Segoe UI",15,"bold"),
                      bg="#f5f6fa",fg="#24334a").pack(anchor="w",padx=25,pady=(24,10))
            _tk.Label(root,text="Python / Tkinter / PySide6 / 行情依赖已就绪",
                      font=("Segoe UI",10),bg="#f5f6fa",fg="#3f785b"
                      ).pack(anchor="w",padx=25)
            root.after(700,root.destroy)
            root.mainloop()
        except Exception:
            pass
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

    root.title("A股 MA 扫描器 · 1/3 库补齐")
    root.geometry("560x185")
    root.resizable(False, False)
    root.configure(bg="#f5f5f7")
    root.protocol("WM_DELETE_WINDOW", lambda: None)
    _ttk.Label(root, text="1/3 · 自动补齐运行环境（含 PySide6）", font=("Segoe UI", 14, "bold"),
               background="#f5f5f7").pack(anchor="w", padx=24, pady=(22, 8))
    status = _tk.StringVar(value="检测到缺少依赖，首次安装可能需要几分钟…")
    _ttk.Label(root, textvariable=status, background="#f5f5f7",
               font=("Segoe UI", 10)).pack(anchor="w", padx=24, pady=(0, 10))
    bar = _ttk.Progressbar(root, mode="indeterminate", length=442)
    bar.pack(padx=24, fill="x")
    bar.start(14)
    _ttk.Label(root, text="仅安装缺失的库；主界面采用 PySide6，数据更新采用 Tkinter。",
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
APP_VERSION = "1.3.0"
RELEASE_API = "https://api.github.com/repos/Xstime/AShareMAScanner/releases/latest"
RELEASES_PAGE = "https://github.com/Xstime/AShareMAScanner/releases"

# Manual updates are downloaded to a sibling temporary .pyw. The old file is
# retained until the helper confirms that the replacement bootstrapped.
MAX_UPDATE_BYTES = 4 * 1024 * 1024
UPDATE_HELPER = r"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

def wait_previous_process(pid):
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 120000) != 0:
                    raise TimeoutError("原程序关闭超时，未替换文件")
            finally:
                kernel.CloseHandle(handle)
    else:
        end = time.monotonic() + 120
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                raise RuntimeError("没有权限确认原程序退出")
            time.sleep(.2)
        raise TimeoutError("原程序关闭超时，未替换文件")

def main():
    parent, old, staged, backup, ack, prior = sys.argv[1:]
    old, staged, backup, ack = map(Path, (old, staged, backup, ack))
    child = None
    swapped = False
    try:
        wait_previous_process(int(parent))
        if not staged.is_file() or not old.is_file():
            raise RuntimeError("更新文件或原文件已丢失，未执行替换")
        if backup.exists():
            raise RuntimeError("发现上一次更新遗留的旧版备份，不允许覆盖")
        os.replace(old, backup)
        try:
            os.replace(staged, old)
            swapped = True
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            child = subprocess.Popen(
                [sys.executable, str(old), "--update-ack", str(ack),
                 "--updated-from", prior],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=flags,
                cwd=str(old.parent))
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if ack.is_file() and ack.read_text(encoding="utf-8").strip() == "ready":
                    backup.unlink()
                    print("新程序已启动，旧版备份已删除", flush=True)
                    return
                if child.poll() is not None:
                    raise RuntimeError("新程序未能正常启动，正在恢复旧版本")
                time.sleep(.2)
            raise TimeoutError("新程序启动确认超时，正在恢复旧版本")
        except Exception:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if backup.exists():
                os.replace(backup, old)
            raise
    except Exception:
        traceback.print_exc()
        raise
    finally:
        ack.unlink(missing_ok=True)
        staged.unlink(missing_ok=True)
        Path(__file__).unlink(missing_ok=True)

if __name__ == "__main__":
    main()
"""


def _github_release_document():
    request = urllib.request.Request(RELEASE_API, headers={
        "User-Agent": f"AShareMAScanner-updater/{APP_VERSION}",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read(128 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"GitHub 响应异常（HTTP {exc.code}）") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("无法连接 GitHub，请稍后重试") from exc
    if len(body) > 128 * 1024:
        raise RuntimeError("GitHub 返回的数据过大")
    try:
        value = json.loads(body)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("GitHub 发布信息不是有效 JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("GitHub 发布信息格式异常")
    return value


def _expected_release_asset(release, latest):
    name = f"AShareMAScanner_v{'.'.join(map(str, latest))}.pyw"
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("GitHub 发布附件列表异常")
    matches = [asset for asset in assets
               if isinstance(asset, dict) and asset.get("name") == name]
    if len(matches) != 1:
        raise RuntimeError("最新版没有可自动安装的 .pyw 源程序")
    item = matches[0]
    url = str(item.get("browser_download_url", ""))
    parts = urllib.parse.urlsplit(url)
    required_path = ("/Xstime/AShareMAScanner/releases/download/"
                     f"v{'.'.join(map(str, latest))}/{name}")
    if parts.scheme != "https" or parts.hostname != "github.com" or (
            parts.path != required_path or parts.username or parts.password
            or parts.port or parts.query or parts.fragment):
        raise RuntimeError("GitHub 更新下载地址不可信")
    digest = str(item.get("digest", ""))
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise RuntimeError("GitHub 未提供 SHA-256 校验值，拒绝自动覆盖原程序")
    try:
        size = int(item.get("size", 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("更新文件大小异常") from exc
    if not 0 < size <= MAX_UPDATE_BYTES:
        raise RuntimeError("更新文件大小超出允许范围")
    return url, digest.split(":", 1)[1].lower(), size


class UpdateDownloadCancelled(Exception):
    """The user cancelled an in-flight update before installation."""


def _ensure_update_active(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise UpdateDownloadCancelled("已取消更新下载")


def _download_release_asset(url, expected_size, staged, on_progress=None,
                            on_status=None, cancel_event=None):
    """Stream with no overall deadline; resume after transient socket timeouts.

    urllib's timeout is a per-socket inactivity guard, NOT a total download
    deadline. The progress window remains responsive and cancellation is
    checked at least after a socket operation/retry delay. Retried requests
    use a validated HTTP Range response or restart cleanly if not supported.
    """
    hasher = hashlib.sha256()
    total = 0
    started = time.monotonic()
    retry_count = 0
    while total < expected_size:
        _ensure_update_active(cancel_event)
        headers = {"User-Agent": f"AShareMAScanner-updater/{APP_VERSION}"}
        if total:
            headers["Range"] = f"bytes={total}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                actual = urllib.parse.urlsplit(response.geturl())
                if actual.scheme != "https" or actual.hostname not in (
                        "github.com", "release-assets.githubusercontent.com"):
                    raise RuntimeError("更新文件最终下载地址不可信")
                status = getattr(response, "status", 200)
                if total and status == 206:
                    content_range = getattr(response, "headers", {}).get(
                        "Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                    if (not match or int(match.group(1)) != total
                            or int(match.group(3)) != expected_size
                            or int(match.group(2)) < total):
                        raise RuntimeError("断点续传区间不可信，拒绝合并更新文件")
                elif status == 200:
                    # Some GitHub endpoints ignore Range. Do not append a full
                    # response to old bytes; restart the verified download.
                    if total:
                        total = 0
                        hasher = hashlib.sha256()
                        if on_progress:
                            on_progress(0, expected_size, 0.0)
                else:
                    raise RuntimeError(f"更新下载状态异常（HTTP {status}）")
                with staged.open("ab" if total else "wb") as dest:
                    while total < expected_size:
                        _ensure_update_active(cancel_event)
                        chunk = response.read(min(64 * 1024, expected_size - total))
                        _ensure_update_active(cancel_event)
                        if not chunk:
                            raise RuntimeError("更新文件提前结束，大小与发行信息不符")
                        total += len(chunk)
                        if total > MAX_UPDATE_BYTES:
                            raise RuntimeError("更新文件超过允许大小")
                        hasher.update(chunk)
                        dest.write(chunk)
                        if on_progress:
                            elapsed = max(time.monotonic() - started, 0.001)
                            on_progress(total, expected_size, total / elapsed)
                _ensure_update_active(cancel_event)
                break
        except urllib.error.HTTPError as exc:
            # 403/404 and other HTTP failures require user-visible diagnosis,
            # not an endless retry loop.
            raise RuntimeError(f"GitHub 下载响应异常（HTTP {exc.code}）") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            _ensure_update_active(cancel_event)
            retry_count += 1
            if on_status:
                on_status(f"下载连接中断，正在重连（第 {retry_count} 次）…")
            # No overall deadline or arbitrary retry-count limit. The user may
            # cancel, and the 30s socket timeout prevents an uninterruptible
            # network read.
            pause = min(retry_count, 5)
            if cancel_event is not None:
                if cancel_event.wait(pause):
                    raise UpdateDownloadCancelled("已取消更新下载") from exc
            else:
                time.sleep(pause)
    return hasher.hexdigest()


def prepare_manual_update(original: Path, on_update_found=None,
                          on_progress=None, on_status=None, cancel_event=None):
    """Explicit update check, verified download and staging; no auto-install."""
    _ensure_update_active(cancel_event)
    release = _github_release_document()
    _ensure_update_active(cancel_event)
    if release is None or release.get("draft") or release.get("prerelease"):
        return "尚无可用正式版本", None
    latest = _release_version(release.get("tag_name", ""))
    current = _release_version(APP_VERSION)
    if latest is None or current is None:
        raise RuntimeError("GitHub 版本号异常")
    if latest < current:
        return ("当前为开发或未发布版本；GitHub 最新正式版是 v"
                + ".".join(map(str, latest)) + "，不会自动降级"), None
    url, expected_digest, size = _expected_release_asset(release, latest)
    if latest == current:
        with original.open("rb") as stream:
            local_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if local_digest == expected_digest:
            return "当前已是最新正式版本（文件校验一致）", None

    original = Path(original).resolve()
    if original.suffix.lower() != ".pyw" or not original.is_file():
        raise RuntimeError("自动更新仅支持从本地 .pyw 源文件运行")
    backup = original.with_name(original.name + ".old-update.bak")
    if backup.exists():
        raise RuntimeError(f"旧版备份尚未清理：{backup.name}，为防止覆盖已取消本次更新")
    _ensure_update_active(cancel_event)
    if on_update_found:
        on_update_found("v" + ".".join(map(str, latest)), size)
    _ensure_update_active(cancel_event)
    fd, candidate = tempfile.mkstemp(prefix=".ashare-update-", suffix=".pyw",
                                     dir=str(original.parent))
    os.close(fd)
    staged = Path(candidate)
    try:
        digest = _download_release_asset(url, size, staged, on_progress=on_progress,
                                         on_status=on_status, cancel_event=cancel_event)
        _ensure_update_active(cancel_event)
        if digest != expected_digest:
            raise RuntimeError("新程序的 SHA-256 不匹配，拒绝安装")
        if staged.stat().st_size != size:
            raise RuntimeError("新程序的文件长度不匹配，拒绝安装")
        if on_status:
            on_status("下载完成，正在验证文件完整性与 Python 语法…")
        source = staged.read_bytes()
        if not re.search(rb"(?m)^APP_VERSION\s*=\s*['\"]" +
                         re.escape(".".join(map(str, latest)).encode()) + rb"['\"]", source):
            raise RuntimeError("下载的程序版本号与 GitHub Release 不一致")
        if b"def main():" not in source or b"--update-ack" not in source:
            raise RuntimeError("下载文件缺少必需的安全更新启动接口")
        try:
            compile(source, str(staged), "exec")
        except (SyntaxError, ValueError) as exc:
            raise RuntimeError("新版本源码未通过 Python 编译检查") from exc
        _ensure_update_active(cancel_event)
        os.chmod(staged, stat.S_IMODE(original.stat().st_mode))
        return (f"已验证并下载 v{'.'.join(map(str, latest))}，即将自动替换并重启",
                staged)
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def _release_version(value: str):
    """仅比较正式发布的三段式版本号。"""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    return tuple(int(part) for part in match.groups()) if match else None

def fetch_latest_release():
    """只读取本项目正式 GitHub Release，不执行远程程序。"""
    request = urllib.request.Request(RELEASE_API, headers={
        "User-Agent": "AShareMAScanner-update-checker/1.3.0",
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
        if latest < current:
            # A higher local version than the latest published release is not
            # equivalent to being the newest stable version (e.g. recalled 1.2.8).
            return (f"当前运行 v{'.'.join(map(str, current))} 开发/未发布版本；"
                    f"GitHub 最新正式版为 v{'.'.join(map(str, latest))}", RELEASES_PAGE)
        if latest == current:
            return "当前已是最新正式版本", None
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

# 逐股数据仍走 BaoStock 后复权接口；并行连接限定为少量独立进程，
# 防止在一个 BaoStock 全局会话上并发访问导致数据串码。
BATCH_SIZE = 200
BATCH_PAUSE = 2.0
DAILY_PARALLEL_THRESHOLD = 100
DAILY_PARALLEL_WORKERS = 3
DAILY_WORKER_STALL_SECONDS = 90

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

@contextmanager
def sqlite_connection(path: Path, timeout: float = 30):
    """Transaction-safe and deterministically closed SQLite connection.

    sqlite3.Connection.__exit__ commits/rolls back but DOES NOT close its file
    handle. Always close explicitly, particularly on Windows where the file
    cannot be renamed or deleted until all connections are closed.
    """
    connection = sqlite3.connect(path, timeout=timeout)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


# Each spawned process has an isolated BaoStock socket. Never write SQLite here.
_DAY_POOL_LOGIN_MONO = 0.0


def _day_pool_fetch(task):
    """Return raw BaoStock K-lines; the parent validates and persists them."""
    global _DAY_POOL_LOGIN_MONO
    code, name, trade_date = task[:3]
    end_date = task[3] if len(task) > 3 else trade_date
    error = None
    for attempt in range(1, QUERY_RETRY + 1):
        try:
            if (_DAY_POOL_LOGIN_MONO == 0
                    or time.monotonic() - _DAY_POOL_LOGIN_MONO >= SESSION_REFRESH_SECONDS):
                try:
                    bs.logout()
                except Exception:
                    pass
                response = bs.login()
                if response.error_code != "0":
                    raise RuntimeError(f"BaoStock 登录失败: {response.error_code} {response.error_msg}")
                _DAY_POOL_LOGIN_MONO = time.monotonic()
            rs = bs.query_history_k_data_plus(
                code, BaoStockBackend.HISTORY_FIELDS,
                start_date=trade_date, end_date=end_date,
                frequency="d", adjustflag=ADJUST_FLAG,
            )
            if rs.error_code != "0":
                raise RuntimeError(f"{rs.error_code} {rs.error_msg}")
            fields = list(rs.fields)
            values = []
            while rs.next():
                values.append(rs.get_row_data())
            return code, name, fields, values, ""
        except Exception as exc:
            error = str(exc)
            _DAY_POOL_LOGIN_MONO = 0
            try:
                bs.logout()
            except Exception:
                pass
            if attempt < QUERY_RETRY:
                time.sleep(RETRY_WAIT * attempt)
    return code, name, [], [], (error or "BaoStock 请求失败")


class MarketUpdateCancelled(RuntimeError):
    """The user requested a safe stop. Downloaded progress is committed."""


class MarketDataUnavailable(RuntimeError):
    """Consecutive market source errors; stop instead of retrying thousands of stocks."""


class BaoStockBackend:
    HISTORY_FIELDS = "date,code,close,volume,tradestatus,isST,turn"

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._last_login_mono = 0.0
        # 同一次运行多个策略共用只读板块K线计算，避免重复全表读取。
        self._sector_chart_cache: dict[tuple[str, str], pd.DataFrame] = {}
        self._instance_lock_file = None
        self._cancel_update_event = threading.Event()

    def cancel_update(self):
        self._cancel_update_event.set()

    def _check_cancel(self, conn=None):
        if self._cancel_update_event.is_set():
            if conn is not None:
                conn.commit()
            raise MarketUpdateCancelled("已安全停止；已保存行情，下次更新将断点续传")

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
                with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
            existing = conn.execute("""
                SELECT code
                FROM daily
                WHERE trade_status=1 AND close > 0 AND close < 1.0e308
                  AND volume IS NOT NULL AND volume >= 0 AND volume < 1.0e308
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT code
                FROM daily
                WHERE trade_date=? AND trade_status=1
                  AND close > 0 AND close < 1.0e308
                  AND volume IS NOT NULL AND volume >= 0 AND volume < 1.0e308
            """, (trade_date,)).fetchall()

        return {r[0] for r in rows}

    def get_day_universe(self, trade_date: str) -> pd.DataFrame:
        with sqlite_connection(self.db_path, timeout=30) as conn:
            return pd.read_sql_query("""
                SELECT trade_date, code, name, trade_status
                FROM day_universe
                WHERE trade_date=?
                ORDER BY code
            """, conn, params=(trade_date,))

    def get_partial_dates(self) -> list[str]:
        with sqlite_connection(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT trade_date
                FROM day_status
                WHERE status <> 'complete'
                ORDER BY trade_date
            """).fetchall()

        return [r[0] for r in rows]

    def get_latest_processed_date(self) -> Optional[str]:
        with sqlite_connection(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT MAX(trade_date)
                FROM day_status
            """).fetchone()

        return row[0] if row and row[0] else None

    def get_latest_daily_date(self) -> Optional[str]:
        with sqlite_connection(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT MAX(trade_date)
                FROM daily
                WHERE trade_status=1 AND close > 0 AND close < 1.0e308
                  AND volume IS NOT NULL AND volume >= 0 AND volume < 1.0e308
            """).fetchone()

        return row[0] if row and row[0] else None

    def get_day_status_info(self, trade_date: str):
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
                  AND d.trade_status=1 AND d.close > 0 AND d.close < 1.0e308
                  AND d.volume IS NOT NULL AND d.volume >= 0 AND d.volume < 1.0e308
            """, (trade_date,)).fetchone()[0]

            # 以前失败、现在已写入成功行情的项目，应自动清理队列。
            conn.execute("""
                DELETE FROM fetch_queue
                WHERE trade_date=?
                  AND EXISTS (
                    SELECT 1 FROM daily AS d
                    WHERE d.code=fetch_queue.code
                      AND d.trade_date=fetch_queue.trade_date
                      AND d.trade_status=1 AND d.close > 0 AND d.close < 1.0e308
                      AND d.volume IS NOT NULL AND d.volume >= 0 AND d.volume < 1.0e308
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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

            with sqlite_connection(self.db_path, timeout=30) as conn:
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

    # -------------------- 近5日行业资金TOP5（仅同花顺） --------------------

    FUND_RANK_TIMEOUT=25
    FUND_JSON_PREFIX='__AShareMA_Fund_JSON__='
    FUND_CHILD=r"""
import sys
import akshare as ak
if len(sys.argv)!=2 or sys.argv[1]!='ths_rank':
    raise ValueError('only ths_rank is supported')
data=ak.stock_fund_flow_industry(symbol='5日排行')
fields=['行业','净额']
if data is None or data.empty or any(x not in data.columns for x in fields):
    raise RuntimeError('同花顺五日行业资金排名为空或缺少字段')
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





    def load_fund_top5(self) -> tuple[list[dict], dict[int, set[str]]]:
        """仅查询五日资金净流入 TOP5 行业榜单。

        兼容旧调用方返回 (rows, {})，但不读取或请求成分股数据。
        """
        with sqlite_connection(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT rank,industry,net_yuan,fetched_at,source
                FROM fund_top5_snapshot WHERE source='同花顺' ORDER BY rank
            """).fetchall()
        return ([dict(rank=int(rank),name=name,net_yuan=float(amount),
                      fetched_at=fetched_at,source=source)
                 for rank,name,amount,fetched_at,source in rows], {})


    def _fund_complete_snapshot(self,notify,now):
        """仅使用同花顺五日行业资金净流入排名，不访问任何成分股接口。"""
        notify('同花顺 · 正在获取近5日行业主力资金净流入排名…')
        ranked=self._fund_request('ths_rank',timeout=self.FUND_RANK_TIMEOUT)
        if ranked.empty or not {'行业','净额'}.issubset(ranked.columns):
            raise RuntimeError('同花顺五日行业资金榜单缺少必要字段')
        ranked=ranked[['行业','净额']].copy()
        ranked['净额']=pd.to_numeric(ranked['净额'],errors='coerce')
        ranked=ranked.dropna(subset=['行业','净额'])
        ranked=ranked.loc[ranked['净额'].map(math.isfinite)]
        ranked['行业']=ranked['行业'].astype(str).str.strip()
        ranked=ranked[ranked['行业'].ne('')].drop_duplicates('行业')
        ranked=ranked.sort_values('净额',ascending=False).head(5)
        if len(ranked)!=5:
            raise RuntimeError(f'同花顺有效行业只有{len(ranked)}个，不足5个')
        stamp=now.strftime('%Y-%m-%d %H:%M:%S')
        # AKShare 同花顺该接口的资金单位为亿元，数据库仍保存元。
        rows=[(i,str(item['行业']),float(item['净额'])*100000000,stamp,'同花顺')
              for i,(_,item) in enumerate(ranked.iterrows(),1)]
        notify('同花顺 · 近5日行业资金TOP5排名获取完成（5/5）')
        return rows


    def refresh_fund_top5(self,force=False,progress=None):
        """单数据源：失败保留旧榜单，不影响独立的七种选股策略。"""
        notify=progress or (lambda _:None)
        previous,_=self.load_fund_top5()
        now=datetime.now(CST)
        if (not force and len(previous)==5
            and previous[0]['fetched_at'][:10]==now.strftime('%Y-%m-%d')
            and (now.hour<18 or previous[0]['fetched_at'][11:13]>='18')):
            return '已使用今日同花顺近5日资金TOP5缓存'
        if now.weekday()<5 and now.hour<18:
            if previous:
                return '今日行情未结算，沿用缓存；18:00后可刷新'
            raise RuntimeError('交易日18:00后可获取完整的近5日资金榜单')
        errors=[]
        # 对短暂网络故障进行一次重试，彻底失败时不删除旧快照。
        for attempt in (1,2):
            try:
                if attempt>1:
                    notify('同花顺 · 首次请求失败，正在重试（2/2）…')
                rows=self._fund_complete_snapshot(notify,now)
                with sqlite_connection(self.db_path, timeout=20) as conn:
                    conn.execute('DELETE FROM fund_top5_snapshot')
                    # 清理早期程序遗留的成分股缓存，新版本不再使用。
                    conn.execute('DELETE FROM fund_top5_member')
                    conn.executemany(
                        'INSERT INTO fund_top5_snapshot(rank,industry,net_yuan,fetched_at,source) VALUES(?,?,?,?,?)',
                        rows)
                return '同花顺 · 近5日行业资金TOP5排名已更新'
            except (RuntimeError,TimeoutError,ValueError,sqlite3.Error) as exc:
                errors.append(f'第{attempt}次：{exc}')
                if attempt==1:
                    time.sleep(0.8)
        raise RuntimeError('同花顺五日资金TOP5排名刷新失败，保留旧缓存。\n'
                           +'\n'.join(errors)[:2500])


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

        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
            dates = conn.execute("SELECT DISTINCT trade_date FROM daily WHERE trade_date<=? "
                                 "ORDER BY trade_date DESC LIMIT 80", (end_date,)).fetchall()
            if not dates:
                return ""
            start = dates[-1][0]
            jobs = conn.execute("SELECT code, MIN(trade_date), MAX(trade_date) FROM daily "
                                "WHERE trade_date BETWEEN ? AND ? AND trade_status=1 "
                                "AND turnover IS NULL GROUP BY code ORDER BY code",
                                (start, end_date)).fetchall()
            self._check_cancel()
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
                with sqlite_connection(self.db_path, timeout=30) as conn:
                    conn.executemany("UPDATE daily SET turnover=? WHERE code=? AND trade_date=? "
                                     "AND turnover IS NULL", rows)
            except Exception:
                # 行情不受影响；缺失值保留，下次启动继续重试。
                pass
            if idx % BATCH_SIZE == 0:
                time.sleep(BATCH_PAUSE)
        cb(96, "近期换手率检查完成")
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT code, name, start_date, end_date
                FROM init_queue
                ORDER BY code
            """).fetchall()

        if not rows:
            cb(end_p, "没有历史失败项")
            return

        total = len(rows)

        with sqlite_connection(self.db_path, timeout=30) as conn:
            for idx, (code, name, start_date, end_date) in enumerate(
                rows,
                start=1,
            ):
                self._check_cancel(conn)
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
        trade_dates = self.recent_n_trade_dates(latest_date, INITIAL_TRADING_DAYS)
        start_date = trade_dates[0]
        ready_codes = self.get_history_ready_codes()
        todo = latest_stocks[~latest_stocks["code"].isin(ready_codes)].copy()

        if todo.empty:
            cb(end_p, "历史缓存已就绪")
            return

        tasks = [(str(r.code), str(r.name or ""), start_date, latest_date)
                 for r in todo.itertuples(index=False)]
        total = len(tasks)
        completed = set()
        began = time.monotonic()
        consecutive_errors = 0

        def record(conn, code, name, fields=None, values=None, error=""):
            nonlocal consecutive_errors
            self._check_cancel(conn)
            if code in completed:
                return
            try:
                if error:
                    raise RuntimeError(error)
                if fields is None:
                    df = self.query_stock_history(code, start_date, latest_date)
                else:
                    df = pd.DataFrame(values, columns=fields)
                rows = self.dataframe_to_daily_rows(df, name)
                rows = [row for row in rows if row[0] == code
                        and start_date <= row[1] <= latest_date]
                if not rows:
                    raise RuntimeError("历史初始化返回空数据")
                self.upsert_daily_rows(conn, rows)
                self.mark_history_ready(conn, code, name)
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                self.queue_init_failure(
                    conn, code, name, start_date, latest_date, exc)
            completed.add(code)
            elapsed = time.monotonic() - began
            eta = ""
            if len(completed) >= 10:
                sec = int(elapsed / len(completed) * (total-len(completed)))
                hours, mins = divmod(sec // 60, 60)
                eta = f" · 预计剩余 {hours}小时{mins:02d}分"
            self.stage_progress(cb, start_p, end_p, len(completed), total,
                                f"初始化历史 {len(completed)}/{total} · "
                                f"{self.symbol_only(code)}{eta}")
            if len(completed) % BATCH_SIZE == 0:
                conn.commit()
            if consecutive_errors >= 25:
                conn.commit()
                raise MarketDataUnavailable(
                    "历史初始化连续25只股票下载失败，已安全停止；"
                    "已获取数据仍保留，下次启动可继续")

        can_parallel = (
            total >= DAILY_PARALLEL_THRESHOLD
            and getattr(self.query_stock_history, "__func__", None)
                is BaoStockBackend.query_stock_history
            and not getattr(sys, "frozen", False)
            and os.environ.get("ASHARE_MA_FETCH_WORKERS", "3") != "1"
        )
        with sqlite_connection(self.db_path, timeout=30) as conn:
            if can_parallel:
                pool = None
                try:
                    workers = max(2, min(4, int(
                        os.environ.get("ASHARE_MA_FETCH_WORKERS", str(DAILY_PARALLEL_WORKERS)))))
                    cb(start_p, f"历史缓存 · 使用 {workers} 条独立 BaoStock 连接")
                    pool = multiprocessing.get_context("spawn").Pool(
                        processes=workers, maxtasksperchild=400)
                    stream = pool.imap_unordered(_day_pool_fetch, tasks, chunksize=1)
                    early_errors = []
                    early_success = 0
                    for _ in tasks:
                        started_waiting = time.monotonic()
                        while True:
                            self._check_cancel(conn)
                            try:
                                code, name, fields, values, error = stream.next(timeout=1)
                                break
                            except multiprocessing.TimeoutError:
                                if time.monotonic() - started_waiting >= DAILY_WORKER_STALL_SECONDS:
                                    raise TimeoutError("历史 BaoStock 并行请求长期无响应")
                        if len(completed) < 12:
                            if error:
                                early_errors.append(code)
                            else:
                                early_success += 1
                        record(conn, code, name, fields, values, error)
                        if len(completed) == 12 and early_success == 0:
                            for retry_code in early_errors:
                                completed.discard(retry_code)
                            consecutive_errors = 0
                            raise RuntimeError("并行历史连接全部失败")
                    pool.close()
                    pool.join()
                    pool = None
                except (MarketUpdateCancelled, MarketDataUnavailable):
                    conn.commit()
                    raise
                except Exception as exc:
                    cb(start_p + (end_p-start_p)*len(completed)/total,
                       f"并行历史初始化异常，逐股恢复剩余 {total-len(completed)} 只：{str(exc)[:80]}")
                finally:
                    if pool is not None:
                        pool.terminate()
                        pool.join()
            for code, name, _, _ in tasks:
                self._check_cancel(conn)
                if code in completed:
                    continue
                record(conn, code, name)
                if len(completed) % BATCH_SIZE == 0:
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
        self._check_cancel()
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

        tasks = [(str(r.code), str(r.name or ""), trade_date)
                 for r in todo.itertuples(index=False)]
        finished = set()
        started = time.monotonic()
        consecutive_errors = 0

        def progress(code):
            count = len(finished)
            elapsed = time.monotonic() - started
            eta_text = ""
            if count >= 10 and elapsed > 0:
                remaining = int(elapsed / count * (total - count))
                hours, minutes = divmod(remaining // 60, 60)
                eta_text = f" · 预计剩余 {hours}小时{minutes:02d}分"
            self.stage_progress(cb, start_p, end_p, count, total,
                                f"更新 {trade_date} · {count}/{total} · "
                                f"{self.symbol_only(code)}{eta_text}")

        def record(conn, code, name, fields=None, values=None, error=""):
            nonlocal consecutive_errors
            self._check_cancel(conn)
            if code in finished:
                return
            try:
                if error:
                    raise RuntimeError(error)
                if fields is None:
                    rows = self.fetch_exact_day_for_stock(code, name, trade_date)
                else:
                    raw = pd.DataFrame(values, columns=fields)
                    rows = self.dataframe_to_daily_rows(raw, name)
                    rows = [row for row in rows
                            if row[0] == code and row[1] == trade_date and row[5] == 1]
                    if not rows:
                        raise RuntimeError("未返回目标交易日日K")
                self.upsert_daily_rows(conn, rows)
                self.clear_day_failure(conn, code, trade_date)
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                self.queue_day_failure(conn, code, trade_date, name, exc)
            finished.add(code)
            progress(code)
            if consecutive_errors >= 25:
                conn.commit()
                raise MarketDataUnavailable(
                    "连续25只股票请求失败，已停止以防长时间无效重试；"
                    "数据已保存，下次联网正常后继续抓取")
            if len(finished) % BATCH_SIZE == 0:
                conn.commit()

        # BaoStock has a process-global socket: thread-level parallelism is unsafe.
        # On Windows use explicit spawn so independent sessions cannot corrupt results.
        # Tests/mock backends and small groups stay sequential for compatibility.
        bound_method = getattr(self.query_stock_history, "__func__", None)
        enable_parallel = (
            len(tasks) >= DAILY_PARALLEL_THRESHOLD
            and bound_method is BaoStockBackend.query_stock_history
            and not getattr(sys, "frozen", False)
            and os.environ.get("ASHARE_MA_FETCH_WORKERS", "3") != "1"
        )
        with sqlite_connection(self.db_path, timeout=30) as conn:
            if enable_parallel:
                pool = None
                try:
                    workers = max(2, min(4, int(
                        os.environ.get("ASHARE_MA_FETCH_WORKERS", str(DAILY_PARALLEL_WORKERS)))))
                    cb(start_p, f"{trade_date} · 开启 {workers} 条独立 BaoStock 连接")
                    pool = multiprocessing.get_context("spawn").Pool(
                        processes=workers, maxtasksperchild=400)
                    stream = pool.imap_unordered(_day_pool_fetch, tasks, chunksize=1)
                    early_errors = []
                    early_success = 0
                    for _ in tasks:
                        # Poll in short intervals so the stop button remains responsive.
                        waiting_since = time.monotonic()
                        while True:
                            self._check_cancel(conn)
                            try:
                                code, name, fields, values, error = stream.next(timeout=1)
                                break
                            except multiprocessing.TimeoutError:
                                if time.monotonic() - waiting_since >= DAILY_WORKER_STALL_SECONDS:
                                    raise TimeoutError("BaoStock 并行任务长时间无响应")

                        if len(finished) < 12:
                            if error:
                                early_errors.append(code)
                            else:
                                early_success += 1
                        record(conn, code, name, fields, values, error)
                        # All first 12 workers returned connection errors:
                        # retry those 12 sequentially instead of leaving them
                        # stuck in the failure queue.
                        if len(finished) == 12 and early_success == 0:
                            for retry_code in early_errors:
                                finished.discard(retry_code)
                            raise RuntimeError("并行 BaoStock 连接均失败")
                    pool.close()
                    pool.join()
                    pool = None
                except (MarketUpdateCancelled, MarketDataUnavailable):
                    conn.commit()
                    raise
                except Exception as exc:
                    cb(start_p + (end_p - start_p) * len(finished) / total,
                       f"并行接口异常，正在顺序补抓剩余 {total-len(finished)} 只：{str(exc)[:90]}")
                finally:
                    if pool is not None:
                        pool.terminate()
                        pool.join()
            for code, name, _ in tasks:
                self._check_cancel(conn)
                if code in finished:
                    continue
                record(conn, code, name)
                if len(finished) % BATCH_SIZE == 0:
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
            self._check_cancel()
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
            self._check_cancel()
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
        self._cancel_update_event.clear()
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

            self._check_cancel()
            # 先处理以前失败的历史初始化。
            self.retry_init_queue(
                cb,
                12,
                20,
            )

            self._check_cancel()
            # 首次或有新上市股票时补历史。
            self.initialize_missing_histories(
                latest_stocks,
                latest_available,
                cb,
                20,
                66,
            )

            self._check_cancel()
            # 以前中途失败的交易日优先补齐。
            self.retry_partial_dates(
                latest_available,
                cb,
                66,
                80,
            )

            self._check_cancel()
            # 数据库断点之后的新交易日。
            self.process_new_trade_dates(
                latest_available,
                cb,
                80,
                94,
            )

            self._check_cancel()
            turnover_warning = self.backfill_turnover(latest_available, cb)

            self._check_cancel()
            # 行业分类用于全部策略的板块联动。
            self.refresh_industry_cache(
                latest_stocks,
                cb,
                96,
                97,
            )

            self._check_cancel()
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
            raw = pd.read_sql_query("SELECT * FROM daily WHERE code=? AND trade_date<=? ORDER BY trade_date",
                                    conn, params=(code, end_date))
        if not raw.empty:
            g = self._prepare_group(raw)
            results = {key: [] for key, _, _ in STRATEGIES}
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=30) as conn:
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
        with sqlite_connection(self.db_path, timeout=20) as conn:
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



# ============================================================
# 阶段 2/3：Tkinter 每日行情抓取，Tk 完全关闭后才创建 QApplication
# ============================================================

def run_tk_data_phase(backend=None, *, autostart=True):
    """运行 8 阶段数据检查。成功返回 (backend, UpdateResult)，失败可重试。
    后台线程只向 Queue 发送状态，所有 Tk 组件操作只在主线程完成。
    """
    import tkinter as _tk
    from tkinter import ttk as _ttk, messagebox as _messagebox
    engine_backend = backend or BaoStockBackend(DB_PATH)
    root = _tk.Tk()
    root.title("A股 MA 扫描器 · 2/3 行情数据抓取")
    root.geometry("610x540")
    root.minsize(560,500)
    root.configure(bg="#f5f6fa")
    card = _tk.Frame(root,bg="#ffffff",highlightbackground="#e1e5eb",highlightthickness=1)
    card.pack(fill="both",expand=True,padx=16,pady=16)
    heading = _tk.Frame(card,bg="#ffffff")
    heading.pack(fill="x",padx=24,pady=(20,4))
    _tk.Label(heading,text="2/3  ·  行情更新与完整性检查",
              font=("Segoe UI",16,"bold"),bg="#ffffff",fg="#223049").pack(anchor="w")
    _tk.Label(heading,text="八阶段准备完成后，自动进入 PySide6 4:3 主界面",
              font=("Segoe UI",10),bg="#ffffff",fg="#788699").pack(anchor="w",pady=(5,0))
    stage_var=_tk.StringVar(value="准备开始")
    task_var=_tk.StringVar(value="正在读取本地数据库")
    counter_var=_tk.StringVar(value="等待运行")
    time_var=_tk.StringVar(value="已用时 00:00")
    pct_var=_tk.StringVar(value="0%")
    progress=_tk.DoubleVar(value=0)
    _tk.Label(card,textvariable=stage_var,font=("Segoe UI",13,"bold"),
              bg="#ffffff",fg="#263a54").pack(anchor="w",padx=24,pady=(23,8))
    _tk.Label(card,textvariable=task_var,wraplength=530,justify="left",
              font=("Segoe UI",10),bg="#ffffff",fg="#6c7889").pack(anchor="w",padx=24)
    _tk.Label(card,textvariable=counter_var,font=("Segoe UI",10,"bold"),
              bg="#ffffff",fg="#334155").pack(anchor="w",padx=24,pady=(12,8))
    _ttk.Progressbar(card,variable=progress,maximum=100,mode="determinate").pack(
        fill="x",padx=24)
    info=_tk.Frame(card,bg="#ffffff")
    info.pack(fill="x",padx=24,pady=(8,4))
    _tk.Label(info,text="流程进度（按步骤权重，非剩余时间）",
              bg="#ffffff",fg="#7a8799",font=("Segoe UI",9)).pack(side="left")
    _tk.Label(info,textvariable=pct_var,bg="#ffffff",fg="#2776d6",
              font=("Segoe UI",11,"bold")).pack(side="right")
    _tk.Frame(card,height=1,bg="#e7ebf1").pack(fill="x",padx=24,pady=(18,12))
    _tk.Label(card,text="实时任务记录",font=("Segoe UI",10,"bold"),
              bg="#ffffff",fg="#334155").pack(anchor="w",padx=24)
    log=_tk.Text(card,height=8,wrap="word",font=("Segoe UI",9),
                 borderwidth=0,background="#fbfcff",foreground="#66758c")
    log.pack(fill="both",expand=True,padx=24,pady=(6,10))
    log.configure(state="disabled")
    footer=_tk.Frame(card,bg="#ffffff")
    footer.pack(fill="x",padx=24,pady=(0,16))
    _tk.Label(footer,textvariable=time_var,fg="#8590a0",bg="#ffffff").pack(side="left")
    controls=_tk.Frame(footer,bg="#ffffff")
    controls.pack(side="right")
    messages=queue.Queue()
    state={"running":False,"success":None,"start":time.monotonic(),
           "aborted":False,"cancel_requested":False}
    stages=[
        ("检查环境与交易日",0,12),("失败数据补抓",12,20),
        ("历史行情缓存",20,66),("缺失交易日补齐",66,80),
        ("最新行情更新",80,94),("换手率修复",94,96),
        ("行业板块资料",96,98),("数据完整性校验",98,100)]
    def append(message):
        log.configure(state="normal")
        log.insert("end",str(message)+"\n")
        log.see("end")
        lines=int(log.index("end-1c").split(".")[0])
        if lines>140:log.delete("1.0","45.0")
        log.configure(state="disabled")
    def abort():
        if state["running"]:
            if not state["cancel_requested"]:
                state["cancel_requested"] = True
                engine_backend.cancel_update()
                stage_var.set("正在安全停止更新…")
                task_var.set("正在结束 BaoStock 请求并提交已完成的数据，不会删除数据库")
                append("用户请求取消：保存已获取行情，停止后可下次断点续传")
                exit_button.configure(text="正在停止…", state="disabled")
            return
        state["aborted"]=True
        root.quit()
    root.protocol("WM_DELETE_WINDOW",abort)
    exit_button=_ttk.Button(controls,text="退出 / 安全停止",command=abort)
    exit_button.pack(side="right")
    retry=_ttk.Button(controls,text="重新抓取",command=lambda:start())
    retry.pack(side="right",padx=(0,10))
    def start():
        if state["running"]:return
        state["running"]=True
        state["cancel_requested"]=False
        exit_button.configure(text="退出 / 安全停止", state="normal")
        state["start"]=time.monotonic()
        retry.configure(state="disabled")
        progress.set(0)
        pct_var.set("0%")
        task_var.set("准备重新抓取…")
        append("开始读取和更新本地历史行情")
        def work():
            try:
                result=engine_backend.update_all(
                    lambda value,message: messages.put(("progress",float(value),str(message))))
                messages.put(("success",result))
            except MarketUpdateCancelled as exc:
                messages.put(("cancelled",str(exc)))
            except Exception:
                messages.put(("failure",traceback.format_exc()))
        threading.Thread(target=work,daemon=True,name="tk-market-update").start()
    def poll():
        if state["aborted"]:return
        elapsed=int(time.monotonic()-state["start"])
        mins,seconds=divmod(max(0,elapsed),60)
        time_var.set(f"已用时 {mins:02d}:{seconds:02d}")
        for _ in range(80):
            try:event=messages.get_nowait()
            except queue.Empty:break
            kind=event[0]
            if kind=="progress":
                value,message=event[1:]
                progress.set(min(100,max(0,value)))
                pct_var.set(f"{value:.1f}%")
                active=next((i for i,(_,lo,hi) in enumerate(stages)
                             if lo<=value<hi),len(stages)-1)
                stage_var.set(f"阶段 {active+1}/8 · {stages[active][0]}")
                task_var.set(message)
                match = re.search(r"(\d+)\s*/\s*(\d+)", message)
                if match and int(match.group(2)) > 0:
                    complete, total = map(int, match.groups())
                    counter_var.set(
                        f"本阶段已处理 {complete:,}/{total:,} 只"
                        f"（{100 * complete / total:.1f}%）")
                else:
                    counter_var.set(message[:84])
                append(message)
            elif kind=="success":
                state["running"]=False
                state["success"]=event[1]
                stage_var.set("完成 · 行情检查通过")
                pct_var.set("100%")
                progress.set(100)
                append("准备关闭 Tkinter 并进入 PySide6 主工作台")
                root.after(160,root.quit)
                return
            elif kind=="cancelled":
                state["running"]=False
                state["aborted"]=True
                stage_var.set("已安全停止 · 已保存下载进度")
                append(event[1])
                root.after(160,root.quit)
                return
            elif kind=="failure":
                state["running"]=False
                exit_button.configure(text="退出", state="normal")
                stage_var.set("更新失败 · 可重试")
                task_var.set(event[1].splitlines()[-1][:180])
                counter_var.set("未进入主界面；旧数据仍保留")
                append("错误详情：\n"+event[1][-2300:])
                retry.configure(state="normal")
        root.after(150,poll)
    root.after(100,poll)
    if autostart:root.after(190,start)
    try:
        root.mainloop()
    finally:
        # Tk can already be destroyed by the OS/window manager during a stop.
        try:
            if root.winfo_exists():
                root.destroy()
        except _tk.TclError:
            pass
    if state["aborted"] or state["success"] is None:
        return None
    return engine_backend,state["success"]


# ============================================================
# 阶段 3/3：真正的 PySide6 4:3 三栏工作台
# ============================================================
import argparse
try:
    from PySide6.QtCore import Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import (
        QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame,
        QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
        QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
        QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTableWidget,
        QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
    )

except Exception as exc:
    _dependency_import_error('PySide6 / Qt',exc)

BEIJING = timezone(timedelta(hours=8))
STRATEGIES = [
    ("breakout_ma5", "突破 MA5", "均线突破"),
    ("breakout_ma10", "突破 MA10", "均线突破"),
    ("breakout_ma20", "突破 MA20", "均线突破"),
    ("ma5_cross_ma10", "MA5 上穿 MA10", "趋势信号"),
    ("ma5_turn_up", "MA5 拐头向上", "趋势信号"),
    ("ma_convergence_up", "均线粘合向上", "趋势信号"),
    ("volume_turnover", "放量 + 换手率", "量价分析"),
]
PHASES = [
    ("环境检查", 0, 12), ("失败补抓", 12, 20),
    ("历史缓存", 20, 66), ("交易日修复", 66, 80),
    ("每日行情", 80, 94), ("换手率", 94, 96),
    ("行业分类", 96, 98), ("完整性校验", 98, 100),
]


def load_engine():
    return sys.modules[__name__]

class ScanWorker(QThread):
    success = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, backend, request_id, strategy, date, previous, filters, cancel_event=None):
        super().__init__()
        self.backend = backend
        self.request_id = request_id
        self.strategy = strategy
        self.date = date
        self.previous = previous
        self.filters = filters
        self.cancel_event = cancel_event

    def run(self):
        try:
            frame = self.backend.scan_strategy(
                self.strategy, self.date, False, self.previous, self.filters,
                cancel_event=self.cancel_event
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


class VersionWorker(QThread):
    """Check on demand; notify the GUI before streaming the asset."""
    update_found = Signal(str, int)
    progress = Signal(int, int, float)
    status = Signal(str)
    success = Signal(str, object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.cancel_event = threading.Event()

    def cancel_download(self):
        self.cancel_event.set()

    def run(self):
        try:
            message, staged_path = prepare_manual_update(
                Path(__file__).resolve(),
                on_update_found=self.update_found.emit,
                on_progress=self.progress.emit,
                on_status=self.status.emit,
                cancel_event=self.cancel_event,
            )
            if self.cancel_event.is_set():
                if staged_path is not None:
                    Path(staged_path).unlink(missing_ok=True)
                self.cancelled.emit()
            else:
                self.success.emit(message, staged_path)
        except UpdateDownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:
            if self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))


class HistoryWorker(QThread):
    success = Signal(object)
    failed = Signal(str)

    def __init__(self, backend, code, date, filters):
        super().__init__()
        self.backend, self.code, self.date, self.filters = backend, code, date, filters

    def run(self):
        try:
            self.success.emit(self.backend.get_signal_history(self.code, self.date, self.filters))
        except Exception:
            self.failed.emit(traceback.format_exc())


class PriceChart(QWidget):
    """Render price / MA / volume / turnover using local data only."""
    COLORS = {"close": "#222938", "MA5": "#347df4", "MA10": "#e6a24b",
              "MA20": "#a487dc", "volume": "#347df4",
              "放量倍数": "#a487dc", "turnover": "#db8b30"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = pd.DataFrame()
        self.series = ["close", "MA5", "MA10", "MA20"]
        self.signal_date = None
        self.setMinimumHeight(160)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_frame(self, data, series=None, signal_date=None):
        self.data = data.copy() if data is not None else pd.DataFrame()
        self.series = list(series) if series else ["close", "MA5", "MA10", "MA20"]
        self.signal_date = signal_date
        self.update()

    def mouseMoveEvent(self, event):
        if not self.data.empty:
            n = len(self.data)
            idx = max(0, min(n-1, round((event.position().x() - 55)
                                        / max(1,self.width()-74) * max(0,n-1))))
            row = self.data.iloc[idx]
            info = [str(row.get("trade_date", "—"))]
            for key in self.series:
                try:
                    value = float(row[key])
                    if math.isfinite(value):
                        info.append(f"{key}: {value:.3f}")
                except (ValueError, TypeError, KeyError):
                    pass
            self.setToolTip("\n".join(info))
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))
        left, top, right, bottom = 55, 20, rect.width()-19, rect.height()-34
        if self.data.empty or right<=left or bottom<=top+15:
            painter.setPen(QColor("#9ca3b0"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无可用的本地走势图")
            painter.end()
            return
        arrays=[(name,pd.to_numeric(self.data[name],errors="coerce"))
                for name in self.series if name in self.data.columns]
        valid=[float(v) for _,a in arrays for v in a.dropna() if math.isfinite(float(v))]
        if not valid:
            painter.setPen(QColor("#9ca3b0"))
            painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,"所选指标没有可用数值")
            painter.end()
            return
        low,high=min(valid),max(valid)
        gap=(high-low) if high>low else max(abs(high)*.02,1)
        low-=gap*.08
        high+=gap*.08
        n=len(self.data)
        def pt(i,v):
            return (int(left+(right-left)*i/max(1,n-1)),
                    int(bottom-(float(v)-low)*(bottom-top)/(high-low)))
        for i in range(5):
            y=int(top+(bottom-top)*i/4)
            painter.setPen(QPen(QColor("#edf0f5"),1))
            painter.drawLine(left,y,right,y)
            painter.setPen(QColor("#7a8190"))
            painter.drawText(2,y+5,f"{high-(high-low)*i/4:.2f}")
        if self.signal_date and "trade_date" in self.data:
            for i,date in enumerate(self.data["trade_date"].astype(str)):
                if date==str(self.signal_date):
                    x,_=pt(i,low)
                    painter.setPen(QPen(QColor("#d11a2a"),1))
                    painter.drawLine(x,top,x,bottom)
                    painter.drawText(x+2,top+12,"触发")
        for name,values in arrays:
            painter.setPen(QPen(QColor(self.COLORS.get(name,"#347df4")),1.8))
            previous=None
            for i,v in enumerate(values):
                if pd.isna(v) or not math.isfinite(float(v)):
                    previous=None
                    continue
                p=pt(i,v)
                if previous is not None:
                    painter.drawLine(*previous,*p)
                previous=p
        if "trade_date" in self.data:
            painter.setPen(QColor("#7a8190"))
            for i in sorted({round((n-1)*k/5) for k in range(6)}):
                x,_=pt(i,low)
                painter.drawText(max(2,x-17),rect.height()-8,str(self.data.iloc[i]["trade_date"])[5:])
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
    def __init__(self, demo=False, prepared_backend=None, prepared_result=None):
        super().__init__()
        self.demo = demo
        self.engine = load_engine()
        self.backend = prepared_backend
        self.update_result = None
        self.frame = pd.DataFrame()
        self.filtered = pd.DataFrame()
        self.funds = []
        self.fund_source = ""
        self.fund_error_details = ""
        self.current_key = STRATEGIES[5][0]
        self.workers = []
        self.scan_token = 0
        self.chart_token = 0
        self._restart_requested = False
        self._scan_cancel_event = None
        self.selected_stock = None
        self.sector_filter = None
        self.current_filters = RangeFilter()
        self._latest_release_url = None
        self._version_worker = None
        self._update_in_progress = False
        self._download_dialog = None
        self.setWindowTitle("A股 MA 扫描器 v1.3.0 · PySide6 4:3 工作台")
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
        self._make_splash()
        self._make_workspace()
        if demo:
            self._load_demo()
        elif prepared_backend is not None and prepared_result is not None:
            self._on_update_ready(prepared_result)
        else:
            raise RuntimeError("主界面必须等待 Tkinter 行情抓取成功后才能启动")

    def closeEvent(self, event):
        # No QThread can be destroyed while it is still running.
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        if self._version_worker is not None and self._version_worker.isRunning():
            self._version_worker.cancel_download()
        if any(worker.isRunning() for worker in self.workers):
            event.ignore()
            self.statusBar().showMessage("后台任务尚未结束，完成后自动关闭…")
            QTimer.singleShot(250, self.close)
            return
        super().closeEvent(event)

    def _text(self, value, role=None, parent=None):
        label = QLabel(value, parent)
        if role:
            label.setObjectName(role)
        return label

    def _make_splash(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(130, 100, 130, 100)
        lay.addStretch(1)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(35, 30, 35, 35)
        cl.setSpacing(15)
        cl.addWidget(self._text("A股 MA 扫描器", "brand"))
        cl.addWidget(self._text("正在准备今日行情 · 完成后自动打开工作台", "small"))
        self.loading_phase = self._text("检查数据存储", "section")
        cl.addWidget(self.loading_phase)
        self.loading_task = self._text("正在初始化本地数据…", "small")
        self.loading_task.setWordWrap(True)
        cl.addWidget(self.loading_task)
        self.loading_fraction = QProgressBar()
        self.loading_fraction.setRange(0, 100)
        self.loading_fraction.setValue(0)
        self.loading_fraction.setTextVisible(False)
        cl.addWidget(self.loading_fraction)
        self.loading_total = self._text("总体流程：0% · 按阶段计数", "small")
        cl.addWidget(self.loading_total)
        self.loading_stages = self._text("○ 环境检查    ○ 历史修复    ○ 每日行情    ○ 完整性校验", "small")
        self.loading_stages.setWordWrap(True)
        cl.addWidget(self.loading_stages)
        self.loading_elapsed = self._text("已用时 00:00", "small")
        cl.addWidget(self.loading_elapsed)
        buttons = QHBoxLayout()
        self.retry = QPushButton("重试")
        self.retry.clicked.connect(self.start_update)
        self.retry.hide()
        demo_button = QPushButton("先预览界面（模拟数据）")
        demo_button.clicked.connect(self._load_demo)
        buttons.addWidget(demo_button)
        buttons.addStretch(1)
        buttons.addWidget(self.retry)
        exit_button = QPushButton("退出")
        exit_button.clicked.connect(self.close)
        buttons.addWidget(exit_button)
        cl.addLayout(buttons)
        lay.addWidget(card)
        lay.addStretch(1)
        self.page.addWidget(page)
        self.loading_started = datetime.now()
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_clock)
        self._clock.start(1000)

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
        self.header_status = self._text("PySide6 · 4:3 工作台", "small")
        brand.addWidget(self.header_status)
        line.addLayout(brand)
        line.addStretch(1)
        self.refresh_market = QPushButton("更新行情")
        self.refresh_market.clicked.connect(self._restart_pipeline)
        self.refresh_market.setEnabled(not self.demo)
        line.addWidget(self.refresh_market)
        self.update_button = QPushButton("检查更新")
        self.update_button.clicked.connect(self._show_release_info)
        line.addWidget(self.update_button)
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
        self.volume_min.setPlaceholderText("最小放量倍数")
        self.volume_max = QLineEdit()
        self.volume_max.setPlaceholderText("最大放量倍数（可留空）")
        self.turnover_min = QLineEdit("3")
        self.turnover_min.setPlaceholderText("最小换手率%")
        self.turnover_max = QLineEdit()
        self.turnover_max.setPlaceholderText("最大换手率%（可留空）")
        for label, entry in (
            ("放量倍数下限", self.volume_min), ("放量倍数上限", self.volume_max),
            ("换手率下限 (%)", self.turnover_min), ("换手率上限 (%)", self.turnover_max)
        ):
            opt.addWidget(self._text(label, "small"))
            opt.addWidget(entry)
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
        change_row = QHBoxLayout()
        self.change_min = QLineEdit()
        self.change_min.setPlaceholderText("涨幅下限 (%)")
        self.change_max = QLineEdit()
        self.change_max.setPlaceholderText("涨幅上限 (%)")
        for label, entry in (("涨幅下限%", self.change_min), ("涨幅上限%", self.change_max)):
            change_row.addWidget(self._text(label, "small"))
            change_row.addWidget(entry, 1)
            entry.editingFinished.connect(self.apply_filters)
        mid.addLayout(change_row)
        sector_head = QHBoxLayout()
        sector_head.addWidget(self._text("板块信号 · 点击筛选 / 双击查看走势", "section"))
        sector_head.addStretch(1)
        self.sector_reset = QPushButton("全部板块")
        self.sector_reset.clicked.connect(self._reset_sector_filter)
        sector_head.addWidget(self.sector_reset)
        mid.addLayout(sector_head)
        self.sector_table = QTableWidget(0, 3)
        self.sector_table.setHorizontalHeaderLabels(["板块", "今日触发", "板块信号"])
        self.sector_table.verticalHeader().hide()
        self.sector_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sector_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sector_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.sector_table.setMaximumHeight(120)
        self.sector_table.itemSelectionChanged.connect(self._on_sector_selected)
        self.sector_table.cellDoubleClicked.connect(self._open_sector_chart)
        mid.addWidget(self.sector_table)
        results = QHBoxLayout()
        results.addWidget(self._text("选股结果", "section"))
        results.addStretch(1)
        clear = QPushButton("重置条件")
        clear.clicked.connect(self.clear_filters)
        results.addWidget(clear)
        mid.addLayout(results)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["代码", "名称", "板块", "收盘价", "当日涨幅%", "放量倍数", "换手率%"]
        )
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._stock_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
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
        footer.showMessage("本地 SQLite / BaoStock · v1.3.0")

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
        self.page.setCurrentIndex(1)
        self._select_strategy(self.current_key)

    def _update_clock(self):
        if self.page.currentIndex() != 0:
            return
        elapsed = int((datetime.now() - self.loading_started).total_seconds())
        mm, ss = divmod(max(0, elapsed), 60)
        self.loading_elapsed.setText(f"已用时 {mm:02d}:{ss:02d}")

    def start_update(self):
        # 保留 Qt 旧加载页按钮的回调兼容；实际更新始终由 Tkinter 启动阶段执行。
        return self._restart_pipeline()

    def _restart_pipeline(self):
        """Exit Qt, release SQLite lock, then restart in main()."""
        confirm=QMessageBox.question(
            self,"重新更新行情",
            "将关闭当前 PySide6 主界面，然后重新显示 Tkinter 行情更新窗口。继续吗？")
        if confirm!=QMessageBox.StandardButton.Yes:return
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        self.refresh_market.setEnabled(False)
        self.statusBar().showMessage("正在等待扫描和资金后台任务安全退出…")
        self._complete_restart()

    def _complete_restart(self):
        if any(worker.isRunning() for worker in self.workers):
            QTimer.singleShot(200, self._complete_restart)
            return
        self._restart_requested = True
        QApplication.instance().quit()


    def _on_update_progress(self, percent, task):
        self.loading_fraction.setValue(min(100, max(0, round(percent))))
        index = next((i for i, (_, a, b) in enumerate(PHASES) if a <= percent < b), 7)
        self.loading_phase.setText(f"第 {index + 1} / 8 阶段 · {PHASES[index][0]}")
        self.loading_task.setText(task)
        self.loading_total.setText(f"总体流程 {percent:.0f}% · 按步骤权重计算")
        self.loading_stages.setText("   ".join(
            ("✓ " if i < index else "● " if i == index else "○ ") + title
            for i, (title, _, _) in enumerate(PHASES)
        ))

    def _on_update_ready(self, result):
        self.update_result = result
        self.header_status.setText(
            f"行情日期 {result.scan_date} · 完整率 {result.completeness:.2f}%"
        )
        self.page.setCurrentIndex(1)
        self.statusBar().showMessage(
            result.warning or f"{result.scan_date} 本地日线已就绪"
        )
        self._select_strategy(self.current_key)
        self._load_funds_from_cache()
        self.start_fund_refresh()

    def _on_update_failed(self, detail):
        self.loading_task.setText(detail.splitlines()[-1][:220])
        self.loading_phase.setText("行情更新失败")
        self.retry.show()
        self._show_error("更新行情失败", detail)

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
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        self.scan_token += 1
        self._scan_cancel_event = threading.Event()
        self.frame = pd.DataFrame()
        self.sector_filter = None
        self.sector_table.blockSignals(True)
        self.sector_table.setRowCount(0)
        self.sector_table.blockSignals(False)
        self.apply_filters()
        if self.demo:
            self.frame = sample_data(self.current_key)
            self._update_industry_filter()
            self._populate_sector_table()
            self.apply_filters()
            return
        try:
            filters = None
            if self.current_key == "volume_turnover":
                filters = self.engine.RangeFilter(
                    float(self.volume_min.text().strip()),
                    float(self.volume_max.text()) if self.volume_max.text().strip() else None,
                    float(self.turnover_min.text().strip()),
                    float(self.turnover_max.text()) if self.turnover_max.text().strip() else None,
                )
                self.current_filters = filters
        except (ValueError, OverflowError) as exc:
            self.result_info.setText("请输入有效的放量倍数及换手率上下限：" + str(exc))
            return
        self.result_info.setText("正在读取本地行情并计算策略…")
        worker = ScanWorker(self.backend, self.scan_token, self.current_key,
                            self.update_result.scan_date,
                            self.update_result.previous_trade_date, filters,
                            self._scan_cancel_event)
        worker.success.connect(self._scan_ready)
        worker.failed.connect(self._scan_failed)
        self._remember(worker)
        worker.start()
    def _scan_ready(self, token, frame):
        if token != self.scan_token:
            return
        self._scan_cancel_event = None
        self.frame = frame
        self._update_industry_filter()
        self._populate_sector_table()
        self.apply_filters()
    def _scan_failed(self, token, detail):
        if token != self.scan_token:
            return
        self._scan_cancel_event = None
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

    def _populate_sector_table(self):
        self.sector_table.blockSignals(True)
        self.sector_table.setRowCount(0)
        if not self.frame.empty and "板块" in self.frame.columns:
            data = []
            for sector, group in self.frame.groupby("板块", dropna=False):
                name = str(sector or "未分类")
                triggered = int((group["触发日"].astype(str) == str(self.update_result.scan_date)).sum())
                status = str(group["板块信号"].iloc[0]) if "板块信号" in group else "未触发"
                data.append((name, triggered, status))
            data.sort(key=lambda item: (item[2] == "今日触发", item[1], item[0]), reverse=True)
            self.sector_table.setRowCount(len(data))
            for r, (name, count, status) in enumerate(data):
                for c, value in enumerate((name, count, status)):
                    item = QTableWidgetItem(str(value))
                    if c == 0:
                        item.setToolTip(name)
                    if c == 1:
                        item.setData(Qt.ItemDataRole.EditRole, int(count))
                    self.sector_table.setItem(r, c, item)
        self.sector_table.blockSignals(False)
        self.sector_table.resizeColumnsToContents()

    def _reset_sector_filter(self):
        self.sector_filter = None
        self.sector_table.blockSignals(True)
        self.sector_table.clearSelection()
        self.sector_table.blockSignals(False)
        self.apply_filters()

    def _on_sector_selected(self):
        chosen = self.sector_table.selectedItems()
        self.sector_filter = (self.sector_table.item(chosen[0].row(), 0).text()
                              if chosen else None)
        self.apply_filters()

    def _open_sector_chart(self, row, column):
        if self.demo or self.backend is None or self.update_result is None:
            QMessageBox.information(self, "板块走势", "演示模式没有真实板块历史数据。")
            return
        item = self.sector_table.item(row, 0)
        if item is None:
            return
        sector = item.text()
        try:
            data = self.backend.get_sector_chart_data(sector, self.update_result.scan_date)
            if data.empty:
                QMessageBox.information(self, "板块走势", "本地板块数据不足，无法绘图。")
                return
            status = self.backend.get_sector_strategy_status(
                sector, self.current_key, self.update_result.scan_date,
                False, self.update_result.previous_trade_date,
                self.current_filters if self.current_key == "volume_turnover" else None)
            dlg = QDialog(self)
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            dlg.setWindowTitle(f"{sector} · {self.strategy_title.text()}")
            dlg.resize(950, 720)
            layout = QVBoxLayout(dlg)
            layout.addWidget(self._text(f"{sector} · {self.strategy_title.text()} · {status}", "brand"))
            layout.addWidget(self._text("行业成分股后复权价格归一化后的等权指数；板块信号按当前策略计算", "small"))
            history = []
            if "trade_date" in data.columns:
                for date in data["trade_date"].astype(str):
                    if date == self.update_result.scan_date:
                        continue
                    if self.backend._sector_strategy_triggered(
                            data, self.current_key, date,
                            self.current_filters if self.current_key == "volume_turnover" else None):
                        history.append(date)
            layout.addWidget(self._text(
                "历史触发：" + "、".join(history[-5:][::-1])
                if history else "本地走势图范围内无其他历史触发", "small"))
            if self.current_key.startswith("breakout_ma"):
                fields = ["close", "MA" + self.current_key.replace("breakout_ma", "")]
            elif self.current_key in ("ma5_turn_up",):
                fields = ["close", "MA5"]
            elif self.current_key == "ma5_cross_ma10":
                fields = ["close", "MA5", "MA10"]
            elif self.current_key == "volume_turnover":
                fields = ["close"]
            else:
                fields = ["close", "MA5", "MA10", "MA20"]
            chart = PriceChart()
            chart.set_frame(data, series=fields, signal_date=self.update_result.scan_date)
            layout.addWidget(chart, 3)
            if self.current_key == "volume_turnover":
                for field, title in (("放量倍数", "板块放量倍数"), ("turnover", "板块等权换手率%")):
                    view = PriceChart()
                    view.set_frame(data, series=[field])
                    layout.addWidget(self._text(title, "small"))
                    layout.addWidget(view, 1)
            dlg.exec()
        except Exception:
            self._show_error("读取板块历史失败", traceback.format_exc())

    def clear_filters(self):
        self.query.clear()
        self.market.setCurrentIndex(0)
        self.industry.setCurrentIndex(0)
        self.change_min.clear()
        self.change_max.clear()
        self._reset_sector_filter()
        self.apply_filters()
    def apply_filters(self):
        try:
            low = float(self.change_min.text()) if self.change_min.text().strip() else None
            high = float(self.change_max.text()) if self.change_max.text().strip() else None
            if any(v is not None and not math.isfinite(v) for v in (low, high)):
                raise ValueError("涨幅上下限必须为有限数字")
            if low is not None and high is not None and low > high:
                raise ValueError("涨幅下限不能大于上限")
        except ValueError as exc:
            self.result_info.setText("涨幅范围无效：" + str(exc))
            return
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
            if self.sector_filter:
                frame = frame.loc[frame["板块"].astype(str).eq(self.sector_filter)]
            if low is not None or high is not None:
                change = pd.to_numeric(frame["当日涨幅%"], errors="coerce")
                if low is not None:
                    frame = frame.loc[change >= low]
                if high is not None:
                    frame = frame.loc[change <= high]
            self.filtered = frame.copy()
        self._draw_table()
        self.hit_count.setText(f"命中 {len(self.filtered)} 只")
        self.result_info.setText(
            "模拟数据 · 非真实行情" if self.demo else
            f"股票结果 {len(self.filtered)} 只 · {self.update_result.scan_date if self.update_result else '—'}"
        )
    def _draw_table(self):
        # Like v1.2.6, show metrics particular to the active strategy.
        common = ["代码", "名称", "板块", "触发日", "收盘价", "当日涨幅%"]
        if self.current_key == "volume_turnover":
            columns = common + ["放量倍数", "换手率%"]
        elif self.current_key == "ma5_turn_up":
            columns = common + ["MA5", "昨日MA5", "MA5上拐幅度%", "放量倍数", "换手率%"]
        elif self.current_key == "ma_convergence_up":
            columns = common + ["MA5", "MA10", "MA20", "昨日粘合度%",
                                "今日发散度%", "发散增加百分点", "放量倍数", "换手率%"]
        elif self.current_key.startswith("breakout_ma"):
            ma = self.current_key.replace("breakout_ma", "")
            columns = common + [f"MA{ma}", f"突破MA{ma}幅度%", "放量倍数", "换手率%"]
        else:
            columns = common + ["MA5", "MA10", "MA5高于MA10%", "放量倍数", "换手率%"]
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(0 if self.filtered.empty else len(self.filtered))
        for row_number, (_, record) in enumerate(self.filtered.iterrows()):
            for column, key in enumerate(columns):
                raw = record.get(key)
                if key in ("代码", "名称", "板块", "触发日"):
                    value = str(raw) if raw is not None and not pd.isna(raw) else "—"
                else:
                    value = value_text(raw)
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(record.get("_code_full", "")))
                if key not in ("代码", "名称", "板块", "触发日"):
                    try:
                        if raw is not None and math.isfinite(float(raw)):
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
        now = datetime.now(CST)
        if now.weekday() < 5 and now.hour < 18:
            # Current trading-day ranking is not yet settled. Do not throw an
            # error dialog on normal morning startup when no cache exists.
            if not self.funds:
                self.fund_source_label.setText("交易日 18:00 后可刷新 TOP5")
            else:
                self._check_fund_freshness()
            self.statusBar().showMessage("交易日资金榜单尚未结算，18:00 后可刷新；扫描策略不受影响")
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
            self._clear_stock()
            return
        row = selected[0].row()
        if row < 0:
            self._clear_stock()
            return
        code_item = self.table.item(row, 0)
        if code_item is None:
            self._clear_stock()
            return
        full_code = code_item.data(Qt.ItemDataRole.UserRole)
        matching = self.filtered.loc[self.filtered["_code_full"].astype(str) == full_code]
        if matching.empty:
            self._clear_stock()
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
        self.selected_stock = None
        self.chart_token += 1
        self.stock_name.setText("请选择股票")
        self.stock_code.setText("点击列表行查看")
        self.stock_price.setText("—")
        self.stock_change.setText("")
        self.metrics.setText("放量倍数   —\n\n换手率        —\n\n触发日期     —")
        self.chart.set_frame(pd.DataFrame())
        self.chart_status.setText("请选择列表中的股票")
    def _chart_ready(self, token, frame):
        if token == self.chart_token:
            self.chart.set_frame(frame)
            self.chart_status.setText("历史日线 · 来源：本地 SQLite")

    def _chart_failed(self, token, detail):
        if token == self.chart_token:
            self.chart_status.setText("走势图读取失败")
            self._show_error("走势图读取失败", detail)
    def _table_context_menu(self, position):
        item = self.table.itemAt(position)
        if item is None:
            return
        self.table.selectRow(item.row())
        menu = QMenu(self)
        chart_action = menu.addAction("走势图")
        history_action = menu.addAction("信号历史")
        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen == chart_action:
            self._full_chart_dialog()
        elif chosen == history_action:
            self._history_dialog()

    def _full_chart_dialog(self):
        record = getattr(self, "selected_stock", None)
        if record is None:
            return
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setWindowTitle(f'{record.get("名称")} · 最近30日行情与成交指标')
        dialog.resize(960, 760)
        layout = QVBoxLayout(dialog)
        layout.addWidget(self._text(
            f'{record.get("代码")} {record.get("名称")} · 触发日 {record.get("触发日", "—")}', "brand"))
        tabs = QTabWidget()
        price = PriceChart()
        price.set_frame(self.chart.data, signal_date=str(record.get("触发日", "")))
        tabs.addTab(price, "价格与均线")
        metrics = QWidget()
        ml = QVBoxLayout(metrics)
        for field, label in (("volume", "成交量（股）"),
                             ("放量倍数", "放量倍数（与前5个交易日比）"),
                             ("turnover", "换手率%")):
            ml.addWidget(self._text(label, "section"))
            chart = PriceChart()
            chart.set_frame(self.chart.data, series=[field],
                            signal_date=str(record.get("触发日", "")))
            ml.addWidget(chart, 1)
        tabs.addTab(metrics, "成交量 · 放量 · 换手率")
        layout.addWidget(tabs, 1)
        dialog.exec()
    def _history_dialog(self):
        record = getattr(self, "selected_stock", None)
        if record is None:
            return
        if self.demo:
            QMessageBox.information(self, "信号历史", "演示模式不提供真实信号历史。")
            return
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window_closed = [False]
        dialog.finished.connect(lambda *_: window_closed.__setitem__(0, True))
        dialog.destroyed.connect(lambda *_: window_closed.__setitem__(0, True))
        dialog.setWindowTitle(f'{record.get("代码")} {record.get("名称")} · 信号历史')
        dialog.resize(1100, 650)
        layout = QVBoxLayout(dialog)
        notice = self._text("正在后台回算本地历史信号…", "small")
        layout.addWidget(notice)
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["触发日", "策略", "连续日数", "收盘价",
                                        "放量倍数", "换手率%", "参数", "来源"])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        layout.addWidget(table, 1)
        code = str(record["_code_full"])
        name = str(record.get("名称", ""))

        def display(history):
            if window_closed[0] or not dialog.isVisible():
                return
            notice.setText(f"历史共 {len(history)} 条信号 · 双击记录查看触发日走势图")
            table.setSortingEnabled(False)
            table.setRowCount(len(history))
            for index, rec in enumerate(history.to_dict("records")):
                try:
                    payload = json.loads(rec.get("payload") or "{}")
                    if not isinstance(payload, dict):
                        payload = {}
                except (ValueError, TypeError):
                    payload = {}
                filter_key = str(rec.get("filter_key", "固定规则"))
                if filter_key != "固定规则":
                    try:
                        lo, hi, tlo, thi = json.loads(filter_key)
                        filter_key = (f"放量 {lo:g}～{hi if hi is not None else '不限'}；"
                                      f"换手率 {tlo:g}～{thi if thi is not None else '不限'}%")
                    except (TypeError, ValueError):
                        pass
                labels = {k: label for k, label, _ in STRATEGIES}
                row = (rec.get("signal_date"), labels.get(rec.get("strategy"), rec.get("strategy")),
                       rec.get("streak"), payload.get("收盘价"),
                       payload.get("放量倍数"), payload.get("换手率%"),
                       filter_key, rec.get("source"))
                for col, value in enumerate(row):
                    item = QTableWidgetItem(value_text(value) if col in (3, 4, 5) else str(value))
                    item.setData(Qt.ItemDataRole.UserRole, str(rec.get("signal_date", "")))
                    table.setItem(index, col, item)
            table.setSortingEnabled(True)
            table.resizeColumnsToContents()

        def fail(details):
            if not window_closed[0] and dialog.isVisible():
                notice.setText("历史记录回算失败")
                self._show_error("历史读取失败", details)

        def view_record(row, column):
            item = table.item(row, 0)
            if item is None:
                return
            date = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
            try:
                frame = self.backend.get_chart_data(code, date)
                if frame.empty:
                    return
                plot = QDialog(dialog)
                plot.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                plot.setWindowTitle(f"{name} · {date} 触发日")
                plot.resize(900, 620)
                view = QVBoxLayout(plot)
                chart = PriceChart()
                chart.set_frame(frame, signal_date=date)
                view.addWidget(chart)
                plot.exec()
            except Exception:
                self._show_error("历史走势图失败", traceback.format_exc())

        table.cellDoubleClicked.connect(view_record)
        worker = HistoryWorker(self.backend, code, self.update_result.scan_date,
                               self.current_filters)
        worker.success.connect(display)
        worker.failed.connect(fail)
        self._remember(worker)
        dialog.show()
        worker.start()

    def _show_release_info(self):
        # Manual trigger only: no automatic network request at startup.
        if self._version_worker is not None and self._version_worker.isRunning():
            return
        if getattr(self, "_update_in_progress", False):
            return
        self._update_in_progress = True
        self.update_button.setEnabled(False)
        self.statusBar().showMessage("正在检查 GitHub 正式版本…")
        worker = VersionWorker()
        self._version_worker = worker
        self._download_dialog = None

        def show_download(version, size):
            # A window appears only if a newer/repaired release needs download.
            if self._download_dialog is not None:
                return
            dialog = QDialog(self)
            dialog.setWindowTitle(f"正在下载更新 · {version}")
            dialog.setWindowModality(Qt.WindowModality.WindowModal)
            dialog.setMinimumWidth(440)
            layout = QVBoxLayout(dialog)
            title = QLabel(f"发现可用更新 {version}，正在下载正式发行文件")
            title.setWordWrap(True)
            layout.addWidget(title)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            layout.addWidget(bar)
            downloaded = QLabel(f"已下载 0 KB / {size / 1024:.1f} KB · 0.0%")
            layout.addWidget(downloaded)
            speed = QLabel("当前速度：等待响应…")
            layout.addWidget(speed)
            state = QLabel("不限制总下载时长；连接中断后自动续传或重试")
            state.setWordWrap(True)
            layout.addWidget(state)
            cancel_button = QPushButton("取消下载")
            layout.addWidget(cancel_button)

            def request_cancel():
                worker.cancel_download()
                cancel_button.setEnabled(False)
                state.setText("正在取消并清理临时文件…")

            cancel_button.clicked.connect(request_cancel)
            dialog.rejected.connect(worker.cancel_download)
            self._download_dialog = dialog
            self._download_ui = (bar, downloaded, speed, state)
            dialog.show()

        def update_progress(received, size, bytes_per_second):
            if self._download_dialog is None:
                return
            bar, downloaded, speed, state = self._download_ui
            percent = received * 100.0 / size if size else 0.0
            bar.setValue(min(1000, round(percent * 10)))
            downloaded.setText(
                f"已下载 {received / 1024:.1f} KB / {size / 1024:.1f} KB · {percent:.1f}%"
            )
            speed.setText(f"平均速度：{bytes_per_second / 1024:.1f} KB/s")
            state.setText("正在下载…（不限制总下载时长）")

        def update_status(message):
            if self._download_dialog is not None:
                self._download_ui[3].setText(message)
            self.statusBar().showMessage(message)

        def finish_ui():
            if self._download_dialog is not None:
                self._download_dialog.accept()
                self._download_dialog = None
                self._download_ui = None
            self._update_in_progress = False
            self.update_button.setEnabled(True)

        def ready(message, staged):
            finish_ui()
            if staged is None:
                QMessageBox.information(self, "检查更新", message)
                self.statusBar().showMessage(message)
                return
            # Download, SHA-256 verification and compile ran outside the UI thread.
            self.statusBar().showMessage("更新已校验，正在安全替换并重启…")
            try:
                self._install_staged_update(Path(staged))
            except Exception as exc:
                Path(staged).unlink(missing_ok=True)
                self._show_error("自动更新无法启动", str(exc))

        def failed(error):
            finish_ui()
            self.statusBar().showMessage("检查更新失败")
            QMessageBox.warning(self, "更新失败（原程序未更改）", error)

        def cancelled():
            finish_ui()
            self.statusBar().showMessage("已取消下载，原程序未更改")

        worker.update_found.connect(show_download)
        worker.progress.connect(update_progress)
        worker.status.connect(update_status)
        worker.success.connect(ready)
        worker.failed.connect(failed)
        worker.cancelled.connect(cancelled)
        self._remember(worker)
        worker.start()

    def _install_staged_update(self, staged: Path):
        old = Path(__file__).resolve()
        if staged.parent != old.parent or not staged.is_file():
            raise RuntimeError("下载文件不在原程序目录，拒绝更新")
        backup = old.with_name(old.name + ".old-update.bak")
        if backup.exists():
            raise RuntimeError("发现旧版备份，拒绝覆盖；请先人工核查")
        helper_fd, helper_name = tempfile.mkstemp(prefix="ashare-updater-", suffix=".py")
        os.close(helper_fd)
        helper = Path(helper_name)
        ack_fd, ack_name = tempfile.mkstemp(prefix="ashare-update-ack-")
        os.close(ack_fd)
        ack = Path(ack_name)
        ack.unlink()
        try:
            helper.write_text(UPDATE_HELPER, encoding="utf-8")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.Popen([sys.executable, str(helper), str(os.getpid()),
                              str(old), str(staged), str(backup), str(ack),
                              APP_VERSION], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags, cwd=str(old.parent))
        except Exception:
            helper.unlink(missing_ok=True)
            raise
        # closeEvent waits for running scanner threads, so the helper replaces
        # the program only after the old process has released SQLite locks.
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        self.close()
    def _show_error(self, title, details):
        if not self.demo:
            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                with (DATA_DIR / "scanner_error.log").open("a", encoding="utf-8") as log:
                    log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {title}\n{details}\n")
            except OSError:
                pass
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setWindowTitle(title)
        dialog.resize(710, 410)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("错误详情 / traceback（可复制用于排查）"))
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(details)
        layout.addWidget(txt, 1)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--demo",action="store_true",
                        help="直接进入 PySide6 虚构数据界面，不访问行情")
    parser.add_argument("--screenshot",default="",
                        help="CI 渲染 4:3 主窗口并保存 PNG 后退出")
    parser.add_argument("--update-ack",default="",help=argparse.SUPPRESS)
    parser.add_argument("--updated-from",default="",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.update_ack:
        # Helper only accepts this acknowledgement after all top-level imports
        # and syntax checks succeeded, before the potentially long market sync.
        ack = Path(args.update_ack)
        if not ack.name.startswith("ashare-update-ack-"):
            raise RuntimeError("非法更新确认路径")
        ack.write_text("ready",encoding="utf-8")
    if args.demo or args.screenshot:
        backend=None
        result=None
    else:
        phase=run_tk_data_phase()
        if phase is None:
            return 1
        backend,result=phase
    # 阶段2 的 Tk root 已销毁，Qt 独占 GUI 事件循环。
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR","1")
    app=QApplication(sys.argv[:1])
    app.setFont(QFont("Segoe UI",10))
    win=ScannerWindow(
        demo=args.demo or bool(args.screenshot),
        prepared_backend=backend,prepared_result=result)
    win.show()
    if args.screenshot:
        def save_and_quit():
            win.grab().save(args.screenshot)
            app.quit()
        QTimer.singleShot(900,save_and_quit)
    code = app.exec()
    if win._restart_requested:
        # The next Tkinter stage must not race the old process's database lock.
        for worker in list(win.workers):
            if worker.isRunning():
                worker.wait(10000)
        if backend is not None and backend._instance_lock_file is not None:
            backend._instance_lock_file.close()
            backend._instance_lock_file = None
        win.close()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen([sys.executable, str(Path(__file__).resolve())],
                         stdin=subprocess.DEVNULL, creationflags=flags,
                         cwd=str(Path(__file__).resolve().parent))
    return code


if __name__=="__main__":
    raise SystemExit(main())
