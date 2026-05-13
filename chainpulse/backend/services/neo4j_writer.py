"""Write DisruptionEvent node + AFFECTS edges into Neo4j. Returns neo4j elementId."""
from __future__ import annotations

import logging
from typing import Any

from chainpulse.backend.db.neo4j import session

log = logging.getLogger("chainpulse.neo4j.writer")


def write_event(event: dict[str, Any]) -> str | None:
    """Create DisruptionEvent node + match nearest port/city, AFFECTS edge."""
    cypher = """
    MERGE (e:DisruptionEvent {id: $id})
    SET e.type = $type,
        e.severity = $severity,
        e.title = $title,
        e.summary = $summary,
        e.source_url = $source_url,
        e.lat = $lat,
        e.lng = $lng,
        e.country_code = $country_code,
        e.timestamp_utc = datetime($timestamp_utc),
        e.delay_min_days = $delay_min,
        e.delay_max_days = $delay_max
    WITH e
    OPTIONAL MATCH (loc) WHERE (loc:Port OR loc:City) AND loc.name = $location_name
    FOREACH (_ IN CASE WHEN loc IS NULL THEN [] ELSE [1] END |
        MERGE (e)-[:AFFECTS]->(loc)
    )
    RETURN elementId(e) AS node_id
    """
    try:
        with session() as s:
            result = s.run(
                cypher,
                id=event["id"],
                type=event["type"],
                severity=event["severity"],
                title=event["title"],
                summary=event.get("summary") or "",
                source_url=event.get("source_url"),
                lat=event.get("lat"),
                lng=event.get("lng"),
                country_code=event.get("country_code"),
                timestamp_utc=event["timestamp_utc"] if isinstance(event["timestamp_utc"], str)
                              else event["timestamp_utc"].isoformat(),
                location_name=event.get("location_name") or "",
                delay_min=event.get("predicted_delay_min_days"),
                delay_max=event.get("predicted_delay_max_days"),
            )
            rec = result.single()
            return rec["node_id"] if rec else None
    except Exception:
        log.exception("neo4j write failed for %s", event.get("id"))
        return None


def seed_minimal_supply_chain() -> None:
    """Bootstraps Port + City nodes for the 40 ports in the gazetteer + sample OEMs."""
    import json
    from pathlib import Path
    gazetteer_path = Path(__file__).resolve().parent.parent / "ml" / "port_gazetteer.json"
    if not gazetteer_path.exists():
        return
    g = json.loads(gazetteer_path.read_text())
    with session() as s:
        s.run("MERGE (r:Region {id:'global', name:'Global'})")
        for key, val in g.items():
            s.run(
                """
                MERGE (p:Port {id: $id})
                SET p.name = $name, p.lat = $lat, p.lng = $lng, p.country_code = $cc
                """,
                id=key.replace(" ", "_"),
                name=val["name"],
                lat=val["lat"],
                lng=val["lng"],
                cc=val["country_code"],
            )
        # sample OEMs
        for oem_id, name, cc in [
            ("oem_apple", "Apple Inc.", "US"),
            ("oem_tesla", "Tesla", "US"),
            ("oem_vw",    "Volkswagen AG", "DE"),
            ("oem_toyota","Toyota", "JP"),
            ("oem_samsung","Samsung Electronics", "KR"),
        ]:
            s.run(
                "MERGE (o:OEM {id:$id}) SET o.name=$name, o.country_code=$cc",
                id=oem_id, name=name, cc=cc,
            )
