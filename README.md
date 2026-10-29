# AShareMAScanner · A股 MA 扫描器

免费、无付费 Token 的沪深 A 股均线策略扫描器（Python / Tkinter）。

## 当前项目状态

- **已入库源码：v1.2.5**。此提交是已有程序的源码基线，不代表已经完成真实 Windows 全市场联网回归测试。
- **v1.2.6 正在开发测试**：开发入口已经改为 `A股MA扫描器_v1.2.6.pyw`，启动先显示八阶段行情加载窗口（流程进度、逐股真实计数、任务及已用时间），成功后才打开扫描器；包括资金 TOP5 自动切源、界面与操作优化、GitHub 检查更新。
- **尚未发布 GitHub Release**。应用内更新检查只认正式 Release，不把普通 commit 或开发分支误认成新版本。

## 七种扫描策略

1. 放量突破 MA5
2. 放量突破 MA10
3. 放量突破 MA20
4. MA5 上穿 MA10
5. 放量与换手率区间筛选
6. MA5 首次拐头向上
7. MA5 / MA10 / MA20 均线粘合后首次向上发散

个股仅展示最近交易日触发的信号；支持行业板块联动、历史信号查询与走势图。数据来源：**BaoStock**（后复权日线），资金 TOP5 当前基线来源为 **AKShare 转接的东方财富行业资金流**。

## 运行

需要 Python 3.10+，Windows / macOS（需 Tkinter）。

```bash
python -m pip install -r requirements.txt
python A股MA扫描器_v1.2.5.py
```

当前源码也会尝试自动安装缺少的依赖；如自动安装失败，按上述命令手动安装即可。

## v1.2.6 开发版（尚未正式发布）

Windows：下载开发分支的 `A股MA扫描器_v1.2.6.pyw` 和 `requirements.txt` 到同一文件夹，安装依赖后可双击 `.pyw` 启动（Python 的文件关联需要正确配置）。`.pyw` 在 Windows 下通常通过 `pythonw.exe` 启动，因此不会弹出命令行窗口；启动时独立显示八阶段行情加载窗口，更新过程展示阶段进度、已处理/总股票数、当前股票代码和实际用时。行情检查成功后才显示主界面，失败可重试或退出。流程百分比不是时间预计。

macOS / Linux：可以运行 `python A股MA扫描器_v1.2.6.pyw`（需要系统 Tkinter 支持）。开发版还没有作为正式 Release 发布，不建议替换现有稳定文件。

## 数据保存

行情与历史记录固定保存在程序文件同级的 `data/a_share_baostock_hfq.db`，**不会迁移到用户配置目录**。首次启动需下载约 45 个交易日的数据，耗时可能较长。

`data/`、数据库、WAL、日志、缓存等不进入 Git 提交。升级源码时保留原 `data/` 即可延续缓存。不要在更新前删除数据库。

## 正式版本与检查更新

正式发布使用 GitHub **Releases**，版本标签建议形如 `v1.2.6`；应用内将通过固定仓库 `Xstime/AShareMAScanner` 的 Releases API 检查新版本，**仅提供前往下载，不自动执行远程代码**。

[查看 Releases](https://github.com/Xstime/AShareMAScanner/releases)

## 免责声明

本项目用于技术研究和行情分析，不构成投资建议。第三方行情与资金流接口可能出现延迟、口径差异、限流或不可用。

## 许可

MIT License，详见 [LICENSE](LICENSE)。
