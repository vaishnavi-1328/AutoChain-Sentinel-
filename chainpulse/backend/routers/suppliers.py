"""/suppliers/geo-resolve — city+country → lat/lng via GeoNames then gazetteer."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from chainpulse.backend.schemas.order import GeoResolveResponse
from chainpulse.backend.services.geo import lookup_gazetteer, lookup_geonames

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("/geo-resolve", response_model=GeoResolveResponse)
async def geo_resolve(
    city: str = Query(min_length=1),
    country: str = Query(min_length=2, max_length=2),
) -> GeoResolveResponse:
    query = f"{city}, {country.upper()}"

    hit = await lookup_geonames(query) or await lookup_geonames(city)
    if not hit:
        hit = lookup_gazetteer(city) or lookup_gazetteer(query)
    if not hit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"could not resolve {query}")

    return GeoResolveResponse(
        lat=float(hit["lat"]),
        lng=float(hit["lng"]),
        resolved_name=hit.get("name") or city,
        country_code=hit.get("country_code") or country.upper(),
        source=hit.get("source"),
    )
