"""Major maritime shipping lanes as polylines.

Each lane = ordered list of (lat, lng) waypoints. A disruption is "on-lane"
if it's within ROUTE_BUFFER_KM of any segment.

Seed list covers top 8 global routes; expand later.
"""
from __future__ import annotations

from dataclasses import dataclass

from geopy.distance import geodesic


@dataclass(frozen=True)
class Lane:
    id: str
    name: str
    waypoints: tuple[tuple[float, float], ...]


LANES: tuple[Lane, ...] = (
    Lane("transpacific_east",  "Trans-Pacific Eastbound (CN→US W. Coast)",
         ((31.23,121.47),(35.0,150.0),(40.0,180.0),(40.0,-150.0),(33.74,-118.26))),
    Lane("asia_europe_suez",   "Asia–Europe via Suez",
         ((22.54,114.06),(1.27,103.82),(13.0,82.0),(12.5,45.0),(30.04,32.35),(36.0,15.0),(51.92,4.48))),
    Lane("transatlantic",      "Trans-Atlantic (US E. Coast↔Europe)",
         ((40.66,-74.05),(45.0,-50.0),(48.0,-20.0),(51.92,4.48))),
    Lane("panama_corridor",    "Panama Canal Corridor",
         ((33.74,-118.26),(15.0,-105.0),(9.08,-79.68),(20.0,-70.0),(40.66,-74.05))),
    Lane("intra_asia",         "Intra-Asia (CN↔SEA)",
         ((31.23,121.47),(22.54,114.06),(1.27,103.82),(13.08,100.89))),
    Lane("middle_east_corridor","Middle East Corridor",
         ((24.98,55.06),(12.5,45.0),(30.04,32.35),(36.0,15.0))),
    Lane("australia_asia",     "Australia–Asia",
         ((-33.87,151.21),(-15.0,135.0),(1.27,103.82),(22.54,114.06))),
    Lane("south_america_east", "South America East–Europe",
         ((-23.96,-46.33),(0.0,-30.0),(20.0,-25.0),(36.0,-9.0),(51.92,4.48))),
)

ROUTE_BUFFER_KM = 120


def _point_to_segment_km(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """Geodesic distance from point p to segment a-b.

    Approximate: pick min of endpoint distances + midpoint distance.
    For ROUTE_BUFFER_KM=120 over 1000+ km segments this is good enough.
    """
    return min(
        geodesic(p, a).km,
        geodesic(p, b).km,
        geodesic(p, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)).km,
    )


def lanes_near(lat: float, lng: float, buffer_km: float = ROUTE_BUFFER_KM) -> list[dict]:
    """Returns lanes whose closest segment is within buffer_km of (lat, lng)."""
    hits = []
    p = (lat, lng)
    for lane in LANES:
        best = float("inf")
        for i in range(len(lane.waypoints) - 1):
            d = _point_to_segment_km(p, lane.waypoints[i], lane.waypoints[i + 1])
            if d < best:
                best = d
        if best <= buffer_km:
            hits.append({"id": lane.id, "name": lane.name, "distance_km": round(best, 1)})
    return hits


def supplier_uses_lane(supplier_country: str, lane_id: str) -> bool:
    """Crude mapping — extend when SKU-route data exists."""
    asia = {"CN", "HK", "TW", "JP", "KR", "VN", "TH", "MY", "SG", "ID", "PH"}
    eu = {"DE", "NL", "BE", "FR", "GB", "ES", "IT", "GR", "PL"}
    am = {"US", "CA", "MX", "BR"}
    me = {"AE", "SA", "EG", "IL", "QA"}

    rules = {
        "transpacific_east":   asia | am,
        "asia_europe_suez":    asia | eu | me,
        "transatlantic":       eu | am,
        "panama_corridor":     am,
        "intra_asia":          asia,
        "middle_east_corridor": me | asia | eu,
        "australia_asia":      {"AU", "NZ"} | asia,
        "south_america_east":  am | eu,
    }
    return supplier_country.upper() in rules.get(lane_id, set())
