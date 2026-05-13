"""Guardian Open Platform — 12k req/day free."""
from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from chainpulse.backend.config.settings import get_settings
from chainpulse.backend.ingest.common import publish_raw
from chainpulse.backend.ingest.keywords import QUERY_TERMS

log = logging.getLogger("chainpulse.ingest.guardian")

ENDPOINT = "https://content.guardianapis.com/search"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
async def _query(term: str, api_key: str) -> dict:
    params = {
        "q": term,
        "api-key": api_key,
        "show-fields": "trailText,body",
        "page-size": 25,
        "order-by": "newest",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(ENDPOINT, params=params)
        r.raise_for_status()
        return r.json()


async def poll_once() -> int:
    s = get_settings()
    key = s.guardian_api_key.strip()
    if not key:
        return 0
    total = 0
    for term in QUERY_TERMS:
        try:
            data = await _query(term, key)
        except Exception:
            log.exception("guardian term failed: %s", term)
            continue
        for item in data.get("response", {}).get("results", []):
            url = item.get("webUrl")
            if not url:
                continue
            fields = item.get("fields") or {}
            article = {
                "source": "guardian",
                "raw_id": item.get("id") or url,
                "headline": item.get("webTitle", "").strip(),
                "body": (fields.get("trailText") or "")[:2000],
                "url": url,
                "published_at": item.get("webPublicationDate"),
            }
            if not article["headline"]:
                continue
            if await publish_raw(article):
                total += 1
    log.info("guardian poll published=%d", total)
    return total
