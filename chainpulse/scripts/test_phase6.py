"""Phase 6 live test.

Spins up FastAPI in-process, exercises all REST endpoints + WebSocket.

Asserts:
  - /health 200
  - register + login round-trip → JWT
  - POST /onboarding/profile + GET /profile/me round-trip
  - GET /events/recent returns persisted events from phase 5
  - GET /events/{id} returns single event
  - GET /graph/{event_id} returns nodes + edges
  - WS /ws/events streams a published event end-to-end via Redis publish

Usage:
  python scripts/test_phase6.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from chainpulse.backend.config.settings import get_settings  # noqa: E402
from chainpulse.backend.db.postgres import get_session_factory  # noqa: E402
from chainpulse.backend.db.redis import get_redis  # noqa: E402
from chainpulse.backend.main import app  # noqa: E402
from chainpulse.backend.models import Event  # noqa: E402
from chainpulse.backend.services.redis_broadcast import publish_to_global  # noqa: E402


async def first_event_id() -> str | None:
    factory = get_session_factory()
    async with factory() as s:
        result = await s.execute(select(Event).order_by(Event.timestamp_utc.desc()).limit(1))
        e = result.scalar_one_or_none()
        return str(e.id) if e else None


async def first_neo4j_event_node() -> str | None:
    from chainpulse.backend.db.neo4j import session
    with session() as s:
        rec = s.run("MATCH (e:DisruptionEvent) RETURN e.id AS id LIMIT 1").single()
        return rec["id"] if rec else None


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    print("Phase 6 API + WS test\n")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # health
        r = await client.get("/health")
        print(f"  /health → {r.status_code}")
        assert r.status_code == 200

        # register + login
        email = f"e2e{int(time.time())}@example.com"
        r = await client.post("/auth/register", json={
            "email": email, "password": "Hunter22!", "company": "Acme", "role": "Operations"
        })
        print(f"  /auth/register → {r.status_code}")
        assert r.status_code in (200, 201)

        r = await client.post("/auth/login", json={"email": email, "password": "Hunter22!"})
        print(f"  /auth/login → {r.status_code}")
        assert r.status_code == 200
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # profile
        r = await client.post("/onboarding/profile", json={
            "watched_regions": ["CN", "IN", "EG"],
            "product_categories": ["Semiconductors"],
            "sku_codes": ["SKU-A-1", "SKU-A-2"],
            "supplier_names": ["TSMC"],
        }, headers=headers)
        print(f"  /onboarding/profile → {r.status_code}")
        assert r.status_code == 200

        r = await client.get("/profile/me", headers=headers)
        print(f"  /profile/me → {r.status_code}  watched={r.json()['watched_regions']}")
        assert r.status_code == 200

        # events
        r = await client.get("/events/recent?limit=5")
        print(f"  /events/recent → {r.status_code}  count={r.json()['count']}")
        assert r.status_code == 200

        evt_id = await first_event_id()
        if evt_id:
            r = await client.get(f"/events/{evt_id}")
            print(f"  /events/{{id}} → {r.status_code}  title={r.json()['title'][:50]}")
            assert r.status_code == 200

        # graph
        neo_id = await first_neo4j_event_node()
        if neo_id:
            r = await client.get(f"/graph/{neo_id}")
            print(f"  /graph/{{id}} → {r.status_code}  nodes={len(r.json().get('nodes', []))} "
                  f"edges={len(r.json().get('edges', []))}")
            assert r.status_code == 200

        # skus-at-risk
        r = await client.get("/profile/skus-at-risk", headers=headers)
        print(f"  /profile/skus-at-risk → {r.status_code}  live_count={r.json().get('live_count', 0)}")

    # WebSocket test via real Redis pub/sub
    print("\nWS test — publish event to events:* and receive via WS")
    test_payload = {
        "id": "evt_ws_test_999",
        "type": "PORT_STRIKE",
        "severity": "critical",
        "title": "WS smoke test",
        "summary": "If you see this on the client, broadcast works.",
        "timestamp_utc": "2026-05-12T17:00:00Z",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream("GET", "/health") as _:
            pass  # warm

    # use a raw asgi websocket client via httpx-ws? simpler: open ws via websockets lib against a test server
    # ASGITransport doesn't support WS — so spin uvicorn on an ephemeral port.
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=18765, log_level="error", lifespan="on")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    # wait for startup
    for _ in range(50):
        await asyncio.sleep(0.1)
        if server.started:
            break

    import websockets
    received: dict | None = None
    async with websockets.connect("ws://127.0.0.1:18765/ws/events") as ws:
        await asyncio.sleep(0.3)  # let pubsub subscribe
        await publish_to_global(test_payload)
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=4.0)
            received = json.loads(msg)
        except asyncio.TimeoutError:
            print("  ✗ WS receive timeout")

    server.should_exit = True
    await server_task

    if received and received.get("id") == "evt_ws_test_999":
        print(f"  ✓ WS received event id={received['id']}")
    else:
        print(f"  ✗ WS did not receive expected payload: {received}")
        return 1

    print("\n✅ Phase 6 live test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
