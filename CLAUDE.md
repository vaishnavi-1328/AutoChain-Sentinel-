# AutoChain-Sentinel

AI "Control Tower" for automotive supply chain monitoring. Ingests RSS news → LLM extracts disruption events → Neo4j graph traversal finds impacted vehicle models → XGBoost predicts delay days → Streamlit "War Room" visualizes + suggests alternative suppliers.

**Status:** Pre-implementation. Only `AutoChain-Sentinel_Master_Specification.md` exists. Treat the spec as source of truth for schemas, prompts, and architecture.

## Architecture

```
RSS feeds → LangChain NER agent → Pydantic DisruptionEvent
                                        ↓
                              Neo4j graph traversal (City → Supplier → Part → VehicleModel)
                                        ↓
                              XGBoost predict_delay_days
                                        ↓
                              FastAPI /process-news
                                        ↓
                              Streamlit dashboard (PyDeck globe + agraph network + mitigation table)
```

## Directory Layout (planned)

```
autochain-sentinel/
├── data/        # CSV seeds, Faker scripts, synthetic generation (data_factory.py)
├── backend/     # FastAPI, LangChain agents, Neo4j drivers, XGBoost
├── frontend/    # Streamlit, PyDeck maps, streamlit-agraph
├── infra/       # Dockerfiles, docker-compose.yml, Terraform (main.tf)
└── tests/       # Pytest: unit, graph integrity, E2E
```

## Stack

- **Backend:** Python, FastAPI, LangChain, Pydantic, feedparser, neo4j-driver, XGBoost, Evidently AI
- **Graph DB:** Neo4j (AuraDB in prod)
- **Frontend:** Streamlit, PyDeck, streamlit-agraph
- **Infra:** Docker, AWS ECS Fargate, S3, Terraform
- **Synthetic data:** Faker + pandas. Optional Kaggle dataset (`bertnardomariouskono/global-supply-chain-disruption-and-resilience`, 10k shipment records) may replace synthetic generation.

## Neo4j Schema

**Nodes:**
- `Supplier {uid, name, tier_level (1-3), risk_score (0.0-1.0)}`
- `Part {part_id, name, criticality (1-10), base_lead_time_days}`
- `VehicleModel {model_id, name, daily_production_target}`
- `City {name, country, lat, lon}`

**Edges:**
- `(Supplier)-[:PRODUCES]->(Part)`
- `(Part)-[:COMPONENT_OF]->(Part)` — hierarchical, T3 → T2 → T1
- `(Part)-[:REQUIRED_FOR]->(VehicleModel)`
- `(Supplier)-[:LOCATED_IN]->(City)`

**Invariant:** every `VehicleModel` must have unbroken graph path to ≥5 Tier-3 suppliers. Orphan nodes dropped/relinked in `data_factory.py` validation step.

## LLM Extraction Schema

```python
class DisruptionEvent(BaseModel):
    city: str
    country: str
    industry_affected: str
    severity_score: int          # 1-10
    event_type: str              # Weather | Strike | Financial | ...
```

## Predictive Model

- **Features:** `Graph_Hops` (City → VehicleModel shortest path), `severity_score`, `Part_Criticality`, `Historical_Risk_Score`
- **Target:** `Predicted_Delay_Days`
- **Cold start:** generate 1,500 synthetic rows where delay scales with hops × severity. Save `.pkl`.

## Synthetic Data Targets

100 suppliers, geo-weighted: 30% DE, 30% CN, 20% US, 20% MX. Tier 3 = raw materials, Tier 2 = sub-assemblies, Tier 1 = major components.

## Endpoints (planned)

- `POST /process-news` — ingest headline, return `DisruptionEvent` + `predicted_delay_days`. Sanity test asserts 200 + delay > 0 for "Port Strike in Shanghai".

## Test Requirements

1. **Unit:** Pydantic parser handles malformed LLM output (e.g., severity as string).
2. **Graph integrity:** Cypher asserting zero `Part` nodes without incoming `PRODUCES`.
3. **E2E:** mock POST `/process-news` returns 200 + delay > 0.

## MLOps

Evidently AI monitors `severity_score` distribution. Rolling 7-day avg deviation from training baseline → log "Concept Drift Warning".

## Deployment

- ECS Fargate runs FastAPI + Streamlit containers
- S3 for model artifacts + MLflow tracking
- IAM roles for ECS → Neo4j AuraDB
- `docker-compose.yml` exposes API on 8000, UI on 8501. Env: `OPENAI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`

## Notes

- Repo dir name has trailing space: `/Users/vaishnavis/Desktop/OEM sentinal ` — quote paths in shell.
- No code committed yet. First commit is spec only.
