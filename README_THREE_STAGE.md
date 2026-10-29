# A股 MA 扫描器 v1.2.8 · 三阶段单文件 .pyw

这是 **Python 源码交付版**，不是 EXE，也不依赖之前的 PySide6 预览程序或旧 Tkinter 主界面。

## Windows 启动

下载 `A股MA扫描器_v1.2.8.pyw`，放到之前的 A 股扫描器目录，保持原来的 `data/a_share_baostock_hfq.db` 不变。

有带 Tkinter 的 Windows Python 3.11+ 即可双击运行。首次启动按需从 PyPI 安装 `pandas`、`baostock`、`akshare`、`PySide6-Essentials`；不打包成 EXE，不需要自行复制 Qt DLL。PySide6 主界面只用到基础 Qt 组件，因此安装 **PySide6-Essentials** 而非完整 PySide6；跳过无须使用的 Qt Addons 等扩展包。首次安装仍可能需要一定时间。

依次显示三个界面：

1. **Tkinter 依赖检查**：每次启动检查库；缺少才从清华镜像 / 官方 PyPI 安装；不会为了使用 TOP5 安装任何行业成分股模块。
2. **Tkinter 行情准备**：在原 SQLite 目录进行 BaoStock 八阶段增量更新，显示每阶段进度、日志及失败重试。
3. **PySide6 主界面**：默认 **1120×840（4:3）**，三栏分别是七种策略、股票结果与同花顺近五日行业资金 TOP5、个股走势和指标。主界面不会重复运行第二阶段抓取。

**TOP5 只显示同花顺的近五日行业板块资金净流入前五名、金额和抓取时间；不读取成分股，不作为股票过滤条件，也不调用东方财富接口。**

行情 SQLite 原地保存，不删除历史数据。原 v1.2.6 正式版不修改。点击主界面「更新行情」将退出 Qt 并重新启动三个阶段，不会同时运行 Tkinter 和 Qt 事件循环。

## 无网络的界面体验 / UI 自动测试

```bash
python A股MA扫描器_v1.2.8.pyw --demo
```

演示仍然经过两个 Tkinter 界面，第三界面使用明确标记的虚构股票和虚构资金值，不调用股票行情接口。此命令会检查和自动安装缺失库，确保 Qt 可运行。

> 此版本需验证 Windows 实机上的 Tk/Qt 安装环境和真实 BaoStock 更新完整流程后才能作为正式 Release 发布。

## 依赖精简审计

| 依赖 | 实际职责 | 决定 |
| --- | --- | --- |
| pandas / NumPy | 历史日线、七种策略计算、分组统计与扫描结果 | 保留，不能安全地只复制几个函数代替 |
| BaoStock | A 股历史行情和交易日下载 | 保留，体积较小，是核心来源 |
| AKShare | 同花顺近五日行业主力资金 TOP5（仅排名） | 保留已验证的接口，不采用自制 HTML 爬虫 |
| PySide6 | 4:3 三栏主界面的 QtCore / QtGui / QtWidgets | 改用 **PySide6-Essentials** 安装，保留代码的 PySide6 导入方式 |
| tkinter、sqlite3、urllib 等 | 启动与行情进度窗口、SQLite 缓存 | Python 标准库，无需 pip 单独安装 |

这是 **精简依赖安装体积**，不是压缩 .pyw 字节码。对已经安装完整 PySide6 的电脑，不主动卸载额外模块，以免影响其他程序。
