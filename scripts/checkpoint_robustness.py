"""Checkpoint 7: verify predictable failure and edge-case behaviour."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.navigator import Event, Query, retrieve


def load_events():
    records = json.loads((Path(__file__).parents[1] / "data" / "events.json").read_text(encoding="utf-8"))
    return [Event(r["event_id"], r["name"], r["start_date"], r["end_date"], r["features"], tuple(r["affected_districts"]), r["source"], r.get("evidence_notes", ""), r.get("evidence_page"), r.get("local_evidence")) for r in records]


def base_query(features):
    return Query(features, {"Chennai": .5}, {"Chennai": .5}, {"Chennai": .5}, {"Chennai": .5})


if __name__ == "__main__":
    library = load_events()
    cases = {
        "dry": base_query({"intensity_mm": 0, "duration_hours": 0}),
        "out_of_range": base_query({"intensity_mm": 5000, "duration_hours": 240}),
        "partial_features": base_query({"intensity_mm": 300}),
    }
    for name, query in cases.items():
        result = retrieve(query, library)
        assert result["analogues"], name
    try:
        retrieve(cases["dry"], [])
    except ValueError:
        pass
    else:
        raise AssertionError("empty library should fail clearly")
    print("LIVE DEMO ROBUSTNESS CHECK: PASS")
    print("cases=dry,out_of_range,partial_features,empty_library")
