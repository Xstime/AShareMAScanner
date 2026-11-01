# AShareMAScanner v1.3.2

**本次版本仅修改安全更新链路、发布同步流程与 macOS 图形界面退出安全性。** 选股策略、BaoStock/同花顺行情获取、SQLite 表结构与 `data/` 均未更改。

## 默认使用已部署的 HTTPS 更新镜像

- 用户点击「检查更新」才联网；程序启动不检查、无定时任务。
- 优先访问固定 HTTPS/IP-SAN 镜像 `https://23.95.88.6:8443/ashare/latest.json`，网络无法连接时尝试 GitHub 最新正式 Release。
- 更新附件只接受 `/ashare/files/<SHA256>/AShareMAScanner_vX.Y.Z.pyw`，严格比对 SHA-256、4 MiB 大小上限、清单版本和固定主机及端口。
- 镜像下载时若遭遇网络断线，可在经过 HTTP 206 / Content-Range 校验后续传；镜像连续失败后才核对 GitHub 官方 Release 的相同版本、大小和摘要，从零重新下载，绝不拼接不同源内容。
- 非法 URL、清单异常、哈希错误、损坏的 Python 源码、版本不符或可疑续传区间一律拒绝安装，不会换源掩盖完整性错误。
- 界面只显示「正在检查更新」「正在下载更新」「正在验证」「已是最新版本」「暂时无法更新」等简单状态与进度、取消按钮。不会在更新窗口暴露 URL、日志、堆栈、令牌。
- 不限制整个更新的累计下载时长；每次读取保留 30 秒无响应超时，失败可尝试重连。
- 保留同版本修复检测、版本防降级、独立临时文件、安全替换、重复更新防护和启动失败回滚。

**部署前提**：公开 CA 正常验证镜像的 IP SAN。程序不会关闭 TLS 验证，也不使用 HTTP、代理设置、证书指纹锁定或并发绕过镜像限速。

## 发行后镜像同步

由 `.github/workflows/sync-mirror.yml` 在 main 分支的 GitHub-hosted runner 上申请短期 GitHub Actions OIDC JWT（audience 精确匹配 `https://23.95.88.6:8443/ashare/publish`），向 VPS 发送 `{"tag":"v1.3.2"}`。收到 HTTP 202 的 `request_id` **不代表完成**；工作流随后读取镜像 `latest.json`，直到本次 `sync_request_id`、`tag_name` 和两个附件摘要与 GitHub 正式 Release 一致才判定成功。失败将报告为失败，不保存 JWT。

## 额外修复：macOS Tkinter → PySide6 切换

解决因 Tkinter `StringVar` / `DoubleVar` 对象在非主线程垃圾回收时可能触发的 `Tcl_AsyncDelete: async handler deleted by the wrong thread` 崩溃；进入 Qt 前在主线程清理已完成 Tk 对象，等待行情工作线程结束。macOS 主界面使用本机字体，避免缺失 Segoe UI 提示。

## 升级

首次接入镜像需要安装完整的新 `.pyw`：旧客户端不会自动认识 VPS 镜像。可从本版 GitHub Release 下载 `AShareMAScanner_v1.3.2.pyw` 或 ZIP，保留现有程序旁的 `data/` 目录，不删除旧数据库。以后通过主窗口“检查更新”即可使用 VPS 镜像优先更新。

## 验收范围

自动化测试覆盖 Linux/Windows/macOS：镜像优先和故障回退、固定 URL 与 SHA 校验、206/ETag 续传和取消、同版本修复、旧版本回滚、数据库目录保留与 PySide6 GUI 实际渲染。已部署 VPS 的 HTTPS/HEAD/206/ETag/SHA 另做真实网络测试；GitHub OIDC 通知与 `sync_request_id` 已在 v1.3.1 上真实验证，v1.3.2 发布后还须以新标签再次确认。

MIT License。软件提供技术研究工具，不构成投资建议。
