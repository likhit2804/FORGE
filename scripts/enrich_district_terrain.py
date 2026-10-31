"""Sample Copernicus DEM GLO-90 elevation at district representative points."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import shape

from src.terrain import TerrainDataError, fetch_elevations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", type=Path, default=Path("data/boundaries/tamil_nadu_districts.geojson"))
    parser.add_argument("--output", type=Path, default=Path("data/layers/district_terrain.json"))
    args = parser.parse_args()
    layer = json.loads(args.boundaries.read_text(encoding="utf-8"))
    features = layer.get("features", [])
    districts = []
    for feature in features:
        point = shape(feature["geometry"]).representative_point()
        districts.append({"district": feature.get("properties", {}).get("shapeName"),
                          "latitude": point.y, "longitude": point.x})
    values = fetch_elevations([(row["latitude"], row["longitude"]) for row in districts])
    records = [{**district, **value} for district, value in zip(districts, values)]
    payload = {"source": "Open-Meteo elevation API / Copernicus DEM GLO-90",
               "source_url": "https://open-meteo.com/en/docs/elevation-api",
               "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "boundary_id": layer.get("metadata", {}).get("district_boundary_id"),
               "sampling_method": "DEM sample at each polygon representative point; not a district mean or floodplain model.",
               "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved terrain samples for {len(records)} districts to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
