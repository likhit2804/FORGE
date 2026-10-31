"""Run the forecast-only historical evaluation from auditable CSV inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.forecast_evaluation import evaluate_archived_forecasts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecasts", type=Path, required=True,
                        help="district/member forecast CSV with source-file hashes")
    parser.add_argument("--observations", type=Path, required=True,
                        help="daily observed rainfall CSV: date,district,rainfall_mm")
    parser.add_argument("--events", type=Path, default=Path("data/events.json"),
                        help="event labels JSON (default: data/events.json)")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True,
                        help="path for the JSON report")
    args = parser.parse_args()

    report = evaluate_archived_forecasts(args.forecasts, args.observations,
                                         args.events, top_k=args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Status: {report['status']}")
    print(f"Eligible events: {report['eligible_event_count']}/{report['minimum_eligible_events_for_skill_claim']}")
    print(f"Forecast runs: {report['forecast_run_count']}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
