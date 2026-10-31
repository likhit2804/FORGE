# Phase 6: pilot readiness and operational checks

## Current readiness

The application now exposes a local-data health check, request IDs and duration
logs, static-layer age metadata, live forecast retrieval times, reservoir report
age, and a manual-scenario recovery action after live forecast failures. Partial
district forecast responses fail closed: the API does not produce a ranking
from incomplete live coverage.

This is not a declaration of pilot approval. No intended-user accessibility,
map-usability, or Tamil-language review has been conducted, and no limited pilot
feedback has been collected. Keep the application labelled as a prototype and
do not use its ranking as an official warning, dispatch instruction, flood-depth
prediction, or dam-release recommendation.

## Operator smoke checks

Run these checks in a configured environment after installing the dependencies
listed in `README.md`:

```powershell
python -m pytest -q
python scripts/validate_events.py
npm --prefix web run build
python -m uvicorn api:app --reload
```

In another terminal, check `GET /api/health`. A healthy response means the
required local event, boundary, and hazard-assessment files exist; it does not
mean a live external source is reachable. Each response includes an
`X-Request-ID`; correlate that value with the API request log when diagnosing a
failure. Do not log credentials or full user-provided query strings.

Exercise these cases before any pilot:

1. Stop the API and confirm the interface presents a readable unavailable
   state, then restart it and confirm bootstrap recovers.
2. Temporarily make a required local data file unavailable in a disposable test
   fixture and confirm `/api/health` reports `degraded`; restore it and confirm
   the status returns to `ok`.
3. Simulate provider timeout, a missing district centroid, and partial provider
   coverage. Confirm live mode fails closed with no new ranking and offers
   retry/manual-scenario recovery. If an earlier ranking is retained, confirm it
   is visibly marked as stale and not for the current attempt.
4. Return an older reservoir report and confirm its report date and age are
   visible. Make the feed unavailable and confirm the ranking remains usable
   without reservoir context, with the failure disclosed.
5. Check the feature-audit snapshot ages. These are static reference-layer
   retrieval dates, not freshness guarantees or live-feed status.
6. Resolve the unrecorded elevation and population layer licence/attribution
   terms before redistributing the app or beginning an operational pilot.

Do not alter or delete production input files to simulate failures; inject
failures in tests or use a disposable copy.

## Intended-user review and limited pilot

Before the first pilot, recruit a small group of Tamil Nadu preparedness users
and Tamil readers, and have them complete tasks without coaching:

- Find the top-ranked districts and explain the evidence and uncertainty.
- Find the source, retrieval time, and staleness of each relevant input.
- Recover from unavailable live forecasts by switching to manual input.
- Use the district map and tables with keyboard-only navigation and a screen
  reader; verify focus visibility, contrast, zoom behavior, and narrow-screen
  layout.
- Read the Tamil advisory and explain whether it is a preparedness aid or an
  official warning.

Record role (not unnecessary personal details), task outcome, confusion points,
accessibility barriers, Tamil wording corrections, and severity. Fix critical
misunderstandings before expanding the pilot. Obtain appropriate organizational
approval before using operational or sensitive data. Never solicit or imply
that participants should rely on this prototype during an active emergency.
