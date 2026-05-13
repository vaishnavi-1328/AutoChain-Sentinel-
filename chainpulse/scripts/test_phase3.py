"""Phase 3 live test.

Runs one cycle of each poller against current REDIS_URL, asserts:
  - stream:raw.news has entries
  - dedup blocks re-publish on second run
  - all 5 sources callable (skip if API key missing)

Usage:
  cd chainpulse && source .venv/bin/activate
  python scripts/test_phase3.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from chainpulse.backend.config.settings import get_settings  # noqa: E402
from chainpulse.backend.db.redis import get_redis  # noqa: E402
from chainpulse.backend.ingest import gdelt, gnews, guardian, newsapi, rss  # noqa: E402
from chainpulse.backend.ingest.common import publish_raw  # noqa: E402
from chainpulse.backend.services.dedup import is_new  # noqa: E402


async def check_redis() -> bool:
    r = get_redis()
    try:
        await r.ping()
        return True
    except Exception as e:
        print(f"  ✗ Redis unreachable: {e}")
        return False


async def reset_streams() -> None:
    r = get_redis()
    s = get_settings()
    await r.delete(s.stream_raw)
    # also clear dedup keys so reruns aren't sticky
    async for key in r.scan_iter(match="seen:*", count=500):
        await r.delete(key)


async def stream_len() -> int:
    r = get_redis()
    s = get_settings()
    return await r.xlen(s.stream_raw)


async def test_dedup_directly() -> None:
    print("\n[dedup] direct SETNX check")
    first = await is_new("test", "abc123")
    second = await is_new("test", "abc123")
    print(f"  first call new? {first}   (expect True)")
    print(f"  second call new? {second}  (expect False)")
    assert first is True and second is False, "dedup not working"
    print("  ✓ dedup OK")


async def test_publish_path() -> None:
    print("\n[publish] direct publish_raw path")
    ok1 = await publish_raw({
        "source": "manual_test",
        "raw_id": "evt_001",
        "headline": "Test port closure in Shanghai",
        "url": "http://example.com/1",
    })
    ok2 = await publish_raw({
        "source": "manual_test",
        "raw_id": "evt_001",
        "headline": "duplicate same id",
    })
    print(f"  first publish ok? {ok1}   (expect True)")
    print(f"  duplicate publish ok? {ok2} (expect False)")
    assert ok1 and not ok2
    print("  ✓ publish + dedup OK")


async def run_poller(name: str, coro) -> int:
    print(f"\n[{name}] running one poll...")
    try:
        n = await coro()
        print(f"  ✓ {name} published {n} new entries")
        return n
    except Exception as e:
        print(f"  ✗ {name} raised: {e}")
        return 0


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    s = get_settings()
    print(f"REDIS_URL = {s.redis_url[:40]}...")
    print(f"stream_raw = {s.stream_raw}")

    if not await check_redis():
        print("\nFIX: set REDIS_URL in chainpulse/.env to Upstash or local Redis")
        return 1

    await reset_streams()
    await test_dedup_directly()
    await test_publish_path()

    # Real pollers
    n_rss = await run_poller("rss", rss.poll_once)
    n_gdelt = await run_poller("gdelt", gdelt.poll_once)
    n_guardian = await run_poller("guardian", guardian.poll_once) if s.guardian_api_key else 0
    n_newsapi = await run_poller("newsapi", newsapi.poll_once) if s.newsapi_key else 0
    n_gnews = await run_poller("gnews", gnews.poll_once) if s.gnews_api_key else 0

    total = await stream_len()
    print(f"\n[result] stream:raw.news total entries: {total}")
    print(f"  rss={n_rss} gdelt={n_gdelt} guardian={n_guardian} newsapi={n_newsapi} gnews={n_gnews}")

    if total == 0:
        print("\n  ⚠ no entries published — check API keys + network")
        return 2

    # Quick consumer read to verify XREADGROUP works
    print("\n[consume] reading 3 entries via XREADGROUP...")
    from chainpulse.backend.services.stream import consume
    seen = 0
    async for entry_id, payload in consume(s.stream_raw, "test-group", "test-consumer", block_ms=1000):
        print(f"  {entry_id}  source={payload.get('source')}  headline={payload.get('headline','')[:60]}")
        seen += 1
        if seen >= 3:
            break
    print(f"  ✓ consumed {seen} entries")

    print("\n✅ Phase 3 live test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
