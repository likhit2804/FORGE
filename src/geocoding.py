"""OpenStreetMap Nominatim district geocoding adapter."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GeocodingError(RuntimeError):
    pass


def geocode_tamil_nadu_district(district: str, timeout: int = 10) -> dict:
    params = urlencode({"q": f"{district}, Tamil Nadu, India", "format": "jsonv2", "limit": 1})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "MonsoonImpactNavigator/0.1"}), timeout=timeout) as response:
            results = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise GeocodingError(f"geocoding unavailable for {district}: {exc}") from exc
    if not results:
        raise GeocodingError(f"no geocoding result for {district}")
    try:
        return {"district": district, "latitude": float(results[0]["lat"]), "longitude": float(results[0]["lon"]), "display_name": results[0].get("display_name", ""), "source": "OpenStreetMap Nominatim", "url": url}
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(f"invalid geocoding result for {district}") from exc
