"""Leakage-aware leave-one-event-out evaluation for the MVP."""

from __future__ import annotations

from .district_layers import canonical_district
from .navigator import Event, Query, priority_ranking, retrieve


def top_k_metrics(predicted: list[str], actual: tuple[str, ...], k: int = 5) -> dict[str, float]:
    predicted_set = {canonical_district(name) for name in predicted[:k]}
    actual_set = {canonical_district(name) for name in actual}
    hits = len(predicted_set & actual_set)
    return {
        "hits": hits,
        "precision_at_k": hits / len(predicted_set) if predicted_set else 0.0,
        "recall_at_k": hits / len(actual_set) if actual_set else 0.0,
    }


def rainfall_only_ranking(query: Query, library: list[Event],
                          rainfall_by_district: dict[str, float] | None = None) -> list[str]:
    district_names = {canonical_district(d): d for event in library for d in event.affected_districts}
    district_names.update({canonical_district(d): d for d in query.forecast_percentile_by_district})
    rainfall_scores = rainfall_by_district or query.forecast_percentile_by_district
    district_names.update({canonical_district(d): d for d in rainfall_scores})
    percentiles = {canonical_district(name): value for name, value in rainfall_scores.items()}
    return sorted(district_names.values(),
                  key=lambda d: (-percentiles.get(canonical_district(d), 0.0), canonical_district(d)))


def static_flood_proneness(library: list[Event]) -> list[str]:
    counts: dict[str, int] = {}
    district_names: dict[str, str] = {}
    for event in library:
        for district in set(event.affected_districts):
            key = canonical_district(district)
            district_names.setdefault(key, district)
            counts[key] = counts.get(key, 0) + 1
    return [district_names[key] for key in sorted(counts, key=lambda d: (-counts[d], d))]


def _evaluate_event(held_out: Event, training: list[Event], k: int) -> dict:
    districts = sorted({d for event in training for d in event.affected_districts} | set(held_out.affected_districts))
    held_district_features = held_out.district_features or {}
    districts = sorted(set(districts) | set(held_district_features))
    local_intensity = {district: features["intensity_mm"]
                       for district, features in held_district_features.items()
                       if "intensity_mm" in features}
    local_duration = {district: held_out.features["duration_hours"] for district in districts}
    local_additional = {
        district: {name: value for name, value in features.items() if name != "intensity_mm"}
        for district, features in held_district_features.items()
    }
    query = Query(held_out.features, {d: 0.5 for d in districts}, {d: 0.5 for d in districts},
                  {d: 0.5 for d in districts}, {d: 0.5 for d in districts},
                  local_intensity or None, local_duration, local_additional or None)
    retrieval = retrieve(query, training, top_k=min(k, len(training)))
    analogue = [row["district"] for row in priority_ranking(query, retrieval)]
    return {
        "event_id": held_out.event_id,
        "event": held_out.name,
        "analogue": top_k_metrics(analogue, held_out.affected_districts, k),
        "rainfall_only": (top_k_metrics(rainfall_only_ranking(query, training, local_intensity),
                                          held_out.affected_districts, k)
                          if local_intensity else {
                              "hits": None, "precision_at_k": None, "recall_at_k": None,
                              "status": "not_evaluated_missing_district_rainfall_series",
                          }),
        "static_flood_proneness": top_k_metrics(static_flood_proneness(training), held_out.affected_districts, k),
        "abstained": retrieval["abstained"],
        "training_event_count": len(training),
    }


def evaluate_leave_one_out(library: list[Event], k: int = 5) -> list[dict]:
    return [_evaluate_event(held_out, [event for event in library if event.event_id != held_out.event_id], k)
            for held_out in library if len(library) > 1]


def evaluate_forward_chaining(library: list[Event], k: int = 5,
                              min_training_events: int = 3) -> list[dict]:
    """Evaluate chronologically using only earlier events; omit cold-start cases."""
    ordered = sorted(library, key=lambda event: (event.start_date, event.event_id))
    rows = []
    for index, held_out in enumerate(ordered):
        training = [event for event in ordered[:index] if event.start_date < held_out.start_date]
        if len(training) < min_training_events:
            rows.append({"event_id": held_out.event_id, "event": held_out.name,
                         "status": "not_evaluated_insufficient_prior_events",
                         "prior_event_count": len(training), "required_prior_events": min_training_events})
            continue
        rows.append(_evaluate_event(held_out, training, k))
    return rows
