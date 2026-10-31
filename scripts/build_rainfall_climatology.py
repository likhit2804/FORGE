"""Create district/month daily-rainfall reference distributions from source CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rainfall-csv", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-metadata", type=Path,
                        help="Optional provenance sidecar produced by the rainfall converter")
    parser.add_argument("--output", type=Path, default=Path("data/layers/rainfall_climatology.json"))
    parser.add_argument("--min-years", type=int, default=10)
    args = parser.parse_args()
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    years: set[int] = set()
    with args.rainfall_csv.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"date", "district", "rainfall_mm"}.issubset(reader.fieldnames):
            parser.error("CSV requires date,district,rainfall_mm columns")
        for row_number, row in enumerate(reader, start=2):
            try:
                observed = date.fromisoformat(row["date"].strip())
                district = row["district"].strip()
                amount = float(row["rainfall_mm"])
                if not district or amount < 0:
                    raise ValueError("empty district or negative rainfall")
            except (AttributeError, TypeError, ValueError) as exc:
                parser.error(f"invalid row {row_number}: {exc}")
            buckets[district][str(observed.month)].append(amount)
            years.add(observed.year)
    if len(years) < args.min_years:
        parser.error(f"only {len(years)} years supplied; at least {args.min_years} required")
    dataset_hash = hashlib.sha256(args.rainfall_csv.read_bytes()).hexdigest()
    source_metadata = None
    if args.source_metadata:
        source_metadata = json.loads(args.source_metadata.read_text(encoding="utf-8"))
    output = {"source": args.source_url,
              "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "sha256": dataset_hash, "year_range": [min(years), max(years)],
              "observed_year_count": len(years), "month_day_distributions": buckets,
              "source_metadata": source_metadata,
              "interpretation": "Empirical district daily rainfall values grouped by calendar month; values are not forecast-calibrated.",
              "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved month-specific rainfall distributions for {len(buckets)} districts, years={min(years)}-{max(years)}, sha256={dataset_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
