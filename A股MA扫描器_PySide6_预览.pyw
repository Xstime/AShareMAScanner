# -*- coding: utf-8 -*-
"""PySide6 4:3 desktop preview for AShareMAScanner.

Usage:
    pip install -r requirements-pyside6.txt
    python A股MA扫描器_PySide6_预览.pyw --demo  # no network, sample data
    python A股MA扫描器_PySide6_预览.pyw         # real BaoStock update and SQLite
The legacy tkinter source is imported only for its existing BaoStockBackend.
No tkinter window is constructed.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

HERE = Path(__file__).resolve().parent
LEGACY_SOURCE = HERE / "A股MA扫描器_v1.2.7.pyw"
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
    if not LEGACY_SOURCE.is_file():
        raise FileNotFoundError(
            f"缺少业务引擎：{LEGACY_SOURCE.name}\n"
            "请从同一个 GitHub 开发分支下载该文件，并放在本程序旁边。"
        )
    loader = SourceFileLoader("ashare_existing_backend", str(LEGACY_SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    spec.loader.exec_module(module)
    return module


class UpdateWorker(QThread):
    progress = Signal(float, str)
    success = Signal(object)
    failed = Signal(str)

    def __init__(self, backend):
        super().__init__()
        self.backend = backend

    def run(self):
        try:
            result = self.backend.update_all(lambda p, t: self.progress.emit(float(p), str(t)))
            self.success.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


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
QPushButton#fundCard { text-align: left; background: #ffffff; border: 1px solid #e1e7f0;
                       border-radius: 11px; padding: 11px 8px; }
QPushButton#fundCard:checked { background: #e9f3ff; border-color: #2081e9; }
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
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.engine = None
        self.backend = None
        self.update_result = None
        self.frame = pd.DataFrame()
        self.filtered = pd.DataFrame()
        self.funds = []
        self.fund_members = {}
        self.fund_source = ""
        self.fund_error_details = ""
        self.fund_ready = False
        self.selected_fund = None
        self.current_key = STRATEGIES[5][0]
        self.workers = []
        self.scan_token = 0
        self.chart_token = 0
        self.setWindowTitle("A股 MA 扫描器 · PySide6 界面预览")
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
        else:
            QTimer.singleShot(120, self.start_update)

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
        self.refresh_market.clicked.connect(self.start_update)
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
            button = QPushButton(f"TOP {i + 1:02d}\n等待数据\n—")
            button.setObjectName("fundCard")
            button.setCheckable(True)
            button.setMinimumHeight(67)
            button.clicked.connect(lambda checked=False, rank=i:self._on_fund_clicked(rank))
            cards.addWidget(button, 1)
            self.fund_cards.append(button)
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
        footer.showMessage("开发预览 · 独立 PySide6 前端 · 不修改原有数据库路径")

    def _load_demo(self):
        self.demo = True
        self.update_result = type("DemoResult", (), {
            "scan_date": "2026-10-29", "previous_trade_date": "2026-10-28",
            "completeness": 100., "expected": 5000, "saved": 5000,
            "warning": "",
        })()
        self.header_status.setText("演示模式 · 全部数据为虚构，仅展示交互")
        self.fund_source_label.setText("演示数据 · 不可用于真实筛选")
        self.funds = [
            {"name": name, "net_yuan": net * 1e8, "source": "演示"}
            for name, net in (("电子", 28.6), ("计算机", 22.1),
                              ("通信", 16.8), ("电力设备", 14.4), ("汽车", 11.2))
        ]
        self.fund_members = {}
        self.fund_ready = False
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
        if self.demo:
            return
        if self.backend is None:
            try:
                self.engine = load_engine()
                self.backend = self.engine.BaoStockBackend(self.engine.DB_PATH)
            except Exception as exc:
                self.loading_task.setText(str(exc))
                self.retry.show()
                return
        self.page.setCurrentIndex(0)
        self.loading_started = datetime.now()
        self.loading_task.setText("正在连接 BaoStock…")
        self.retry.hide()
        worker = UpdateWorker(self.backend)
        worker.progress.connect(self._on_update_progress)
        worker.success.connect(self._on_update_ready)
        worker.failed.connect(self._on_update_failed)
        self._remember(worker)
        worker.start()

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
        self.selected_fund = None
        self.query.clear()
        self.market.setCurrentIndex(0)
        self.industry.setCurrentIndex(0)
        self._render_funds()
        self.apply_filters()

    def _filter_valid_fund_members(self):
        if not self.selected_fund or not self.fund_ready:
            return None
        return self.fund_members.get(self.selected_fund)

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
            members = self._filter_valid_fund_members()
            if members is not None:
                frame = frame.loc[frame["代码"].astype(str).str.zfill(6).isin(members)]
            elif self.selected_fund and self.demo:
                frame = frame.loc[frame["板块"].eq(self.funds[self.selected_fund - 1]["name"])]
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
        else:
            self._clear_stock()

    def _on_fund_clicked(self, index):
        if not self.demo and not self.fund_ready:
            self._show_error(
                "资金筛选尚不可用",
                "行业资金 TOP5 必须同时取得完整的五个行业和对应的同源成分股。"
                "\n目前可以查看缓存榜单，但不会用不完整或旧数据进行筛选。"
                "\n\n" + self.fund_error_details
            )
            self._render_funds()
            return
        new_rank = index + 1
        self.selected_fund = None if self.selected_fund == new_rank else new_rank
        self._render_funds()
        self.apply_filters()

    def _render_funds(self):
        for idx, button in enumerate(self.fund_cards):
            if idx < len(self.funds):
                record = self.funds[idx]
                net = float(record["net_yuan"]) / 1e8
                name = str(record["name"])
                button.setText(f"TOP {idx + 1:02d}\n{name}\n{net:+.2f} 亿")
            else:
                button.setText(f"TOP {idx + 1:02d}\n暂无数据\n—")
            button.blockSignals(True)
            button.setChecked(self.selected_fund == idx + 1)
            button.blockSignals(False)

    def _load_funds_from_cache(self):
        try:
            rows, members = self.backend.load_fund_top5()
            self.funds, self.fund_members = rows, members
            self._check_fund_freshness()
            self._render_funds()
        except Exception as exc:
            self.fund_error_details = str(exc)

    def _check_fund_freshness(self):
        rows, members = self.funds, self.fund_members
        complete = len(rows) == 5 and all(members.get(i) for i in range(1, 6))
        if complete and self.update_result is not None:
            try:
                captured = datetime.strptime(rows[0]["fetched_at"][:10], "%Y-%m-%d").date()
                scanned = datetime.strptime(self.update_result.scan_date, "%Y-%m-%d").date()
                lag = 2 if datetime.now(BEIJING).weekday() >= 5 else 0
                complete = 0 <= (captured - scanned).days <= lag
            except (ValueError, TypeError, KeyError):
                complete = False
        self.fund_ready = bool(complete)
        self.fund_source = rows[0].get("source", "未知来源") if rows else ""
        if self.demo:
            return
        self.fund_source_label.setText(
            (self.fund_source + (" · 可筛选" if self.fund_ready else " · 仅缓存显示"))
            if rows else "暂无资金榜单"
        )
        if not self.fund_ready:
            self.selected_fund = None

    def start_fund_refresh(self):
        if self.demo:
            return
        if self.backend is None or any(isinstance(w, FundWorker) and w.isRunning() for w in self.workers):
            return
        self.fund_error_details = ""
        self.fund_refresh.setEnabled(False)
        self.fund_source_label.setText("获取资金排名和同源成分股中…")
        worker = FundWorker(self.backend)
        worker.notice.connect(self.fund_source_label.setText)
        worker.success.connect(self._fund_ready)
        worker.failed.connect(self._fund_failed)
        worker.finished.connect(lambda: self.fund_refresh.setEnabled(True))
        self._remember(worker)
        worker.start()

    def _fund_ready(self, message, rows, members):
        self.funds, self.fund_members = rows, members
        self._check_fund_freshness()
        self._render_funds()
        self.statusBar().showMessage(message)

    def _fund_failed(self, detail, notices, rows, members):
        self.fund_error_details = detail + "\n\n请求步骤：\n" + notices
        self.funds, self.fund_members = rows, members
        self._check_fund_freshness()
        self._render_funds()
        self.fund_source_label.setText(
            (self.fund_source + " · 旧缓存" if rows else "两个来源均失败 · 查看原因")
        )
        self._show_error(
            "TOP5 刷新失败",
            "自动刷新失败；不会丢弃旧缓存，也不会使用缺少成员的榜单筛选。\n\n"
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
            "这是独立 PySide6 开发预览，不会覆盖 v1.2.6 正式版。\n"
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="不联网，使用显式标记的虚构数据预览界面")
    parser.add_argument("--screenshot", default="", help="保存窗口截图并退出，用于 CI")
    args = parser.parse_args()
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    app = QApplication(sys.argv[:1])
    app.setFont(QFont("Segoe UI", 10))
    win = ScannerWindow(demo=args.demo or bool(args.screenshot))
    win.show()
    if args.screenshot:
        def save_and_quit():
            win.grab().save(args.screenshot)
            app.quit()
        QTimer.singleShot(900, save_and_quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
