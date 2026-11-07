# AShareMAScanner v1.5.0 · VPS BaoStock 行情同步

## 主要变化
- **默认接入已配置的 VPS**：内置 `https://23.95.88.6:8443/marketdata/latest.json`，用户无需手动创建 JSON 配置；保留 `data/marketdata_client.json` 和 `ASHARE_MARKETDATA_URL` 覆盖能力。
- **每次启动优先检查只读数据快照**：对比版本并在行情更新时下载；未变化则复用本地缓存，避免客户端重新逐股抓取 5,000 多只股票。
- **下载安全**：要求 HTTPS 和有效证书，校验文件大小与 SHA-256、ZIP 结构、SQLite `quick_check`、数据表字段和当日完整率。导入过程中失败不会覆盖原有数据库。
- **故障回退**：服务器不可用时使用近期已验证的 BaoStock 缓存；无可用缓存时回退本地 AKShare。
- **隔离数据源**：BaoStock 使用 `data/a_share_baostock_hfq.db`，AKShare 使用 `data/a_share_akshare_hfq.db`，两种来源的后复权行情不混入同一数据库。
- **原功能不变**：保留原有八种策略、三阶段 Tkinter/PySide6 GUI、Excel 导出和同花顺行业资金 TOP5。

## 使用
下载 `AShareMAScanner_v1.5.0.pyw` 或 ZIP，使用 Python 3.10+ 运行。
无需另建配置文件；默认指向用户当前的 VPS HTTPS 数据接口。

若需更换数据源，可在文件同级创建 `data/marketdata_client.json`：
```json
{"manifest_url": "https://example.com:8443/marketdata/latest.json", "min_completeness": 0.995, "offline_cache_max_days": 4}
```

## 兼容与边界
- 原 `v1.3.7` 与数据库文件继续保留，不自动删除。
- 部分行情源的复权调整可能不完全相同；策略结果需注意不同来源间的差异。
- 自动化验证不保证用户设备实际图形环境和网络路径下的运行效果。
- 下载服务端的请求由服务器 Nginx 管理，与桌面应用的软件更新流量相互独立。
- 此版本不改变 VPS 采集程序、Nginx 配置、每日调度和软件镜像限速。
