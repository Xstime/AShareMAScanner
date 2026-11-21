# v1.5.1 · 更新与行情镜像迁移

- 启动时检查更新和下载软件包改用洛杉矶 VPS 的 IPv6 HTTPS 地址。更新服务不可达时，客户端可以通过 GitHub 官方 Release 检查和下载。
- BaoStock 每日行情使用同一 VPS 的新地址。已有的本地缓存、数据源覆盖设置及 AKShare 回退仍可使用。
- GitHub Actions 通过独立的 IPv4 HTTPS 入口发送经过 OIDC 签名的发布通知并确认同步。软件包和行情快照从 IPv6 入口提供。

- 兼容新版 AKShare 的行情接口名称，以及旧版 AKShare 的原接口。

如果旧客户端无法检查更新，可从本页下载 `AShareMAScanner_v1.5.1.pyw` 或 `AShareMAScanner_v1.5.1.zip`，在原程序目录运行新版以继续使用已有数据。
