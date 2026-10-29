#!/usr/bin/env python3
"""Assemble the clean single-file 3-stage Windows .pyw from reviewed development sources.

This is a developer-only reproducible builder. Published output is self-contained
at source level, except for third-party libraries installed by phase 1.
"""
import urllib.request
from pathlib import Path

BASE="https://raw.githubusercontent.com/Xstime/AShareMAScanner/dev/v1.2.7-pyside6/"
OLD="A股MA扫描器_v1.2.7.pyw"
QT="A股MA扫描器_PySide6_预览.pyw"
OUT=Path(__file__).resolve().parents[1]/"A股MA扫描器_v1.2.8.pyw"

def get(name):
    with urllib.request.urlopen(BASE + urllib.parse.quote(name),timeout=30) as res:
        return res.read().decode("utf-8")

def patch_unique(s,old,new):
    if s.count(old)!=1:
        raise RuntimeError(f"Cannot patch uniquely ({s.count(old)}): {old[:100]}")
    return s.replace(old,new)

def remove_method(s,name):
    start=s.index("    def "+name+"(")
    end=s.index("\n    def ",start+10)
    return s[:start]+s[end:]

HEADER=r'''# -*- coding: utf-8 -*-
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

'''
PHASE2=r'''
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

'''
MAIN=r'''
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
'''

def assemble():
    import urllib.parse
    L=get(OLD)
    Q=get(QT)
    if L.count("class StockScannerApp:")!=1:raise RuntimeError("Legacy class not found")
    core=L[L.index("# ============================================================\n# 配置"):L.index("class StockScannerApp:")]
    core=patch_unique(core,'APP_VERSION = "1.2.7"','APP_VERSION = "1.2.8"')
    core=patch_unique(core,"if endpoint=='em_rank':\n    data=ak.stock_sector_fund_flow_rank(indicator='5日',sector_type='行业资金流')\n    fields=['名称','5日主力净流入-净额']\nelif endpoint=='ths_rank':\n    data=ak.stock_fund_flow_industry(symbol='5日排行')\n    fields=['行业','净额']",
                      "if endpoint=='ths_rank':\n    data=ak.stock_fund_flow_industry(symbol='5日排行')\n    fields=['行业','净额']")
    core=patch_unique(core,"if endpoint not in ('em_rank','ths_rank'):","if endpoint != 'ths_rank':")
    first=core.index("    def _fund_source_order(")
    second=core.index("\n    def ",first+10)
    core=core[:first]+"    def _fund_source_order(self):\n        return ['同花顺']\n"+core[second:]
    core=patch_unique(core,"FROM fund_top5_snapshot ORDER BY rank",
                      "FROM fund_top5_snapshot WHERE source='同花顺' ORDER BY rank")
    core=patch_unique(core,
        "endpoint='em_rank' if source=='东方财富' else 'ths_rank'\n        notify(f'正在读取{source}近5日行业资金净流入排名…')\n        ranked=self._fund_request(endpoint,timeout=self.FUND_RANK_TIMEOUT)\n        name_col,amount_col=('名称','5日主力净流入-净额') if source=='东方财富' else ('行业','净额')",
        "if source != '同花顺':\n            raise ValueError('仅支持同花顺资金排名')\n        notify('正在读取同花顺近5日行业资金净流入排名…')\n        ranked=self._fund_request('ths_rank',timeout=self.FUND_RANK_TIMEOUT)\n        name_col,amount_col='行业','净额'")
    core=patch_unique(core,"multiplier=1 if source=='东方财富' else 100000000","multiplier=100000000")
    core=patch_unique(core,
        "raise RuntimeError('两个来源的行业资金排名均未获取成功，原有榜单缓存已保留。\\n'",
        "raise RuntimeError('同花顺行业资金排名获取失败，原有同花顺榜单缓存已保留。\\n'")

    qtimports=Q[Q.index("from PySide6.QtCore"):Q.index("\nHERE =")]
    strategies=Q[Q.index("STRATEGIES = ["):Q.index("\nPHASES =")]
    widgets=Q[Q.index("class ScanWorker("):Q.index("\ndef main():")]
    a=widgets.index("    def _make_splash(")
    b=widgets.index("    def _make_workspace(",a)
    widgets=widgets[:a]+widgets[b:]
    widgets=patch_unique(widgets,"    def __init__(self, demo=False):",
                         "    def __init__(self, demo=False, backend=None, update_result=None):")
    widgets=patch_unique(widgets,
        "        self.demo = demo\n        self.engine = None\n        self.backend = None\n        self.update_result = None",
        "        self.demo = demo\n        self.engine = sys.modules[__name__]\n        self.backend = backend\n        self.update_result = None\n        self._restart_requested = False")
    widgets=patch_unique(widgets,
        'self.setWindowTitle("A股 MA 扫描器 · PySide6 界面预览")',
        'self.setWindowTitle("A股 MA 扫描器 v1.2.8 · PySide6")')
    widgets=patch_unique(widgets,
        "        self._make_splash()\n        self._make_workspace()\n        if demo:\n            self._load_demo()\n        else:\n            QTimer.singleShot(120, self.start_update)",
        "        self._make_workspace()\n        if demo:\n            self._load_demo()\n        elif backend is not None and update_result is not None:\n            QTimer.singleShot(40,lambda:self._on_update_ready(update_result))\n        else:\n            raise RuntimeError('行情抓取阶段尚未完成')")
    widgets=patch_unique(widgets,
        "self.refresh_market.clicked.connect(self.start_update)",
        "self.refresh_market.clicked.connect(self.restart_pipeline)")
    # Both real and demo data now enter the only Qt workspace page (index 0).
    if widgets.count("self.page.setCurrentIndex(1)")!=2:
        raise RuntimeError("Unexpected Qt page structure")
    widgets=widgets.replace("self.page.setCurrentIndex(1)","self.page.setCurrentIndex(0)")
    a=widgets.index("    def _update_clock(")
    b=widgets.index("    def _on_update_ready(",a)
    widgets=widgets[:a]+'''    def restart_pipeline(self):
        """Exit Qt first, then restart the full three-stage .pyw."""
        self._restart_requested = True
        QApplication.instance().quit()

'''+widgets[b:]
    a=widgets.index("    def _on_update_failed(")
    b=widgets.index("    def _remember(",a)
    widgets=widgets[:a]+widgets[b:]
    widgets=patch_unique(widgets,"PySide6 · 4:3 工作台","v1.2.8 · PySide6 · 4:3 工作台")
    widgets=patch_unique(widgets,"开发预览 · 独立 PySide6 前端 · 不修改原有数据库路径",
                                "三阶段启动完成 · PySide6 4:3 工作台 · SQLite 数据原位保留")
    widgets=patch_unique(widgets,
        "这是独立 PySide6 开发预览，不会覆盖 v1.2.6 正式版。",
        "当前为三阶段 .pyw 开发版，尚未发布正式 Release。")
    widgets=patch_unique(widgets,"两个资金排名来源均失败 · 查看原因",
                                "同花顺资金排名失败 · 查看原因")
    widgets=patch_unique(widgets,"两家数据源的资金排名获取失败；原有榜单缓存未被覆盖。",
                                "同花顺资金排名获取失败；原有同花顺榜单缓存未被覆盖。")
    if "self.start_update" in widgets or "LEGACY_SOURCE" in widgets:
        raise RuntimeError("Unexpected old updater remains in Qt")
    output=HEADER+core+PHASE2+"\n"+qtimports+"\n"+strategies+"\n"+widgets+MAIN
    compile(output,str(OUT),"exec")
    OUT.write_text(output,encoding="utf-8")
    print("CREATED",OUT,"bytes",OUT.stat().st_size)
    assert "stock_sector_fund_flow_rank" not in output
    assert "stock_board_industry_cons" not in output
    assert output.count("class ScannerWindow")==1

if __name__=="__main__":
    assemble()
