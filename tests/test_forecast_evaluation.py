import csv
import hashlib
import json
from pathlib import Path

import pytest

from src.forecast_evaluation import evaluate_archived_forecasts


def write_forecast_inputs(directory: Path, lead_start: int = 1, lead_end: int = 1):
    original = directory / "original.grib"
    original.write_bytes(b"fixture forecast bytes")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    forecasts = directory / "forecasts.csv"
    columns = [
        "event_id", "initialization_time_utc", "centre", "member",
        "lead_start_days", "lead_end_days", "valid_start_date", "valid_end_date",
        "district", "precipitation_mm", "source_file", "source_file_sha256",
        "source_url", "licence",
    ]
    with forecasts.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for member, amount in (("m1", 10), ("m2", 20)):
            writer.writerow({
                "event_id": "event-1", "initialization_time_utc": "2020-10-01T00:00:00Z",
                "centre": "centre-a", "member": member,
                "lead_start_days": lead_start, "lead_end_days": lead_end,
                "valid_start_date": "2020-10-02", "valid_end_date": "2020-10-02",
                "district": "Alpha", "precipitation_mm": amount,
                "source_file": original.name, "source_file_sha256": digest,
                "source_url": "https://example.org/archive", "licence": "test-only",
            })

    observations = directory / "observations.csv"
    with observations.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "district", "rainfall_mm"])
        writer.writeheader()
        writer.writerow({"date": "2020-10-02", "district": "Alpha", "rainfall_mm": 15})

    events = directory / "events.json"
    events.write_text(json.dumps([{
        "event_id": "event-1", "start_date": "2020-10-02", "end_date": "2020-10-02",
        "affected_districts": ["Alpha", "Beta"],
    }]), encoding="utf-8")
    return forecasts, observations, events


def test_lead_interval_must_match_utc_valid_dates(tmp_path):
    forecasts, observations, events = write_forecast_inputs(tmp_path, lead_start=2, lead_end=2)

    with pytest.raises(ValueError, match="lead interval does not match valid window"):
        evaluate_archived_forecasts(forecasts, observations, events)


def test_impact_recall_uses_all_event_labels_and_reports_coverage(tmp_path):
    forecasts, observations, events = write_forecast_inputs(tmp_path)

    result = evaluate_archived_forecasts(forecasts, observations, events, top_k=1)
    run = result["runs"][0]

    assert run["impact_label_coverage"] == {
        "labelled_districts_in_forecast": 1, "total_labelled_districts": 2,
        "fraction": 0.5,
    }
    assert run["climatology_impact_label_coverage"]["fraction"] == 0.0
    assert run["forecast_rainfall_ranking"]["hits"] == 1
    assert run["forecast_rainfall_ranking"]["recall_at_k"] == 0.5
