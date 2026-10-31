"""Checkpoint 1: validate event-library provenance and schema."""

from __future__ import annotations

import json
import hashlib
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_FEATURES = ("intensity_mm", "duration_hours")
OPTIONAL_FEATURES = ("antecedent_7d_mm", "antecedent_30d_mm", "reservoir_storage_pct")
REQUIRED_FIELDS = ("event_id", "name", "start_date", "end_date", "analysis_window",
                   "features", "affected_districts", "source")
VERIFIED_STATUSES = {"verified_source_report", "verified_satellite_extent", "verified_government_report"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse {path}: {exc}"]
    if not isinstance(records, list) or not records:
        return ["event library must be a non-empty JSON list"]
    ids: set[str] = set()
    for index, record in enumerate(records):
        prefix = f"event[{index}]"
        missing = [field for field in REQUIRED_FIELDS if not record.get(field)]
        errors.extend(f"{prefix}: missing {field}" for field in missing)
        event_id = record.get("event_id")
        if event_id in ids:
            errors.append(f"{prefix}: duplicate event_id {event_id}")
        ids.add(event_id)
        try:
            start = date.fromisoformat(record["start_date"])
            end = date.fromisoformat(record["end_date"])
            if end < start:
                errors.append(f"{prefix}: end_date precedes start_date")
            window = record.get("analysis_window", {})
            if window.get("start") != start.isoformat() or window.get("end") != end.isoformat():
                errors.append(f"{prefix}: analysis_window must match the recorded event dates")
        except (KeyError, TypeError, ValueError):
            errors.append(f"{prefix}: dates must use YYYY-MM-DD")
        features = record.get("features", {})
        for feature in (*REQUIRED_FEATURES, *OPTIONAL_FEATURES):
            value = features.get(feature)
            if feature in REQUIRED_FEATURES and (not isinstance(value, (int, float)) or value < 0):
                errors.append(f"{prefix}: {feature} must be a non-negative number")
            elif feature in features and (not isinstance(value, (int, float)) or value < 0):
                errors.append(f"{prefix}: {feature} must be a non-negative number when supplied")
        districts = record.get("affected_districts")
        if not isinstance(districts, list) or not all(isinstance(d, str) and d.strip() for d in districts):
            errors.append(f"{prefix}: affected_districts must be a non-empty list of names")
        source = str(record.get("source", ""))
        parsed = urlparse(source)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{prefix}: source must be an http(s) URL")
        status = record.get("label_status")
        if not status:
            errors.append(f"{prefix}: missing label_status")
        if status in VERIFIED_STATUSES:
            local_evidence = record.get("local_evidence")
            evidence_path = (path.parents[1] / local_evidence).resolve() if local_evidence else None
            repo_root = path.parents[1].resolve()
            if not local_evidence or not evidence_path.is_relative_to(repo_root) or not evidence_path.is_file():
                errors.append(f"{prefix}: verified record requires existing local_evidence")
            if not record.get("evidence_notes") or not isinstance(record.get("evidence_page"), int):
                errors.append(f"{prefix}: verified record requires evidence_notes and evidence_page")
            retrieved = record.get("source_retrieved_at_utc")
            try:
                datetime.fromisoformat(str(retrieved).replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{prefix}: verified record requires source_retrieved_at_utc in ISO-8601 format")
            digest = record.get("raw_file_sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                errors.append(f"{prefix}: verified record requires a SHA-256 hash of local evidence")
            elif evidence_path and evidence_path.is_file():
                actual_digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                if actual_digest.lower() != digest.lower():
                    errors.append(f"{prefix}: raw_file_sha256 does not match local_evidence")
            if not isinstance(record.get("analysis_buffer_days"), int) or record["analysis_buffer_days"] < 0:
                errors.append(f"{prefix}: verified record requires a non-negative analysis_buffer_days")
            if record.get("cyclone_window_verified_clear") is not True:
                errors.append(f"{prefix}: verified record requires a clear, checked cyclone window")
            if not record.get("cyclone_window_evidence"):
                errors.append(f"{prefix}: verified record requires cyclone-window evidence")
            if not record.get("feature_method"):
                errors.append(f"{prefix}: verified record requires a feature_method description")
    return errors


def verified_count(path: Path) -> int:
    records = json.loads(path.read_text(encoding="utf-8"))
    return sum(record.get("label_status") in VERIFIED_STATUSES for record in records)


if __name__ == "__main__":
    target = Path(__file__).parents[1] / "data" / "events.json"
    failures = validate(target)
    if failures:
        print("PROVENANCE CHECK: FAIL")
        print("\n".join(f"- {failure}" for failure in failures))
        sys.exit(1)
    records = json.loads(target.read_text(encoding="utf-8"))
    print(f"PROVENANCE CHECK: PASS ({len(records)} events; {verified_count(target)} verified, {len(records) - verified_count(target)} pending)")
