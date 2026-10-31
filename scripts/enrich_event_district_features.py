"""Derive district-level event and antecedent rainfall from daily CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

from src.district_layers import canonical_district


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_series(path: Path) -> dict[str, dict[date, float]]:
    series: dict[str, dict[date, float]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "district", "rainfall_mm"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("daily rainfall CSV requires date,district,rainfall_mm")
        for line, row in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(row["date"].strip())
                district = canonical_district(row["district"].strip())
                amount = float(row["rainfall_mm"])
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid rainfall row {line}: {exc}") from exc
            if not district or amount < 0:
                raise ValueError(f"invalid district or negative rainfall at row {line}")
            if day in series[district]:
                raise ValueError(f"duplicate date for district at CSV row {line}")
            series[district][day] = amount
    return series


def build_features(events: list[dict], rainfall_path: Path,
                   source_metadata_path: Path | None = None) -> dict:
    rainfall = load_series(rainfall_path)
    results = {}
    for event in events:
        start = date.fromisoformat(event["start_date"])
        end = date.fromisoformat(event["end_date"])
        if end < start:
            raise ValueError(f"event {event.get('event_id')} ends before it starts")
        event_days = [start + timedelta(days=offset)
                      for offset in range((end - start).days + 1)]
        districts = {}
        for district, observations in rainfall.items():
            antecedent_7 = [start - timedelta(days=offset) for offset in range(1, 8)]
            antecedent_30 = [start - timedelta(days=offset) for offset in range(1, 31)]
            if not all(day in observations for day in (*event_days, *antecedent_7, *antecedent_30)):
                continue
            districts[district] = {
                "intensity_mm": max(observations[day] for day in event_days),
                "antecedent_7d_mm": sum(observations[day] for day in antecedent_7),
                "antecedent_30d_mm": sum(observations[day] for day in antecedent_30),
            }
        if not districts:
            raise ValueError(f"no complete district rainfall features for event {event.get('event_id')}")
        results[event["event_id"]] = districts

    source_metadata = None
    if source_metadata_path:
        source_metadata = json.loads(source_metadata_path.read_text(encoding="utf-8"))
    return {
        "source": "IMD 0.25-degree gridded daily rainfall aggregated to 2021 ADM2 polygons",
        "source_url": "https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html",
        "rainfall_csv": str(rainfall_path),
        "rainfall_csv_sha256": sha256_file(rainfall_path),
        "source_metadata": source_metadata,
        "aggregation": "Maximum district-average daily rainfall during each report-defined event window; district sums over preceding 7 and 30 days.",
        "feature_note": "These are supplementary gridded district means, not replacements for report-derived station maxima or officially recorded impact labels. District durations are omitted because daily grids do not resolve sub-day rainfall duration.",
        "event_count": len(results),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=Path("data/events.json"))
    parser.add_argument("--rainfall-csv", type=Path, required=True)
    parser.add_argument("--source-metadata", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/processed/event_district_features.json"))
    args = parser.parse_args()
    try:
        events = json.loads(args.events.read_text(encoding="utf-8"))
        result = build_features(events, args.rainfall_csv, args.source_metadata)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    district_counts = [len(districts) for districts in result["events"].values()]
    print(f"Wrote district features for {result['event_count']} events; districts/event={min(district_counts)}-{max(district_counts)}")
    print(f"Rainfall CSV SHA-256: {result['rainfall_csv_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
