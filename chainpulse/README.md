# AutoChain-Sentinel — ChainPulse

AI Control Tower for automotive supply chain monitoring. News headline → LLM NER → Neo4j graph traversal → XGBoost delay prediction → Streamlit War Room.

**No Docker. No Kafka. No Postgres.** Deploys free on Streamlit Community Cloud + Neo4j AuraDB.

## Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill NEO4J_* + ANTHROPIC_API_KEY (or OPENAI_API_KEY)
streamlit run frontend/app.py
```

UI → http://localhost:8501. Click "Seed minimal graph" once on first run.

Optional REST API (not required for UI):

```bash
uvicorn chainpulse.backend.main:app --reload --port 8000
curl -X POST localhost:8000/process-news -H 'content-type: application/json' \
  -d '{"headline":"Port Strike in Shanghai"}'
```

## Deploy (free, public)

**1. Neo4j AuraDB Free**
- https://neo4j.com/cloud/aura-free/ → create instance
- Save bolt+s URI + password

**2. Push repo to GitHub** (public or private)

**3. Streamlit Community Cloud**
- https://share.streamlit.io → New app
- Repo: `<you>/<repo>`, branch: `main`, main file: `chainpulse/streamlit_app.py`
- Settings → Secrets → paste contents of `.streamlit/secrets.toml.example` with real values
- Deploy. Public URL provisioned.

**4. First-time seed**
- Set `ALLOW_SEED=1` in secrets → reload app → click "🌱 Seed minimal graph"
- Optionally set `ALLOW_SEED=0` afterwards

## Layout

- `frontend/app.py` — Streamlit dashboard (PyDeck map + impact table)
- `backend/core/` — pipeline, NER (LangChain), graph (Cypher), predictor (XGBoost stub)
- `backend/main.py` — optional FastAPI `/process-news`
- `backend/db/neo4j.py` — driver singleton
- `data/data_factory.py` — synthetic topology generator
- `streamlit_app.py` — Cloud entrypoint at repo root

## Stack

Python 3.11 · Streamlit · LangChain (Anthropic / OpenAI) · Neo4j AuraDB · XGBoost · PyDeck
