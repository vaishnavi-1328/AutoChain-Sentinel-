"""Phase 4 live test.

Reads N raw entries from stream:raw.news, runs Groq extraction + geo resolve,
publishes to stream:processed.events, prints results.

Usage:
  python scripts/test_phase4.py [N]
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
from chainpulse.backend.services.nlp_pipeline import process_one  # noqa: E402
from chainpulse.backend.services.stream import publish  # noqa: E402


async def main(n: int) -> int:
    logging.basicConfig(level=logging.WARNING)
    s = get_settings()
    print(f"GROQ_MODEL = {s.groq_model}")
    if not s.groq_api_key:
        print("✗ GROQ_API_KEY missing; set in chainpulse/.env")
        return 1

    r = get_redis()
    raw_len = await r.xlen(s.stream_raw)
    print(f"stream:raw.news entries available: {raw_len}")
    if raw_len == 0:
        print("✗ no raw entries — run scripts/test_phase3.py first to populate")
        return 2

    entries = await r.xrange(s.stream_raw, count=n)
    print(f"\nprocessing {len(entries)} entries through Groq + geo resolver...\n")

    import json
    successes = 0
    drops = 0
    for entry_id, fields in entries:
        raw = json.loads(fields["data"])
        headline = raw.get("headline", "")[:80]
        print(f"[{entry_id}] src={raw.get('source')}  {headline}")
        try:
            event = await process_one(raw)
        except Exception as e:
            print(f"   ✗ error: {e}")
            continue
        if event is None:
            print("   ↳ DROPPED (irrelevant / low confidence)")
            drops += 1
            continue
        await publish(s.stream_processed, event.model_dump(mode="json"))
        print(f"   ✓ {event.type:<18} sev={event.severity:<8} {event.location_name or '?':<25} "
              f"({event.lat},{event.lng})")
        successes += 1

    processed_len = await r.xlen(s.stream_processed)
    print(f"\n[result] processed published this run: {successes}")
    print(f"         dropped: {drops}")
    print(f"         stream:processed.events total: {processed_len}")
    if successes == 0:
        print("\n⚠ no events extracted — check Groq key + model name")
        return 3
    print("\n✅ Phase 4 live test PASSED")
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    sys.exit(asyncio.run(main(n)))
