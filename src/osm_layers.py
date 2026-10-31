"""Live OpenStreetMap/Overpass exposure-layer adapter.

The adapter returns auditable counts, not a fabricated flood prediction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen


class OSMDataError(RuntimeError):
    pass


def fetch_osm_profile(name: str, south: float, west: float, north: float, east: float, timeout: int = 20) -> dict:
    if south >= north or west >= east:
        raise ValueError("invalid bounding box")
    query = f"""[out:json][timeout:15];(way[highway]({south},{west},{north},{east});node[amenity~\"hospital|clinic|school\"]({south},{west},{north},{east});node[amenity=\"shelter\"]({south},{west},{north},{east}););out count;"""
    request = Request("https://overpass-api.de/api/interpreter", data=query.encode("utf-8"), headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "MonsoonImpactNavigator/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise OSMDataError(f"OpenStreetMap profile unavailable: {exc}") from exc
    elements = payload.get("elements", [])
    if not elements or "tags" not in elements[0] or "total" not in elements[0]["tags"]:
        raise OSMDataError("Overpass returned no count result")
    total = int(elements[0]["tags"]["total"])
    return {"district": name, "osm_elements": total, "source": "OpenStreetMap Overpass API", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "bbox": [south, west, north, east]}
