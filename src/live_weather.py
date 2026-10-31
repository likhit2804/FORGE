"""Small live forecast adapter with explicit provenance and failure handling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class LiveWeatherError(RuntimeError):
    pass


def fetch_open_meteo_forecast(latitude: float, longitude: float, days: int = 3, timeout: int = 10) -> dict:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid latitude or longitude")
    if not 1 <= days <= 7:
        raise ValueError("days must be between 1 and 7")
    params = urlencode({"latitude": latitude, "longitude": longitude, "hourly": "precipitation", "forecast_days": days, "timezone": "UTC"})
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    request = Request(url, headers={"User-Agent": "MonsoonImpactNavigator/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise LiveWeatherError(f"live forecast unavailable: {exc}") from exc
    precipitation = payload.get("hourly", {}).get("precipitation")
    if not isinstance(precipitation, list) or not precipitation:
        raise LiveWeatherError("live forecast returned no hourly precipitation")
    hourly_values = [float(value or 0) for value in precipitation]
    window = min(24, len(hourly_values))
    max_24h = max(sum(hourly_values[start:start + window])
                  for start in range(len(hourly_values) - window + 1))
    return {
        "source": "Open-Meteo forecast API",
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "latitude": latitude,
        "longitude": longitude,
        "forecast_days": days,
        "precipitation_mm": hourly_values,
        "total_precipitation_mm": round(sum(hourly_values), 2),
        "max_24h_precipitation_mm": round(max_24h, 2),
        "precipitation_hours": sum(value > 0.1 for value in hourly_values),
    }
