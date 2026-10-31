"""Fetch current India district boundaries and retain Tamil Nadu features.

Source: geoBoundaries gbOpen. Attribution and per-layer license are written to
the sidecar manifest and must be kept with redistributed boundary files.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from shapely.geometry import shape


API = "https://www.geoboundaries.org/api/current/gbOpen/IND/{level}/"


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "MonsoonImpactNavigator/0.1 (data pipeline)"})
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(value: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").replace("_", " ").casefold())
    ascii_name = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(ascii_name.strip().split())


def download_layer(level: str) -> tuple[dict, dict, str]:
    metadata_url = API.format(level=level)
    metadata = fetch_json(metadata_url)
    geojson_url = metadata.get("gjDownloadURL") or metadata.get("simplifiedGeometryGeoJSON")
    if not geojson_url:
        raise ValueError(f"geoBoundaries metadata has no GeoJSON URL for {level}")
    data = fetch_json(geojson_url)
    return metadata, data, geojson_url


def tamil_nadu_districts() -> tuple[dict, dict, dict, dict, str, str]:
    state_meta, states, state_url = download_layer("ADM1")
    district_meta, districts, district_url = download_layer("ADM2")
    state_features = states.get("features", [])
    tamil_nadu = [feature for feature in state_features
                  if norm(feature.get("properties", {}).get("shapeName")) == "tamil nadu"]
    if len(tamil_nadu) != 1:
        raise ValueError(f"expected one Tamil Nadu state polygon, found {len(tamil_nadu)}")
    state_geometry = shape(tamil_nadu[0]["geometry"])
    kept = []
    for feature in districts.get("features", []):
        geometry = shape(feature["geometry"])
        representative = geometry.representative_point()
        if state_geometry.covers(representative):
            kept.append(feature)
    if not kept:
        raise ValueError("no ADM2 district polygons intersected Tamil Nadu")
    filtered = {key: value for key, value in districts.items() if key != "features"}
    filtered["features"] = kept
    filtered["metadata"] = {"state_boundary_id": state_meta.get("boundaryID"),
                            "district_boundary_id": district_meta.get("boundaryID")}
    return state_meta, district_meta, states, filtered, state_url, district_url


def main() -> int:
    target = Path(__file__).parents[1] / "data" / "boundaries"
    target.mkdir(parents=True, exist_ok=True)
    state_meta, district_meta, _, filtered, state_url, district_url = tamil_nadu_districts()
    geojson_bytes = (json.dumps(filtered, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    geojson_path = target / "tamil_nadu_districts.geojson"
    geojson_path.write_bytes(geojson_bytes)
    manifest = {
        "source": "geoBoundaries gbOpen",
        "api": API.format(level="ADM2"),
        "state_geojson_url": state_url,
        "district_geojson_url": district_url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "district_layer": {key: district_meta.get(key) for key in
                           ("boundaryID", "boundaryName", "boundaryYearRepresented", "boundarySource", "boundaryLicense", "licenseSource", "buildDate")},
        "state_layer": {key: state_meta.get(key) for key in
                         ("boundaryID", "boundaryYearRepresented", "boundarySource", "boundaryLicense", "licenseSource", "buildDate")},
        "feature_count": len(filtered["features"]),
        "geojson_sha256": sha256_bytes(geojson_bytes),
        "attribution": "geoBoundaries; retain the source attribution and license shown in this manifest.",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(filtered['features'])} district polygons to {geojson_path}")
    print(f"License: {district_meta.get('boundaryLicense')} · attribution required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
