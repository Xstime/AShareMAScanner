# AShareMAScanner v1.2.8 开发版：独立功能与鲁棒性审计

- 审计日期：2026-10-30
- 审计对象：`dev/v1.2.8-full-fix`，测试版本 `af4db09d2392eb9d41cb73d6536be3b251221c6b`
- 审计基线：保留 v1.2.6 的核心功能，v1.2.8 使用三阶段 Tkinter / Tkinter / PySide6 启动；资金 TOP5 仅来自同花顺，不抓成分股
- 修改限制：仅在开发分支修复与运行测试；**没有合并到 main，也没有重新发布 v1.2.8**
- 正式版状态：v1.2.8 Release 保持 Draft，`main` 保持 `dcdc88253981d4d1a77074ebb42a5595c89f7152`

## 1. 实测结果

| 测试 | 环境 | 结果 | 测试记录 |
| --- | --- | --- | --- |
| 81 项单元/集成/故障注入测试、源码编译及 1120×840 Qt 截图 | Ubuntu + Xvfb + Python 3.12 | 全部通过 | [GitHub Actions](https://github.com/Xstime/AShareMAScanner/actions/runs/40925157690) |
| 60 项原生 Windows 下的 SQLite/Qt/策略/API 模拟测试与源码编译 | windows-latest + Python 3.12 + Qt offscreen | 全部通过 | [GitHub Actions](https://github.com/Xstime/AShareMAScanner/actions/runs/40925157690) |
| BaoStock 真实联网登录及指定后复权日线 | Ubuntu | 通过，返回 3 根日K | [上游验证](https://github.com/Xstime/AShareMAScanner/actions/runs/40924344394) |
| 同花顺五日行业净流入实时接口 `stock_fund_flow_industry(symbol='5日排行')` | Ubuntu | 通过，返回 90 个行业 | [上游验证](https://github.com/Xstime/AShareMAScanner/actions/runs/40924344394) |

**注意计数口径：**Linux 的 81 项中，有 19 项旧测试仍加载 v1.2.6；其余 62 项直接测试修复版或其 Tk/Qt 功能。Windows 的 60 项均针对 v1.2.8 实现。两个环境重复运行的同一测试不算成独立的 141 个功能点。

### 实际验证的主要路径

1. **启动与界面：**依赖检查入口、模拟 Tk 第二阶段、三栏布局、七种策略导航、后台线程扫描、股票详情、历史窗口、真实 Qt 截图。
2. **选股与过滤：**七策略执行、ST 排除、放量与换手率上下限、市场/行业/涨幅过滤、板块选择、策略专属结果列、旧扫描取消及新结果防串台。
3. **数据库及行情：**真实 SQLite 日K、后复权数据结构、均线及成交指标、板块等权指数、首次建库、重复启动仅增量更新、交易日完整率、失败队列记录及下一次启动自动补齐。
4. **异常处理：**无效价格/成交量、NaN/Infinity、损坏数据库原件保留、单实例锁、SQLite 提交与回滚、Windows 文件句柄释放、同花顺请求超时与失败不覆盖已成功的缓存。
5. **历史及图表：**实时线程读取 SQLite 并回填 UI、历史信号回算、连续日数、参数、成交量/换手率图、行业板块历史、窗口关闭时避免滞留 QObject。
6. **更新提示：**新版本识别、不可信更新链接回退、已撤回且高于正式版本号的本地开发版不会再被误报为“最新正式版”。
7. **资金榜单：**同花顺单来源、金额单位换算、TOP5 排序、重复/异常值过滤、失败重试、旧东方财富缓存隔离、交易日未结算时间的友好提示。

## 2. 本轮从零审计发现并在 dev 修复的问题

| 问题 | 证据/影响 | 处理 |
| --- | --- | --- |
| SQLite 连接未确定性关闭 | 30 处 `with sqlite3.connect(...)` 并不能在退出时关闭句柄；Windows 出现 WinError 32 | 引入显式关闭且保留事务提交/回滚的 `sqlite_connection()` |
| 无穷大行情虚增完整率 | 旧 SQLite 若有 `Infinity`，可被视为保存成功甚至跳过补抓 | 对数据库完成率、已保存日K和历史就绪判断统一排除非有限的异常量级 |
| 取消表格选择后详情残留 | `itemSelectionChanged` 触发但空选择直接 `return` | 显式清空股票详情与旧走势图 |
| 信号历史对话框长期累积 | 关闭非模态历史窗口后 QObject 继续由主窗口持有；后台信号可能晚于关闭 | `WA_DeleteOnClose` 与关闭状态守卫，处理坏 JSON |
| 更新检查把被撤回的 v1.2.8 误报为最新版 | 本地版本号高于 GitHub 目前正式版 1.2.6 | 区分“开发/未发布版本”与“最新正式版本” |
| 交易日 18:00 前无 TOP5 缓存时出现错误弹窗 | 正常的未结算时间被当作异常 | 显示结算时间说明，不中断扫描 |
| 源码顶部的旧东方财富/成分股注释过时 | 与单来源 TOP5 的真实行为冲突 | 更新代码说明 |

这些改动都已有对应回归测试，且未修改用户真实行情数据库。

## 3. 尚不能宣称验证完成的部分

- **Windows 用户桌面实机**：验证的是 Windows 原生 GitHub Runner 上的 Qt offscreen 和本地测试数据，尚未在真实用户的高 DPI 桌面、杀毒软件和文件关联环境中验收完整三阶段交互。
- **全市场在线扫描**：仅对 BaoStock 做了小规模真实联网探测；尚未真实抓取、处理和核对整个 A 股市场全部股票的 45 日初始化和持续增量速度。
- **接口可用性**：同花顺和 BaoStock 本次联网返回正确，但第三方接口可能随时更改、限频或连接失败；单次通过不能保证长期可用。
- **长时间运行和大数据量**：尚未执行连续多日/多小时 soak test、海量历史信号下的耗时和内存基准。
- **极短或中途截断的历史返回**：旧后端目前对非空初始历史就可能标记 `history_ready`；长期上市个股若服务端异常返回极短历史，可能需要补充与上市日期相关的历史覆盖判定。此项属于仍需进一步验证的边界风险。
- **Linux CI 中文界面截图**：CI 缺少中文字体，截图中部分汉字显示为方框；Windows 的功能用例通过，但仍需在真实中文桌面验证字体及布局。

## 4. 结论和发布门槛

**已通过当前可执行的静态检查、跨平台离线功能回归、故障注入及两项小规模真实数据源探测；没有发现最新测试集中的未修复断言。**

**不能因此宣称整个产品“完全没有 BUG”或满足正式重新发布。** 上述 Windows 实机、完整全市场、持续运行测试仍然缺席。建议维持 `main` 不变及 v1.2.8 Release Draft，待完整上线前验收后，再单独征得维护者授权。

### 关键证据

- [最新跨平台回归](https://github.com/Xstime/AShareMAScanner/actions/runs/40925157690)
- [真实数据源探测](https://github.com/Xstime/AShareMAScanner/actions/runs/40924344394)
- [本次故障注入测试](https://github.com/Xstime/AShareMAScanner/blob/dev/v1.2.8-full-fix/tests/test_fresh_robustness.py)
- [真实 SQLite/Qt 集成测试](https://github.com/Xstime/AShareMAScanner/blob/dev/v1.2.8-full-fix/tests/test_live_sqlite_gui.py)
