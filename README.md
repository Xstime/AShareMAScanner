# A股 MA 扫描器 · v1.2.8

纯 Python / **Tkinter 单文件 `.pyw`**，不使用 PySide6、Qt，也不需要构建 EXE。

## 下载和运行

1. 从 [Releases](https://github.com/Xstime/AShareMAScanner/releases) 下载 `AShareMAScanner_v1.2.8.pyw`，可重命名为 `A股MA扫描器_v1.2.8.pyw`。
2. Windows 已安装 Python 3.10+ 且正确关联 `.pyw` 后，可直接双击文件。缺少库时先显示 **Tkinter 库补齐窗口**；然后显示独立的 **八阶段行情加载窗口**；行情数据通过校验后进入 **Tkinter 4:3 三栏主界面**。
3. `pandas`、`baostock` 是核心依赖；`akshare` 用于同花顺 TOP5。启动时尝试自动安装缺少的依赖（清华镜像优先、官方 PyPI 备用）。离线环境如自动补库失败，可在命令行手动执行：

```bash
python -m pip install -r requirements.txt
python A股MA扫描器_v1.2.8.pyw
```

可从 GitHub ZIP 下载包取得中文文件名的源代码和依赖清单。

## 七种策略（全部保留）

1. 放量突破 MA5
2. 放量突破 MA10
3. 放量突破 MA20
4. MA5 上穿 MA10
5. 放量倍数 / 换手率区间
6. MA5 首次拐头向上
7. MA5/MA10/MA20 均线粘合后首次向上发散

支持行业板块信号、股票搜索和排序、历史信号、收盘价与均线走势图。

## 资金 TOP5（仅展示行业）

- 仅调用 **同花顺** `ak.stock_fund_flow_industry(symbol="5日排行")`，获取过去 5 日资金净流入最高的 **5 个行业**。
- 展示行业名称、排名、净流入金额（亿元）及缓存抓取时间；**不请求行业成分股，不按 TOP5 筛选股票**。
- 请求超时或失败时最多重试一次，仍失败则保留最近成功缓存，七种策略不受影响。
- 更新同花顺榜单成功才清理旧版本历史遗留的成分股记录；不会删除数据库或行情历史。

行情数据来自 **BaoStock**。数据始终保存在脚本所在文件夹下 `data/a_share_baostock_hfq.db`。**升级时原样保留 `data/` 文件夹**。

## 发布与版本说明

- 最新：**v1.2.8**，单 `.pyw` Tkinter，资金 TOP5 只保留同花顺行业排名。
- 旧版：v1.2.6，可在 [历史 Release](https://github.com/Xstime/AShareMAScanner/releases/tag/v1.2.6) 下载。
- v1.2.7 的 PySide6/TOP5 成分股实验**不属于正式版**；此分支不包含其入口和依赖。
- 应用内检查更新只读取固定仓库的正式 GitHub Release，不远程执行代码。

## 已验证范围

自动化验证覆盖 Python 语法、Tkinter Xvfb 图形环境、TOP5 单来源/重试/旧缓存保留、启动与七种策略相关既有回归。曾在 GitHub 云端真实测通同花顺五日资金排名；不保证任何时刻的第三方网站都可用。**尚未完整验证 Windows 实机和 BaoStock 全市场实时逐股更新**。

项目用于研究和行情分析，不构成投资建议；第三方数据接口可能延迟、改变或限制访问。

MIT License。
