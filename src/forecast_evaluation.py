"""Evaluate archived ensemble precipitation forecasts against observations.

This module is deliberately separate from the observed-rainfall reconstruction in
``src.evaluation``. It accepts only forecast rows with explicit issue times and
file-level provenance; it never derives forecasts from observed rainfall.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev
from urllib.parse import urlparse

from .district_layers import canonical_district

MINIMUM_ELIGIBLE_EVENTS = 5
FORECAST_COLUMNS = {
    "event_id", "initialization_time_utc", "centre", "member",
    "lead_start_days", "lead_end_days", "valid_start_date", "valid_end_date",
    "district", "precipitation_mm", "source_file", "source_file_sha256",
    "source_url", "licence",
}
OBSERVATION_COLUMNS = {"date", "district", "rainfall_mm"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing required columns: {', '.join(sorted(missing))}")
        return list(reader)


def _parse_date(value: str, context: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: expected YYYY-MM-DD, got {value!r}") from exc


def _parse_utc(value: str, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context}: invalid ISO-8601 timestamp {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{context}: timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _load_events(path: Path) -> dict[str, dict]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"{path}: expected a JSON array of event records")
    events = {}
    for index, row in enumerate(records):
        if not isinstance(row, dict) or not all(key in row for key in ("event_id", "start_date", "end_date", "affected_districts")):
            raise ValueError(f"{path}: event row {index + 1} is missing required fields")
        event_id = row["event_id"]
        if not isinstance(event_id, str) or not event_id or event_id in events:
            raise ValueError(f"{path}: invalid or duplicate event_id at row {index + 1}")
        start = _parse_date(row["start_date"], f"event {event_id} start_date")
        end = _parse_date(row["end_date"], f"event {event_id} end_date")
        if end < start:
            raise ValueError(f"event {event_id}: end_date precedes start_date")
        districts = row["affected_districts"]
        if not isinstance(districts, list) or not districts:
            raise ValueError(f"event {event_id}: affected_districts must be a non-empty array")
        events[event_id] = {**row, "_start": start, "_end": end}
    return events


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_forecast_provenance(rows: list[dict[str, str]], base_dir: Path) -> None:
    verified: dict[str, str] = {}
    for line, row in enumerate(rows, start=2):
        label = f"forecast CSV row {line}"
        file_name = row["source_file"].strip()
        expected_hash = row["source_file_sha256"].strip().lower()
        if not file_name or not SHA256_RE.fullmatch(expected_hash):
            raise ValueError(f"{label}: source_file and a 64-character SHA-256 are required")
        source = (base_dir / file_name).resolve()
        if not source.is_relative_to(base_dir.resolve()):
            raise ValueError(f"{label}: source_file must be inside the forecast CSV directory")
        if not source.is_file():
            raise ValueError(f"{label}: source file does not exist: {source}")
        actual_hash = verified.get(str(source))
        if actual_hash is None:
            actual_hash = _sha256(source)
            verified[str(source)] = actual_hash
        if actual_hash != expected_hash:
            raise ValueError(f"{label}: SHA-256 does not match source file {source}")
        parsed_url = urlparse(row["source_url"].strip())
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"{label}: source_url must be an HTTP(S) URL")
        if not row["licence"].strip():
            raise ValueError(f"{label}: licence must be recorded")


def _load_observations(path: Path) -> dict[tuple[date, str], float]:
    rows = _read_csv(path, OBSERVATION_COLUMNS)
    observations: dict[tuple[date, str], float] = {}
    for line, row in enumerate(rows, start=2):
        day = _parse_date(row["date"], f"observation CSV row {line} date")
        district = canonical_district(row["district"])
        if not district:
            raise ValueError(f"observation CSV row {line}: district is empty")
        try:
            amount = float(row["rainfall_mm"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"observation CSV row {line}: invalid rainfall_mm") from exc
        if not math.isfinite(amount) or amount < 0:
            raise ValueError(f"observation CSV row {line}: rainfall_mm must be finite and non-negative")
        key = (day, district)
        if key in observations:
            raise ValueError(f"observation CSV row {line}: duplicate date/district {day}/{row['district']}")
        observations[key] = amount
    return observations


def _top_k_metrics(scores: dict[str, float], actual: set[str], k: int) -> dict:
    ordered = sorted(scores, key=lambda name: (-scores[name], name))
    selected = set(ordered[:k])
    hits = len(selected & actual)
    return {
        "k": k,
        "hits": hits,
        "precision_at_k": hits / len(selected) if selected else 0.0,
        "recall_at_k": hits / len(actual) if actual else None,
    }


def _climatology(district: str, month: int, before: date,
                 observations_by_district_month: dict[tuple[str, int], list[tuple[date, float]]]) -> float | None:
    values = [amount for day, amount in observations_by_district_month.get((district, month), ())
              if day < before]
    return mean(values) if values else None


def _bootstrap_mean_interval(values: list[float], seed: int = 20261031,
                             samples: int = 2000) -> dict:
    if len(values) < 2:
        return {"lower_95": None, "upper_95": None,
                "status": "insufficient_events_for_interval"}
    generator = random.Random(seed)
    bootstraps = sorted(mean(generator.choices(values, k=len(values))) for _ in range(samples))
    return {"lower_95": bootstraps[int(0.025 * (samples - 1))],
            "upper_95": bootstraps[int(0.975 * (samples - 1))],
            "method": "percentile bootstrap over event-level scores",
            "resamples": samples, "seed": seed}


def evaluate_archived_forecasts(forecast_csv: Path, observation_csv: Path,
                                events_json: Path, *, top_k: int = 5) -> dict:
    """Return per-run scores and event-bootstrap aggregates for pre-event forecasts."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    events = _load_events(events_json)
    observations = _load_observations(observation_csv)
    observations_by_district_month: dict[tuple[str, int], list[tuple[date, float]]] = defaultdict(list)
    for (day, district), amount in observations.items():
        observations_by_district_month[(district, day.month)].append((day, amount))
    forecasts = _read_csv(forecast_csv, FORECAST_COLUMNS)
    _validate_forecast_provenance(forecasts, forecast_csv.resolve().parent)

    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for line, row in enumerate(forecasts, start=2):
        context = f"forecast CSV row {line}"
        event_id = row["event_id"].strip()
        if event_id not in events:
            raise ValueError(f"{context}: unknown event_id {event_id!r}")
        start = _parse_date(row["valid_start_date"], f"{context} valid_start_date")
        end = _parse_date(row["valid_end_date"], f"{context} valid_end_date")
        if end < start or start < events[event_id]["_start"] or end > events[event_id]["_end"]:
            raise ValueError(f"{context}: valid window must be inside the labelled event window")
        initialization = _parse_utc(row["initialization_time_utc"], f"{context} initialization_time_utc")
        event_start = datetime.combine(events[event_id]["_start"], datetime.min.time(), timezone.utc)
        if initialization >= event_start:
            raise ValueError(f"{context}: forecast was initialized at/after event start")
        try:
            lead_start = int(row["lead_start_days"])
            lead_end = int(row["lead_end_days"])
            amount = float(row["precipitation_mm"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{context}: lead bounds and precipitation must be numeric") from exc
        if lead_start < 0 or lead_end < lead_start:
            raise ValueError(f"{context}: invalid lead interval")
        expected_start = initialization.date() + timedelta(days=lead_start)
        expected_end = initialization.date() + timedelta(days=lead_end)
        if start != expected_start or end != expected_end:
            raise ValueError(
                f"{context}: lead interval does not match valid window under the UTC calendar-day convention; "
                f"expected {expected_start.isoformat()} through {expected_end.isoformat()}")
        if not math.isfinite(amount) or amount < 0:
            raise ValueError(f"{context}: precipitation_mm must be finite and non-negative")
        district = canonical_district(row["district"])
        member = row["member"].strip()
        centre = row["centre"].strip()
        if not district or not member or not centre:
            raise ValueError(f"{context}: centre, member, and district are required")
        key = (event_id, initialization.isoformat(), centre, lead_start, lead_end,
               start.isoformat(), end.isoformat())
        grouped[key].append({"district": district, "member": member, "amount": amount})

    run_results = []
    skipped_runs = []
    for key, rows in sorted(grouped.items()):
        event_id, init_time, centre, lead_start, lead_end, valid_start_s, valid_end_s = key
        event = events[event_id]
        valid_start = date.fromisoformat(valid_start_s)
        valid_end = date.fromisoformat(valid_end_s)
        days = [date.fromordinal(ordinal) for ordinal in range(valid_start.toordinal(), valid_end.toordinal() + 1)]
        by_district_member: dict[tuple[str, str], float] = {}
        by_district: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            pair = (row["district"], row["member"])
            if pair in by_district_member:
                raise ValueError(f"duplicate forecast district/member in run {event_id}/{centre}/{lead_start}-{lead_end}")
            by_district_member[pair] = row["amount"]
            by_district[row["district"]].append(row["amount"])
        members = {member for _, member in by_district_member}
        districts = sorted(by_district)
        if len(members) < 2:
            raise ValueError(f"run {event_id}/{centre}/{lead_start}-{lead_end}: at least two ensemble members are required")
        if any({member for district, member in by_district_member if district == name} != members for name in districts):
            raise ValueError(f"run {event_id}/{centre}/{lead_start}-{lead_end}: every district must have the same ensemble members")

        actual: dict[str, float] = {}
        climatology: dict[str, float] = {}
        missing: list[str] = []
        event_label = {canonical_district(name) for name in event["affected_districts"]}
        for district in districts:
            daily = [observations.get((day, district)) for day in days]
            if any(amount is None for amount in daily):
                missing.append(district)
                continue
            actual[district] = sum(amount for amount in daily if amount is not None)
            daily_normals = [_climatology(district, day.month, event["_start"], observations_by_district_month)
                             for day in days]
            if all(value is not None for value in daily_normals):
                climatology[district] = sum(value for value in daily_normals if value is not None)

        if missing:
            skipped_runs.append({
                "event_id": event_id,
                "initialization_time_utc": init_time,
                "centre": centre,
                "lead_days": {"start": lead_start, "end": lead_end},
                "status": "not_evaluated_missing_observations",
                "missing_observation_districts": missing,
            })
            continue
        if not actual:
            continue
        ensemble_mean = {district: mean(by_district[district]) for district in districts}
        forecast_errors = [ensemble_mean[district] - actual[district] for district in districts]
        forecast_mae = mean(abs(error) for error in forecast_errors)
        forecast_rmse = math.sqrt(mean(error * error for error in forecast_errors))
        common = sorted(set(actual) & set(climatology))
        baseline_metrics = None
        if common:
            baseline_errors = [climatology[district] - actual[district] for district in common]
            baseline_metrics = {
                "district_count": len(common),
                "mae_mm": mean(abs(error) for error in baseline_errors),
                "rmse_mm": math.sqrt(mean(error * error for error in baseline_errors)),
                "baseline": "same-calendar-month observed daily climatology, using dates strictly before event start",
            }
        valid_label_districts = event_label & set(ensemble_mean)
        run_results.append({
            "event_id": event_id,
            "event": event.get("name", event_id),
            "initialization_time_utc": init_time,
            "centre": centre,
            "lead_days": {"start": lead_start, "end": lead_end},
            "valid_window": {"start": valid_start_s, "end": valid_end_s},
            "ensemble_member_count": len(members),
            "district_count": len(actual),
            "forecast_precipitation": {"mae_mm": forecast_mae, "rmse_mm": forecast_rmse},
            "district_error_diagnostics": [
                {
                    "district": district,
                    "ensemble_mean_mm": ensemble_mean[district],
                    "ensemble_spread_sd_mm": stdev(by_district[district]),
                    "ensemble_spread_p90_p10_mm": (
                        sorted(by_district[district])[round(0.90 * (len(members) - 1))]
                        - sorted(by_district[district])[round(0.10 * (len(members) - 1))]
                    ),
                    "observed_mm": actual[district],
                    "absolute_error_mm": abs(ensemble_mean[district] - actual[district]),
                }
                for district in districts
            ],
            "climatology_precipitation": baseline_metrics or {"status": "not_evaluated_no_prior_same_month_observations"},
            "impact_label_coverage": {"labelled_districts_in_forecast": len(valid_label_districts),
                                       "total_labelled_districts": len(event_label),
                                       "fraction": (len(valid_label_districts) / len(event_label)
                                                    if event_label else None)},
            "climatology_impact_label_coverage": {
                "labelled_districts_in_baseline": len(event_label & set(climatology)),
                "total_labelled_districts": len(event_label),
                "fraction": (len(event_label & set(climatology)) / len(event_label)
                             if event_label else None)},
            "forecast_rainfall_ranking": _top_k_metrics(ensemble_mean, event_label, top_k),
            "climatology_rainfall_ranking": (_top_k_metrics(climatology, event_label, top_k)
                                             if common else {"status": "not_evaluated_no_prior_same_month_observations"}),
            "status": "eligible_pre_event_forecast",
        })

    event_ids = {row["event_id"] for row in run_results}
    strata: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for row in run_results:
        lead = row["lead_days"]
        strata[(row["centre"], lead["start"], lead["end"])].append(row)
    aggregate = []
    for (centre, lead_start, lead_end), rows in sorted(strata.items()):
        event_rows: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            event_rows[row["event_id"]].append(row)
        event_level_mae = [mean(item["forecast_precipitation"]["mae_mm"] for item in event_runs)
                           for event_runs in event_rows.values()]
        event_level_rmse = [mean(item["forecast_precipitation"]["rmse_mm"] for item in event_runs)
                            for event_runs in event_rows.values()]
        aggregate.append({
            "centre": centre,
            "lead_days": {"start": lead_start, "end": lead_end},
            "eligible_event_count": len(event_rows),
            "forecast_run_count": len(rows),
            "event_macro_mae_mm": mean(event_level_mae) if event_level_mae else None,
            "event_macro_mae_95_ci": _bootstrap_mean_interval(event_level_mae),
            "event_macro_rmse_mm": mean(event_level_rmse) if event_level_rmse else None,
            "event_macro_rmse_95_ci": _bootstrap_mean_interval(event_level_rmse, seed=20261101),
            "claim_threshold_met": len(event_rows) >= MINIMUM_ELIGIBLE_EVENTS,
        })
    eligible_count = len(event_ids)
    claim_threshold_met = any(row["claim_threshold_met"] for row in aggregate)
    all_event_ids = set(events)
    return {
        "evaluation_type": "archived_operational_forecast_vs_observation",
        "status": "forecast_skill_claim_threshold_met" if claim_threshold_met else "pending_insufficient_eligible_events",
        "minimum_eligible_events_for_skill_claim": MINIMUM_ELIGIBLE_EVENTS,
        "eligible_event_count": eligible_count,
        "claim_threshold_met": claim_threshold_met,
        "events_without_evaluable_forecast": sorted(all_event_ids - event_ids),
        "forecast_run_count": len(run_results),
        "inputs": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (forecast_csv, observation_csv, events_json)
        },
        "aggregate_by_centre_and_lead": aggregate,
        "uncertainty_unit": "held-out event; runs within an event/centre/lead stratum are averaged first",
        "runs": run_results,
        "skipped_runs": skipped_runs,
        "limitations": [
            "Forecast skill is not established until the minimum eligible-event threshold is met.",
            "District-average rainfall and report-derived affected-district labels are imperfect observation and impact proxies.",
            "Climatology uses only matching calendar-month daily observations strictly before each event start.",
            "Spatial correlation means district-level scores are not independent samples; uncertainty intervals resample events only.",
        ],
    }
