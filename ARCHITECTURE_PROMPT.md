# Architecture & Structure Prompt — ChainPulse Supply Chain Intelligence Platform

## Product Summary

**ChainPulse** is a real-time supply chain disruption intelligence platform. It monitors global news 24/7, extracts supply chain relevant events (port strikes, weather disruptions, sanctions, factory closures), resolves them to geographic coordinates, predicts associated shipping delays, and broadcasts them live to a dark-themed world-map dashboard.

Each user configures their supply chain profile once (countries, products, suppliers). The system then continuously filters and personalises the live event stream to show only disruptions that affect their specific supply chain graph, stored in Neo4j.

There is no manual input on the main dashboard. The product is entirely event-driven.

---

## High-Level Architecture — C4 Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL WORLD                                   │
│                                                                         │
│  [GDELT]  [NewsAPI]  [Reuters]  [IMO RSS]  [WTO RSS]  [Port RSS feeds] │
│      │         │         │          │          │             │           │
│      └─────────┴─────────┴──────────┴──────────┴─────────────┘          │
│                                   │                                     │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │  raw news (HTTP/RSS)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       CHAINPULSE PLATFORM                               │
│                                                                         │
│  ┌───────────────────┐   Kafka   ┌──────────────────────┐              │
│  │  Ingest Workers   │──────────▶│   NLP Pipeline       │              │
│  │  (Python async)   │ raw.news  │   (spaCy + BERT)     │              │
│  └───────────────────┘           └──────────┬───────────┘              │
│                                             │ processed.events          │
│  ┌──────────────────────────────────────────▼──────────────────────┐   │
│  │                    Storage Layer                                 │   │
│  │  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐   │   │
│  │  │  PostgreSQL  │  │    Neo4j        │  │  Redis Streams    │   │   │
│  │  │  (events,    │  │  (supply chain  │  │  (live TTL feed,  │   │   │
│  │  │   users)     │  │   graph)        │  │   WS pub/sub)     │   │   │
│  │  └──────────────┘  └────────────────┘  └───────────────────┘   │   │
│  └─────────────────────────────┬────────────────────────────────────┘   │
│                                │                                        │
│  ┌─────────────────────────────▼────────────────────────────────────┐   │
│  │                    FastAPI Backend                                │   │
│  │         REST API  +  WebSocket  +  Neo4j Cypher proxy            │   │
│  └─────────────────────────────┬────────────────────────────────────┘   │
│                                │                                        │
└────────────────────────────────┼────────────────────────────────────────┘
                                 │  WebSocket (WSS) + REST (HTTPS)
                                 ▼
                    ┌────────────────────────────┐
                    │  Browser Dashboard          │
                    │  (HTML/CSS/JS + Leaflet)    │
                    │  Supply Chain Engineers     │
                    └────────────────────────────┘
```

---

## Detailed Component Map

```
chainpulse/
│
├── frontend/                         ← Static web assets (served by nginx)
│   ├── index.html                    ← Main dashboard (single page)
│   ├── onboarding.html               ← Account setup (one-time)
│   ├── css/
│   │   ├── theme.css                 ← CSS vars, global reset, dark mode base
│   │   ├── map.css                   ← Leaflet overrides, pin animations
│   │   ├── sidebar.css               ← News log sidebar styles
│   │   ├── modal.css                 ← Knowledge graph modal overlay
│   │   ├── titlebar.css              ← Header, status indicators
│   │   └── ticker.css                ← Bottom bar, scrolling ticker
│   ├── js/
│   │   ├── ws-client.js              ← WebSocket + reconnect logic
│   │   ├── map-manager.js            ← Leaflet init, pin lifecycle, lanes
│   │   ├── sidebar-feed.js           ← News items, queue, filter controls
│   │   ├── graph-modal.js            ← neovis.js init, traversal, close
│   │   ├── stats-updater.js          ← Bottom bar chip values
│   │   ├── ticker.js                 ← Delay ticker scroll content
│   │   └── onboarding.js             ← Multi-step profile form
│   └── assets/
│       ├── logo.svg
│       └── shipping-lanes.geojson    ← Major shipping route polylines
│
├── backend/                          ← Python FastAPI application
│   ├── main.py                       ← App init, lifespan, CORS, router mount
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   ├── config/
│   │   └── settings.py               ← Pydantic BaseSettings (all env vars)
│   │
│   ├── routers/
│   │   ├── auth.py                   ← POST /auth/login, /auth/register
│   │   ├── events.py                 ← GET /events/recent, GET /events/{id}
│   │   ├── graph.py                  ← GET /graph/{event_id}
│   │   ├── profile.py                ← POST /onboarding/profile, GET /profile/skus-at-risk
│   │   └── websocket.py              ← WS /ws/events  (JWT-authenticated)
│   │
│   ├── services/
│   │   ├── kafka_producer.py         ← Publish raw news to Kafka
│   │   ├── kafka_consumer.py         ← Consume processed.events → WS broadcast
│   │   ├── nlp_pipeline.py           ← Orchestrate all NLP steps
│   │   ├── geo_resolver.py           ← GeoNames API + port gazetteer
│   │   ├── event_classifier.py       ← BERT classification inference
│   │   ├── severity_scorer.py        ← Keyword + rule-based severity
│   │   ├── delay_predictor.py        ← sklearn GBR model inference
│   │   ├── neo4j_service.py          ← Neo4j driver, Cypher query methods
│   │   └── redis_service.py          ← Redis client, bloom filter, pub/sub
│   │
│   ├── models/                       ← SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── event.py
│   │   └── profile.py
│   │
│   ├── schemas/                      ← Pydantic request/response schemas
│   │   ├── user.py
│   │   ├── event.py
│   │   └── profile.py
│   │
│   ├── db/                           ← Database connections
│   │   ├── postgres.py               ← asyncpg pool, session factory
│   │   ├── neo4j.py                  ← Neo4j driver singleton
│   │   └── redis.py                  ← Redis connection pool
│   │
│   ├── ingest/                       ← News ingestion workers
│   │   ├── gdelt_poller.py           ← APScheduler job, GDELT CSV parser
│   │   ├── newsapi_client.py         ← NewsAPI REST polling
│   │   └── rss_scraper.py            ← feedparser-based RSS scraper
│   │
│   └── ml/                           ← Machine learning assets
│       ├── classifier/               ← Fine-tuned distilbert model
│       │   ├── config.json
│       │   ├── pytorch_model.bin
│       │   └── tokenizer/
│       ├── delay_model_min.pkl       ← GBR model for delay_min_days
│       ├── delay_model_max.pkl       ← GBR model for delay_max_days
│       └── port_gazetteer.json       ← {port_name: {lat, lng, country_code}}
│
├── infra/                            ← Infrastructure config
│   ├── docker-compose.yml            ← All services for local dev
│   ├── nginx/
│   │   └── default.conf              ← Reverse proxy: frontend + API routing
│   └── kafka/
│       └── topics.sh                 ← Create Kafka topics on first run
│
└── data/                             ← Seed data and training sets
    ├── shipping_lanes.geojson        ← Source for frontend asset
    ├── port_gazetteer_raw.csv        ← Source for ml/port_gazetteer.json
    └── training/
        ├── disruption_events.csv     ← Labeled historical disruption data
        └── train_delay_model.py      ← Model training script
```

---

## Data Flow — End to End

```
Step 1: INGESTION  (every 60s for GDELT/RSS, every 5min for NewsAPI)
─────────────────────────────────────────────────────────────
Poller/scraper fetches raw articles/events
        │
        ▼
Normalize to raw news schema
        │
        ▼
Publish to Kafka topic: raw.news

Step 2: NLP PROCESSING  (real-time Kafka consumer)
─────────────────────────────────────────────────────────────
Consumer reads from raw.news
        │
        ├─ Deduplication (Redis bloom filter)
        │
        ├─ NER (spaCy en_core_web_trf)
        │
        ├─ Geo-resolution (gazetteer → GeoNames fallback)
        │
        ├─ Event classification (fine-tuned distilbert)
        │
        ├─ Severity scoring (rules + keyword weighting)
        │
        ├─ Delay prediction (scikit-learn GBR)
        │
        └─ Publish to Kafka topic: processed.events

Step 3: STORAGE  (Kafka consumer → databases)
─────────────────────────────────────────────────────────────
Consumer reads from processed.events
        │
        ├─ INSERT into PostgreSQL: events table
        │
        ├─ CREATE in Neo4j: DisruptionEvent node
        │     + (DisruptionEvent)-[:AFFECTS]->(Port)
        │     + (DisruptionEvent)-[:IMPACTS]->(OEM) where resolvable
        │
        ├─ SET in Redis: event:{id}  JSON  EX 300
        │
        └─ PUBLISH to Redis channel: events:{user_id}
           (for all users whose watched_regions match country_code)

Step 4: BROADCAST  (FastAPI WebSocket)
─────────────────────────────────────────────────────────────
Redis pub/sub subscriber in FastAPI picks up events:{user_id}
        │
        ▼
ConnectionManager sends event JSON to the matching WebSocket client

Step 5: DISPLAY  (Browser)
─────────────────────────────────────────────────────────────
ws.onmessage → addEventPin(map) + addSidebarItem() + updateStats()
Pin fades after 5 minutes via setTimeout
```

---

## API Contract

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create user account |
| POST | `/auth/login` | Get JWT access token |

### Events

| Method | Endpoint | Description |
|---|---|---|
| GET | `/events/recent?limit=100` | Last N processed events (auth required) |
| GET | `/events/{event_id}` | Full event detail with source URL |

### Graph

| Method | Endpoint | Description |
|---|---|---|
| GET | `/graph/{event_id}` | Neo4j subgraph (nodes + edges) for graph modal |

### Profile

| Method | Endpoint | Description |
|---|---|---|
| POST | `/onboarding/profile` | Save user supply chain profile |
| GET | `/profile/me` | Get current user's profile |
| GET | `/profile/skus-at-risk` | SKUs affected by current live events |

### WebSocket

| Protocol | Endpoint | Auth |
|---|---|---|
| WSS | `/ws/events?token={jwt}` | JWT in query string |

---

## WebSocket Message Schema (Server → Client)

```json
{
  "id": "evt_3f8a1c",
  "type": "PORT_STRIKE",
  "severity": "critical",
  "title": "Port workers begin indefinite strike at Port of Shanghai",
  "summary": "Dock workers at the Port of Shanghai began an indefinite strike...",
  "source_url": "https://reuters.com/business/...",
  "source_name": "Reuters",
  "lat": 31.2304,
  "lng": 121.4737,
  "location_name": "Port of Shanghai, China",
  "country_code": "CN",
  "predicted_delay_min_days": 8,
  "predicted_delay_max_days": 14,
  "delay_confidence": 0.81,
  "neo4j_event_node_id": "node_7x9a2b",
  "affected_sku_count": 47,
  "affected_route_count": 12,
  "timestamp_utc": "2025-06-14T09:41:00Z",
  "ttl_seconds": 300
}
```

---

## Service Dependencies Map

```
FastAPI API
   ├── depends on: PostgreSQL (events, users, profiles)
   ├── depends on: Neo4j     (graph queries, subgraph for modal)
   ├── depends on: Redis     (pub/sub for WS broadcast, event TTL)
   └── depends on: Kafka     (consumer: processed.events → WS push)

NLP Pipeline (Kafka consumer process)
   ├── depends on: Kafka     (consume raw.news, publish processed.events)
   ├── depends on: Redis     (bloom filter deduplication)
   ├── depends on: spaCy model: en_core_web_trf
   ├── depends on: distilbert fine-tuned classifier
   ├── depends on: sklearn GBR models (delay_min, delay_max)
   └── depends on: GeoNames API (HTTP, rate-limited to 1000 req/hr free tier)

Ingest Workers (APScheduler)
   ├── depends on: Kafka     (publish raw.news)
   ├── depends on: GDELT     (HTTP poll every 60s)
   ├── depends on: NewsAPI   (HTTP poll every 5min per query term)
   └── depends on: RSS feeds (HTTP poll every 60s)

Frontend
   ├── depends on: FastAPI WS endpoint (/ws/events)
   ├── depends on: FastAPI REST (/events, /graph, /profile)
   └── depends on: CartoDB tile server (map tiles, CDN)
```

---

## Infrastructure Setup Order

Run these in order when setting up from scratch:

```bash
# 1. Start infrastructure
docker-compose up -d postgres neo4j redis zookeeper kafka

# 2. Create Kafka topics
./infra/kafka/topics.sh

# 3. Run database migrations
alembic upgrade head

# 4. Seed Neo4j with base supply chain graph
python data/seed_neo4j.py

# 5. Download spaCy model
python -m spacy download en_core_web_trf

# 6. Train or place ML models
python data/training/train_delay_model.py
# → writes ml/delay_model_min.pkl and ml/delay_model_max.pkl

# 7. Start FastAPI
uvicorn backend.main:app --reload --port 8000

# 8. Start NLP consumer (separate process)
python -m backend.services.kafka_consumer

# 9. Start ingest workers (separate process)
python -m backend.ingest.runner

# 10. Serve frontend (dev)
npx serve frontend/ -p 3000
```

---

## Scalability Notes

| Concern | Solution |
|---|---|
| Many concurrent WS connections | Use Redis pub/sub fan-out — only one Kafka consumer needed regardless of WS client count |
| NLP pipeline latency | Run as a separate process from the API; pipeline latency does not block HTTP responses |
| GDELT rate limits | GDELT is public and free; no rate limit. NewsAPI: 1 req/sec on developer plan |
| Neo4j query load | Cache graph subgraph results in Redis with 60s TTL keyed on event_id |
| ML model cold start | Load models into memory at worker startup, not per-request |
| Port gazetteer misses | Log unresolvable location strings to PostgreSQL `unresolved_locations` table for manual review and gazetteer expansion |

---

## Development Milestones

| Milestone | Components | Goal |
|---|---|---|
| M1 — Live data foundation | GDELT poller → Kafka → PostgreSQL | Raw news flowing and stored |
| M2 — NLP pipeline | spaCy NER + geo-resolver + classifier | Events classified with lat/lng |
| M3 — Map MVP | FastAPI REST + Leaflet map (static pins) | Pins appearing on map from DB |
| M4 — WebSocket live | Redis pub/sub + WS endpoint + frontend WS client | Real-time pin appearance |
| M5 — Sidebar + source links | News log sidebar with source URL links | Validation feature complete |
| M6 — Onboarding | Profile form + PostgreSQL storage | User profiles collected |
| M7 — Neo4j graph | Neo4j schema + Cypher queries + graph modal | Knowledge graph visible |
| M8 — Delay prediction | sklearn model + training data | Delay estimates on all events |
| M9 — SKU personalisation | user_event_impacts table + profile matching | Per-user SKU risk count |
| M10 — Polish & hardening | Pin fade TTL, WS reconnect, auth security | Production-ready |

---

## Technology Versions (pin these)

```
Python          3.11.x
FastAPI         0.111.x
SQLAlchemy      2.0.x
asyncpg         0.29.x
confluent-kafka 2.4.x
neo4j           5.x (driver 5.x)
redis-py        5.x
spaCy           3.7.x (model: en_core_web_trf)
transformers    4.40.x (distilbert-base-uncased)
scikit-learn    1.4.x
APScheduler     3.10.x
feedparser      6.0.x
PostgreSQL      16.x
Neo4j           5.x
Redis           7.x
Kafka           3.7.x (Confluent Platform)
Leaflet         1.9.x
D3              7.x
neovis.js       2.x
Tailwind CSS    3.x (CDN)
```
