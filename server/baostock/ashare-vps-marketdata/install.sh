#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash install.sh" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="/opt/ashare-marketdata"
DATA_DIR="/var/lib/ashare-marketdata"
ENV_FILE="/etc/ashare-marketdata.env"

if ! command -v python3 >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip
elif ! python3 -m venv --help >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3-venv python3-pip
fi

if ! id asharedata >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin asharedata
fi

install -d -m 0755 "$APP_DIR"
install -d -o asharedata -g asharedata -m 0750 "$DATA_DIR"
install -d -o asharedata -g asharedata -m 0750 "$DATA_DIR/public" "$DATA_DIR/logs"

rm -rf "$APP_DIR/ashare_server"
cp -a "$SOURCE_DIR/ashare_server" "$APP_DIR/ashare_server"
install -m 0644 "$SOURCE_DIR/requirements.txt" "$APP_DIR/requirements.txt"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0600 "$SOURCE_DIR/.env.example" "$ENV_FILE"
  sed -i "s#^ASHARE_DATA_DIR=.*#ASHARE_DATA_DIR=$DATA_DIR#" "$ENV_FILE"
  chown root:asharedata "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
  echo "Created $ENV_FILE. Set ASHARE_PUBLIC_BASE_URL after configuring HTTPS reverse proxy."
fi

install -m 0644 "$SOURCE_DIR/systemd/ashare-market-update.service" /etc/systemd/system/
install -m 0644 "$SOURCE_DIR/systemd/ashare-market-update.timer" /etc/systemd/system/
install -m 0644 "$SOURCE_DIR/systemd/ashare-market-api.service" /etc/systemd/system/
chown -R root:root "$APP_DIR"
chmod -R a+rX "$APP_DIR"
chown -R asharedata:asharedata "$DATA_DIR"
systemctl daemon-reload
systemctl enable --now ashare-market-api.service
# Do NOT enable the timer until BaoStock probe succeeds. This prevents a
# known 10001011 blacklist from causing repeated scheduled login attempts.

echo
echo "Installed. Next steps:"
echo "  1) Probe BaoStock login: sudo -u asharedata $APP_DIR/.venv/bin/python -m ashare_server.cli probe"
echo "  2) Only if probe succeeds, run first bootstrap: sudo systemctl start ashare-market-update.service"
echo "  3) After a verified snapshot exists, enable daily schedule: sudo systemctl enable --now ashare-market-update.timer"
echo "  4) Check logs: journalctl -u ashare-market-update.service -f"
echo "  5) Add nginx/marketdata.location.conf to the existing HTTPS server block."
echo "  6) Set ASHARE_PUBLIC_BASE_URL in $ENV_FILE and restart ashare-market-api.service."
echo "Daily schedule: 18:00 Asia/Shanghai (10:00 UTC); server timezone is unchanged."
