"""Groq Llama 3.1 single-call NER + classification + severity + summary.

One LLM call replaces spaCy NER + distilbert classifier + rule-based severity scorer.
Output is JSON. Strict prompt + response_format=json_object.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential

from chainpulse.backend.config.settings import get_settings

log = logging.getLogger("chainpulse.nlp.groq")

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncGroq(api_key=s.groq_api_key)
    return _client


SYSTEM_PROMPT = """You are a supply-chain disruption analyst. Read the news headline and body, then extract a structured event.

Output JSON ONLY with this exact schema:
{
  "is_supply_chain": boolean,        // false if irrelevant to supply chain
  "type": "PORT_STRIKE" | "WEATHER_EVENT" | "FACTORY_CLOSURE" | "SANCTIONS" | "GEOPOLITICAL" | "LOGISTICS_DELAY" | "OTHER",
  "severity": "critical" | "high" | "medium" | "low",
  "title": string,                   // <= 100 chars, headline rewritten cleanly
  "summary": string,                 // <= 280 chars
  "location_name": string,           // city or port name, e.g. "Port of Shanghai" or "Suez Canal"
  "country_code": string,            // ISO-3166 alpha-2, e.g. "CN"
  "lat": number | null,
  "lng": number | null,
  "confidence": number               // 0.0 to 1.0
}

Severity rules:
- critical: full port closure, force majeure, major strike halting ops
- high: partial closure, strike, typhoon landfall, major sanctions
- medium: slowdown, weather warning, tariff change, minor disruption
- low: advisory, monitoring, scheduled outage

If headline is NOT supply-chain relevant (sports, politics unrelated to trade, entertainment), set is_supply_chain=false and use type=OTHER, confidence < 0.3.

Infer location if implied: "Suez Canal blockage" → location_name="Suez Canal", country_code="EG".

Output ONLY the JSON object. No markdown fences, no prose."""


def _strip_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def _call_groq(headline: str, body: str, model: str) -> dict[str, Any]:
    client = _get_client()
    user_msg = f"Headline: {headline}\n\nBody: {body[:800]}"
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(_strip_json(content))


async def extract(headline: str, body: str = "") -> dict[str, Any] | None:
    """Returns parsed dict or None if Groq call fails or output is unparseable."""
    s = get_settings()
    if not s.groq_api_key:
        log.warning("GROQ_API_KEY missing; skipping extraction")
        return None
    try:
        data = await _call_groq(headline, body, s.groq_model)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("groq call failed")
        return None

    # normalize / defensively coerce
    data.setdefault("is_supply_chain", True)
    data.setdefault("type", "OTHER")
    data.setdefault("severity", "low")
    data.setdefault("title", headline[:100])
    data.setdefault("summary", (body or headline)[:280])
    data.setdefault("location_name", "")
    data.setdefault("country_code", "")
    data.setdefault("lat", None)
    data.setdefault("lng", None)
    try:
        data["confidence"] = float(data.get("confidence", 0.5))
    except Exception:
        data["confidence"] = 0.5

    # constrain to allowed enums
    valid_types = {"PORT_STRIKE","WEATHER_EVENT","FACTORY_CLOSURE","SANCTIONS","GEOPOLITICAL","LOGISTICS_DELAY","OTHER"}
    if data["type"] not in valid_types:
        data["type"] = "OTHER"
    valid_sev = {"critical","high","medium","low"}
    if data["severity"] not in valid_sev:
        data["severity"] = "low"

    return data
