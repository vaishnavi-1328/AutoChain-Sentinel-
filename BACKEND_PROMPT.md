# Backend Build Prompt — Supply Chain Intelligence Platform

## Project Context

You are building the backend for **ChainPulse**, a real-time supply chain disruption intelligence platform. The backend is responsible for ingesting news from multiple sources in real time, processing it through an NLP pipeline to classify and geo-locate events, storing structured data, maintaining a Neo4j knowledge graph, and delivering live events to connected frontend clients via WebSocket.

No user prompt is required to trigger news. The system continuously monitors sources based on each user's account profile (their customer countries, products, and supplier graph built during onboarding).

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| API framework | **FastAPI** (Python 3.11+) | Async-native, WebSocket support, OpenAPI docs |
| Task queue / streaming | **Apache Kafka** (via `confluent-kafka-python`) | Fan-out, deduplication, durable event log |
| NLP pipeline | **spaCy** + **Hugging Face Transformers** | NER, classification, geo-resolution |
| Relational store | **PostgreSQL 16** (via `asyncpg` + `SQLAlchemy 2.0`) | Users, events, SKU mapping, audit log |
| Graph database | **Neo4j 5** (via `neo4j` Python driver) | OEM supply chain graph, traversal |
| Cache / TTL store | **Redis 7** (via `redis-py` async) | Live event TTL (5-min), WS broadcast buffer |
| Geo-resolution | **GeoNames API** + custom port gazetteer | Lat/lng from extracted location names |
| News sources | GDELT, NewsAPI, RSS scrapers | Multi-source ingestion |
| Background jobs | **APScheduler** | Polling GDELT and RSS every 60 seconds |
| Auth | **JWT** (via `python-jose`) + OAuth2 password flow | User sessions |
| Config | **Pydantic Settings** + `.env` | Environment-based config |
| Containerization | **Docker** + **Docker Compose** | Local dev and deployment |

---

## System Architecture Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                        NEWS INGESTION LAYER                          │
│                                                                      │
│   [GDELT Poller]   [NewsAPI Stream]   [RSS Scrapers]   [Reuters]     │
│        │                │                  │               │         │
│        └────────────────┴──────────────────┴───────────────┘         │
│                                   │                                  │
│                           Kafka Topic: raw.news                      │
└───────────────────────────────────┼──────────────────────────────────┘
                                    │
┌───────────────────────────────────▼──────────────────────────────────┐
│                        NLP PROCESSING PIPELINE                       │
│                                                                      │
│   Consumer reads raw.news → dedup check (Redis bloom filter)         │
│        │                                                             │
│        ▼                                                             │
│   [spaCy NER] → extract: organizations, locations, events            │
│        │                                                             │
│        ▼                                                             │
│   [Geo-resolver] → map location strings → (lat, lng, country_code)   │
│        │                                                             │
│        ▼                                                             │
│   [Event Classifier] → classify type: PORT | WEATHER | STRIKE | …   │
│        │                                                             │
│        ▼                                                             │
│   [Severity Scorer] → assign: critical | high | medium | low         │
│        │                                                             │
│        ▼                                                             │
│   [Delay Predictor] → predict: min_days, max_days, confidence        │
│        │                                                             │
│        ▼                                                             │
│   Publish to Kafka Topic: processed.events                           │
└───────────────────────────────────┼──────────────────────────────────┘
                                    │
┌───────────────────────────────────▼──────────────────────────────────┐
│                          STORAGE LAYER                               │
│                                                                      │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│   │   PostgreSQL     │  │     Neo4j        │  │  Redis Streams  │     │
│   │  events table    │  │  supply chain    │  │  live event TTL │     │
│   │  users table     │  │  graph nodes     │  │  WS pub/sub     │     │
│   │  skus table      │  │  + relationships │  │  bloom filter   │     │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘     │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
┌───────────────────────────────────▼──────────────────────────────────┐
│                         FASTAPI BACKEND                              │
│                                                                      │
│   REST Endpoints:                                                    │
│     POST /auth/login            — JWT issue                          │
│     POST /auth/register         — user creation                      │
│     POST /onboarding/profile    — save supply chain profile          │
│     GET  /events/recent         — last 100 processed events          │
│     GET  /events/{id}           — single event detail                │
│     GET  /graph/{event_id}      — Neo4j subgraph for event           │
│     GET  /profile/skus-at-risk  — user's SKUs affected by live events│
│                                                                      │
│   WebSocket:                                                         │
│     WS /ws/events               — live event stream per user         │
│                                                                      │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │
                          WebSocket broadcast
                                    │
                    ┌───────────────▼────────────┐
                    │   Frontend Dashboard        │
                    │   (Leaflet map + sidebar)   │
                    └────────────────────────────┘
```

---

## Module 1 — News Ingestion

### GDELT Poller (`ingest/gdelt_poller.py`)

GDELT releases a new CSV every 15 minutes at:
```
http://data.gdeltproject.org/gdeltv2/lastupdate.txt
```

Poll this endpoint every 60 seconds using APScheduler. Parse the `.export.CSV` file. Filter rows where:
- `EventCode` starts with `14` (Protest), `17` (Coercion), `18` (Assault), or `20` (Provide Aid) — supply-chain-relevant CAMEO event codes
- Additionally filter by geography against the user profile's watched regions

Push raw rows to Kafka topic `raw.news`.

### NewsAPI Consumer (`ingest/newsapi_client.py`)

Use the NewsAPI `/v2/everything` endpoint with a rotating set of supply-chain query terms:

```python
QUERY_TERMS = [
    "port strike OR port closure",
    "shipping delay OR freight delay",
    "factory shutdown OR plant closure",
    "trade sanctions OR trade embargo",
    "typhoon flood earthquake supply chain",
    "semiconductor shortage",
    "customs delay OR border closure",
]
```

Poll each term every 5 minutes (stagger calls to respect rate limits). Push raw article objects to `raw.news`.

### RSS Scraper (`ingest/rss_scraper.py`)

Scrape the following RSS feeds every 60 seconds:

```python
RSS_FEEDS = [
    "https://www.hellenicshippingnews.com/feed/",
    "https://splash247.com/feed/",
    "https://www.tradewindsnews.com/rss",
    "https://www.portmanagement.org/rss",
    # WTO news feed
    "https://www.wto.org/english/news_e/news_e.rss",
]
```

Use `feedparser` library. Push items to `raw.news` Kafka topic.

### Raw news Kafka message schema

```json
{
  "source": "gdelt | newsapi | rss | reuters",
  "raw_id": "unique_id_from_source",
  "headline": "string",
  "body": "string (article body or GDELT actor fields)",
  "url": "string | null",
  "published_at": "ISO 8601 UTC",
  "ingested_at": "ISO 8601 UTC"
}
```

---

## Module 2 — NLP Processing Pipeline

### Pipeline flow (detailed)

```
raw.news Kafka message
        │
        ▼
1. DEDUPLICATION
   └─ Compute SHA-256 hash of (source + raw_id)
   └─ Check Redis bloom filter → if exists, discard
   └─ If new: add to bloom filter, continue

        │
        ▼
2. TEXT NORMALIZATION
   └─ Strip HTML tags (BeautifulSoup)
   └─ Truncate body to first 512 tokens for model input

        │
        ▼
3. NER — spaCy (en_core_web_trf model)
   └─ Extract ORG entities  → potential OEMs, shipping companies
   └─ Extract GPE entities  → countries, cities
   └─ Extract LOC entities  → ports, facilities, geographic features
   └─ Extract EVENT entities → named storms, named strikes

        │
        ▼
4. GEO-RESOLUTION
   └─ For each extracted GPE/LOC entity:
      └─ Lookup in local port gazetteer first (fast, high confidence)
      └─ Fallback: GeoNames API query → return (lat, lng, country_code)
      └─ Select primary location: highest confidence entity
   └─ Output: primary_lat, primary_lng, primary_location_name, country_code

        │
        ▼
5. EVENT CLASSIFICATION
   └─ Model: fine-tuned distilbert-base-uncased on labeled SCM dataset
   └─ Labels: PORT_STRIKE | WEATHER_EVENT | FACTORY_CLOSURE |
              SANCTIONS | GEOPOLITICAL | LOGISTICS_DELAY | OTHER
   └─ Output: event_type (label), confidence (float 0-1)
   └─ If confidence < 0.55 and event_type == OTHER → discard

        │
        ▼
6. SEVERITY SCORING
   └─ Rule-based + keyword scoring:
      └─ CRITICAL: "major port closed", "full stoppage", "force majeure"
      └─ HIGH:     "partial closure", "strike", "typhoon landfall"
      └─ MEDIUM:   "slowdown", "weather warning", "tariff increase"
      └─ LOW:      "minor delay", "advisory", "monitoring"
   └─ Override severity upward if the affected location appears in
      any active user's watched_regions (personalisation uplift)

        │
        ▼
7. DELAY PREDICTION
   └─ Feature vector: [event_type, severity, port_throughput_rank,
                       historical_avg_delay_for_type, country_risk_score]
   └─ Model: scikit-learn GradientBoostingRegressor (trained on
             historical disruption dataset: Lloyd's, IMO, World Bank)
   └─ Output: delay_min_days (int), delay_max_days (int),
              delay_confidence (float 0-1)

        │
        ▼
8. USER IMPACT MATCHING
   └─ Query PostgreSQL: which user profiles have watched_regions
      that overlap with country_code?
   └─ For each matched user: query Neo4j for shortest path between
      the event's location node and any of that user's SKU nodes
   └─ Count: affected_sku_count, affected_route_count

        │
        ▼
9. PUBLISH to Kafka topic: processed.events
```

### Processed event Kafka message schema

```json
{
  "id": "evt_uuid",
  "type": "PORT_STRIKE",
  "severity": "critical",
  "title": "string",
  "summary": "string (max 280 chars)",
  "source_url": "string",
  "source_name": "string",
  "lat": 31.2304,
  "lng": 121.4737,
  "location_name": "Port of Shanghai, China",
  "country_code": "CN",
  "predicted_delay_min_days": 8,
  "predicted_delay_max_days": 14,
  "delay_confidence": 0.81,
  "neo4j_event_node_id": "node_7x9a2b",
  "affected_sku_counts": { "user_id_1": 47, "user_id_2": 12 },
  "affected_route_count": 12,
  "timestamp_utc": "2025-06-14T09:41:00Z",
  "ttl_seconds": 300
}
```

---

## Module 3 — PostgreSQL Schema

```sql
-- Users
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  company     TEXT,
  role        TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- User supply chain profiles (from onboarding)
CREATE TABLE user_profiles (
  user_id         UUID REFERENCES users(id),
  watched_regions TEXT[],        -- e.g. ['CN', 'VN', 'IN']
  product_categories TEXT[],     -- e.g. ['Semiconductors', 'Textiles']
  sku_codes       TEXT[],        -- optional uploaded SKU list
  supplier_names  TEXT[],
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Processed events (append-only log)
CREATE TABLE events (
  id                  UUID PRIMARY KEY,
  type                TEXT NOT NULL,
  severity            TEXT NOT NULL,
  title               TEXT NOT NULL,
  summary             TEXT,
  source_url          TEXT,
  source_name         TEXT,
  lat                 DOUBLE PRECISION,
  lng                 DOUBLE PRECISION,
  location_name       TEXT,
  country_code        CHAR(2),
  delay_min_days      INT,
  delay_max_days      INT,
  delay_confidence    NUMERIC(4,3),
  neo4j_node_id       TEXT,
  affected_route_count INT,
  timestamp_utc       TIMESTAMPTZ NOT NULL,
  ingested_at         TIMESTAMPTZ DEFAULT now()
);

-- Per-user event impact (denormalised for fast sidebar queries)
CREATE TABLE user_event_impacts (
  event_id         UUID REFERENCES events(id),
  user_id          UUID REFERENCES users(id),
  affected_sku_count INT,
  PRIMARY KEY (event_id, user_id)
);

-- Indexes
CREATE INDEX idx_events_timestamp ON events(timestamp_utc DESC);
CREATE INDEX idx_events_country   ON events(country_code);
CREATE INDEX idx_events_severity  ON events(severity);
```

---

## Module 4 — Neo4j Graph Schema

### Node types and properties

```cypher
// Supply chain location node
(:Port   { id, name, country_code, lat, lng, throughput_rank })
(:City   { id, name, country_code, lat, lng })
(:Region { id, name })

// Actor nodes
(:OEM              { id, name, country_code, tier })
(:Supplier         { id, name, country_code, tier })
(:ShippingLine     { id, name, flag_country })
(:FreightForwarder { id, name })

// User's supply chain nodes
(:SKU              { id, sku_code, user_id, product_category, description })
(:UserProfile      { id, user_id, company })

// Event nodes (written when an event is processed)
(:DisruptionEvent  { id, type, severity, title, timestamp_utc, lat, lng })
```

### Relationships

```cypher
// Supply chain graph (built during onboarding + enriched from public data)
(SKU)-[:MANUFACTURED_BY]->(OEM)
(OEM)-[:SOURCES_FROM]->(Supplier)
(Supplier)-[:LOCATED_IN]->(Port)
(Port)-[:ROUTES_THROUGH]->(Port)        // shipping lane connections
(ShippingLine)-[:OPERATES_ROUTE { lane_id }]->(Port)
(OEM)-[:SHIPS_VIA]->(ShippingLine)
(FreightForwarder)-[:HANDLES]->(ShippingLine)
(UserProfile)-[:TRACKS]->(SKU)

// Event relationships (written at processing time)
(DisruptionEvent)-[:AFFECTS]->(Port)
(DisruptionEvent)-[:AFFECTS]->(Region)
(DisruptionEvent)-[:IMPACTS]->(OEM)
(DisruptionEvent)-[:IMPACTS]->(ShippingLine)
```

### Key Cypher queries

**Get subgraph for an event (for the modal graph panel):**
```cypher
MATCH path = (e:DisruptionEvent {id: $event_id})-[*1..3]-(n)
WHERE NOT n:UserProfile
RETURN nodes(path), relationships(path)
LIMIT 80
```

**Find which SKUs are affected for a user:**
```cypher
MATCH (e:DisruptionEvent {id: $event_id})-[:AFFECTS]->(p:Port)
      <-[:LOCATED_IN|ROUTES_THROUGH*1..4]-(supplier:Supplier)
      <-[:SOURCES_FROM]-(oem:OEM)
      <-[:MANUFACTURED_BY]-(sku:SKU {user_id: $user_id})
RETURN sku.sku_code, sku.description, count(*) as hops
ORDER BY hops ASC
```

**Shortest path between event and user's SKU:**
```cypher
MATCH (e:DisruptionEvent {id: $event_id}), (sku:SKU {user_id: $user_id})
MATCH path = shortestPath((e)-[*]-(sku))
RETURN path
```

---

## Module 5 — FastAPI Application Structure

```
/backend
  main.py                   ← FastAPI app init, lifespan, CORS
  /routers
    auth.py                 ← /auth/login, /auth/register
    events.py               ← GET /events/recent, GET /events/{id}
    graph.py                ← GET /graph/{event_id}
    profile.py              ← POST /onboarding/profile, GET /profile
    websocket.py            ← WS /ws/events
  /services
    kafka_producer.py       ← publish to Kafka topics
    kafka_consumer.py       ← consume processed.events → broadcast WS
    nlp_pipeline.py         ← orchestrates all NLP steps (called by consumer)
    geo_resolver.py         ← GeoNames + port gazetteer lookup
    event_classifier.py     ← distilbert inference wrapper
    severity_scorer.py      ← rule-based severity assignment
    delay_predictor.py      ← sklearn model wrapper
    neo4j_service.py        ← Neo4j driver, Cypher query methods
    redis_service.py        ← Redis client, bloom filter, stream pub/sub
  /models
    user.py                 ← SQLAlchemy ORM models
    event.py
    profile.py
  /schemas
    user.py                 ← Pydantic schemas (request/response)
    event.py
    profile.py
  /db
    postgres.py             ← asyncpg connection pool, session factory
    neo4j.py                ← Neo4j driver singleton
    redis.py                ← Redis connection pool
  /ingest
    gdelt_poller.py         ← APScheduler job, GDELT CSV parse
    newsapi_client.py       ← NewsAPI REST polling
    rss_scraper.py          ← feedparser scraper
  /ml
    classifier/             ← fine-tuned distilbert model files
    delay_model.pkl         ← trained sklearn GBR model
    port_gazetteer.json     ← port name → lat/lng lookup table
  /config
    settings.py             ← Pydantic BaseSettings, all env vars
  requirements.txt
  Dockerfile
  docker-compose.yml
```

---

## Module 6 — WebSocket Event Broadcasting

### Connection flow

```
Client connects: WS /ws/events
    │
    ▼
FastAPI extracts JWT from query param: ?token=...
    │
    ▼
Validate JWT → get user_id
    │
    ▼
Add connection to ConnectionManager registry:
  active_connections[user_id] = WebSocket
    │
    ▼
Subscribe to Redis channel: events:{user_id}
    │
    ▼
Kafka consumer (separate async task) reads processed.events
    │
    ▼
For each event:
  → Write event to PostgreSQL (events table)
  → Write to Neo4j (DisruptionEvent node + AFFECTS relationships)
  → Write to Redis key: event:{evt_id}  EX 300  (5-min TTL)
  → For each affected user_id in event.affected_sku_counts:
      PUBLISH events:{user_id}  event_json
    │
    ▼
Redis subscriber in FastAPI picks up published message
    │
    ▼
Send via WebSocket to connected client: ws.send_json(event)
```

### ConnectionManager class

```python
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id] = ws

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)

    async def send_to_user(self, user_id: str, data: dict):
        ws = self.active.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except WebSocketDisconnect:
                self.disconnect(user_id)
```

---

## Module 7 — Delay Prediction Model

### Training data

Source: Compile a dataset of ~2,000 historical supply chain disruption events from:
- Lloyd's List port disruption database
- IMO casualty reports
- World Bank Logistics Performance Index data
- Compiled news archives (GDELT historical data)

Each training row:

```
event_type, port_throughput_rank (1-100), country_risk_score (0-10),
historical_avg_days (from past events of same type at same port),
severity_label → actual_delay_days (target)
```

### Model

```python
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

pipeline = Pipeline([
    ('enc', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)),
    ('model', GradientBoostingRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        loss='quantile',   # allows confidence interval prediction
        alpha=0.9          # 90th percentile for max_days variant
    ))
])
```

Train two models: one for `delay_min_days` (alpha=0.1) and one for `delay_max_days` (alpha=0.9). Save both as `delay_model_min.pkl` and `delay_model_max.pkl`.

---

## Module 8 — Environment Variables

```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/chainpulse

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_RAW_TOPIC=raw.news
KAFKA_PROCESSED_TOPIC=processed.events
KAFKA_GROUP_ID=chainpulse-nlp-group

# External APIs
NEWSAPI_KEY=your_newsapi_key
GEONAMES_USERNAME=your_geonames_username

# Auth
JWT_SECRET=your_jwt_secret_min_32_chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# ML models
MODEL_DIR=./ml

# App
APP_ENV=development
CORS_ORIGINS=http://localhost:3000,https://chainpulse.io
```

---

## Docker Compose (local dev)

```yaml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, neo4j, redis, kafka]

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: chainpulse
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes: [pgdata:/var/lib/postgresql/data]

  neo4j:
    image: neo4j:5
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/your_password

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"

volumes:
  pgdata:
```

---

## Security Checklist

- [ ] JWT tokens expire after 24 hours; use refresh tokens for extended sessions
- [ ] All WebSocket connections validate JWT before accepting
- [ ] Rate-limit `/auth/login` to 5 attempts per minute per IP
- [ ] Never return raw `source_url` from external APIs without validation — sanitize all URLs before storage
- [ ] Neo4j Cypher queries use parameterized inputs only — never string-interpolated user input
- [ ] PostgreSQL connection pool max size: 20; never allow unbounded connections
- [ ] CORS: restrict to known frontend origins only
- [ ] All secrets loaded from environment — never hardcoded
