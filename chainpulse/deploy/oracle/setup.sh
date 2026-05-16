#!/usr/bin/env bash
# Oracle Cloud Ubuntu 22.04 ARM (Ampere A1) — one-shot ChainPulse setup.
#
# Run as: ubuntu user with sudo. Idempotent — safe to re-run.
#
# Prereq: VM running, ports 80+443 open in Oracle VCN Security List, opc/ubuntu has sudo.
#
# Usage:
#   chmod +x setup.sh
#   sudo bash setup.sh chainpulse.yourdomain.com you@example.com

set -euo pipefail

DOMAIN="${1:-chainpulse.example.com}"
ACME_EMAIL="${2:-admin@example.com}"
APP_USER="chainpulse"
APP_DIR="/opt/chainpulse"
REPO_URL="${REPO_URL:-https://github.com/vaishnavi-1328/chainpulse.git}"
PYTHON_BIN="python3.11"

echo "==> domain=$DOMAIN  email=$ACME_EMAIL  repo=$REPO_URL"

# 1) packages
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential libpq-dev libgomp1 curl git ufw \
  python3.11 python3.11-venv python3.11-dev \
  supervisor redis-server \
  debian-keyring debian-archive-keyring apt-transport-https

# 2) caddy (auto HTTPS)
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  > /etc/apt/sources.list.d/caddy-stable.list
apt-get update -y
apt-get install -y caddy

# 3) firewall — allow 22, 80, 443
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 4) redis — bind localhost only
sed -i 's/^# *requirepass.*/# requirepass disabled — local only/' /etc/redis/redis.conf || true
systemctl enable --now redis-server

# 5) app user
id -u "$APP_USER" &>/dev/null || useradd -m -s /bin/bash "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"

# 6) clone or pull
if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
else
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
fi

# 7) python venv + deps
if [[ ! -d "$APP_DIR/.venv" ]]; then
  sudo -u "$APP_USER" $PYTHON_BIN -m venv "$APP_DIR/.venv"
fi
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/chainpulse/requirements.txt"

# 8) env file
if [[ ! -f "$APP_DIR/chainpulse/.env" ]]; then
  echo "==> WARNING: $APP_DIR/chainpulse/.env missing — copy from .env.example and fill secrets, then re-run."
  exit 1
fi
chown "$APP_USER:$APP_USER" "$APP_DIR/chainpulse/.env"
chmod 600 "$APP_DIR/chainpulse/.env"

# 9) Caddyfile — auto HTTPS + WSS proxy
cat >/etc/caddy/Caddyfile <<EOF
{
    email $ACME_EMAIL
}

$DOMAIN {
    encode zstd gzip

    # API + WebSocket
    @api path /health /auth/* /events* /events/* /graph/* /orders* /orders/* /suppliers/* /onboarding/* /profile/* /docs /openapi.json /ws/events
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }

    # Static frontend
    handle {
        root * $APP_DIR/chainpulse/frontend
        file_server
        try_files {path} /index.html
    }
}
EOF
systemctl enable --now caddy
systemctl reload caddy

# 10) install systemd units
cp "$APP_DIR/chainpulse/deploy/oracle/systemd/"*.service /etc/systemd/system/
systemctl daemon-reload
for svc in chainpulse-api chainpulse-ingest chainpulse-nlp chainpulse-storage; do
  systemctl enable --now "$svc"
done

# 11) daily Neo4j keep-alive
cat >/etc/systemd/system/chainpulse-neo4j-ping.service <<EOF
[Unit]
Description=ChainPulse Neo4j keep-alive
After=network.target

[Service]
Type=oneshot
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/chainpulse/.env
Environment=PYTHONPATH=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/chainpulse/scripts/keep_alive_neo4j.py
EOF

cat >/etc/systemd/system/chainpulse-neo4j-ping.timer <<EOF
[Unit]
Description=Ping Neo4j AuraDB every 12h

[Timer]
OnBootSec=10min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now chainpulse-neo4j-ping.timer

echo
echo "──────────────────────────────────────"
echo "✓ ChainPulse deployed"
echo "  API:       https://$DOMAIN/health"
echo "  Dashboard: https://$DOMAIN/"
echo "  Logs:      journalctl -u chainpulse-api -f"
echo "  Update:    cd $APP_DIR && sudo -u $APP_USER git pull && sudo systemctl restart chainpulse-*"
echo "──────────────────────────────────────"
