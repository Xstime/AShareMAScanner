# BaoStock 行情服务 · 服务器端 v1.0.0

此目录是独立服务器端发行包，不属于 AShareMAScanner 桌面端的 GitHub Release。该分支不会自动触发 main 的发布与 VPS 同步。

服务器要求：Ubuntu 24.04；建议 1 GB RAM + 1 GB Swap；现有 Nginx/代理服务不应被覆盖。每天北京时间 18:00（UTC 10:00）运行一次 BaoStock 增量更新。

## VPS 下载与验证

在 VPS Console 中操作（不需要 Mac SSH/SCP）：

```bash
cd /root
curl --fail --location --retry 3 --output AShareMAScanner_VPS_BaoStock_Server_1.0.0.zip 'https://raw.githubusercontent.com/Xstime/AShareMAScanner/dev/vps-baostock-daily-1800/server/baostock/AShareMAScanner_VPS_BaoStock_Server_1.0.0.zip'
echo '811fda9a48bee4e02f8a7fc874fdaf4e590eab5ed162eef7d4369ae0e3fec038  AShareMAScanner_VPS_BaoStock_Server_1.0.0.zip' | sha256sum --check
unzip -l AShareMAScanner_VPS_BaoStock_Server_1.0.0.zip
```

看到 `OK` 并检查 20 个文件后，才开始解压与安装：

```bash
apt-get install -y unzip
unzip -o AShareMAScanner_VPS_BaoStock_Server_1.0.0.zip
cd ashare-vps-marketdata
cat README.md
```

**不要立即运行 install.sh**：先检查里面的 `/etc/systemd/system`、`/opt/ashare-marketdata`、`/etc/ashare-marketdata.env` 路径是否与你当前 VPS 冲突。安装仅应在你确认后进行。

安装后首先执行 BaoStock `probe`。只有 probe 成功且首次数据库构建完成，才启用 systemd timer；黑名单 `10001011` 时停止尝试，不要暴力重试。

```bash
sudo bash install.sh
sudo -u asharedata /opt/ashare-marketdata/.venv/bin/python -m ashare_server.cli probe
```

服务监听 `127.0.0.1:8765`；公网 HTTPS 需要在现有 Nginx server 块手动追加 `nginx/marketdata.location.conf`，不要修改现有 `/ashare/` Release 镜像路由。

**发布数据规则**：首次保留80交易日，日后只更新新增/失败的数据；最新交易日完整率未达阈值时不发布快照；SHA-256 校验数据库 ZIP。旧客户端仍需另行开发远程数据库同步，**当前桌面 v1.3.7 不会自动下载本服务的行情数据库**。
