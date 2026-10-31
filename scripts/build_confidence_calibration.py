"""Build a gated spread-versus-error diagnostic from archived forecast scores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.confidence_calibration import build_spread_error_diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True,
                        help="JSON output from scripts/evaluate_archived_forecasts.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-events", type=int, default=10)
    parser.add_argument("--minimum-samples", type=int, default=100)
    parser.add_argument("--bins", type=int, default=5)
    args = parser.parse_args()

    result = build_spread_error_diagnostics(
        args.evaluation, minimum_events=args.minimum_events,
        minimum_samples=args.minimum_samples, bins=args.bins)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Status: {result['status']}")
    print(f"Centre/lead strata: {len(result['strata'])}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
