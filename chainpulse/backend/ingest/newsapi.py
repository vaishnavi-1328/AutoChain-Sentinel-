"""NewsAPI.org poller — /v2/everything across rotating query terms."""
from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from chainpulse.backend.config.settings import get_settings
from chainpulse.backend.ingest.common import publish_raw
from chainpulse.backend.ingest.keywords import QUERY_TERMS

log = logging.getLogger("chainpulse.ingest.newsapi")

ENDPOINT = "https://newsapi.org/v2/everything"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
async def _query(term: str, api_key: str) -> dict:
    params = {"q": term, "language": "en", "sortBy": "publishedAt", "pageSize": 25}
    headers = {"X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(ENDPOINT, params=params, headers=headers)
        r.raise_for_status()
        return r.json()


async def poll_once() -> int:
    s = get_settings()
    if not s.newsapi_key:
        return 0
    total = 0
    for term in QUERY_TERMS:
        try:
            data = await _query(term, s.newsapi_key)
        except Exception:
            log.exception("newsapi term failed: %s", term)
            continue
        for art in data.get("articles", []):
            url = art.get("url")
            if not url:
                continue
            article = {
                "source": "newsapi",
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
    log.info("newsapi poll published=%d", total)
    return total
