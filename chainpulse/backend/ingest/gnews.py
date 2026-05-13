"""GNews — 100 req/day free."""
from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from chainpulse.backend.config.settings import get_settings
from chainpulse.backend.ingest.common import publish_raw
from chainpulse.backend.ingest.keywords import QUERY_TERMS

log = logging.getLogger("chainpulse.ingest.gnews")

ENDPOINT = "https://gnews.io/api/v4/search"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
async def _query(term: str, api_key: str) -> dict:
    params = {"q": term, "lang": "en", "max": 10, "apikey": api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(ENDPOINT, params=params)
        r.raise_for_status()
        return r.json()


async def poll_once() -> int:
    s = get_settings()
    key = s.gnews_api_key.strip()
    if not key:
        return 0
    total = 0
    # gnews quota tight: sample a single term per tick, rotate over time.
    import time
    term = QUERY_TERMS[int(time.time() // 900) % len(QUERY_TERMS)]
    try:
        data = await _query(term, key)
    except Exception:
        log.exception("gnews failed term=%s", term)
        return 0
    for art in data.get("articles", []):
        url = art.get("url")
        if not url:
            continue
        article = {
            "source": "gnews",
            "raw_id": url,
            "headline": art.get("title", "").strip(),
            "body": (art.get("description") or "")[:2000],
            "url": url,
            "published_at": art.get("publishedAt"),
        }
        if not article["headline"]:
            continue
        if await publish_raw(article):
            total += 1
    log.info("gnews poll published=%d term=%s", total, term)
    return total
