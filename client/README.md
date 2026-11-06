# AShareMAScanner · VPS BaoStock 客户端（v1.3.8 开发版）

本版基于 `A股MA扫描器_v1.3.7.pyw`，保留原有 Tkinter → PySide6 三阶段界面、八种策略、图表、同花顺资金榜单及 AKShare 行情下载作为回退。新增可选的 **VPS BaoStock 只读快照优先** 模式，不修改正式版和 `data/a_share_akshare_hfq.db`。

## 获取客户端

在本分支下载：`A股MA扫描器_v1.3.8_dev_BaoStockRemote.pyw`。

## 启用远程同步

服务器须已完成首次数据初始化并发布 `latest.json`、`snapshot.zip`。当前 VPS 的 API 默认只监听 `127.0.0.1:8765`，还需在已有的 HTTPS Nginx server block 中添加原服务器包提供的 `nginx/marketdata.location.conf`（**仅添加对应 location，不替换原有 GitHub Release 镜像路由、证书或代理服务**）。确保外部可通过 HTTPS GET 访问 `https://你的域名或具有有效证书的地址[:端口]/marketdata/latest.json`。

在 `.pyw` 文件同级新建 `data/marketdata_client.json`：

```json
{
  "manifest_url": "https://your-domain.example:8443/marketdata/latest.json",
  "min_completeness": 0.995,
  "offline_cache_max_days": 4
}
```

以上只是示例 URL，不能直接连接；必须替换为实际 HTTPS 地址。也可设置环境变量 `ASHARE_MARKETDATA_URL` 覆盖配置文件中的地址。必须使用有效 TLS 证书；客户端不会关闭证书验证。

若不创建配置文件、也不设置环境变量，则完全保持 v1.3.7 原先的本地 AKShare 更新流程。

## 同步过程

1. 在第二阶段后台线程读取并校验 `latest.json`（含行情日期、数据库结构版本、完整率、ZIP 文件大小和 SHA-256）。
2. 与本地版本比较；同一 SHA-256 时直接复用缓存，拒绝用旧版快照覆盖较新本地数据。
3. 下载时校验来源、文件大小和 SHA-256，限制下载/解压大小，拒绝 ZIP 路径注入或异常结构。
4. 只读取 `marketdata.sqlite3`，执行 SQLite `quick_check`、字段、交易日期与实际存储量验证。
5. 使用临时数据库完成导入，保留已有的本地 `signal_history`、资金缓存等客户端专有表；原子替换至 `data/a_share_baostock_hfq.db`。
6. 启动原有 `AKShareBackend` 的只读扫描能力，继续使用现有八种策略及界面，资金榜单仍走原有客户端接口。

## 出错与数据来源

- **VPS 可用**：使用独立 BaoStock 数据缓存，不再逐只在本机请求行情。
- **VPS 出错但近期有已验证快照**：显示带日期及过期提示的旧快照（默认最长 4 个自然日）。
- **没有可用快照**：按原版流程执行本地 AKShare 下载并使用原 AKShare 数据库。
- **取消同步**：停止下载，保留原有数据库。

注意：BaoStock 和 AKShare 的复权算法/数据源不能假定逐点完全一致，因此分别存入不同 SQLite 文件，切换数据源后历史信号需核对口径。服务器的快照不含同花顺五日资金 TOP5，本功能仍由客户端处理。

## 测试与限制

```
python -m unittest discover -s client/tests -v
python -m py_compile A股MA扫描器_v1.3.8_dev_BaoStockRemote.pyw
```

本地模拟测试覆盖：首次下载、重复快照复用、校验失败回滚、ZIP 损坏、SQLite 数据合并保护、旧快照降级防护、低完整率拒绝、取消、HTTPS 限制及离线缓存。未在用户 VPS 上验证 HTTPS 下载接口，也未做本机 PySide6 GUI 端到端验收；这些要在服务器完成 HTTPS 反向代理后实测。

此客户端是独立开发版本，**不替换** `main` 或最新 GitHub Release。
