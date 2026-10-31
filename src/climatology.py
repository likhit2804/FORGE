"""Percentile transforms for observed district rainfall climatology."""

from __future__ import annotations

import json
from pathlib import Path

from .district_layers import canonical_district
from .navigator import rank_normalise


def load_monthly_rainfall_percentiles(root: Path, rainfall_by_district: dict[str, float], month: int) -> tuple[dict[str, float], dict]:
    path = root / "data" / "layers" / "rainfall_climatology.json"
    if not path.is_file():
        return {}, {"available": False}
    dataset = json.loads(path.read_text(encoding="utf-8"))
    distributions = dataset.get("month_day_distributions", {})
    canonical_values = {canonical_district(name): values for name, values in distributions.items()}
    results = {}
    for district, amount in rainfall_by_district.items():
        values = canonical_values.get(canonical_district(district), {}).get(str(month), [])
        if values:
            results[district] = rank_normalise(float(amount), [float(value) for value in values])
    return results, {"available": bool(results), "source": dataset.get("source"),
                     "retrieved_at_utc": dataset.get("retrieved_at_utc"),
                     "year_range": dataset.get("year_range"), "sha256": dataset.get("sha256"),
                     "month": month, "district_count": len(results)}
