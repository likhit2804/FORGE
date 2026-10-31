"""Attach WorldPop population estimates to downloaded district polygons."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.worldpop import WorldPopError, population_for_geometry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", type=Path, default=Path("data/boundaries/tamil_nadu_districts.geojson"))
    parser.add_argument("--output", type=Path, default=Path("data/layers/district_population.json"))
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--resolution", choices=("100m", "1km"), default="1km")
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()
    boundaries = json.loads(args.boundaries.read_text(encoding="utf-8"))
    rows = []
    errors = []
    for index, feature in enumerate(boundaries.get("features", []), start=1):
        name = feature.get("properties", {}).get("shapeName")
        try:
            population = population_for_geometry(feature["geometry"], args.year, args.resolution)
            rows.append({"district": name, **population})
            print(f"[{index}/{len(boundaries['features'])}] {name}: {population['population']:.0f}")
        except (KeyError, WorldPopError, ValueError) as exc:
            errors.append({"district": name, "error": str(exc)})
            print(f"[{index}/{len(boundaries['features'])}] {name}: failed: {exc}")
        if index < len(boundaries.get("features", [])):
            time.sleep(max(0.0, args.pause_seconds))
    payload = {"source": "WorldPop Global 2 Population API",
               "source_url": "https://api.worldpop.org/v2/",
               "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "year": args.year, "resolution": args.resolution,
               "boundary_id": boundaries.get("metadata", {}).get("district_boundary_id"),
               "records": rows, "errors": errors}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(rows)} population records; failures={len(errors)} to {args.output}")
    return 0 if rows and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
