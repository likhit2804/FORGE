"""Load versioned district polygons and optional derived district features."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from .navigator import rank_normalise


ALIASES = {
    "kancheepuram": "kanchipuram",
    "thiruvallur": "tiruvallur",
    "tuticorin": "thoothukudi",
    "thoothukkudi": "thoothukudi",
    "kanniyakumari": "kanyakumari",
    "tinnevelly": "tirunelveli",
}


def canonical_district(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    plain = " ".join(plain.replace("_", " ").split())
    return ALIASES.get(plain, plain)


def load_district_layers(root: Path) -> dict:
    boundary_path = root / "data" / "boundaries" / "tamil_nadu_districts.geojson"
    if not boundary_path.is_file():
        return {"geojson": None, "centroids": {}, "exposure": {}, "vulnerability": {}, "sources": {}}
    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    try:
        from shapely.geometry import shape
    except ImportError:
        return {"geojson": geojson, "centroids": {}, "exposure": {}, "vulnerability": {}, "sources": {}}
    centroids = {}
    source_names = {}
    for feature in geojson.get("features", []):
        name = feature.get("properties", {}).get("shapeName")
        if not name or not feature.get("geometry"):
            continue
        point = shape(feature["geometry"]).representative_point()
        key = canonical_district(name)
        centroids[key] = {"latitude": point.y, "longitude": point.x, "name": name}
        source_names[key] = name

    exposure: dict[str, float] = {}
    terrain_path = root / "data" / "layers" / "district_terrain.json"
    if terrain_path.is_file():
        terrain = json.loads(terrain_path.read_text(encoding="utf-8"))
        records = terrain.get("records", [])
        values = [float(row["elevation_m"]) for row in records if isinstance(row.get("elevation_m"), (int, float))]
        for row in records:
            if values and isinstance(row.get("elevation_m"), (int, float)):
                exposure[canonical_district(row["district"])] = 1.0 - rank_normalise(float(row["elevation_m"]), values)

    vulnerability: dict[str, float] = {}
    population_path = root / "data" / "layers" / "district_population.json"
    population_sources = {}
    if population_path.is_file():
        population = json.loads(population_path.read_text(encoding="utf-8"))
        records = population.get("records", [])
        values = [float(row["population"]) for row in records if isinstance(row.get("population"), (int, float))]
        for row in records:
            if values and isinstance(row.get("population"), (int, float)):
                vulnerability[canonical_district(row["district"])] = rank_normalise(float(row["population"]), values)
        population_sources = {"population": population.get("source"), "population_year": population.get("year"),
                              "population_retrieved_at_utc": population.get("retrieved_at_utc")}
    isolation: dict[str, float] = {}
    osm_features: dict[str, dict] = {}
    osm_sources = {}
    vulnerability_method = "WorldPop population rank only"
    osm_path = root / "data" / "layers" / "district_osm.json"
    if osm_path.is_file():
        osm = json.loads(osm_path.read_text(encoding="utf-8"))
        osm_records = osm.get("records", [])
        road_values = [float(row["road_ways_per_100_km2"]) for row in osm_records
                       if isinstance(row.get("road_ways_per_100_km2"), (int, float))]
        for row in osm_records:
            key = canonical_district(row.get("district", ""))
            osm_features[key] = row
            density = row.get("road_ways_per_100_km2")
            if road_values and isinstance(density, (int, float)):
                isolation[key] = 1.0 - rank_normalise(float(density), road_values)
        if source_names and set(osm_features) >= set(source_names):
            facility_counts = {
                key: float(row.get("hospital_count", 0) + row.get("clinic_count", 0) + row.get("school_count", 0))
                for key, row in osm_features.items()
            }
            counts = list(facility_counts.values())
            for key, population_rank in list(vulnerability.items()):
                if key in facility_counts:
                    facilities_rank = rank_normalise(facility_counts[key], counts)
                    vulnerability[key] = 0.75 * population_rank + 0.25 * facilities_rank
            vulnerability_method = "75% WorldPop population rank + 25% OSM mapped hospital/clinic/school count rank; OSM inventory is incomplete"
        osm_sources = {"osm": osm.get("source"), "osm_retrieved_at_utc": osm.get("retrieved_at_utc"),
                       "osm_coverage": f"{len(osm_records)} district profiles"}
    manifest_path = root / "data" / "boundaries" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    terrain_sources = {}
    if terrain_path.is_file():
        terrain = json.loads(terrain_path.read_text(encoding="utf-8"))
        terrain_sources = {"terrain": terrain.get("source"), "terrain_retrieved_at_utc": terrain.get("retrieved_at_utc")}
    return {"geojson": geojson, "centroids": centroids, "source_names": source_names,
            "exposure": exposure, "vulnerability": vulnerability, "isolation": isolation,
            "osm_features": osm_features,
            "sources": {"boundaries": manifest.get("source"),
                        "boundaries_retrieved_at_utc": manifest.get("retrieved_at_utc"),
                        "vulnerability_method": vulnerability_method,
                        **terrain_sources, **population_sources, **osm_sources}}
