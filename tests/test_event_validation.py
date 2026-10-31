import json
from pathlib import Path

from scripts.validate_events import REPO_ROOT, validate, validate_source_manifest


def event_record(**changes):
    record = {
        "event_id": "candidate-1",
        "name": "Candidate rainfall event",
        "start_date": "2024-10-01",
        "end_date": "2024-10-02",
        "analysis_window": {"start": "2024-10-01", "end": "2024-10-02"},
        "features": {"intensity_mm": 80.0, "duration_hours": 48.0},
        "affected_districts": ["Chennai"],
        "source": "https://example.org/report.pdf",
        "label_status": "pending_review",
        "label_confidence": "medium",
    }
    record.update(changes)
    return record


def write_events(tmp_path: Path, records) -> Path:
    path = tmp_path / "events.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_accepts_schema_valid_pending_candidate(tmp_path):
    assert validate(write_events(tmp_path, [event_record()])) == []


def test_reports_schema_errors_for_missing_feature_and_bad_confidence(tmp_path):
    record = event_record(label_confidence="certain")
    record["features"].pop("duration_hours")

    errors = validate(write_events(tmp_path, [record]))

    assert any("duration_hours" in error for error in errors)
    assert any("label_confidence" in error for error in errors)


def test_checks_analysis_window_matches_event_dates(tmp_path):
    record = event_record(analysis_window={"start": "2024-10-02", "end": "2024-10-02"})

    errors = validate(write_events(tmp_path, [record]))

    assert any("analysis_window must match" in error for error in errors)


def test_rejects_duplicate_ids_and_case_insensitive_district_duplicates(tmp_path):
    first = event_record()
    second = event_record(affected_districts=["Chennai", " chennai "])

    errors = validate(write_events(tmp_path, [first, second]))

    assert any("duplicate event_id" in error for error in errors)
    assert any("affected_districts" in error and "duplicates" in error for error in errors)


def test_checks_verified_evidence_hash(tmp_path):
    evidence_path = REPO_ROOT / "data" / "sources" / "imd_rsmc_annual_report_2010.pdf"
    record = event_record(
        label_status="verified_government_report",
        local_evidence="data/sources/imd_rsmc_annual_report_2010.pdf",
        evidence_notes="IMD report documents the event and district impact.",
        evidence_page=104,
        source_retrieved_at_utc="2026-10-31T17:00:10Z",
        raw_file_sha256="0" * 64,
        analysis_buffer_days=2,
        cyclone_window_verified_clear=True,
        cyclone_window_evidence="The reported system was a depression.",
        feature_method="Station 24-hour maximum; event window duration.",
    )
    assert evidence_path.is_file()

    errors = validate(write_events(tmp_path, [record]))

    assert any("raw_file_sha256 does not match" in error for error in errors)


def test_source_manifest_matches_every_local_source_file():
    assert validate_source_manifest() == []
