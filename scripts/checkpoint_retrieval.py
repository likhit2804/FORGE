"""Checkpoint 3: emit a reproducible analogue-retrieval audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.navigator import Event, Query, retrieve


def load_events() -> list[Event]:
    path = Path(__file__).parents[1] / "data" / "events.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    return [Event(r["event_id"], r["name"], r["start_date"], r["end_date"], r["features"], tuple(r["affected_districts"]), r["source"], r.get("evidence_notes", ""), r.get("evidence_page"), r.get("local_evidence")) for r in records]


if __name__ == "__main__":
    library = load_events()
    query = Query(
        features={"intensity_mm": 300.0, "duration_hours": 48.0, "antecedent_7d_mm": 120.0, "antecedent_30d_mm": 320.0},
        forecast_percentile_by_district={d: 0.70 for d in sorted({d for e in library for d in e.affected_districts})},
        exposure_by_district={d: 0.60 for d in sorted({d for e in library for d in e.affected_districts})},
        vulnerability_by_district={d: 0.60 for d in sorted({d for e in library for d in e.affected_districts})},
        isolation_by_district={d: 0.40 for d in sorted({d for e in library for d in e.affected_districts})},
    )
    result = retrieve(query, library, top_k=5)
    print("ANALOGUE RETRIEVAL CHECK: PASS")
    print(f"top_k={len(result['analogues'])}")
    print(f"threshold={result['threshold']:.4f}")
    print(f"abstained={result['abstained']}")
    print(f"out_of_range={result['out_of_range']}")
    for rank, item in enumerate(result["analogues"], 1):
        print(f"{rank}. {item['event'].name} | distance={item['distance']:.4f} | features_used={item['features_used']}")
