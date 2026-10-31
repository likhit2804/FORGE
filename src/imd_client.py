"""India Meteorological Department district forecast adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen


class IMDDataError(RuntimeError):
    pass


DEFAULT_ENDPOINT = "https://api.imd.gov.in/api/v1/state_district_rainfall_forecast"


def fetch_imd_district_forecast(endpoint: str = DEFAULT_ENDPOINT, api_key: str | None = None, timeout: int = 15) -> dict:
    headers = {"User-Agent": "MonsoonImpactNavigator/0.1", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with urlopen(Request(endpoint, headers=headers), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise IMDDataError(f"IMD district forecast unavailable: {exc}") from exc
    if not isinstance(payload, (list, dict)):
        raise IMDDataError("IMD response is not a JSON object or list")
    return {"source": "India Meteorological Department", "endpoint": endpoint, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "records": payload}
