"""Audit current hazard/exposure layers and publish a deterministic inventory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from src.district_layers import canonical_district


def file_fingerprint(path: Path, root: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": digest.hexdigest()}


def record_coverage(records: list[dict], districts: set[str]) -> dict:
    keys = [canonical_district(row.get("district", "")) for row in records]
    counts: dict[str, int] = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    present = {key for key in keys if key}
    return {
        "expected_districts": len(districts),
        "record_count": len(records),
        "unique_district_count": len(present),
        "missing_districts": sorted(districts - present),
        "unexpected_districts": sorted(present - districts),
        "duplicate_districts": sorted(key for key, count in counts.items() if key and count > 1),
        "coverage_fraction": round(len(districts & present) / len(districts), 4) if districts else 0.0,
    }


def read_json(path: Path, default: dict | None = None) -> dict:
    if not path.is_file():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_assessment(root: Path) -> dict:
    layers_dir = root / "data" / "layers"
    boundary_path = root / "data" / "boundaries" / "tamil_nadu_districts.geojson"
    boundary_manifest_path = root / "data" / "boundaries" / "manifest.json"
    events_path = root / "data" / "events.json"
    if not boundary_path.is_file() or not boundary_manifest_path.is_file():
        raise ValueError("district boundary GeoJSON and manifest are required for coverage assessment")

    boundaries = read_json(boundary_path)
    boundary_manifest = read_json(boundary_manifest_path)
    district_names = [feature.get("properties", {}).get("shapeName", "")
                      for feature in boundaries.get("features", [])]
    districts = {canonical_district(name) for name in district_names if name}
    expected = int(boundary_manifest.get("district_count", len(districts)))
    if len(districts) != expected:
        raise ValueError(f"boundary name count is {len(districts)}, manifest expects {expected}")

    terrain_path = layers_dir / "district_terrain.json"
    population_path = layers_dir / "district_population.json"
    osm_path = layers_dir / "district_osm.json"
    rainfall_path = root / "data" / "processed" / "imd_district_daily_rainfall_2015_2024.csv"
    rainfall_meta_path = rainfall_path.with_suffix(rainfall_path.suffix + ".metadata.json")
    events = read_json(events_path, [])
    if not isinstance(events, list):
        raise ValueError("data/events.json must contain a list")

    terrain = read_json(terrain_path)
    population = read_json(population_path)
    osm = read_json(osm_path)
    terrain_records = terrain.get("records", [])
    population_records = population.get("records", [])
    osm_records = osm.get("records", [])

    sources = {}
    for name, path, metadata in (
        ("district_boundaries", boundary_path, boundary_manifest),
        ("district_elevation", terrain_path, terrain),
        ("population", population_path, population),
        ("osm_features", osm_path, osm),
        ("daily_rainfall", rainfall_path, read_json(rainfall_meta_path)),
    ):
        if not path.is_file():
            sources[name] = {"status": "missing"}
            continue
        item = file_fingerprint(path, root)
        boundary_details = metadata.get("district_layer", {})
        item.update({
            "source": metadata.get("source", metadata.get("boundary_source")),
            "source_url": metadata.get("source_url", metadata.get("district_geojson_url", metadata.get("api"))),
            "licence": metadata.get("license", metadata.get("boundary_license",
                                                               boundary_details.get("boundaryLicense", "not recorded in layer metadata"))),
            "retrieved_at_utc": metadata.get("retrieved_at_utc", metadata.get("created_at_utc")),
            "method": metadata.get("sampling_method", metadata.get("aggregation", metadata.get("method"))),
        })
        sources[name] = item

    rainfall_dates = set()
    rainfall_districts = set()
    rainfall_rows = 0
    invalid_rainfall = 0
    if rainfall_path.is_file():
        with rainfall_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"date", "district", "rainfall_mm"}
            if not required.issubset(reader.fieldnames or ()):
                raise ValueError("daily rainfall CSV must include date,district,rainfall_mm")
            for row in reader:
                rainfall_rows += 1
                rainfall_dates.add(row["date"])
                rainfall_districts.add(canonical_district(row["district"]))
                try:
                    amount = float(row["rainfall_mm"])
                    if not math.isfinite(amount) or amount < 0:
                        invalid_rainfall += 1
                except (TypeError, ValueError):
                    invalid_rainfall += 1

    satellite_events = [row.get("event_id") for row in events
                        if row.get("label_status") == "verified_satellite_extent"]
    return {
        "assessment_version": 1,
        "boundary_reference": {
            "boundary_id": boundary_manifest.get("district_layer", {}).get("boundaryID"),
            "boundary_year": boundary_manifest.get("district_layer", {}).get("boundaryYearRepresented"),
            "expected_district_count": expected,
            "boundary_license": boundary_manifest.get("district_layer", {}).get("boundaryLicense"),
            "geojson_sha256": boundary_manifest.get("geojson_sha256"),
        },
        "source_files": sources,
        "coverage": {
            "elevation": record_coverage(terrain_records, districts),
            "population": record_coverage(population_records, districts),
            "osm": record_coverage(osm_records, districts),
            "daily_rainfall": {
                "row_count": rainfall_rows,
                "distinct_dates": len(rainfall_dates),
                "date_start": min(rainfall_dates) if rainfall_dates else None,
                "date_end": max(rainfall_dates) if rainfall_dates else None,
                "district_count": len(rainfall_districts),
                "missing_boundary_districts": sorted(districts - rainfall_districts),
                "invalid_or_negative_rows": invalid_rainfall,
            },
            "osm_error_count": len(osm.get("errors", [])),
            "satellite_extent_event_count": len(satellite_events),
            "satellite_extent_event_ids": satellite_events,
        },
        "ranking_inputs": [
            {"signal": "rainfall_hazard", "current_use": "active; forecast percentile and analogue rainfall features",
             "meaning": "forecast rainfall intensity/duration with observed-rainfall event analogues",
             "limitations": ["Archived operational forecast validation is pending.",
                             "Observed rainfall reconstruction is not forecast skill."]},
            {"signal": "elevation_exposure_proxy", "current_use": "active; inverse rank of one representative-point elevation per district",
             "meaning": "relative elevation at a single point from Copernicus DEM GLO-90 via Open-Meteo",
             "limitations": ["Not district mean elevation, local floodplain elevation, drainage, or inundation depth.",
                             "Spatial support is one representative point per district."]},
            {"signal": "population_vulnerability_proxy", "current_use": "active; WorldPop 2025 1-km district total rank",
             "meaning": "relative resident population total by current district polygon",
             "limitations": ["Not event-time population, exposed population, or a flood footprint intersection.",
                             "The layer metadata does not record a data licence."]},
            {"signal": "mapped_facility_context", "current_use": "active; OSM hospitals/clinics/schools contribute 25% of vulnerability rank when full coverage exists",
             "meaning": "count of mapped amenities assigned by the current Overpass geometry method",
             "limitations": ["OSM completeness and tagging are uneven; counts are not authoritative service capacity.",
                             "The layer records retrieval time and ODbL, but not a per-feature quality score."]},
            {"signal": "road_density_isolation_proxy", "current_use": "active; inverse rank of OSM road ways per 100 km2",
             "meaning": "mapped road-way density, not road length or network connectivity",
             "limitations": ["Does not establish passability, flood closure, travel time, or access to a particular facility.",
                             "OSM coverage is incomplete and uneven."]},
        ],
        "candidate_signals": [
            {"signal": "river_proximity", "status": "not_available",
             "why_existing_waterway_counts_are_not_a_substitute": "District counts of mapped waterway ways do not provide distance to a river, stream order, floodplain, or upstream catchment."},
            {"signal": "drainage_capacity", "status": "not_available",
             "why": "No drainage network, culvert capacity, or stormwater-system layer is present."},
            {"signal": "observed_inundation", "status": "single_preliminary_event_label_only",
             "coverage": f"{len(satellite_events)} satellite-extent event among {len(events)} curated events",
             "why": "The one NRSC/ISRO extent is preliminary and ungrounded; there is no repeated, event-aligned inundation raster series."},
            {"signal": "road_passability_or_travel_time", "status": "not_available",
             "why": "Static mapped road density cannot represent event-time closures, surface condition, or network travel time."},
            {"signal": "cropland_exposure", "status": "not_available",
             "why": "No dated cropland/land-cover layer intersected with event inundation or rainfall footprints is present."},
        ],
        "independent_added_value": {
            "status": "not_evaluated",
            "reason": "Existing population, elevation, and OSM proxies currently enter the ranking, but no independent event-holdout ablation establishes their incremental value. The impact labels are sparse and mostly report-derived.",
            "required_evaluation": "Compare the locked baseline against one added signal at a time with the same chronological held-out events, metrics, and sample; report per-event deltas and uncertainty before enabling any new signal.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path,
                        help="optional JSON report path; default prints to stdout")
    args = parser.parse_args()
    report = build_assessment(args.root.resolve())
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(f"Wrote hazard/exposure assessment to {args.output}")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
