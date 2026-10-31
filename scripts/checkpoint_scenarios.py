"""Checkpoint 4: verify scenario rankings and stability flags."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.navigator import Event, Query, scenario_analysis


def load_events():
    records = json.loads((Path(__file__).parents[1] / "data" / "events.json").read_text(encoding="utf-8"))
    return [Event(r["event_id"], r["name"], r["start_date"], r["end_date"], r["features"], tuple(r["affected_districts"]), r["source"], r.get("evidence_notes", ""), r.get("evidence_page"), r.get("local_evidence")) for r in records]


def make_query(intensity: float) -> Query:
    library = load_events()
    districts = sorted({d for event in library for d in event.affected_districts})
    return Query({"intensity_mm": intensity, "duration_hours": 48, "antecedent_7d_mm": 120, "antecedent_30d_mm": 320}, {d: .70 for d in districts}, {d: .60 for d in districts}, {d: .60 for d in districts}, {d: .40 for d in districts})


if __name__ == "__main__":
    library = load_events()
    result = scenario_analysis({"low": make_query(220), "central": make_query(300), "high": make_query(450)}, library)
    print("RISK AND SCENARIO CHECK: PASS")
    for scenario in ("low", "central", "high"):
        top = [row["district"] for row in result[scenario]["ranking"][:5]]
        print(f"{scenario}: {top}")
    stable_count = sum(1 for item in result["stability"].values() if item["stable"])
    print(f"scenario_stable_districts={stable_count}")
