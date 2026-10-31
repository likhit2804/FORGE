"""Checkpoint 1: validate event-library provenance and schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

VERIFIED_STATUSES = {"verified_source_report", "verified_satellite_extent", "verified_government_report"}
REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "data" / "event.schema.json"
SOURCE_MANIFEST_PATH = REPO_ROOT / "data" / "sources" / "manifest.json"


def reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric value {value}")


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        records = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_nonstandard_constant)
    except Exception as exc:
        return [f"cannot parse {path}: {exc}"]
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"cannot load event schema {SCHEMA_PATH}: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for issue in sorted(validator.iter_errors(records), key=lambda error: list(map(str, error.absolute_path))):
        location = ".".join(str(part) for part in issue.absolute_path) or "events"
        errors.append(f"{location}: {issue.message}")
    if not isinstance(records, list):
        return errors

    ids: set[str] = set()
    for index, record in enumerate(records):
        prefix = f"event[{index}]"
        if not isinstance(record, dict):
            continue
        event_id = record.get("event_id")
        if isinstance(event_id, str) and event_id in ids:
            errors.append(f"{prefix}: duplicate event_id {event_id}")
        elif isinstance(event_id, str):
            ids.add(event_id)
        districts = record.get("affected_districts")
        if (isinstance(districts, list)
                and all(isinstance(district, str) for district in districts)
                and len({district.casefold().strip() for district in districts}) != len(districts)):
            errors.append(f"{prefix}: affected_districts must be non-empty and contain no duplicates")
        status = record.get("label_status")
        if isinstance(status, str) and status in VERIFIED_STATUSES:
            local_evidence = record.get("local_evidence")
            evidence_path = (REPO_ROOT / local_evidence).resolve() if isinstance(local_evidence, str) else None
            if (not evidence_path or not evidence_path.is_relative_to(REPO_ROOT)
                    or not evidence_path.is_file()):
                errors.append(f"{prefix}: verified record requires existing local_evidence")
            digest = record.get("raw_file_sha256")
            if isinstance(digest, str) and evidence_path and evidence_path.is_file():
                actual_digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                if actual_digest.lower() != digest.lower():
                    errors.append(f"{prefix}: raw_file_sha256 does not match local_evidence")
        start = record.get("start_date")
        end = record.get("end_date")
        window = record.get("analysis_window")
        if isinstance(start, str) and isinstance(end, str) and isinstance(window, dict):
            if end < start:
                errors.append(f"{prefix}: end_date precedes start_date")
            if window.get("start") != start or window.get("end") != end:
                errors.append(f"{prefix}: analysis_window must match the recorded event dates")
    return errors


def validate_source_manifest(path: Path = SOURCE_MANIFEST_PATH) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse source manifest {path}: {exc}"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list):
        return ["source manifest must be an object with a sources list"]

    seen_paths: set[str] = set()
    for index, entry in enumerate(manifest["sources"]):
        prefix = f"source[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: entry must be an object")
            continue
        relative_path = entry.get("path")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append(f"{prefix}: path must be a non-empty string")
            continue
        if relative_path in seen_paths:
            errors.append(f"{prefix}: duplicate path {relative_path}")
            continue
        seen_paths.add(relative_path)
        source_path = (REPO_ROOT / relative_path).resolve()
        if not source_path.is_relative_to(REPO_ROOT) or not source_path.is_file():
            errors.append(f"{prefix}: source file is missing or outside the repository")
            continue
        expected_size = entry.get("bytes")
        if (not isinstance(expected_size, int) or isinstance(expected_size, bool)
                or source_path.stat().st_size != expected_size):
            errors.append(f"{prefix}: byte size does not match {relative_path}")
        expected_hash = entry.get("sha256")
        if (not isinstance(expected_hash, str) or len(expected_hash) != 64
                or any(char not in "0123456789abcdefABCDEF" for char in expected_hash)):
            errors.append(f"{prefix}: sha256 must contain 64 hexadecimal characters")
        elif hashlib.sha256(source_path.read_bytes()).hexdigest().lower() != expected_hash.lower():
            errors.append(f"{prefix}: sha256 does not match {relative_path}")
        for field in ("title", "publisher", "source_url", "license_status", "redistribution_status"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}: {field} must be a non-empty string")
        source_url = entry.get("source_url")
        if isinstance(source_url, str) and not source_url.startswith(("http://", "https://")):
            errors.append(f"{prefix}: source_url must use http or https")

    actual_paths = {
        source_path.relative_to(REPO_ROOT).as_posix()
        for source_path in SOURCE_MANIFEST_PATH.parent.rglob("*")
        if source_path.is_file() and source_path.resolve() != path.resolve()
    }
    for unlisted in sorted(actual_paths - seen_paths):
        errors.append(f"source manifest is missing an entry for {unlisted}")
    listed_bytes = sum(
        entry.get("bytes", 0) for entry in manifest["sources"]
        if isinstance(entry, dict) and isinstance(entry.get("bytes"), int)
        and not isinstance(entry.get("bytes"), bool)
    )
    if manifest.get("total_source_bytes") != listed_bytes:
        errors.append("source manifest total_source_bytes does not match the listed file sizes")
    return errors


def verified_count(path: Path) -> int:
    records = json.loads(path.read_text(encoding="utf-8"))
    return sum(record.get("label_status") in VERIFIED_STATUSES for record in records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=REPO_ROOT / "data" / "events.json",
                        help="event JSON file to validate (default: data/events.json)")
    target = parser.parse_args().events.resolve()
    failures = validate(target)
    failures.extend(validate_source_manifest())
    if failures:
        print("PROVENANCE CHECK: FAIL")
        print("\n".join(f"- {failure}" for failure in failures))
        sys.exit(1)
    records = json.loads(target.read_text(encoding="utf-8"))
    print(f"PROVENANCE CHECK: PASS ({len(records)} events; {verified_count(target)} verified, {len(records) - verified_count(target)} pending)")
