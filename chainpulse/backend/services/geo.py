"""Geo resolver: port gazetteer (local JSON, fast) → GeoNames fallback (HTTP)."""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from chainpulse.backend.config.settings import get_settings

log = logging.getLogger("chainpulse.geo")

GAZETTEER_PATH = Path(__file__).resolve().parent.parent / "ml" / "port_gazetteer.json"
GEONAMES_URL = "http://api.geonames.org/searchJSON"


class GeoHit(TypedDict, total=False):
    name: str
    lat: float
    lng: float
    country_code: str
    source: str


@lru_cache(maxsize=1)
def _gazetteer() -> dict[str, dict]:
    if not GAZETTEER_PATH.exists():
        return {}
    return json.loads(GAZETTEER_PATH.read_text())


def lookup_gazetteer(location_str: str) -> GeoHit | None:
    if not location_str:
        return None
    key = location_str.strip().lower()
    g = _gazetteer()
    if key in g:
        return {**g[key], "source": "gazetteer"}
    # substring match — "Port of Shanghai" → "shanghai"
    for k, v in g.items():
        if k in key:
            return {**v, "source": "gazetteer"}
    return None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
async def _geonames_query(name: str, username: str) -> dict:
    params = {"q": name, "maxRows": 1, "username": username, "type": "json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(GEONAMES_URL, params=params)
        r.raise_for_status()
        return r.json()


async def lookup_geonames(location_str: str) -> GeoHit | None:
    s = get_settings()
    user = s.geonames_username.strip()
    if not user or not location_str:
        return None
    try:
        data = await _geonames_query(location_str, user)
    except Exception:
        log.warning("geonames lookup failed for %s", location_str)
        return None
    items = data.get("geonames") or []
    if not items:
        return None
    top = items[0]
    return {
        "name": top.get("name") or location_str,
        "lat": float(top.get("lat")),
        "lng": float(top.get("lng")),
        "country_code": top.get("countryCode") or "",
        "source": "geonames",
    }


async def resolve(location_str: str | None, llm_lat: float | None, llm_lng: float | None,
                  llm_country: str | None) -> GeoHit | None:
    """Resolve order: gazetteer → GeoNames → LLM-provided lat/lng (last resort)."""
    if location_str:
        hit = lookup_gazetteer(location_str)
        if hit:
            return hit
        hit = await lookup_geonames(location_str)
        if hit:
            return hit
    if llm_lat is not None and llm_lng is not None:
        return {
            "name": location_str or "Unknown",
            "lat": float(llm_lat),
            "lng": float(llm_lng),
            "country_code": (llm_country or "")[:2].upper(),
            "source": "llm",
        }
    return None
