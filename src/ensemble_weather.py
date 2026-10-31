"""Forecast rainfall quantiles from Open-Meteo's ensemble endpoint."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class EnsembleWeatherError(RuntimeError):
    pass


def fetch_ensemble_forecast(latitude: float, longitude: float, days: int = 3,
                            model: str = "ecmwf_ifs025_ensemble", timeout: int = 20) -> dict:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("invalid latitude or longitude")
    if not 1 <= days <= 7:
        raise ValueError("days must be between 1 and 7")
    params = urlencode({"latitude": latitude, "longitude": longitude,
                        "hourly": "precipitation", "models": model,
                        "forecast_days": days, "timezone": "UTC"})
    url = f"https://ensemble-api.open-meteo.com/v1/ensemble?{params}"
    try:
        request = Request(url, headers={"User-Agent": "MonsoonImpactNavigator/0.1"})
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise EnsembleWeatherError(f"ensemble forecast unavailable: {exc}") from exc
    hourly = payload.get("hourly", {})
    member_keys = sorted(key for key in hourly if re.fullmatch(r"precipitation_member\d+", key))
    if not member_keys:
        member_keys = sorted(key for key in hourly if key.startswith("precipitation_member"))
    if not member_keys:
        raise EnsembleWeatherError("ensemble response has no precipitation member series")
    member_intensity = []
    member_hours = []
    member_totals = []
    for key in member_keys:
        values = hourly.get(key)
        if not isinstance(values, list) or not values:
            continue
        numeric = [float(value or 0) for value in values]
        rolling_window = min(24, len(numeric))
        member_intensity.append(max(sum(numeric[start:start + rolling_window])
                                    for start in range(len(numeric) - rolling_window + 1)))
        member_hours.append(float(sum(value > 0.1 for value in numeric)))
        member_totals.append(sum(numeric))
    if len(member_intensity) < 3:
        raise EnsembleWeatherError(f"only {len(member_intensity)} valid precipitation members returned")
    ordered = sorted(member_intensity)
    quantile = lambda q: ordered[round(q * (len(ordered) - 1))]
    ordered_totals = sorted(member_totals)
    total_quantile = lambda q: ordered_totals[round(q * (len(ordered_totals) - 1))]
    median_hours = sorted(member_hours)[len(member_hours) // 2]
    return {
        "source": "Open-Meteo ensemble API",
        "model": payload.get("model", model),
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latitude": latitude,
        "longitude": longitude,
        "forecast_days": days,
        "member_count": len(member_totals),
        "low_24h_intensity_mm": round(quantile(0.10), 2),
        "central_24h_intensity_mm": round(quantile(0.50), 2),
        "high_24h_intensity_mm": round(quantile(0.90), 2),
        "median_precipitation_hours": round(median_hours, 1),
        "total_precipitation_median_mm": round(total_quantile(0.50), 2),
        "member_24h_intensity_mm": [round(value, 2) for value in ordered],
    }


def fetch_ensemble_forecasts(locations: dict[str, tuple[float, float]], days: int = 3,
                             model: str = "ecmwf_ifs025_ensemble", timeout: int = 40) -> dict:
    """Fetch member rainfall for multiple districts with one provider request."""
    if not locations or len(locations) > 100:
        raise ValueError("provide between 1 and 100 district locations")
    if not 1 <= days <= 7:
        raise ValueError("days must be between 1 and 7")
    names = list(locations)
    coords = [locations[name] for name in names]
    if any(not (-90 <= lat <= 90 and -180 <= lon <= 180) for lat, lon in coords):
        raise ValueError("invalid latitude or longitude")
    params = urlencode({"latitude": ",".join(str(lat) for lat, _ in coords),
                        "longitude": ",".join(str(lon) for _, lon in coords),
                        "hourly": "precipitation", "models": model,
                        "forecast_days": days, "timezone": "UTC"})
    url = f"https://ensemble-api.open-meteo.com/v1/ensemble?{params}"
    try:
        request = Request(url, headers={"User-Agent": "MonsoonImpactNavigator/0.1"})
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise EnsembleWeatherError(f"district ensemble forecast unavailable: {exc}") from exc
    payloads = payload if isinstance(payload, list) else [payload]
    if len(payloads) != len(names):
        raise EnsembleWeatherError(
            f"partial district coverage: provider returned {len(payloads)} locations for {len(names)} requested; no ranking was generated")
    results = {}
    for name, point, location_payload in zip(names, coords, payloads):
        hourly = location_payload.get("hourly", {})
        keys = sorted(key for key in hourly if re.fullmatch(r"precipitation_member\d+", key))
        if not keys:
            keys = sorted(key for key in hourly if key.startswith("precipitation_member"))
        totals, intensities, durations = [], [], []
        for key in keys:
            values = hourly.get(key)
            if not isinstance(values, list) or not values:
                continue
            numeric = [float(value or 0) for value in values]
            window = min(24, len(numeric))
            intensities.append(max(sum(numeric[start:start + window])
                                   for start in range(len(numeric) - window + 1)))
            totals.append(sum(numeric))
            durations.append(sum(value > 0.1 for value in numeric))
        if len(intensities) < 3:
            raise EnsembleWeatherError(f"{name}: fewer than three precipitation members returned")
        ordered = sorted(intensities)
        quantile = lambda q: ordered[round(q * (len(ordered) - 1))]
        results[name] = {
            "district": name, "latitude": point[0], "longitude": point[1],
            "low_24h_intensity_mm": round(quantile(0.10), 2),
            "central_24h_intensity_mm": round(quantile(0.50), 2),
            "high_24h_intensity_mm": round(quantile(0.90), 2),
            "precipitation_hours": round(sorted(durations)[len(durations) // 2], 1),
            "total_precipitation_median_mm": round(sorted(totals)[len(totals) // 2], 2),
            "member_count": len(intensities), "model": location_payload.get("model", model),
            "source": "Open-Meteo ensemble API", "url": url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    return {"source": "Open-Meteo ensemble API", "url": url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model, "forecast_days": days, "districts": results}
