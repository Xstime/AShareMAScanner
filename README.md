# AShareMAScanner v1.3.0 · 行情抓取提速与可恢复更新

本版重点改进 BaoStock 全市场下载：超过 100 只待抓股票时默认使用三个独立 Python 子进程；允许安全停止后下次断点续传，避免网络故障时反复无效抓取，并显示当前阶段真正完成率和预计剩余时间。详情见 [v1.3.0 更新说明](RELEASE_NOTES_v1.3.0.md)。

**只有点击 PySide6 主界面的「检查更新」才会联网查询 GitHub Release**，每次启动**不会自动检查**软件版本。发现更高版本、或当前版本号相同但发行文件 SHA-256 不一致时，程序自动下载官方 `.pyw` 源文件，验证文件大小、SHA-256、Python 语法和启动参数后，退出旧进程、替换同路径程序并启动新版。新版完成基本启动确认后，更新器及时删除旧程序备份；若启动失败，将尝试恢复旧版。整个过程不触碰同级 `data/` 数据库文件。

**v1.2.8 用户首次升级仍需手动下载安装 v1.3.0；v1.2.9 用户可在主界面点击「检查更新」自动升级。** v1.2.8 没有自动安装功能；v1.2.9 起支持手动触发安全自动升级。仅支持本地可写的单文件 `.pyw`，不支持打包 EXE、只读目录或 zip 内直接运行。

- [v1.3.0 正式发行页面](https://github.com/Xstime/AShareMAScanner/releases/tag/v1.3.0)
- [v1.3.0 更新说明](RELEASE_NOTES_v1.3.0.md)
- 演示界面：`python A股MA扫描器_v1.3.0.pyw --demo`
- 保留原有 `data/a_share_baostock_hfq.db`，不要删除数据库目录。

---


# AShareMAScanner · A股 MA 扫描器 v1.3.0

**单个 Python `.pyw` 文件**，保留三个依次运行的桌面界面。无需制作、安装大型 EXE，但需要系统 Python 3.10+ 和 Tkinter。

## 三阶段启动流程

1. **Python 环境检查与补库（Tkinter）**：检测 pandas、BaoStock、AKShare、PySide6。缺少的库通过清华镜像优先、官方 PyPI 备用的方式安装；已有库时短暂显示“环境检查通过”。
2. **行情抓取与更新（Tkinter）**：八阶段完整进度、逐股处理消息和已用时；异常可重试。数据准备成功后，关闭 Tkinter 窗口。
3. **4:3 主工作台（PySide6）**：默认 **1120×840**，左侧七种策略、中间资金 TOP5/搜索/股票列表、右侧选中股票的价格与 MA5/MA10/MA20 走势图。主窗口直接使用前一阶段的更新结果，**不重复全市场抓取**。

Windows 配置好 Python `.pyw` 文件关联后可直接双击；通常不出现黑色控制台。

## 下载与运行

从 [GitHub Releases](https://github.com/Xstime/AShareMAScanner/releases) 下载：

- `AShareMAScanner_v1.3.0.pyw`：完整的单文件源程序（可重命名为中文）。
- `AShareMAScanner_v1.3.0.zip`：包含中文脚本、`requirements.txt` 和说明。

如果自动补库失败，可手动运行：

```bash
python -m pip install -r requirements.txt
python A股MA扫描器_v1.3.0.pyw
```

**离线体验主界面：**

```bash
python A股MA扫描器_v1.3.0.pyw --demo
```

`--demo` 仅使用明确标记的虚构股票和资金数据，不联网更新行情，主要用于查看 PySide6 的外观。

## 保留的七种选股策略

- 放量突破 MA5、放量突破 MA10、放量突破 MA20
- MA5 上穿 MA10
- 放量倍数与换手率区间筛选
- MA5 首次拐头向上
- MA5 / MA10 / MA20 均线粘合后向上发散

主要行情来自 BaoStock 的后复权日线；保留原数据库、历史数据、行业板块分类以及策略信号。主界面支持按名称/代码搜索股票、市场与行业筛选、点击表格选择股票、走势图和信号历史查看。

## TOP5 资金行业（只展示）

- **仅同花顺**：`ak.stock_fund_flow_industry(symbol="5日排行")`
- 显示最近五日主力资金净流入最高的五个**行业板块**、金额（亿元）和实际抓取时间。
- **不抓成分股，不使用 TOP5 筛选个股，也不再连接东方财富接口。**
- 抓取失败最多重试一次，仍失败保留先前成功的榜单，不影响七种策略。

## 数据保存

仍固定保存在脚本同级：

`data/a_share_baostock_hfq.db`

**升级时原样保留 `data/` 文件夹，勿删除或移动。** 新版本不会清空历史行情。

## 测试说明

GitHub Actions 自动校验 Python 语法、Tkinter 数据窗口、PySide6 真实 4:3 界面、七种策略相关回归、TOP5 同花顺排名/重试/缓存兼容，并生成真实 Qt 截图。曾在 GitHub 云端测通同花顺五日行业资金排名，但第三方接口可用性随网络环境变化；Windows 实机/全面全市场联网测试仍需实际环境确认。

MIT License。内容仅用于技术研究和行情分析，不构成投资建议。
