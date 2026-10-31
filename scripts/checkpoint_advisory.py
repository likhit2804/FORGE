"""Checkpoint 5: verify source-backed English and Tamil advisories."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.advisory import build_advisory
from src.navigator import Event, Query, priority_ranking, retrieve


def load_events():
    records = json.loads((Path(__file__).parents[1] / "data" / "events.json").read_text(encoding="utf-8"))
    return [Event(r["event_id"], r["name"], r["start_date"], r["end_date"], r["features"], tuple(r["affected_districts"]), r["source"]) for r in records]


if __name__ == "__main__":
    library = load_events()
    districts = sorted({d for event in library for d in event.affected_districts})
    query = Query({"intensity_mm": 300, "duration_hours": 48, "antecedent_7d_mm": 120, "antecedent_30d_mm": 320}, {d: .7 for d in districts}, {d: .5 for d in districts}, {d: .5 for d in districts}, {d: .5 for d in districts})
    retrieval = retrieve(query, library)
    ranking = priority_ranking(query, retrieval)
    english = build_advisory(ranking, retrieval, "en")
    tamil = build_advisory(ranking, retrieval, "ta")
    assert english["source_tags"]["analogue_events"]
    assert tamil["source_tags"]["official_precedence"]
    print("SOURCE-BACKED ADVISORY CHECK: PASS")
    print(f"confidence={english['confidence']}")
    print(f"top_districts={', '.join(row['district'] for row in ranking[:3])}")
    print("languages=en,ta")
