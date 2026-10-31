"""Live terrain exposure adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TerrainDataError(RuntimeError):
    pass


def fetch_elevation(latitude: float, longitude: float, timeout: int = 10) -> dict:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid latitude or longitude")
    return fetch_elevations([(latitude, longitude)], timeout=timeout)[0]


def fetch_elevations(locations: list[tuple[float, float]], timeout: int = 20) -> list[dict]:
    if not locations or len(locations) > 100:
        raise ValueError("provide between 1 and 100 coordinate pairs")
    if any(not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
           for latitude, longitude in locations):
        raise ValueError("invalid latitude or longitude")
    params = urlencode({"latitude": ",".join(str(lat) for lat, _ in locations),
                        "longitude": ",".join(str(lon) for _, lon in locations)})
    url = f"https://api.open-meteo.com/v1/elevation?{params}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "MonsoonImpactNavigator/0.1"}), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise TerrainDataError(f"elevation data unavailable: {exc}") from exc
    values = payload.get("elevation")
    if not isinstance(values, list) or len(values) != len(locations) or any(not isinstance(value, (int, float)) for value in values):
        raise TerrainDataError("elevation response does not match the requested coordinates")
    retrieved = datetime.now(timezone.utc).isoformat()
    return [{"latitude": latitude, "longitude": longitude, "elevation_m": float(value),
             "source": "Open-Meteo elevation API (Copernicus DEM GLO-90)",
             "retrieved_at_utc": retrieved, "url": url}
            for (latitude, longitude), value in zip(locations, values)]
