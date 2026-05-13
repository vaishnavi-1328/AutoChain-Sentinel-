"""/graph/{event_id} — Neo4j subgraph for graph modal."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from neo4j.time import Date as NeoDate
from neo4j.time import DateTime as NeoDateTime

from chainpulse.backend.db.neo4j import session as neo_session

router = APIRouter(prefix="/graph", tags=["graph"])


def _serialize(v: Any) -> Any:
    if isinstance(v, (NeoDateTime, NeoDate)):
        return v.iso_format()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _serialize(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_serialize(x) for x in v]
    return v


@router.get("/{event_id}")
def subgraph(event_id: str, depth: int = Query(2, ge=1, le=4)) -> dict:
    cypher = f"""
    MATCH path = (e:DisruptionEvent {{id: $event_id}})-[*1..{depth}]-(n)
    WHERE NOT n:UserProfile
    WITH collect(DISTINCT path) AS paths
    UNWIND paths AS p
    UNWIND nodes(p) AS nd
    UNWIND relationships(p) AS rl
    WITH collect(DISTINCT nd) AS ns, collect(DISTINCT rl) AS rs
    RETURN
      [n IN ns | {{
          id: elementId(n),
          labels: labels(n),
          props: properties(n)
      }}] AS nodes,
      [r IN rs | {{
          id: elementId(r),
          type: type(r),
          from: elementId(startNode(r)),
          to: elementId(endNode(r)),
          props: properties(r)
      }}] AS edges
    """
    try:
        with neo_session() as s:
            result = s.run(cypher, event_id=event_id).single()
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"neo4j query failed: {e}")

    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not in graph")
    return {
        "nodes": _serialize(result["nodes"]),
        "edges": _serialize(result["edges"]),
    }
