#!/usr/bin/env bash
# AWS Lightsail / EC2 Ubuntu 22.04 — one-shot ChainPulse setup.
#
# Idempotent — safe to re-run.
#
# Prereq:
#   - Lightsail instance running, ports 22+80+443 open in Networking firewall
#   - Free domain via DuckDNS: https://www.duckdns.org → sign in (Google/GitHub) → pick
#     subdomain (e.g. "chainpulse") → copy your token from top of page.
#
# Usage:
#   chmod +x setup.sh
#   sudo bash setup.sh <duckdns-subdomain> <duckdns-token> <acme-email>
#   e.g.
#   sudo bash setup.sh chainpulse abc12345-aaaa-bbbb-cccc-1234567890 you@gmail.com
#
# IP-only mode (no HTTPS, browsers warn):
#   sudo bash setup.sh IPONLY '' ''

set -euo pipefail

DUCK_SUB="${1:-IPONLY}"
DUCK_TOKEN="${2:-}"
ACME_EMAIL="${3:-admin@example.com}"

if [[ "$DUCK_SUB" == "IPONLY" ]]; then
  DOMAIN=""
  USE_HTTPS=0
else
  DOMAIN="${DUCK_SUB}.duckdns.org"
  USE_HTTPS=1
  if [[ -z "$DUCK_TOKEN" ]]; then
    echo "ERROR: DuckDNS token required for HTTPS mode" >&2
    exit 1
  fi
fi

APP_USER="chainpulse"
APP_DIR="/opt/chainpulse"
REPO_URL="${REPO_URL:-https://github.com/vaishnavi-1328/chainpulse.git}"
PYTHON_BIN="python3.11"

echo "==> domain=${DOMAIN:-<IP-only>}  https=$USE_HTTPS  email=$ACME_EMAIL  repo=$REPO_URL"

# 1) packages
apt-get update -y
add-apt-repository -y ppa:deadsnakes/ppa  # python 3.11 on 22.04
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential libpq-dev libgomp1 curl git ufw \
  python3.11 python3.11-venv python3.11-dev \
  redis-server \
  debian-keyring debian-archive-keyring apt-transport-https

# 2) caddy (auto HTTPS)
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  > /etc/apt/sources.list.d/caddy-stable.list
apt-get update -y
apt-get install -y caddy

# 3) firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 4) redis — local only
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

# 9) DuckDNS auto-update timer (only if HTTPS mode)
if [[ "$USE_HTTPS" == "1" ]]; then
  install -d /opt/duckdns
  cat >/opt/duckdns/duck.sh <<EOF
#!/usr/bin/env bash
echo url="https://www.duckdns.org/update?domains=$DUCK_SUB&token=$DUCK_TOKEN&ip=" \
  | curl -k -o /var/log/duckdns.log -K -
EOF
  chmod 700 /opt/duckdns/duck.sh
  /opt/duckdns/duck.sh

  cat >/etc/systemd/system/duckdns.service <<EOF
[Unit]
Description=DuckDNS update
[Service]
Type=oneshot
ExecStart=/opt/duckdns/duck.sh
EOF
  cat >/etc/systemd/system/duckdns.timer <<EOF
[Unit]
Description=Update DuckDNS every 5 minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now duckdns.timer
fi

# 10) Caddyfile
if [[ "$USE_HTTPS" == "1" ]]; then
  cat >/etc/caddy/Caddyfile <<EOF
{
    email $ACME_EMAIL
}

$DOMAIN {
    encode zstd gzip

    @api path /health /auth/* /events* /events/* /graph/* /orders* /orders/* /suppliers/* /onboarding/* /profile/* /docs /openapi.json /ws/events
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * $APP_DIR/chainpulse/frontend
        file_server
        try_files {path} /index.html
    }
}
EOF
else
  # IP-only fallback — HTTP on :80, no HTTPS
  cat >/etc/caddy/Caddyfile <<EOF
:80 {
    encode zstd gzip

    @api path /health /auth/* /events* /events/* /graph/* /orders* /orders/* /suppliers/* /onboarding/* /profile/* /docs /openapi.json /ws/events
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * $APP_DIR/chainpulse/frontend
        file_server
        try_files {path} /index.html
    }
}
EOF
fi

systemctl enable --now caddy
systemctl reload caddy

# 11) systemd units
cp "$APP_DIR/chainpulse/deploy/aws/systemd/"*.service /etc/systemd/system/
systemctl daemon-reload
for svc in chainpulse-api chainpulse-ingest chainpulse-nlp chainpulse-storage; do
  systemctl enable --now "$svc"
done

# 12) Neo4j keep-alive
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

PROTO=$([[ "$USE_HTTPS" == "1" ]] && echo "https" || echo "http")
TARGET=$([[ "$USE_HTTPS" == "1" ]] && echo "$DOMAIN" || echo "<lightsail-public-ip>")

echo
echo "──────────────────────────────────────"
echo "✓ ChainPulse deployed"
echo "  API:       $PROTO://$TARGET/health"
echo "  Dashboard: $PROTO://$TARGET/"
echo "  Logs:      journalctl -u chainpulse-api -f"
echo "  Update:    cd $APP_DIR && sudo -u $APP_USER git pull && sudo systemctl restart chainpulse-*"
echo "──────────────────────────────────────"
