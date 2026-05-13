"""GDELT poller. Reads lastupdate.txt → fetches .export.CSV → filters CAMEO event codes."""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from chainpulse.backend.ingest.common import publish_raw

log = logging.getLogger("chainpulse.ingest.gdelt")

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
TARGET_CAMEO_PREFIXES = ("14", "17", "18", "20")
HTTP_TIMEOUT = 30.0


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _http_get(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


async def _latest_export_url() -> str | None:
    body = (await _http_get(LASTUPDATE_URL)).decode("utf-8", errors="ignore")
    for line in body.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2].endswith(".export.CSV.zip"):
            return parts[2]
    return None


def _parse_csv_zip(blob: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as f:
            text = f.read().decode("utf-8", errors="ignore")
    return [row for row in csv.reader(io.StringIO(text), delimiter="\t")]


async def poll_once() -> int:
    url = await _latest_export_url()
    if url is None:
        log.warning("no GDELT export found")
        return 0

    blob = await _http_get(url)
    rows = _parse_csv_zip(blob)
    count = 0
    for row in rows:
        # GDELT v2 column 26 = EventCode (CAMEO). Defensive index.
        if len(row) < 60:
            continue
        event_code = row[26]
        if not event_code or not event_code.startswith(TARGET_CAMEO_PREFIXES):
            continue

        global_event_id = row[0]
        action_geo_country = row[51] or ""
        action_geo_name = row[53] or ""
        source_url = row[57] if len(row) > 57 else ""

        headline = f"GDELT event {event_code} in {action_geo_name or action_geo_country}".strip()
        article = {
            "source": "gdelt",
            "raw_id": global_event_id,
            "headline": headline,
            "body": f"event_code={event_code} country={action_geo_country} location={action_geo_name}",
            "url": source_url or None,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        if await publish_raw(article):
            count += 1
    log.info("gdelt poll published=%d", count)
    return count
