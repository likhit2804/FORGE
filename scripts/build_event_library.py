"""Build auditable event records from daily district rainfall and event labels.

Rainfall CSV columns: date,district,rainfall_mm
Label JSON is a list of event objects containing event_id, name, start_date,
end_date, affected_districts, source, local_evidence, evidence_notes,
evidence_page, label_status, and label_confidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rainfall(path: Path) -> dict[str, dict[date, float]]:
    by_district: dict[str, dict[date, float]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "district", "rainfall_mm"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("rainfall CSV requires date,district,rainfall_mm columns")
        for line, row in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(row["date"].strip())
                district = row["district"].strip()
                amount = float(row["rainfall_mm"])
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid rainfall row {line}: {exc}") from exc
            if not district or amount < 0:
                raise ValueError(f"invalid district or negative rainfall at row {line}")
            series = by_district.setdefault(district, {})
            if day in series:
                raise ValueError(f"duplicate rainfall date and district at row {line}")
            series[day] = amount
    return by_district


def maximum_daily(by_district: dict[str, dict[date, float]], days: set[date]) -> float:
    values = [amount for series in by_district.values() for day, amount in series.items() if day in days]
    if not values:
        raise ValueError("rainfall input has no rows for the event window")
    return max(values)


def maximum_rolling_sum(by_district: dict[str, dict[date, float]], end: date, days: int) -> float:
    window = {end - timedelta(days=offset) for offset in range(1, days + 1)}
    totals = []
    for series in by_district.values():
        if window.issubset(series):
            totals.append(sum(series[day] for day in window))
    if not totals:
        raise ValueError(f"rainfall input has no observations in the {days}-day antecedent window")
    return max(totals)


def build_library(labels: list[dict], rainfall_path: Path, rainfall_source_url: str,
                  rainfall_retrieved_at_utc: str, buffer_days: int = 2) -> list[dict]:
    daily = load_rainfall(rainfall_path)
    rain_hash = sha256_file(rainfall_path)
    records = []
    for label in labels:
        start = date.fromisoformat(label["start_date"])
        end = date.fromisoformat(label["end_date"])
        if end < start:
            raise ValueError(f"event {label.get('event_id')} ends before it starts")
        if label.get("cyclone_window_verified_clear") is not True:
            raise ValueError(f"event {label.get('event_id')} lacks a verified cyclone-window exclusion")
        if not label.get("cyclone_window_evidence"):
            raise ValueError(f"event {label.get('event_id')} lacks evidence for the cyclone-window check")
        window = {start + timedelta(days=offset) for offset in range((end - start).days + 1)}
        feature_values = {
            "intensity_mm": maximum_daily(daily, window),
            "duration_hours": float(len(window) * 24),
            "antecedent_7d_mm": maximum_rolling_sum(daily, start, 7),
            "antecedent_30d_mm": maximum_rolling_sum(daily, start, 30),
        }
        record = dict(label)
        record["features"] = feature_values
        record["analysis_window"] = {"start": start.isoformat(), "end": end.isoformat()}
        record["analysis_buffer_days"] = buffer_days
        record["feature_method"] = (
            "Maximum district daily rainfall during the event; maximum district total over the preceding "
            "7 and 30 calendar days. Duration is event-window length. Source CSV aggregation is retained as supplied."
        )
        record["rainfall_data_source"] = rainfall_source_url
        record["rainfall_retrieved_at_utc"] = rainfall_retrieved_at_utc
        record["rainfall_sha256"] = rain_hash
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rainfall-csv", type=Path, required=True)
    parser.add_argument("--labels-json", type=Path, required=True)
    parser.add_argument("--rainfall-source-url", required=True)
    parser.add_argument("--rainfall-retrieved-at-utc", default=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    parser.add_argument("--buffer-days", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.buffer_days < 0:
        parser.error("--buffer-days must be non-negative")
    labels = json.loads(args.labels_json.read_text(encoding="utf-8"))
    records = build_library(labels, args.rainfall_csv, args.rainfall_source_url,
                            args.rainfall_retrieved_at_utc, args.buffer_days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(records)} event records; rainfall sha256={sha256_file(args.rainfall_csv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
