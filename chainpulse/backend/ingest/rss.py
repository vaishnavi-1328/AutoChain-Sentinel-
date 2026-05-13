"""RSS feed poller (feedparser)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import feedparser

from chainpulse.backend.ingest.common import publish_raw
from chainpulse.backend.ingest.keywords import RSS_FEEDS

log = logging.getLogger("chainpulse.ingest.rss")


def _parse_published(entry) -> str:
    if getattr(entry, "published_parsed", None):
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


async def _poll_feed(url: str) -> int:
    feed = await asyncio.to_thread(feedparser.parse, url)
    count = 0
    for entry in feed.entries:
        article = {
            "source": "rss",
            "raw_id": entry.get("id") or entry.get("link") or entry.get("title", ""),
            "headline": entry.get("title", "").strip(),
            "body": (entry.get("summary") or "")[:2000],
            "url": entry.get("link"),
            "published_at": _parse_published(entry),
        }
        if not article["raw_id"] or not article["headline"]:
            continue
        if await publish_raw(article):
            count += 1
    return count


async def poll_once() -> int:
    total = 0
    for url in RSS_FEEDS:
        try:
            total += await _poll_feed(url)
        except Exception:
            log.exception("rss feed failed: %s", url)
    log.info("rss poll published=%d", total)
    return total
