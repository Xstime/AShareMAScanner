# v1.2.8 · Tkinter × PySide6 三阶段单文件版

- **单 `.pyw`，不打包 EXE。** 所需 Python 包运行时检测并尝试补装。
- 启动界面 1：Tkinter 库检查/补齐，包含 PySide6 依赖。
- 启动界面 2：Tkinter 八阶段 BaoStock 行情抓取，实时任务与进度、失败重试。
- 启动界面 3：真正的 PySide6 **1120×840（4:3）** 三栏主界面。Tk 数据窗口销毁后才创建 Qt GUI，**不会重复抓取**。
- 资金 TOP5 只使用同花顺 `5日排行`，**仅展示五个行业板块及净流入金额**，无成分股、无股票联动筛选。
- 保留七种策略、股票列表、右侧 MA5/MA10/MA20 图、股票详情和信号历史。
- 保留原有 SQLite `data/a_share_baostock_hfq.db`，失败更新不覆盖原资金快照。
- 清理 v1.2.7 的 PySide6 双文件预览/旧 Tk 主窗口实验，正式入口是唯一的 `A股MA扫描器_v1.2.8.pyw`。

Windows 需安装 Python 3.10+ 及 Tkinter；这是可编辑的 Python 源程序，**不是免 Python 的可执行文件**。系统配置正确后双击 `.pyw` 即可启动。

验证包含 Github Actions Qt GUI 截图和 Tk/Qt 测试，但不等于 Windows 全市场联网实机验证。
