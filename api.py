"""FastAPI service for the React Monsoon Impact Navigator client."""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.advisory import build_advisory
from src.climatology import load_monthly_rainfall_percentiles
from src.district_layers import canonical_district, load_district_layers
from src.ensemble_weather import EnsembleWeatherError, fetch_ensemble_forecasts
from src.evaluation import (evaluate_forward_chaining, evaluate_leave_one_out, rainfall_only_ranking,
                            static_flood_proneness)
from src.navigator import (DEFAULT_PRIORITY_WEIGHTS, Event, Query, confidence,
                           district_confidence, missing_feature_fraction,
                           priority_ranking, retrieve, scenario_analysis,
                           adjust_correlated_weights)
from src.reservoirs import (DEFAULT_BUFFER_CONCERN_THRESHOLD_PCT,
                            ReservoirDataError, apply_buffer_flags,
                            fetch_reservoir_status)


ROOT = Path(__file__).parent
WEB_DIST = ROOT / "web" / "dist"
app = FastAPI(title="Monsoon Impact Navigator API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class RunRequest(BaseModel):
    mode: Literal["manual", "live_ensemble"] = "manual"
    intensity_mm: float = Field(300, ge=0, le=2000)
    duration_hours: float = Field(48, ge=0, le=720)
    antecedent_7d_mm: float = Field(120, ge=0, le=5000)
    antecedent_30d_mm: float = Field(320, ge=0, le=10000)
    forecast_days: int = Field(3, ge=1, le=7)
    latitude: float = Field(13.08, ge=-90, le=90)
    longitude: float = Field(80.27, ge=-180, le=180)
    uncertainty_pct: float = Field(25, ge=0, le=100)
    month: int = Field(default_factory=lambda: date.today().month, ge=1, le=12)
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_PRIORITY_WEIGHTS))
    exposure: dict[str, float] = Field(default_factory=dict)
    vulnerability: dict[str, float] = Field(default_factory=dict)
    isolation: dict[str, float] = Field(default_factory=dict)
    forecast_percentiles: dict[str, float] = Field(default_factory=dict)
    load_reservoir_context: bool = False
    reservoir_threshold_pct: float = Field(DEFAULT_BUFFER_CONCERN_THRESHOLD_PCT, ge=0, le=100)


def _load_events() -> list[Event]:
    records = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))
    feature_path = ROOT / "data" / "processed" / "event_district_features.json"
    enriched = json.loads(feature_path.read_text(encoding="utf-8")) if feature_path.is_file() else {}
    district_features = enriched.get("events", {})
    return [Event(
        row["event_id"], row["name"], row["start_date"], row["end_date"], row["features"],
        tuple(row["affected_districts"]), row["source"], row.get("evidence_notes", ""),
        row.get("evidence_page"), row.get("local_evidence"), district_features.get(row["event_id"]),
    ) for row in records]


@lru_cache(maxsize=1)
def _district_layers() -> dict:
    return load_district_layers(ROOT)


def _events() -> list[Event]:
    return _load_events()


def _event_provenance() -> dict[str, dict]:
    records = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))
    return {row["event_id"]: row for row in records}


def _event_public(event: Event) -> dict:
    provenance = _event_provenance().get(event.event_id, {})
    return {"event_id": event.event_id, "name": event.name, "start_date": event.start_date,
            "end_date": event.end_date, "features": event.features,
            "affected_districts": list(event.affected_districts), "source": event.source,
            "evidence_notes": event.evidence_notes, "evidence_page": event.evidence_page,
            "local_evidence": event.local_evidence,
            "label_status": provenance.get("label_status"),
            "label_confidence": provenance.get("label_confidence"),
            "source_retrieved_at_utc": provenance.get("source_retrieved_at_utc"),
            "analysis_buffer_days": provenance.get("analysis_buffer_days"),
            "cyclone_window_evidence": provenance.get("cyclone_window_evidence")}


def _analogue_public(item: dict) -> dict:
    return {"event": _event_public(item["event"]), "distance": item["distance"],
            "features_used": item["features_used"]}


def _validate_weights(weights: dict[str, float]) -> dict[str, float]:
    if set(weights) != set(DEFAULT_PRIORITY_WEIGHTS):
        raise HTTPException(422, f"weights must contain: {', '.join(DEFAULT_PRIORITY_WEIGHTS)}")
    if any(value < 0 or value > 1 for value in weights.values()) or sum(weights.values()) <= 0:
        raise HTTPException(422, "weights must be between 0 and 1 and sum to a positive value")
    return weights


def _normalised_overrides(names: list[str], values: dict[str, float], label: str,
                          default_values: dict[str, float]) -> dict[str, float]:
    lookup = {canonical_district(key): value for key, value in values.items()}
    result = {name: float(default_values.get(canonical_district(name), 0.5)) for name in names}
    for name in names:
        value = lookup.get(canonical_district(name))
        if value is not None:
            if not 0 <= value <= 1:
                raise HTTPException(422, f"{label} values must be between 0 and 1")
            result[name] = float(value)
    return result


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "application": "Monsoon Impact Navigator"}


@app.get("/api/bootstrap")
def bootstrap() -> dict:
    layers = _district_layers()
    events = _events()
    names = layers.get("source_names", {})
    district_list = sorted(names.values()) or sorted({d for event in events for d in event.affected_districts})
    osm_path = ROOT / "data" / "layers" / "district_osm.json"
    osm_data = json.loads(osm_path.read_text(encoding="utf-8")) if osm_path.is_file() else {}
    return {
        "districts": [{"name": name, "key": canonical_district(name),
                       "centroid": layers.get("centroids", {}).get(canonical_district(name)),
                       "exposure": layers.get("exposure", {}).get(canonical_district(name), 0.5),
                       "vulnerability": layers.get("vulnerability", {}).get(canonical_district(name), 0.5),
                       "isolation": layers.get("isolation", {}).get(canonical_district(name), 0.5),
                       "osm": layers.get("osm_features", {}).get(canonical_district(name))}
                      for name in district_list],
        "events": [_event_public(event) for event in events],
        "boundaries": layers.get("geojson"),
        "sources": layers.get("sources", {}),
        "osm": {"records": len(osm_data.get("records", [])),
                "errors": osm_data.get("errors", []), "license": osm_data.get("license"),
                "retrieved_at_utc": osm_data.get("retrieved_at_utc")},
        "event_count": len(events),
        "limitations": [
            f"Prototype event library contains {len(events)} curated events; affected-district reports are uneven.",
            "District rankings are preparation support, not flood-depth predictions, dispatch, or routing.",
            "River distance, cropland exposure, and travel-time/passability are not modelled.",
            "Forecast ensemble spread is not calibrated forecast error.",
        ],
    }


@app.post("/api/run")
async def run_analysis(request: RunRequest) -> dict:
    layers = _district_layers()
    events = _events()
    weights = _validate_weights(request.weights)
    districts = sorted(layers.get("source_names", {}).values()) or sorted(
        {district for event in events for district in event.affected_districts})
    intensity_by_district = {name: request.intensity_mm for name in districts}
    duration_by_district = {name: request.duration_hours for name in districts}
    forecast_source = {"mode": "manual prototype input"}
    forecast_scenarios_by_district = None
    ensemble_metadata = None
    if request.mode == "live_ensemble":
        locations = {name: (point["latitude"], point["longitude"])
                     for name in districts
                     if (point := layers.get("centroids", {}).get(canonical_district(name)))}
        if not locations:
            raise HTTPException(503, "District centroid data is unavailable for live ensemble forecasts")
        try:
            ensemble_metadata = await run_in_threadpool(
                fetch_ensemble_forecasts, locations, request.forecast_days)
        except (EnsembleWeatherError, ValueError) as exc:
            raise HTTPException(502, str(exc)) from exc
        forecasts = ensemble_metadata["districts"]
        forecast_scenarios_by_district = {
            scenario: {name: values[key] for name, values in forecasts.items()}
            for scenario, key in (("low", "low_24h_intensity_mm"),
                                  ("central", "central_24h_intensity_mm"),
                                  ("high", "high_24h_intensity_mm"))
        }
        intensity_by_district = forecast_scenarios_by_district["central"]
        duration_by_district = {name: values["precipitation_hours"] for name, values in forecasts.items()}
        forecast_source = {"source": ensemble_metadata["source"], "model": ensemble_metadata["model"],
                           "url": ensemble_metadata["url"],
                           "retrieved_at_utc": ensemble_metadata["retrieved_at_utc"],
                           "district_count": len(forecasts), "member_count": min(
                               values["member_count"] for values in forecasts.values())}

    default_exposure = layers.get("exposure", {})
    default_vulnerability = layers.get("vulnerability", {})
    default_isolation = layers.get("isolation", {})
    exposure = _normalised_overrides(districts, request.exposure, "exposure", default_exposure)
    vulnerability = _normalised_overrides(districts, request.vulnerability, "vulnerability", default_vulnerability)
    isolation = _normalised_overrides(districts, request.isolation, "isolation", default_isolation)
    rainfall_by_district = (forecast_scenarios_by_district["central"] if forecast_scenarios_by_district
                            else intensity_by_district)
    climatology, climatology_status = load_monthly_rainfall_percentiles(ROOT, rainfall_by_district, request.month)
    percentile = {name: float(request.forecast_percentiles.get(name,
                       climatology.get(name, request.forecast_percentiles.get(canonical_district(name), 0.5))))
                  for name in districts}
    if any(not 0 <= value <= 1 for value in percentile.values()):
        raise HTTPException(422, "forecast percentiles must be between 0 and 1")
    if not any(value > 1.0 and duration_by_district.get(name, 0) > 0
               for name, value in intensity_by_district.items()):
        return {"status": "dry_or_no_significant_rain", "central_forecast_mm": request.intensity_mm,
                "forecast_source": forecast_source, "official_warning": "Follow official IMD and district-administration bulletins."}

    values = list(intensity_by_district.values()) or [request.intensity_mm]
    median_intensity = sorted(values)[len(values) // 2]
    durations = list(duration_by_district.values()) or [request.duration_hours]
    median_duration = sorted(durations)[len(durations) // 2]
    central_query = Query(
        {"intensity_mm": median_intensity, "duration_hours": median_duration,
         "antecedent_7d_mm": request.antecedent_7d_mm,
         "antecedent_30d_mm": request.antecedent_30d_mm},
        percentile, exposure, vulnerability, isolation,
        intensity_by_district, duration_by_district)
    score_weights, overlap_rho, overlap_adjusted = adjust_correlated_weights(
        weights, exposure, isolation)
    threshold_cache: dict[str | None, float] = {}
    retrieval = retrieve(central_query, events, threshold_cache=threshold_cache)
    ranking = priority_ranking(central_query, retrieval, score_weights)

    if forecast_scenarios_by_district:
        scenario_values = forecast_scenarios_by_district
        spread = any((scenario_values["high"].get(name, 0) - scenario_values["low"].get(name, 0))
                     / max(scenario_values["central"].get(name, 0), 1) > 0.75
                     for name in districts)
    else:
        delta = median_intensity * request.uncertainty_pct / 100
        scenario_values = {"low": {name: max(0, value - delta) for name, value in intensity_by_district.items()},
                           "central": intensity_by_district,
                           "high": {name: value + delta for name, value in intensity_by_district.items()}}
        spread = request.uncertainty_pct > 75
    scenario_queries = {
        scenario: Query({**central_query.features, "intensity_mm": sorted(values.values())[len(values) // 2]},
                        percentile, exposure, vulnerability, isolation, values, duration_by_district)
        for scenario, values in scenario_values.items()
    }
    scenarios = scenario_analysis(scenario_queries, events, score_weights, threshold_cache)
    top_five = {row["district"] for row in ranking[:5]}
    scenario_sensitive = any(not scenarios["stability"].get(name, {}).get("stable", False)
                             for name in top_five)
    missing_fraction = missing_feature_fraction(retrieval)
    overall_confidence = confidence(retrieval, ranking, missing_fraction, spread, scenario_sensitive)
    for row in ranking:
        row["scenario_status"] = "stable" if scenarios["stability"].get(row["district"], {}).get("stable") else "scenario-sensitive"
        row["confidence"] = district_confidence(
            retrieval, row, missing_fraction, spread,
            row["scenario_status"] == "scenario-sensitive")
    severity = {"High": 0, "Medium": 1, "Low": 2}
    if ranking:
        overall_confidence = max((row["confidence"] for row in ranking[:5]), key=lambda item: severity[item])

    reservoir = None
    if request.load_reservoir_context:
        try:
            raw_reservoir = await run_in_threadpool(fetch_reservoir_status, date.today())
            reservoir = apply_buffer_flags(raw_reservoir, request.reservoir_threshold_pct)
        except ReservoirDataError as exc:
            reservoir = {"error": str(exc), "source_url": "https://www.tnagrisnet.tn.gov.in/home/reservoir/"}

    english = build_advisory(ranking, retrieval, "en", overall_confidence, reservoir if reservoir and "records" in reservoir else None)
    tamil = build_advisory(ranking, retrieval, "ta", overall_confidence, reservoir if reservoir and "records" in reservoir else None)
    scenario_result = {name: [{"district": row["district"], "priority": row["priority"]}
                              for row in value["ranking"][:10]]
                       for name, value in scenarios.items() if name in ("low", "central", "high")}
    stability_rows = [{"district": name, "positions": item["positions"], "stable": item["stable"]}
                      for name, item in scenarios["stability"].items()]
    analogues = [_analogue_public(item) for item in retrieval["analogues"]]
    public_retrieval = {"analogues": analogues, "threshold": retrieval["threshold"],
                        "abstained": retrieval["abstained"], "out_of_range": retrieval["out_of_range"],
                        "query_feature_count": retrieval["query_feature_count"]}
    sensitivity = []
    for title, values in (("Selected weights", score_weights),
                          ("Hazard emphasis", {"hazard": .55, "exposure": .20, "vulnerability": .15, "isolation": .10}),
                          ("Community context emphasis", {"hazard": .25, "exposure": .30, "vulnerability": .25, "isolation": .20})):
        sensitivity.append({"weight_set": title,
                            "top_5": [row["district"] for row in priority_ranking(central_query, retrieval, values)[:5]],
                            "weights": values})
    return {
        "status": "ok", "query": {**central_query.features, "month": request.month},
        "forecast_source": forecast_source, "ensemble": ensemble_metadata,
        "forecast_scenarios": {key: {name: round(value, 2) for name, value in rows.items()}
                               for key, rows in scenario_values.items()},
        "climatology": climatology_status,
        "confidence": overall_confidence,
        "confidence_inputs": {"forecast_spread_high": spread, "missing_feature_fraction": missing_fraction,
                              "scenario_sensitive_top_five": scenario_sensitive,
                              "exposure_isolation_spearman": overlap_rho,
                              "overlap_adjustment_applied": overlap_adjusted},
        "score_weights": {"requested": weights, "applied": score_weights},
        "ranking": ranking, "retrieval": public_retrieval,
        "scenarios": scenario_result, "scenario_stability": stability_rows,
        "baselines": {"rainfall_only": rainfall_only_ranking(central_query, events)[:5],
                      "static_flood_proneness": static_flood_proneness(events)[:5]},
        "sensitivity": sensitivity,
        "advisory": {"english": english, "tamil": tamil},
        "reservoir_context": reservoir,
        "limitations": ["Forecast scenario spread is not a calibrated error distribution.",
                        "District-level priority is not a flood extent or operational instruction.",
                        "Reservoir storage is context only and is not linked to districts or ranking."],
    }


@app.get("/api/evaluation")
async def evaluation() -> dict:
    try:
        rows = await run_in_threadpool(evaluate_leave_one_out, _events())
    except Exception as exc:
        raise HTTPException(500, f"hindcast evaluation failed: {exc}") from exc
    def mean_metric(method: str, metric: str) -> float | None:
        values = [row[method].get(metric) for row in rows if row[method].get(metric) is not None]
        return round(sum(values) / len(values), 4) if values else None

    summary = {
        method: {metric: mean_metric(method, metric)
                 for metric in ("precision_at_k", "recall_at_k")}
        for method in ("analogue", "rainfall_only", "static_flood_proneness")
    }
    summary["rainfall_only"]["evaluated_events"] = sum(
        row["rainfall_only"].get("precision_at_k") is not None for row in rows)
    return {"events": rows, "event_count": len(rows), "k": 5,
            "macro_average": summary,
            "note": "Macro averages are means of per-event scores. Small, report-labelled retrospective hindcast; it does not use archived operational forecast inputs."}


@app.get("/api/forward-evaluation")
async def forward_evaluation() -> dict:
    try:
        rows = await run_in_threadpool(evaluate_forward_chaining, _events())
    except Exception as exc:
        raise HTTPException(500, f"chronological hindcast failed: {exc}") from exc
    evaluated = [row for row in rows if row.get("status") is None]
    summary = {}
    for method in ("analogue", "rainfall_only", "static_flood_proneness"):
        summary[method] = {}
        for metric in ("precision_at_k", "recall_at_k"):
            values = [row[method].get(metric) for row in evaluated if row[method].get(metric) is not None]
            summary[method][metric] = round(sum(values) / len(values), 4) if values else None
        summary[method]["evaluated_events"] = sum(
            row[method].get("precision_at_k") is not None for row in evaluated)
    return {"events": rows, "event_count": len(rows), "evaluated_event_count": len(evaluated),
            "minimum_prior_events": 3, "k": 5, "macro_average": summary,
            "note": "Chronological retrospective reconstruction using only earlier event-library cases. Inputs include observed rainfall from the held-out event, not archived operational forecasts; this is not forecast skill."}


if WEB_DIST.is_dir() and (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{client_path:path}", include_in_schema=False)
    def serve_client(client_path: str):
        if client_path.startswith("api/"):
            raise HTTPException(404, "not found")
        target = (WEB_DIST / client_path).resolve()
        if target.is_file() and WEB_DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(WEB_DIST / "index.html")
