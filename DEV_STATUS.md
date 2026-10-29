# v1.2.8 三阶段混合 GUI 验收记录

程序入口：`A股MA扫描器_v1.2.8.pyw`。所有 Python 业务代码和 GUI 都在此文件中，不依赖第二个脚本或 PyInstaller 打包。

| 阶段 | 技术 | 行为 |
|---|---|---|
| 1. 环境检查 / 库补齐 | Tkinter | 检查 pandas、BaoStock、AKShare 和 PySide6，必要时自动补装 |
| 2. 行情抓取 / 完整性检查 | Tkinter | 显示真实八阶段进度和错误信息，成功后销毁 Tk 窗口 |
| 3. 主界面 | PySide6 | 4:3 三栏、七种策略、股票列表、右侧走势以及仅展示的同花顺行业资金 TOP5 |

- 每次行情抓取成功后才创建 QApplication，不在两套 GUI 框架之间共享事件循环。
- BaoStock SQLite 原址不动：`data/a_share_baostock_hfq.db`。
- 资金 TOP5 不抓成分股；同花顺失败重试且保留旧快照。
- 代码质量覆盖语法、旧策略回归、Tk 更新阶段、Qt 4:3 主界面和同花顺接口 mock。
- 实际 Windows 设备的 UI、真实全市场抓取与行情接口长期稳定性仍未完整验收。
