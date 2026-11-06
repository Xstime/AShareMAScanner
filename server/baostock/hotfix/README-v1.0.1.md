# BaoStock v1.0.1 SQLite lock hotfix

The v1.0.0 updater kept a SQLite write transaction open while requesting another BaoStock stock. The provider records each request in api_usage using a second connection, so the updater could repeatedly fail with `database is locked`.

This patch changes only `ashare_server/updater.py`: commits every stock's write transaction in both historical initialization and daily updates. It preserves the SQLite database and all existing systemd, nginx, and Shadowsocks settings. A regression test covering initial data and next-day incremental updates passed (13/13).

Verified target (v1.0.0):
- old updater SHA-256: `3b0f97c04e52cfd37b43fd974c861846a437e33bb26dea27f50fcd3e387cedaf`
- patch SHA-256: `e64c171c78ec2003232cfaa7250d3ebc0688a7f225bd9d7fc79fddb6cfae4e9e`
- updated updater SHA-256: `cb4e9fa7adb2af8a1a27cfd3745553b37fe807ea984c3bec4a02beb0d6f1beba`

On the VPS, ensure the update service has stopped and MainPID=0. Download the patch via HTTPS from this branch; verify its SHA-256. Run `patch --dry-run -p1 -d /opt/ashare-marketdata < /root/ashare-v1.0.1.patch`. Only after verification, back up the installed updater.py, then apply once with `patch -p1 -d /opt/ashare-marketdata < /root/ashare-v1.0.1.patch`. Verify the updated updater SHA-256 before starting the updater service. The timer must remain disabled until a complete snapshot is published.

No need to re-run install.sh or delete existing databases.
