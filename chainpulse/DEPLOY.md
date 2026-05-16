# ChainPulse — Production Deploy ($7/mo)

Always-on stack: **Render Web Service** (backend + workers, supervisord) + **Neon** (Postgres) + **Upstash** (Redis) + **AuraDB Free** + 12h keep-alive cron + **Cloudflare Pages** (frontend) + **Groq** (LLM).

---

## 1. Provision managed services (~15 min)

### Neon Postgres (no idle pause)
1. https://neon.tech → sign in with GitHub
2. Create project "chainpulse"
3. Dashboard → Connection string → "Pooled connection" + "Python" + "asyncpg" → copy.
   Looks like: `postgresql+asyncpg://user:pass@ep-xxx.pooler.neon.tech/neondb?sslmode=require`

### Upstash Redis
1. https://upstash.com → sign in
2. Create Database → free → region near Oregon
3. Details tab → copy "redis-cli" URL (rediss://)

### Neo4j AuraDB Free
1. https://neo4j.com/cloud/aura-free/ → create instance
2. Save the password (shown once)
3. Capture URI: `neo4j+s://xxx.databases.neo4j.io`

### Groq
1. https://console.groq.com/keys → create key (`gsk_...`)

### Already have
- Guardian API key
- GNews key

---

## 2. Apply DB migration once (locally)

```bash
cd "/Users/vaishnavis/Desktop/OEM sentinal "
source chainpulse/.venv/bin/activate
export PYTHONPATH="$(pwd)"
export DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.pooler.neon.tech/neondb?sslmode=require"
export NEO4J_URI="neo4j+s://...neo4j.io"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="..."

python chainpulse/scripts/migrate.py
python chainpulse/scripts/seed_neo4j.py
```

---

## 3. Push code to GitHub

```bash
cd "/Users/vaishnavis/Desktop/OEM sentinal "
git init  # if not already
git add chainpulse/ .gitignore
git commit -m "chainpulse deploy"
gh repo create chainpulse --public --source=. --remote=origin --push
# or manually: https://github.com/new → push
```

Check `.gitignore` excludes `.env` and `.venv/`.

---

## 4. Deploy to Render

1. https://dashboard.render.com → "New" → "Blueprint"
2. Connect GitHub → select repo
3. Render detects `chainpulse/render.yaml` → creates 2 services (web + cron)
4. Click "Apply"
5. After services created → web service → Environment tab → fill secrets:

```
DATABASE_URL       postgresql+asyncpg://user:pass@ep-xxx.pooler.neon.tech/neondb?sslmode=require
NEO4J_URI          neo4j+s://xxx.databases.neo4j.io
NEO4J_USER         neo4j
NEO4J_PASSWORD     <yours>
REDIS_URL          rediss://default:xxx@xxx.upstash.io:6379
GROQ_API_KEY       gsk_xxx
GUARDIAN_API_KEY   <yours>
GNEWS_API_KEY      <yours>
CORS_ORIGINS       https://chainpulse.pages.dev,http://localhost:3000
ALERTS_ENABLED     0
```

Repeat for `neo4j-keep-alive` cron (only NEO4J_* needed).

6. Render builds Docker image + deploys → live at `https://chainpulse.onrender.com`
7. Test: `curl https://chainpulse.onrender.com/health` → `{"status":"ok"}`

---

## 5. Deploy frontend to Cloudflare Pages

Edit `chainpulse/frontend/js/config.js` first:
```js
const def = {
  API_BASE: 'https://chainpulse.onrender.com',
  WS_URL:   'wss://chainpulse.onrender.com/ws/events',
  ...
};
```
Edit `chainpulse/frontend/onboarding.html` line `const CP_API = ...` same URL.
Commit + push.

Then:
1. https://dash.cloudflare.com → Pages → "Create application" → Connect to Git
2. Pick repo
3. Build config:
   - Build command: *(blank — static)*
   - Build output dir: `chainpulse/frontend`
4. Deploy
5. Live at `https://chainpulse.pages.dev`

Update Render `CORS_ORIGINS` to include the Pages URL.

---

## 6. Smoke checklist

- [ ] `https://chainpulse.onrender.com/health` returns `{"status":"ok"}`
- [ ] `https://chainpulse.pages.dev` loads dark dashboard
- [ ] Title bar `LIVE` within 2s
- [ ] News pins on map within 90s (next Guardian poll)
- [ ] Register at `/onboarding.html`
- [ ] `+ Add Order` → drawer slides in
- [ ] Type Shenzhen + China + blur → mini map pin shows
- [ ] Save order → diamond marker + toast
- [ ] `📊 Full analysis` → waterfall + map + table + mitigations
- [ ] Click pin → `◈ View supply chain graph` → D3 graph + SHAP panel

---

## 7. Cost ceiling — under $10/mo

| Item | Cost | Quota |
|---|---|---|
| Render Web Starter | **$7/mo** | 512MB, always-on |
| Render Cron Starter | $0 | 1 cron free |
| Neon Free | $0 | 0.5GB, no pause |
| Upstash Free | $0 | 10k cmd/day |
| AuraDB Free | $0 | 200k nodes |
| Groq Free | $0 | 14.4k req/day |
| Cloudflare Pages | $0 | unlimited bandwidth |
| **TOTAL** | **$7/mo** | |

Domain optional: Cloudflare Registrar `.xyz` ~$3/yr.

---

## 8. Watch for quota limits

- **Groq 14.4k req/day** — ingest cadence (RSS 60s + GDELT 60s + Guardian 120s) can exceed. If 429s, increase intervals in `chainpulse/backend/ingest/scheduler.py` (60s → 180s).
- **Upstash 10k cmds/day** — each event = ~5 cmds (XADD, SET, PUBLISH). Plenty for personal demo.
- **AuraDB 200k nodes** — current usage ~50 nodes.

---

## 9. Update deploy

`git push` → Render auto-rebuilds + redeploys. ~3 min downtime during build (Render swaps containers at end, brief 502 possible).

Zero-downtime: enable Render's "Zero-downtime deploys" toggle in dashboard (Starter plan includes).

---

## 10. Troubleshooting

**Render build fails on xgboost compile** — uses prebuilt wheel; should just work on Python 3.11 slim. If fails, add to Dockerfile before `pip install`:
```dockerfile
RUN apt-get install -y --no-install-recommends gcc g++
```

**Memory exceeded** — `supervisord` running all 4 procs may peak 400MB. If OOM kills container:
- Drop ingest pollers to single 300s tick
- Disable Faker dep
- Upgrade to Render Standard $25 (2GB)

**Neon connection limit** — Free tier = 100 conns. Pooled URL handles it. `asyncpg` pool_size=20 fits.

**Groq quota burnt** — fallback to OpenAI `gpt-4o-mini`. Edit `groq_extractor.py` to add second backend.
