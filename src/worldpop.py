"""Small client for WorldPop's asynchronous polygon population API."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.worldpop.org/v2"


class WorldPopError(RuntimeError):
    pass


def _request(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json",
                      "User-Agent": "MonsoonImpactNavigator/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WorldPopError(f"WorldPop request failed: {exc}") from exc
    if not isinstance(result, dict):
        raise WorldPopError("WorldPop returned an unexpected response")
    return result


def population_for_geometry(geometry: dict, year: int = 2025, resolution: str = "1km",
                            timeout: int = 120, poll_interval: float = 2.0) -> dict:
    if not 2015 <= year <= 2030:
        raise ValueError("WorldPop Global2 supports years from 2015 through 2030")
    if resolution not in {"100m", "1km"}:
        raise ValueError("resolution must be 100m or 1km")
    submitted = _request(f"{BASE_URL}/population", {"geojson": geometry,
                       "year": year, "resolution": resolution})
    task_id = submitted.get("task_id")
    if not task_id:
        raise WorldPopError("WorldPop did not return a task_id")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = _request(f"{BASE_URL}/tasks/{task_id}")
        state = status.get("status")
        if state == "success":
            result = status.get("result", {})
            return {"population": float(result["total_population"]),
                    "population_density": float(result["population_density"]),
                    "area_km2": float(result["area_km2"]), "year": int(result.get("data_year", year)),
                    "resolution": resolution, "dataset": result.get("data_source", "WorldPop Global 2"),
                    "source": f"{BASE_URL}/population", "task_id": task_id,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if state in {"failure", "failed"}:
            raise WorldPopError(f"WorldPop task failed: {status.get('error', 'unknown error')}")
        time.sleep(poll_interval)
    raise WorldPopError(f"WorldPop task {task_id} timed out after {timeout}s")
