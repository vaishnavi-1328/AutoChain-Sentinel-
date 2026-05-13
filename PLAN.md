# AutoChain-Sentinel — Phased Build Plan

## Context

Repo currently holds `AutoChain-Sentinel_Master_Specification.md` + `CLAUDE.md` + `.gitignore`. Spec describes a 5-year, production-grade "AI Control Tower" for automotive supply chains: RSS → LLM NER → Neo4j graph traversal → XGBoost delay prediction → Streamlit War Room + AWS deployment. No code yet.

Strategy: respect spec phases, but start with a **vertical slice** so the full pipeline (RSS → NER → graph → predict → UI) is provable end-to-end before any single phase is deepened.

**Locked decisions:**

- **Data:** Hybrid — Faker for graph topology (suppliers/parts/vehicles/cities); Kaggle `bertnardomariouskono/global-supply-chain-disruption-and-resilience` (10k shipments) → historical delays for XGBoost.
- **LLM:** Anthropic Claude via `langchain-anthropic`. Env `ANTHROPIC_API_KEY`.
- **First milestone:** thin vertical slice end-to-end.
- **Deploy:** docker-compose + Neo4j AuraDB free tier. Defer ECS/Terraform to M5.

---

## Milestones

### M0 — Repo scaffold

Create `autochain-sentinel/` tree:

```
autochain-sentinel/
├── data/
│   ├── __init__.py
│   ├── data_factory.py
│   ├── kaggle_loader.py
│   └── seeds/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── ner_agent.py
│   ├── graph.py
│   ├── predictor.py
│   ├── mitigation.py
│   └── schemas.py
├── frontend/
│   ├── app.py
│   └── components/
│       ├── globe.py
│       └── network.py
├── infra/
│   ├── docker-compose.yml
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── terraform/main.tf
├── tests/
│   ├── test_ner_parser.py
│   ├── test_graph_integrity.py
│   └── test_e2e_process_news.py
├── pyproject.toml
├── .env.example
└── README.md
```

Update `.gitignore`: add `autochain-sentinel/data/seeds/`, `*.pkl`, `mlruns/`.

### M1 — Vertical slice

1. **Mini seed** (`data_factory.py` v0.1): 6 suppliers, 4 parts, 1 VehicleModel, 4 cities.
2. **NER agent** (`ner_agent.py`): `ChatAnthropic` (claude-haiku-4-5) + `PydanticOutputParser[DisruptionEvent]`. `extract(headline) -> DisruptionEvent`.
3. **Graph traversal** (`graph.py`): Cypher shortest path City → Supplier → Part chain → VehicleModel.
4. **Predictor stub** (`predictor.py`): `delay = hops * severity * 0.4 + criticality * 0.3`.
5. **FastAPI** (`main.py`): `POST /process-news` → orchestrate.
6. **Streamlit** (`frontend/app.py`): text input → API → JSON + delay table.
7. **Compose** (`infra/docker-compose.yml`): api 8000 + ui 8501 (AuraDB env-driven).
8. **Smoke test**: post "Port Strike in Shanghai", assert 200 + delay > 0.

**Exit:** `docker compose up`, type headline in UI, see delay.

### M2 — Phase 1 deepening

1. Faker generator scaled to 100 suppliers (DE 30 / CN 30 / US 20 / MX 20), ~40 parts, 5 vehicle models.
2. Validation: every VehicleModel reaches ≥5 Tier-3 suppliers; orphans relinked or dropped.
3. Kaggle loader → training rows for XGBoost.
4. `test_graph_integrity.py`.

### M3 — Phase 2 + 3 deepening

1. `train_predictor.py` — XGBoost on Kaggle + 1.5k synthetic. Save `models/predictor.pkl`.
2. `predictor.py` loads `.pkl`, falls back to stub if missing.
3. PyDeck globe (rotating, color = risk).
4. streamlit-agraph sub-tier network.
5. `mitigation.py` — alternative-supplier Cypher.
6. What-If sidebar.
7. `rss_poller.py` — feedparser cron.

### M4 — Phase 4: QA + MLOps

1. Full pytest: `test_ner_parser`, `test_graph_integrity`, `test_e2e_process_news`.
2. Evidently AI drift monitor on `severity_score`. Rolling 7-day mean → "Concept Drift Warning".
3. GitHub Actions CI: ruff, pytest, docker build.

### M5 — Phase 5: cloud (deferred)

1. `infra/terraform/main.tf` — ECS Fargate, S3, IAM, ECR.
2. GH Actions deploy: build → ECR → terraform apply.
3. MLflow tracking server pointer in trainer.

---

## Critical Files (per milestone)

| File | Milestone |
|------|-----------|
| `pyproject.toml`, `.env.example`, `README.md` | M0 |
| `data/data_factory.py`, `backend/{schemas,ner_agent,graph,predictor,main}.py` | M1 |
| `frontend/app.py`, `infra/{docker-compose.yml,*.Dockerfile}` | M1 |
| `tests/test_e2e_process_news.py` | M1 |
| `data/kaggle_loader.py`, `tests/test_graph_integrity.py` | M2 |
| `backend/{train_predictor,mitigation,rss_poller}.py` | M3 |
| `frontend/components/{globe,network}.py` | M3 |
| `tests/test_ner_parser.py`, `backend/drift_monitor.py`, `.github/workflows/ci.yml` | M4 |
| `infra/terraform/main.tf` | M5 |

## Verification

**M1:**
```bash
cp autochain-sentinel/.env.example autochain-sentinel/.env
# fill ANTHROPIC_API_KEY + NEO4J_URI/USER/PASSWORD
docker compose -f autochain-sentinel/infra/docker-compose.yml up --build
curl -X POST localhost:8000/process-news -H 'content-type: application/json' \
  -d '{"headline":"Port Strike in Shanghai"}'
pytest autochain-sentinel/tests/test_e2e_process_news.py -v
```

**M2:** `python -m autochain_sentinel.data.data_factory --suppliers 100 --validate` + integrity test green.

**M3:** trainer writes `predictor.pkl`, UI shows globe + network + mitigation table.

**M4:** full pytest green, ruff clean, drift warning logged on synthetic high-severity batch.

**M5:** `terraform apply` → ECS healthy, /process-news reachable on public ALB.

## Progress

- [x] Plan approved
- [x] M0 scaffold — dirs, pyproject, .env.example, README, .gitignore updated
- [x] M1 vertical slice — schemas, NER agent (Claude), Neo4j seed + traversal, predictor stub, FastAPI /process-news, Streamlit UI, Dockerfiles, compose, smoke test passing
- [ ] M2 data ecosystem — 100 suppliers, validation, Kaggle loader, integrity test
- [ ] M3 ML + UI — XGBoost, PyDeck globe, agraph, mitigation, RSS poller
- [ ] M4 QA + MLOps — full pytest, Evidently drift, GH Actions CI
- [ ] M5 AWS deploy — Terraform, ECS, ECR, MLflow
