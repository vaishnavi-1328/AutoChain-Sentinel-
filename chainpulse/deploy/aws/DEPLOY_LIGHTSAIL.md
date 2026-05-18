# ChainPulse — AWS Lightsail Deploy (cheapest always-on)

End-to-end deploy guide. Tested on Ubuntu 22.04, $5 Lightsail plan (2GB RAM, 1 vCPU, 60GB SSD).

## Architecture

| Layer | Service | Cost |
|---|---|---|
| Backend VM (FastAPI + ingest + NLP + storage + Redis + Caddy) | **AWS Lightsail $5** | $5/mo |
| Postgres | **Neon Free** | $0 |
| Neo4j | **AuraDB Free** | $0 |
| LLM | **Groq Free** | $0 |
| Domain | **DuckDNS** (free subdomain) | $0 |
| HTTPS | **Let's Encrypt** via Caddy | $0 |
| **Total** | | **$5/mo** |

---

## Prerequisites

You already have:
- Lightsail instance running (2GB plan, Ubuntu 22.04, us-east-2 or similar)
- Static IP attached to instance
- Default SSH key downloaded to `~/Downloads/LightsailDefaultKey-<region>.pem`
- DuckDNS subdomain pointing to static IP (e.g. `chainpulse.duckdns.org`)
- DuckDNS token
- Neon Postgres URL (asyncpg form)
- Neo4j AuraDB URI + password
- Groq API key
- Guardian/GNews/GeoNames keys
- Code pushed to GitHub repo

If missing any: see § **Prerequisite signups** at bottom.

---

## Step 1 — SSH into instance

From your Mac:

```bash
chmod 600 ~/Downloads/LightsailDefaultKey-us-east-2.pem
ssh -i ~/Downloads/LightsailDefaultKey-us-east-2.pem ubuntu@<static-ip>
```

If timeout / connection closed:
- Lightsail console → Instances → Stop → Start (wait 60s) → retry
- OR use **"Connect using SSH"** button in console (browser shell, no key needed)

---

## Step 2 — Add 4GB swap (prevents OOM-kill of sshd during XGBoost load)

```bash
# Skip if already done — check first
swapon --show

# If empty, create
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
# Expect: Swap row shows 4.0Gi
```

---

## Step 3 — Clone repo (clean slate)

```bash
sudo rm -rf /opt/chainpulse
sudo mkdir -p /opt/chainpulse
sudo chown ubuntu:ubuntu /opt/chainpulse
cd /opt/chainpulse

# Use YOUR repo URL here
git clone https://github.com/<your-github-user>/AutoChain-Sentinel.git .

# Verify layout — must see `chainpulse/` subdir + .git
ls -la
ls chainpulse/deploy/aws/setup.sh
```

If your repo cloned with a wrapper folder (e.g. `AutoChain-Sentinel/chainpulse`), flatten:

```bash
# only if needed
cd /opt/chainpulse
mv AutoChain-Sentinel/* AutoChain-Sentinel/.git AutoChain-Sentinel/.gitignore .
rmdir AutoChain-Sentinel
```

---

## Step 4 — Write `.env` with production secrets

```bash
sudo cp /opt/chainpulse/chainpulse/.env.example /opt/chainpulse/chainpulse/.env
sudo nano /opt/chainpulse/chainpulse/.env
```

Fill these values (replace placeholders):

```env
APP_ENV=production

DATABASE_URL=postgresql+asyncpg://<neon-user>:<neon-password>@<neon-host>/<db>?sslmode=require

NEO4J_URI=neo4j+s://<your-aura-id>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-aura-password>

REDIS_URL=redis://localhost:6379/0

GROQ_API_KEY=gsk_<your-groq-key>
GROQ_MODEL=llama-3.1-8b-instant

GUARDIAN_API_KEY=<your-key>
GNEWS_API_KEY=<your-key>
GEONAMES_USERNAME=<your-geonames-user>

JWT_SECRET=<run: openssl rand -hex 32>
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

MODEL_DIR=/opt/chainpulse/chainpulse/backend/ml

ALERTS_ENABLED=0
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=alerts@chainpulse.duckdns.org

STREAM_RAW=stream:raw.news
STREAM_PROCESSED=stream:processed.events
STREAM_GROUP=chainpulse-nlp

CORS_ORIGINS=https://chainpulse.duckdns.org
ALLOW_SEED=0
```

Generate JWT_SECRET in another terminal:
```bash
openssl rand -hex 32
```

Save: Ctrl+O, Enter, Ctrl+X.

---

## Step 5 — Run setup script

```bash
sudo bash /opt/chainpulse/chainpulse/deploy/aws/setup.sh <duckdns-subdomain> <duckdns-token> <your-email>
```

Example:
```bash
sudo bash /opt/chainpulse/chainpulse/deploy/aws/setup.sh chainpulse abc12345-aaaa-bbbb-cccc-1234567890ab you@gmail.com
```

What it does (5-8 min):
1. Installs Python 3.11, Redis, Caddy, UFW
2. Creates `chainpulse` system user
3. Creates Python venv at `/opt/chainpulse/.venv`
4. Installs `requirements.txt` (XGBoost, FastAPI, etc — slowest step)
5. Configures Caddy with auto-HTTPS for your DuckDNS domain
6. Writes systemd units for `chainpulse-api`, `chainpulse-ingest`, `chainpulse-nlp`, `chainpulse-storage`
7. Enables DuckDNS auto-update timer (every 5 min)
8. Enables Neo4j keep-alive timer (every 12h, prevents AuraDB pause)
9. Opens firewall ports 22 / 80 / 443

If it errors out, paste output and we fix. Re-run script — it's idempotent.

---

## Step 6 — Migrate Postgres + seed Neo4j

```bash
sudo -u chainpulse bash -c '
cd /opt/chainpulse
source .venv/bin/activate
export PYTHONPATH=$(pwd)
python chainpulse/scripts/migrate.py
python chainpulse/scripts/seed_neo4j.py
'
```

Expect:
```
✅ migrations applied
Seeded 40 ports + 5 OEMs
```

If migrate fails with DNS error: check `DATABASE_URL` format. Must start `postgresql+asyncpg://` (NOT plain `postgresql://`).

---

## Step 7 — Verify services

```bash
sudo systemctl is-active chainpulse-api chainpulse-ingest chainpulse-nlp chainpulse-storage caddy
# Expect: 5x "active"

curl -s http://127.0.0.1/health
# Expect: {"status":"ok"}
```

If any service `failed`:
```bash
sudo journalctl -u chainpulse-api -n 50 --no-pager
```

Common fixes:
- `ModuleNotFoundError`: re-run `pip install -r chainpulse/requirements.txt` as chainpulse user
- `KeyError: DATABASE_URL`: `.env` not loaded → check `/opt/chainpulse/chainpulse/.env` exists, permissions `chainpulse:chainpulse`
- `connection refused` (Postgres): wrong URL or Neon paused (sign in to Neon → resume)

---

## Step 8 — Verify HTTPS from your Mac

```bash
curl -s https://chainpulse.duckdns.org/health
# Expect: {"status":"ok"}

curl "https://chainpulse.duckdns.org/suppliers/geo-resolve?city=Shenzhen&country=CN"
# Expect: lat/lng JSON
```

If TLS handshake fails:
- Wait 60s for Let's Encrypt cert
- Check Caddy log: `sudo journalctl -u caddy -n 50 --no-pager`
- DuckDNS IP correct? `dig chainpulse.duckdns.org +short` (should equal static IP)

---

## Step 9 — Open dashboard

Browser → https://chainpulse.duckdns.org/onboarding.html

1. Register email + password (8+ chars)
2. Auto-redirects to dashboard https://chainpulse.duckdns.org/
3. World map loads, sidebar shows live news
4. Click `+ Add Order` → fill Shenzhen / China / Sea freight / future date / Save
5. Diamond marker appears on map
6. Click `📊 Full analysis` → waterfall + mitigations modal opens

---

## Step 10 — AWS billing alert (do this NOW)

Prevents surprise charges after credits exhaust:

1. AWS Console → search "Billing"
2. Sidebar → Budgets → **Create budget**
3. Template → Monthly cost budget
4. Amount: **$10**
5. Threshold: 80% → email you
6. Save

---

## Updates after code changes

```bash
ssh -i ~/Downloads/LightsailDefaultKey-*.pem ubuntu@<static-ip>
cd /opt/chainpulse
sudo -u chainpulse git pull
sudo systemctl restart chainpulse-api chainpulse-ingest chainpulse-nlp chainpulse-storage
```

For schema changes (new migration):
```bash
sudo -u chainpulse bash -c '
cd /opt/chainpulse
source .venv/bin/activate
export PYTHONPATH=$(pwd)
python chainpulse/scripts/migrate.py
'
sudo systemctl restart chainpulse-*
```

---

## Troubleshooting

### SSH `Connection closed`
Instance OOM-killed sshd. Reboot via Lightsail console (Stop → Start). Swap (Step 2) prevents recurrence.

### Browser SSH `UPSTREAM_ERROR 515`
SSM agent crashed. Reboot instance. If repeats: delete + recreate instance ($5 plan, attach static IP back).

### `chainpulse-nlp` keeps failing
Groq daily quota exhausted (14k req free). Wait until UTC midnight reset OR get fresh key on new Google account.

### `chainpulse-storage` slow / hangs
Neo4j AuraDB paused (free tier sleeps after 3 days idle). Lightsail Neo4j keep-alive timer prevents this — verify:
```bash
sudo systemctl status chainpulse-neo4j-ping.timer
```
If inactive: `sudo systemctl enable --now chainpulse-neo4j-ping.timer`

### High RAM, services killed
Check: `free -h`
If used >1.7GB consistently:
- Increase swap to 6GB: `sudo swapoff /swapfile && sudo fallocate -l 6G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`
- OR upgrade Lightsail to **$10 plan** (4GB RAM)

### Frontend loads but no events
Check WS connection — browser DevTools Network → filter "ws" — should see `wss://chainpulse.duckdns.org/ws/events`. If 502: Caddy not proxying WS. Re-run setup.sh (regenerates Caddyfile).

### Logs
```bash
sudo journalctl -u chainpulse-api -f       # tail live
sudo journalctl -u chainpulse-ingest -n 100 --no-pager
sudo journalctl -u caddy -n 50 --no-pager
```

---

## Prerequisite signups (skip if already done)

| Service | URL | Free tier |
|---|---|---|
| Neon Postgres | https://neon.tech | 0.5GB no idle pause |
| Neo4j AuraDB | https://neo4j.com/cloud/aura-free | 200k nodes, pauses 3d idle |
| Groq | https://console.groq.com/keys | 14k req/day |
| DuckDNS | https://www.duckdns.org | unlimited subdomains |
| Guardian | https://open-platform.theguardian.com/access | 12 req/sec |
| GNews | https://gnews.io | 100 req/day |
| GeoNames | https://www.geonames.org/login | enable web services after signup |
| AWS Lightsail | https://lightsail.aws.amazon.com | $5/mo (credits cover for months) |

---

## Cost projection

| Period | Lightsail | Others | Total |
|---|---|---|---|
| Month 1 (credits) | $0 (covered) | $0 | $0 |
| Month 12 (still on credits) | $0 | $0 | $0 |
| After credits | $5 | $0 | $5/mo |
| Year 2 | $60 | $0 | $60/yr |

Pause anytime: Lightsail → Stop instance → $0 storage cost only ($0.10/mo for 60GB) → restart when needed.
