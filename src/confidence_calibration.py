"""Summarise archived ensemble spread against held-out absolute errors.

The output is a diagnostic calibration candidate, not a probability model. It
must be reviewed and matched to the same forecast system and lead before use.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _spread_bins(rows: list[dict], count: int) -> list[dict]:
    ordered = sorted(rows, key=lambda row: row["spread"])
    size = math.ceil(len(ordered) / count)
    bins = []
    for start in range(0, len(ordered), size):
        selected = ordered[start:start + size]
        errors = sorted(row["error"] for row in selected)
        bins.append({
            "sample_count": len(selected),
            "event_count": len({row["event_id"] for row in selected}),
            "spread_min_mm": selected[0]["spread"],
            "spread_max_mm": selected[-1]["spread"],
            "median_absolute_error_mm": mean(errors) if len(errors) == 1 else (errors[(len(errors) - 1) // 2] + errors[len(errors) // 2]) / 2,
            "p90_absolute_error_mm": errors[round(0.90 * (len(errors) - 1))],
        })
    return bins


def build_spread_error_diagnostics(evaluation_path: Path, *, minimum_events: int = 10,
                                   minimum_samples: int = 100, bins: int = 5) -> dict:
    if minimum_events < 2 or minimum_samples < 1 or bins < 1:
        raise ValueError("minimum_events must be >=2; minimum_samples and bins must be positive")
    report = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if report.get("evaluation_type") != "archived_operational_forecast_vs_observation":
        raise ValueError("input must be an archived forecast evaluation report")

    groups: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for run in report.get("runs", []):
        if run.get("status") != "eligible_pre_event_forecast":
            continue
        lead = run["lead_days"]
        key = (run["centre"], int(lead["start"]), int(lead["end"]))
        for district in run.get("district_error_diagnostics", []):
            spread = district.get("ensemble_spread_p90_p10_mm")
            error = district.get("absolute_error_mm")
            if (isinstance(spread, (int, float)) and math.isfinite(spread) and spread >= 0
                    and isinstance(error, (int, float)) and math.isfinite(error) and error >= 0):
                groups[key].append({"event_id": run["event_id"], "spread": float(spread), "error": float(error)})

    strata = []
    for (centre, lead_start, lead_end), rows in sorted(groups.items()):
        event_count = len({row["event_id"] for row in rows})
        ready = event_count >= minimum_events and len(rows) >= minimum_samples
        strata.append({
            "centre": centre,
            "lead_days": {"start": lead_start, "end": lead_end},
            "event_count": event_count,
            "district_run_sample_count": len(rows),
            "status": "ready_for_independent_review" if ready else "pending_insufficient_evidence",
            "spread_error_bins": _spread_bins(rows, bins) if rows else [],
        })

    return {
        "artifact_type": "ensemble_spread_vs_absolute_error_diagnostic",
        "status": "candidate_strata_available_for_review" if any(
            item["status"] == "ready_for_independent_review" for item in strata
        ) else "pending_insufficient_evidence",
        "source_evaluation": {"file": evaluation_path.name, "sha256": _sha256(evaluation_path)},
        "readiness_gate": {
            "minimum_distinct_events_per_centre_and_lead": minimum_events,
            "minimum_district_run_samples_per_centre_and_lead": minimum_samples,
            "spread_bins": bins,
            "required_next_step": "independent_review_and_out-of-sample validation before enabling confidence calibration",
        },
        "strata": strata,
        "limitations": [
            "Bins describe empirical absolute error conditional on ensemble P90-P10 spread; they are not calibrated probabilities.",
            "Districts within an event are spatially dependent; event count is the primary readiness gate.",
            "Do not transfer calibration between forecast centres, models, lead intervals, or providers.",
            "A ready stratum is only a candidate for review and does not activate High confidence.",
        ],
    }
