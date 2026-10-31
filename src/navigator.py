"""Core Monsoon Impact Navigator MVP logic.

The module is intentionally dependency-light so the scoring and abstention
rules can be tested before adding GIS and live API integrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import quantiles
from typing import Iterable
import unicodedata


FEATURES = ("intensity_mm", "duration_hours", "antecedent_7d_mm", "antecedent_30d_mm")
KEY_FEATURES = ("intensity_mm", "duration_hours")
DEFAULT_PRIORITY_WEIGHTS = {
    "hazard": 0.40,
    "exposure": 0.25,
    "vulnerability": 0.20,
    "isolation": 0.15,
}

_DISTRICT_ALIASES = {
    "kancheepuram": "kanchipuram",
    "thiruvallur": "tiruvallur",
    "tuticorin": "thoothukudi",
    "thoothukkudi": "thoothukudi",
    "kanniyakumari": "kanyakumari",
    "tinnevelly": "tirunelveli",
}


def _district_key(value: str) -> str:
    plain = "".join(char for char in unicodedata.normalize("NFKD", value).casefold()
                    if not unicodedata.combining(char))
    return _DISTRICT_ALIASES.get(" ".join(plain.replace("_", " ").split()),
                                " ".join(plain.replace("_", " ").split()))


@dataclass(frozen=True)
class Event:
    event_id: str
    name: str
    start_date: str
    end_date: str
    features: dict[str, float]
    affected_districts: tuple[str, ...]
    source: str
    evidence_notes: str = ""
    evidence_page: int | None = None
    local_evidence: str | None = None
    district_features: dict[str, dict[str, float]] | None = None


@dataclass(frozen=True)
class Query:
    features: dict[str, float]
    forecast_percentile_by_district: dict[str, float]
    exposure_by_district: dict[str, float]
    vulnerability_by_district: dict[str, float]
    isolation_by_district: dict[str, float]
    rainfall_intensity_by_district: dict[str, float] | None = None
    duration_hours_by_district: dict[str, float] | None = None
    additional_features_by_district: dict[str, dict[str, float]] | None = None


def rank_normalise(value: float, values: Iterable[float]) -> float:
    """Return an empirical percentile in [0, 1], with ties handled safely."""
    ordered = sorted(values)
    if not ordered:
        return 0.5
    below = sum(v < value for v in ordered)
    equal = sum(v == value for v in ordered)
    return (below + 0.5 * equal) / len(ordered)


def spearman_correlation(first: dict[str, float], second: dict[str, float]) -> float | None:
    """Spearman rank correlation over shared keys, or None when undefined."""
    keys = sorted(set(first) & set(second))
    if len(keys) < 3:
        return None
    x = [rank_normalise(float(first[key]), [float(first[k]) for k in keys]) for key in keys]
    y = [rank_normalise(float(second[key]), [float(second[k]) for k in keys]) for key in keys]
    mean_x, mean_y = sum(x) / len(x), sum(y) / len(y)
    dx, dy = [value - mean_x for value in x], [value - mean_y for value in y]
    denom = sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denom == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def adjust_correlated_weights(weights: dict[str, float], exposure: dict[str, float],
                              isolation: dict[str, float], threshold: float = 0.70
                              ) -> tuple[dict[str, float], float | None, bool]:
    """Down-weight isolation by half when exposure/isolation ranks overlap strongly."""
    adjusted = dict(weights)
    correlation = spearman_correlation(exposure, isolation)
    if correlation is None or abs(correlation) <= threshold:
        return adjusted, correlation, False
    transfer = adjusted.get("isolation", 0.0) * 0.5
    adjusted["isolation"] -= transfer
    adjusted["exposure"] = adjusted.get("exposure", 0.0) + transfer
    return adjusted, correlation, True


def _feature_value(event: Event, feature: str, district: str | None = None) -> float | None:
    if district and event.district_features:
        key = _district_key(district)
        for name, values in event.district_features.items():
            if _district_key(name) == key and feature in values:
                return values[feature]
    return event.features.get(feature)


def feature_vector(event: Event, library: list[Event], features=FEATURES,
                   district: str | None = None) -> dict[str, float]:
    result: dict[str, float] = {}
    for feature in features:
        values = [value for item in library
                  if (value := _feature_value(item, feature, district)) is not None]
        event_value = _feature_value(event, feature, district)
        if event_value is not None and values:
            result[feature] = rank_normalise(event_value, values)
    return result


def distance(query_features: dict[str, float], event: Event, library: list[Event],
             district: str | None = None) -> tuple[float, int]:
    query_event = Event("query", "query", "", "", query_features, (), "")
    q = feature_vector(query_event, library, district=district)
    e = feature_vector(event, library, district=district)
    shared = sorted(set(q) & set(e))
    if not shared:
        return float("inf"), 0
    value = sqrt(sum((q[f] - e[f]) ** 2 for f in shared) / len(shared))
    return value, len(shared)


def _vector_distance(first: dict[str, float], second: dict[str, float]) -> tuple[float, int]:
    shared = sorted(set(first) & set(second))
    if not shared:
        return float("inf"), 0
    value = sqrt(sum((first[key] - second[key]) ** 2 for key in shared) / len(shared))
    return value, len(shared)


def _ranked_distances(query_features: dict[str, float], library: list[Event],
                      district: str | None = None) -> list[tuple[Event, float, int]]:
    """Compute each rank-normalised feature vector once per retrieval pass."""
    query_event = Event("query", "query", "", "", query_features, (), "")
    query_vector = feature_vector(query_event, library, district=district)
    event_vectors = [(event, feature_vector(event, library, district=district)) for event in library]
    return [(event, *_vector_distance(query_vector, vector)) for event, vector in event_vectors]


def observed_range(library: list[Event], feature: str,
                   district: str | None = None) -> tuple[float, float]:
    values = [value for event in library
              if (value := _feature_value(event, feature, district)) is not None]
    return min(values), max(values)


def best_match_threshold(library: list[Event], district: str | None = None) -> float:
    """90th percentile of leave-one-out best-match distances."""
    best: list[float] = []
    for held_out in library:
        remaining = [e for e in library if e.event_id != held_out.event_id]
        if not remaining:
            continue
        held_features = ({**held_out.features, **next(
            (values for name, values in (held_out.district_features or {}).items()
             if _district_key(name) == _district_key(district)), {})}
            if district else held_out.features)
        best.append(min(item[1] for item in _ranked_distances(held_features, remaining, district)))
    if len(best) < 2:
        return 0.35
    return quantiles(best, n=10, method="inclusive")[8]


def retrieve(query: Query, library: list[Event], top_k: int = 5,
             threshold_cache: dict[str | None, float] | None = None) -> dict:
    if not library:
        raise ValueError("event library is empty")
    if not 1 <= top_k <= 5:
        raise ValueError("top_k must be between 1 and 5")
    if any(value < 0 for value in query.features.values()):
        raise ValueError("query features must be non-negative")
    for local_values in (query.rainfall_intensity_by_district, query.duration_hours_by_district):
        if local_values and any(value < 0 for value in local_values.values()):
            raise ValueError("district query features must be non-negative")
    if query.additional_features_by_district and any(
            value < 0 for features in query.additional_features_by_district.values()
            for value in features.values()):
        raise ValueError("district query features must be non-negative")
    thresholds = threshold_cache if threshold_cache is not None else {}
    if None not in thresholds:
        thresholds[None] = best_match_threshold(library)
    threshold = thresholds[None]
    ranked = [{"event": event, "distance": d, "features_used": used}
              for event, d, used in _ranked_distances(query.features, library)]
    ranked.sort(key=lambda item: item["distance"])
    top = ranked[: max(3, min(top_k, 5))]
    out_of_range = []
    for feature in KEY_FEATURES:
        if feature in query.features:
            low, high = observed_range(library, feature)
            if query.features[feature] < low or query.features[feature] > high:
                out_of_range.append({"feature": feature, "value": query.features[feature], "range": [low, high]})
    abstained = top[0]["distance"] > threshold
    district_analogues = {}
    local_intensities = query.rainfall_intensity_by_district or {}
    local_durations = query.duration_hours_by_district or {}
    local_additional = query.additional_features_by_district or {}
    for district in sorted(set(local_intensities) | set(local_durations) | set(local_additional)):
        local_features = dict(query.features)
        local_features.update(local_additional.get(district, {}))
        if district in local_intensities:
            local_features["intensity_mm"] = local_intensities[district]
        if district in local_durations:
            local_features["duration_hours"] = local_durations[district]
        local_ranked = [{"event": event, "distance": local_distance, "features_used": used}
                        for event, local_distance, used in _ranked_distances(local_features, library, district)]
        local_ranked.sort(key=lambda item: item["distance"])
        local_top = local_ranked[:max(3, min(top_k, 5))]
        local_range = []
        for feature in KEY_FEATURES:
            if feature in local_features:
                low, high = observed_range(library, feature, district)
                value = local_features[feature]
                if value < low or value > high:
                    local_range.append({"feature": feature, "value": value, "range": [low, high]})
        if district not in thresholds:
            thresholds[district] = best_match_threshold(library, district)
        local_threshold = thresholds[district]
        district_analogues[district] = {
            "analogues": local_top,
            "abstained": local_top[0]["distance"] > local_threshold,
            "out_of_range": local_range,
            "threshold": local_threshold,
        }
    return {"analogues": top, "threshold": threshold, "abstained": abstained,
            "out_of_range": out_of_range, "query_feature_count": len(query.features),
            "district_analogues": district_analogues}


def percentile_rank(value: float, values: list[float]) -> float:
    return rank_normalise(value, values)


def priority_ranking(query: Query, retrieval: dict, score_weights: dict[str, float] | None = None) -> list[dict]:
    weights = dict(DEFAULT_PRIORITY_WEIGHTS if score_weights is None else score_weights)
    if set(weights) != set(DEFAULT_PRIORITY_WEIGHTS):
        raise ValueError(f"score_weights must contain exactly {sorted(DEFAULT_PRIORITY_WEIGHTS)}")
    if any(not isinstance(value, (int, float)) or value < 0 for value in weights.values()):
        raise ValueError("score weights must be non-negative numbers")
    weight_total = sum(weights.values())
    if weight_total <= 0:
        raise ValueError("at least one score weight must be positive")
    weights = {name: value / weight_total for name, value in weights.items()}
    analogues = retrieval["analogues"]
    district_names: dict[str, str] = {}
    # Prefer the current district-layer spelling from query inputs, then fill
    # any remaining keys from historical labels. This prevents pre-split or
    # alternate spellings from appearing as duplicate districts in output.
    for source in (query.forecast_percentile_by_district,
                   query.rainfall_intensity_by_district or {},
                   query.additional_features_by_district or {}):
        for name in source:
            district_names.setdefault(_district_key(name), name)
    for item in analogues:
        for name in item["event"].affected_districts:
            district_names.setdefault(_district_key(name), name)
    districts = [district_names[key] for key in sorted(district_names)]
    rows = []
    for district in districts:
        local_retrieval = retrieval.get("district_analogues", {}).get(district)
        district_items = local_retrieval["analogues"] if local_retrieval else analogues
        support = 0.0
        weight_total = 0.0
        for item in district_items:
            weight = 1.0 / (item["distance"] + 1e-6)
            weight_total += weight
            if _district_key(district) in {_district_key(name) for name in item["event"].affected_districts}:
                support += weight
        analogue_impact = support / weight_total if weight_total else 0.0
        hazard = 0.60 * analogue_impact + 0.40 * query.forecast_percentile_by_district.get(district, 0.0)
        exposure = query.exposure_by_district.get(district, 0.0)
        vulnerability = query.vulnerability_by_district.get(district, 0.0)
        isolation = query.isolation_by_district.get(district, 0.0)
        priority = (weights["hazard"] * hazard + weights["exposure"] * exposure
                    + weights["vulnerability"] * vulnerability + weights["isolation"] * isolation)
        district_key = _district_key(district)
        supporting = sum(1 for item in district_items
                         if district_key in {_district_key(name) for name in item["event"].affected_districts})
        rows.append({"district": district, "hazard": round(hazard, 4), "analogue_support": supporting,
                     "exposure": exposure, "vulnerability": vulnerability, "isolation": isolation,
                     "priority": round(priority, 4), "score_weights": weights,
                     "rainfall_intensity_mm": (query.rainfall_intensity_by_district or {}).get(district),
                     "district_abstained": local_retrieval["abstained"] if local_retrieval else retrieval["abstained"],
                     "district_out_of_range": local_retrieval["out_of_range"] if local_retrieval else retrieval["out_of_range"]})
    return sorted(rows, key=lambda row: row["priority"], reverse=True)


def confidence(retrieval: dict, priorities: list[dict], missing_fraction: float = 0.0,
               high_spread: bool = False, scenario_sensitive: bool = False,
               empirically_calibrated: bool = False) -> str:
    if retrieval["abstained"] or retrieval["out_of_range"] or high_spread or missing_fraction > 0.30 or scenario_sensitive:
        return "Low"
    top_support = priorities[0].get("analogue_support", 0) if priorities else 0
    if (not empirically_calibrated or top_support < 3 or missing_fraction > 0
            or len(priorities) == 0):
        return "Medium"
    return "High"


def district_confidence(retrieval: dict, row: dict, missing_fraction: float = 0.0,
                        high_spread: bool = False, scenario_sensitive: bool = False,
                        empirically_calibrated: bool = False) -> str:
    """Confidence for one district; callers aggregate the top-five worst case."""
    if (row.get("district_abstained", retrieval["abstained"])
            or row.get("district_out_of_range", retrieval["out_of_range"]) or high_spread
            or missing_fraction > 0.30 or scenario_sensitive):
        return "Low"
    if (not empirically_calibrated or row.get("analogue_support", 0) < 3
            or missing_fraction > 0):
        return "Medium"
    return "High"


def missing_feature_fraction(retrieval: dict) -> float:
    """Share of expected query features absent across the retrieved analogues."""
    analogues = retrieval.get("analogues", [])
    expected = retrieval.get("query_feature_count", 0)
    if not analogues or expected == 0:
        return 1.0
    return sum(max(0, expected - item.get("features_used", 0)) for item in analogues) / (len(analogues) * expected)


def scenario_analysis(queries: dict[str, Query], library: list[Event],
                      score_weights: dict[str, float] | None = None,
                      threshold_cache: dict[str | None, float] | None = None) -> dict:
    """Rank low/central/high scenarios and identify top-five stability."""
    results = {}
    for name, query in queries.items():
        retrieval = retrieve(query, library, threshold_cache=threshold_cache)
        ranking = priority_ranking(query, retrieval, score_weights)
        results[name] = {"retrieval": retrieval, "ranking": ranking}
    scenario_names = tuple(results)
    districts = sorted({row["district"] for name in scenario_names for row in results[name]["ranking"]})
    for district in districts:
        positions = {}
        for name in scenario_names:
            result = results[name]
            ordered = [row["district"] for row in result["ranking"]]
            positions[name] = ordered.index(district) + 1 if district in ordered else None
        stable = all(position is not None and position <= 5 for position in positions.values())
        results.setdefault("stability", {})[district] = {"positions": positions, "stable": stable}
    return results
