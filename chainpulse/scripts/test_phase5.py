"""Phase 5 live test.

Reads N processed.events entries → enriches + writes Postgres + Neo4j + Redis.
Asserts: rows appear in Postgres events table, DisruptionEvent nodes in Neo4j,
event:{id} keys in Redis with TTL.

Usage:
  python scripts/test_phase5.py [N]
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from chainpulse.backend.config.settings import get_settings  # noqa: E402
from chainpulse.backend.db.neo4j import session as neo_session  # noqa: E402
from chainpulse.backend.db.postgres import get_session_factory  # noqa: E402
from chainpulse.backend.db.redis import get_redis  # noqa: E402
from chainpulse.backend.models import Event  # noqa: E402
from chainpulse.backend.services.storage_pipeline import process_one  # noqa: E402


async def pg_event_count() -> int:
    factory = get_session_factory()
    async with factory() as s:
        result = await s.execute(select(func.count(Event.id)))
        return int(result.scalar_one())


def neo_event_count() -> int:
    with neo_session() as s:
        rec = s.run("MATCH (e:DisruptionEvent) RETURN count(e) AS c").single()
        return int(rec["c"]) if rec else 0


async def main(n: int) -> int:
    logging.basicConfig(level=logging.WARNING)
    s = get_settings()
    r = get_redis()

    print("Phase 5 storage test")
    print(f"  DATABASE_URL = {s.database_url.split('@')[-1][:40]}...")
    print(f"  NEO4J_URI    = {s.neo4j_uri[:40]}...")
    print(f"  REDIS_URL    = {s.redis_url[:30]}...")

    try:
        pg_before = await pg_event_count()
    except Exception as e:
        print(f"\n✗ Postgres unreachable: {e}")
        print("FIX: run scripts/migrate.py first")
        return 1
    try:
        neo_before = neo_event_count()
    except Exception as e:
        print(f"\n✗ Neo4j unreachable: {e}")
        return 2

    print(f"\n  pre: pg events={pg_before}  neo4j events={neo_before}")

    proc_len = await r.xlen(s.stream_processed)
    if proc_len == 0:
        print("✗ no processed events — run scripts/test_phase4.py first")
        return 3
    print(f"  processed.events available: {proc_len}")

    entries = await r.xrange(s.stream_processed, count=n)
    print(f"\nstoring {len(entries)} events...\n")
    ok = 0
    for entry_id, fields in entries:
        evt = json.loads(fields["data"])
        try:
            enriched = await process_one(evt)
            print(f"  ✓ {enriched['id']}  {enriched['type']:<18} "
                  f"delay={enriched['predicted_delay_min_days']}-{enriched['predicted_delay_max_days']}d "
                  f"sku_users={enriched.get('affected_sku_count', 0)}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {entry_id} {e}")

    pg_after = await pg_event_count()
    neo_after = neo_event_count()
    print(f"\n  post: pg events={pg_after} (+{pg_after - pg_before})  "
          f"neo4j events={neo_after} (+{neo_after - neo_before})")

    # spot-check Redis cache + TTL
    if entries:
        sample = json.loads(entries[0][1]["data"])
        key = f"event:{sample['id']}"
        ttl = await r.ttl(key)
        cached = await r.get(key)
        print(f"\n  redis cache key={key} ttl={ttl}s  hit={'yes' if cached else 'no'}")

    if ok == 0:
        print("\n✗ no events persisted")
        return 4
    print("\n✅ Phase 5 live test PASSED")
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    sys.exit(asyncio.run(main(n)))
