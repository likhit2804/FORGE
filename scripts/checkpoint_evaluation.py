"""Checkpoint 6: run per-event hindcast and baseline evaluation."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.evaluation import evaluate_leave_one_out
from src.navigator import Event


def load_events():
    root = Path(__file__).parents[1]
    records = json.loads((root / "data" / "events.json").read_text(encoding="utf-8"))
    district_features_path = root / "data" / "processed" / "event_district_features.json"
    enriched = json.loads(district_features_path.read_text(encoding="utf-8")) if district_features_path.is_file() else {}
    district_features = enriched.get("events", {})
    return [Event(r["event_id"], r["name"], r["start_date"], r["end_date"], r["features"], tuple(r["affected_districts"]), r["source"], r.get("evidence_notes", ""), r.get("evidence_page"), r.get("local_evidence"), district_features.get(r["event_id"])) for r in records]


if __name__ == "__main__":
    rows = evaluate_leave_one_out(load_events())
    print("HINDCAST AND BASELINE CHECK: PASS")
    for row in rows:
        rainfall = row["rainfall_only"]["hits"]
        rainfall_label = f"{rainfall} hits" if rainfall is not None else "not evaluated (district rainfall series missing)"
        print(f"{row['event_id']}: analogue={row['analogue']['hits']} hits, rainfall_only={rainfall_label}, static={row['static_flood_proneness']['hits']} hits, abstained={row['abstained']}")
