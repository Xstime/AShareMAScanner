# v1.2.8 修复版（2026-10-30）

本次替换了先前已撤回的 v1.2.8 发行文件；版本号保持 **v1.2.8**，但源文件和下载包均以本次修复后的 main 提交为准。旧版文件请勿继续使用。

## 功能修复
- 修复信号历史运行异常，恢复完整历史日期、策略、连续日数、参数和指标。
- 恢复七策略各自的 MA / 量价指标列，以及第五策略放量倍数、换手率的上下限。
- 恢复涨幅区间筛选、板块信号列表与板块走势、完整个股 MA/成交量/换手率走势图、右键菜单。
- 修复 GitHub 版本检查，正确识别未正式发布的开发版本，不自动安装或修改数据库。
- TOP5 仅使用同花顺五日排行，保留网络失败重试和旧同花顺榜单；交易日 18:00 前不给出错误弹窗。
- Windows SQLite 连接显式关闭，保留事务回滚；保护异常行情、失败队列与原有数据库。
- 修复股票选中状态残留、历史弹窗释放、后台扫描取消及退出/重新更新时的线程交接。

## 启动与要求
- 单文件 Python `.pyw`，三个阶段：Tkinter 环境检查 → Tkinter BaoStock 八阶段行情更新 → PySide6 三栏主界面。
- 需 Python 3.10+、Tkinter 和 `requirements.txt` 所列依赖；**不是独立 EXE**。
- 更新时**保留脚本同级的 `data/` 目录**；不要删除或覆盖 `data/a_share_baostock_hfq.db`。
- 七个扫描策略保留；近五日行业净流入 TOP5 **不抓成分股，也不用于筛选个股**。

## 验证记录
- [Linux 81 项 + Windows 60 项回归测试全部通过](https://github.com/Xstime/AShareMAScanner/actions/runs/40925157690)。
- [BaoStock 后复权日线与同花顺五日行业资金接口真实读取成功](https://github.com/Xstime/AShareMAScanner/actions/runs/40924344394)。
- [独立审计报告](https://github.com/Xstime/AShareMAScanner/blob/main/AUDIT_DEV_v1.2.8_2026-10-30.md)。

**测试边界**：尚未验收 Windows 用户真实桌面完整交互、数千只股票的全市场持续联网更新性能、以及多日长时间运行。通过现有测试不代表没有未知缺陷。

MIT License；仅供行情研究分析，不构成投资建议。
