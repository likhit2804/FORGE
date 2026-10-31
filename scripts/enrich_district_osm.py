"""Build auditable district road, waterway, and public-service proxies from OSM."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "MonsoonImpactNavigator/0.1 (research prototype)"


def _polygons(geometry: dict) -> list[list[list[list[float]]]]:
    if geometry.get("type") == "Polygon":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiPolygon":
        return geometry.get("coordinates", [])
    raise ValueError(f"unsupported boundary geometry: {geometry.get('type')}")


def _ring_area_km2(ring: list[list[float]], latitude: float) -> float:
    """Approximate ring area in a local equirectangular projection."""
    scale_x = 111.32 * max(0.01, abs(math.cos(math.radians(latitude))))
    points = [(coordinate[0] * scale_x, coordinate[1] * 111.32) for coordinate in ring]
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1]
                   - points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points))) / 2.0)


def area_km2(geometry: dict) -> float:
    polygons = _polygons(geometry)
    latitudes = [point[1] for polygon in polygons for ring in polygon for point in ring]
    latitude = sum(latitudes) / max(1, len(latitudes))
    return sum(max(0.0, _ring_area_km2(polygon[0], latitude)
                   - sum(_ring_area_km2(hole, latitude) for hole in polygon[1:]))
               for polygon in polygons if polygon)


def _ring_contains(ring: list[list[float]], lon: float, lat: float) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[0], previous[1]
        x2, y2 = current[0], current[1]
        if ((y1 > lat) != (y2 > lat)) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def _geometry_covers(geometry: dict, lon: float, lat: float) -> bool:
    return any(polygon and _ring_contains(polygon[0], lon, lat)
               and not any(_ring_contains(hole, lon, lat) for hole in polygon[1:])
               for polygon in _polygons(geometry))


def build_query(geometry: dict) -> tuple[str, tuple[float, float, float, float]]:
    coordinates = [point for polygon in _polygons(geometry) for ring in polygon for point in ring]
    west = min(point[0] for point in coordinates)
    east = max(point[0] for point in coordinates)
    south = min(point[1] for point in coordinates)
    north = max(point[1] for point in coordinates)
    bbox = (south, west, north, east)
    box = ",".join(f"{value:.6f}" for value in bbox)
    query = f"""[out:json][timeout:60];
(
 way[highway]({box});
 nwr[amenity~\"hospital|clinic|doctors|shelter|school\"]({box});
 way[waterway~\"river|stream|canal\"]({box});
);
out center tags;"""
    return query, bbox


def fetch_features(name: str, geometry: dict, timeout: int = 45) -> dict:
    query, bbox = build_query(geometry)
    request = Request(OVERPASS_URL, data=urlencode({"data": query}).encode("utf-8"),
                      headers={"Content-Type": "application/x-www-form-urlencoded",
                               "User-Agent": USER_AGENT})
    payload = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

    counts = {"road_way_count": 0, "waterway_way_count": 0, "hospital_count": 0,
              "clinic_count": 0, "shelter_count": 0, "school_count": 0}
    seen: set[tuple[str, int]] = set()
    for element in payload.get("elements", []):
        kind, osm_id = element.get("type"), element.get("id")
        if kind not in {"node", "way", "relation"} or not isinstance(osm_id, int):
            continue
        center = element.get("center", element)
        lat, lon = center.get("lat"), center.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if not _geometry_covers(geometry, lon, lat):
            continue
        identity = (kind, osm_id)
        if identity in seen:
            continue
        seen.add(identity)
        tags = element.get("tags", {})
        highway, waterway, amenity = tags.get("highway"), tags.get("waterway"), tags.get("amenity")
        if highway:
            counts["road_way_count"] += 1
        if waterway in {"river", "stream", "canal"}:
            counts["waterway_way_count"] += 1
        if amenity == "hospital":
            counts["hospital_count"] += 1
        elif amenity in {"clinic", "doctors"}:
            counts["clinic_count"] += 1
        elif amenity == "shelter":
            counts["shelter_count"] += 1
        elif amenity == "school":
            counts["school_count"] += 1

    area = area_km2(geometry)
    counts["area_km2_approx"] = round(area, 2)
    counts["road_ways_per_100_km2"] = round(counts["road_way_count"] / max(area, 0.01) * 100, 3)
    counts["waterway_ways_per_100_km2"] = round(counts["waterway_way_count"] / max(area, 0.01) * 100, 3)
    return {"district": name, **counts, "bbox_south_west_north_east": list(bbox),
            "osm_elements_returned": len(payload.get("elements", []))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", type=Path, default=Path("data/boundaries/tamil_nadu_districts.geojson"))
    parser.add_argument("--output", type=Path, default=Path("data/layers/district_osm.json"))
    parser.add_argument("--pause-seconds", type=float, default=1.5)
    parser.add_argument("--limit", type=int, help="Process only the first N districts (for a smoke test).")
    parser.add_argument("--resume", action="store_true", help="Keep successful records already in the output file.")
    args = parser.parse_args()

    boundary_data = json.loads(args.boundaries.read_text(encoding="utf-8"))
    features = boundary_data.get("features", [])
    existing = {}
    if args.resume and args.output.is_file():
        prior = json.loads(args.output.read_text(encoding="utf-8"))
        existing = {row["district"]: row for row in prior.get("records", [])}
    errors = []
    records = dict(existing)
    selected = features[:args.limit] if args.limit else features

    for index, feature in enumerate(selected, start=1):
        name = feature.get("properties", {}).get("shapeName")
        if name in records:
            continue
        try:
            records[name] = fetch_features(name, feature["geometry"])
            print(f"[{index}/{len(selected)}] {name}: roads={records[name]['road_way_count']}, hospitals={records[name]['hospital_count']}, shelters={records[name]['shelter_count']}")
        except Exception as exc:
            errors.append({"district": name, "error": str(exc)})
            print(f"[{index}/{len(selected)}] {name}: failed: {exc}")
        payload = {"source": "OpenStreetMap contributors via Overpass API",
                   "source_url": OVERPASS_URL, "license": "Open Database License (ODbL)",
                   "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "boundary_id": boundary_data.get("metadata", {}).get("district_boundary_id"),
                   "method": "Query district bounding box; count unique road/waterway ways and amenity features whose OSM node or way centre lies inside the district polygon.",
                   "limitations": ["OSM coverage is incomplete and uneven; counts are mapping proxies, not authoritative facility inventories.",
                                   "Road-way counts are not road length or passability.",
                                   "Waterway-way counts do not measure river proximity, flood extent, or drainage capacity.",
                                   "Representative centres and district boundary geometry can omit features crossing polygon edges."],
                   "records": list(records.values()), "errors": errors}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, args.output)
        if index < len(selected):
            time.sleep(max(0.0, args.pause_seconds))

    print(f"Saved {len(records)} OSM district profiles; failures={len(errors)} to {args.output}")
    return 0 if records and not errors and len(records) == len(features) else 1


if __name__ == "__main__":
    raise SystemExit(main())
