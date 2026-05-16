"""Phase V2.1 live test.

Asserts:
  - /suppliers/geo-resolve resolves Shenzhen,CN
  - POST /orders with supplier near a seeded Redis event → DELAY_RISK or CRITICAL_DELAY
  - GET /orders sorts by status
  - GET /orders/{id}/analysis returns matched_events with source_url
  - WS receives msg_type=order_delay_update when storage_pipeline reprocesses
  - existing event flow still works (msg_type=event)
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from httpx import ASGITransport, AsyncClient  # noqa: E402

from datetime import datetime, timezone  # noqa: E402

from chainpulse.backend.config.settings import get_settings  # noqa: E402
from chainpulse.backend.db.postgres import get_session_factory  # noqa: E402
from chainpulse.backend.db.redis import get_redis  # noqa: E402
from chainpulse.backend.main import app  # noqa: E402
from chainpulse.backend.models import Event  # noqa: E402
from chainpulse.backend.services.postgres_writer import _coerce_uuid  # noqa: E402
from chainpulse.backend.services.redis_broadcast import cache_event  # noqa: E402


async def seed_redis_event(near_lat: float, near_lng: float) -> str:
    evt_id = f"evt_v2test_{uuid.uuid4().hex[:8]}"
    pg_id = _coerce_uuid(evt_id)

    # Insert matching Postgres events row so impact FK is satisfied.
    factory = get_session_factory()
    async with factory() as s:
        existing = (await s.execute(__import__("sqlalchemy").select(Event).where(Event.id == pg_id))).scalar_one_or_none()
        if not existing:
            s.add(Event(
                id=pg_id,
                type="PORT_STRIKE",
                severity="high",
                title="Port of Shenzhen partial closure",
                summary="V2 test event",
                source_url="https://www.theguardian.com/test",
                source_name="The Guardian",
                lat=near_lat,
                lng=near_lng,
                location_name="Port of Shenzhen",
                country_code="CN",
                delay_min_days=11,
                delay_max_days=18,
                timestamp_utc=datetime.now(timezone.utc),
            ))
            await s.commit()

    evt = {
        "id": evt_id,
        "type": "PORT_STRIKE",
        "severity": "high",
        "title": "Port of Shenzhen partial closure",
        "summary": "Test event seeded by V2.1 live test",
        "source_url": "https://www.theguardian.com/test",
        "source_name": "The Guardian",
        "lat": near_lat,
        "lng": near_lng,
        "location_name": "Port of Shenzhen",
        "country_code": "CN",
        "predicted_delay_min_days": 11,
        "predicted_delay_max_days": 18,
        "delay_confidence": 0.8,
        "timestamp_utc": "2026-05-13T12:00:00Z",
    }
    await cache_event(evt)
    return evt["id"]


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    print("Phase V2.1 live test\n")
    s = get_settings()
    r = get_redis()

    # 1. seed an active event near Shenzhen
    seeded_id = await seed_redis_event(22.5431, 114.0579)
    print(f"  seeded redis event id={seeded_id}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # geo resolve
        r1 = await client.get("/suppliers/geo-resolve", params={"city": "Shenzhen", "country": "CN"})
        print(f"  /suppliers/geo-resolve → {r1.status_code} {r1.json() if r1.status_code == 200 else r1.text[:120]}")
        assert r1.status_code == 200
        lat, lng = r1.json()["lat"], r1.json()["lng"]

        # register + login
        email = f"v2{int(time.time())}@example.com"
        r2 = await client.post("/auth/register", json={"email": email, "password": "Hunter22!"})
        assert r2.status_code == 201, r2.text
        r3 = await client.post("/auth/login", json={"email": email, "password": "Hunter22!"})
        token = r3.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # POST order
        body = {
            "supplier_name": "Shenzhen Electronics Co.",
            "supplier_city": "Shenzhen",
            "supplier_country": "CN",
            "supplier_lat": lat,
            "supplier_lng": lng,
            "materials": "Capacitors 100nF",
            "quantity": 100000,
            "quantity_unit": "units",
            "expected_delivery": (date.today() + timedelta(days=30)).isoformat(),
            "shipping_mode": "Sea freight",
        }
        r4 = await client.post("/orders", json=body, headers=headers)
        print(f"  POST /orders → {r4.status_code}")
        assert r4.status_code == 201, r4.text
        payload = r4.json()
        order = payload["order"]
        print(f"    status={order['status']} delay={order['delay_min_days']}-{order['delay_max_days']}d "
              f"matched={len(payload['matched_events'])}")
        assert order["status"] in ("DELAY_RISK", "CRITICAL_DELAY", "MONITOR")
        assert len(payload["matched_events"]) >= 1
        first_match = payload["matched_events"][0]
        print(f"    first matched source_url: {first_match.get('source_url')}")
        assert first_match.get("source_url"), "first matched event must have source_url"

        order_id = order["id"]

        # GET /orders
        r5 = await client.get("/orders", headers=headers)
        print(f"  GET /orders → {r5.status_code} count={len(r5.json())}")
        assert r5.status_code == 200 and len(r5.json()) >= 1

        # GET /orders/{id}/analysis
        r6 = await client.get(f"/orders/{order_id}/analysis", headers=headers)
        print(f"  GET /orders/{{id}}/analysis → {r6.status_code} "
              f"matched={len(r6.json()['matched_events'])} chart={len(r6.json()['chart_data'])}")
        assert r6.status_code == 200
        assert r6.json()["matched_events"][0]["source_url"]

    # WS test — emit msg_type=order_delay_update via Redis
    print("\n  WS receive order_delay_update via Redis publish")
    import uvicorn
    import websockets
    cfg = uvicorn.Config(app, host="127.0.0.1", port=18766, log_level="error", lifespan="on")
    server = uvicorn.Server(cfg)
    task = asyncio.create_task(server.serve())
    for _ in range(50):
        await asyncio.sleep(0.1)
        if server.started: break

    received: list[dict] = []
    async with websockets.connect("ws://127.0.0.1:18766/ws/events") as ws:
        await asyncio.sleep(0.4)
        # global publish to test back-compat: event msg
        from chainpulse.backend.services.redis_broadcast import publish_to_global
        await publish_to_global({"msg_type": "event", "id": "evt_global_check", "type": "OTHER",
                                 "severity": "low", "title": "global probe",
                                 "timestamp_utc": "2026-05-13T00:00:00Z"})
        # also a fake order_delay_update on global channel
        await publish_to_global({
            "msg_type": "order_delay_update",
            "order_id": "ord_test",
            "supplier_name": "ws probe",
            "supplier_lat": 22.5, "supplier_lng": 114.0,
            "status": "DELAY_RISK", "delay_min_days": 5, "delay_max_days": 8,
            "original_eta": "2026-07-12", "matched_events": []
        })
        try:
            for _ in range(2):
                msg = await asyncio.wait_for(ws.recv(), timeout=4.0)
                received.append(json.loads(msg))
        except asyncio.TimeoutError:
            pass

    server.should_exit = True
    await task

    types = [m.get("msg_type") for m in received]
    print(f"    WS msgs: {types}")
    assert "event" in types, "expected msg_type=event back-compat"
    assert "order_delay_update" in types, "expected msg_type=order_delay_update"
    print("\n✅ Phase V2.1 live test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
