# Oracle Cloud Free Deploy — $0/mo always-on

Stack:
- **Oracle Cloud Ampere A1** ARM VM, 2 OCPU + 12 GB RAM (Always Free)
- **Local Redis** (apt package, no Upstash)
- **Caddy** auto-HTTPS reverse proxy
- **systemd** runs 4 procs (api + ingest + nlp + storage)
- **Neon Postgres** Free (no idle pause)
- **Neo4j AuraDB Free** + 12h systemd timer keep-alive
- **Groq** LLM Free
- **Static frontend** served by Caddy from same VM

## 1. Create Oracle Cloud account

1. https://signup.cloud.oracle.com → free tier
2. **Choose home region carefully** — pick one with ARM availability:
   - Frankfurt, Hyderabad, Osaka, Singapore, São Paulo usually OK
   - Avoid Ashburn / Phoenix (overloaded)
3. Verify credit card (no charge — security only)
4. Wait for account provisioning (5-30 min)

## 2. Provision Ampere A1 VM

1. Console → **Compute** → **Instances** → **Create Instance**
2. Name: `chainpulse`
3. **Image and shape** → Change shape:
   - Shape series: **Ampere**
   - Shape: `VM.Standard.A1.Flex`
   - OCPUs: **2**, Memory: **12 GB** (within free quota of 4 OCPU + 24 GB)
4. **Image:** Canonical Ubuntu 22.04
5. **Networking:**
   - Public IPv4: **assign**
   - Add SSH key (upload `~/.ssh/id_rsa.pub`)
6. Create. Wait ~2 min.
7. Note public IP.

If "Out of capacity" → try a different region or retry every few hours.

## 3. Open ports

Console → **Networking** → **Virtual Cloud Networks** → your VCN → "Default Security List" → Add Ingress Rules:
| Source | Protocol | Port |
|---|---|---|
| 0.0.0.0/0 | TCP | 80 |
| 0.0.0.0/0 | TCP | 443 |

(Port 22 already open.)

Inside VM also run:
```bash
sudo iptables -I INPUT -p tcp -m tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp -m tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 4. Point domain at VM

Buy domain (Cloudflare Registrar $3-10/yr, Namecheap $1-15/yr).

Add DNS A record:
- Name: `chainpulse` (or `@` for apex)
- Type: A
- Value: your Oracle VM public IP
- Proxy: **off** (Cloudflare proxy breaks WebSockets at free tier unless on Pro)

## 5. Provision external services

Same as Render path — already on file:
- **Neon Postgres** → https://neon.tech → pooled `postgresql+asyncpg://` URL
- **Neo4j AuraDB Free** → already have
- **Groq key** → already have (or new from console.groq.com)
- News API keys → already have

## 6. Push repo to GitHub

```bash
cd "/Users/vaishnavis/Desktop/OEM sentinal "
git init
git add chainpulse/
echo "chainpulse/.env" >> .gitignore
git commit -m "deploy: chainpulse"
gh repo create chainpulse --public --source=. --push
```

## 7. SSH to VM + run setup

```bash
ssh ubuntu@<VM-public-IP>
# clone temporarily to read setup.sh
git clone https://github.com/YOURUSER/chainpulse.git /tmp/cp
sudo cp /tmp/cp/chainpulse/deploy/oracle/setup.sh /root/

# create .env first
sudo mkdir -p /opt/chainpulse/chainpulse
sudo nano /opt/chainpulse/chainpulse/.env   # paste your secrets

# run setup with your domain + email
sudo REPO_URL=https://github.com/YOURUSER/chainpulse.git \
  bash /root/setup.sh chainpulse.yourdomain.com you@example.com
```

The script:
- Installs Python 3.11, Caddy, Redis, supervisor
- Clones repo to `/opt/chainpulse`
- Creates `chainpulse` user
- Installs Python deps
- Writes Caddy config with auto-HTTPS
- Installs 4 systemd units (api, ingest, nlp, storage)
- Installs 12h Neo4j keep-alive timer
- Enables ufw firewall

## 8. Verify

```bash
ssh ubuntu@VM
sudo systemctl status chainpulse-api chainpulse-ingest chainpulse-nlp chainpulse-storage
sudo journalctl -u chainpulse-api -f      # live logs
curl https://chainpulse.yourdomain.com/health
```

Open browser: `https://chainpulse.yourdomain.com/`

## 9. Update code

```bash
ssh ubuntu@VM
cd /opt/chainpulse
sudo -u chainpulse git pull
sudo systemctl restart chainpulse-*
```

## 10. Apply migrations + Neo4j seed (one-time, from VM)

```bash
ssh ubuntu@VM
cd /opt/chainpulse
sudo -u chainpulse bash -c 'export PYTHONPATH=/opt/chainpulse && /opt/chainpulse/.venv/bin/python chainpulse/scripts/migrate.py'
sudo -u chainpulse bash -c 'export PYTHONPATH=/opt/chainpulse && /opt/chainpulse/.venv/bin/python chainpulse/scripts/seed_neo4j.py'
sudo systemctl restart chainpulse-*
```

## 11. Frontend config

Edit `chainpulse/frontend/js/config.js` BEFORE first deploy:
```js
const def = {
  API_BASE: 'https://chainpulse.yourdomain.com',
  WS_URL:   'wss://chainpulse.yourdomain.com/ws/events',
  ...
};
```
Same for `frontend/onboarding.html` `const CP_API = ...`.

Commit + push. SSH + `git pull` + restart.

## 12. Cost reminder

| Item | Cost |
|---|---|
| Oracle VM (2 OCPU, 12 GB) | **$0** always free |
| Block storage (50 GB default) | $0 (under 200 GB limit) |
| Outbound bandwidth | $0 (under 10 TB/mo) |
| Neon | $0 |
| AuraDB | $0 |
| Groq | $0 |
| Caddy + Let's Encrypt | $0 |
| Domain | $3-15/yr (one-time annual) |
| **TOTAL** | **~$5-15/year** for domain only |

**No monthly charges.**

## 13. Watch list

- **Idle reclaim:** Oracle reserves right to reclaim Always Free VMs idle >7 days. Your 4 daemons hit network constantly — safe.
- **Account verification:** Some signups blocked by fraud detection. Use a less-popular region + standard card.
- **ARM availability:** First-create may fail "out of capacity". Retry in 1-4h or try different region.
- **Snapshots/backups:** Not in free tier. Set up `pg_dump` from Neon + manual git commits.
- **Caddy auto-renew certs:** Built-in, nothing to do.
- **systemd auto-restart:** if a service crashes, restarts in 5-10s.

## 14. Hardening (optional)

```bash
sudo apt install fail2ban
sudo ufw deny 6379       # belt + suspenders — redis already bound localhost
sudo nano /etc/ssh/sshd_config   # set PasswordAuthentication no
sudo systemctl restart ssh
```
