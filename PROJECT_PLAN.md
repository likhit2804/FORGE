# Monsoon Impact Navigator improvement plan

## Goal

Make the prototype reproducible, build a trustworthy and traceable event library, and then evaluate whether live forecasts support useful district prioritisation. The app is a decision-support prototype; it must not imply operational flood warnings or relief dispatch capability.

## Phase 1 — Reproducible project setup

### Work

- Declare the supported Python and Node.js versions in repository-level version files and use those versions in CI.
- Document setup, local development, production build, data validation, and test commands for Windows and macOS/Linux.
- Use the committed npm lockfile with `npm ci`; document one Python install path that installs the application and its development checks.
- Extend CI to install the frontend dependencies from the lockfile and build the frontend, in addition to Python provenance checks, tests, and compilation.
- Document optional network integrations, environment variables, large input data, generated files, attribution, and licensing expectations.
- Keep caches, virtual environments, raw downloads, and build output out of Git. Keep only source files and curated/generated assets required to run the app or reproduce the included results.

### Completion criteria

- A clean checkout can be installed by following the README without machine-specific paths.
- Python and frontend checks run in CI using the declared runtimes.
- Every required input is either committed with provenance or described with a reproducible retrieval/generation command.

## Phase 2 — Event library quality and provenance

### Current status

The schema, provenance validator, source manifest, and inventory are in place,
but the library has 11 events and the plan's expansion target of at least 20 is
not met. Treat this phase as incomplete; do not fill the gap with unverified
records.

### Work

- Define and document one schema for event records, including stable ID, event window, features, affected districts, label status and confidence, public source, local evidence, retrieval time, evidence notes/page, source hash, and cyclone-window screening.
- Strengthen the provenance validator to report malformed records clearly and check types, duplicate IDs/districts, date-window consistency, supported confidence/status values, valid URLs, evidence paths, and SHA-256 values.
- Check all eleven current events against the schema and source files; correct documentation that disagrees about event counts.
- Document a review checklist for adding or changing an event: source quality, dates, district boundary vintage/crosswalk, rainfall measurement type, label confidence, cyclone screening, and evidence hashes.
- Preserve uncertainty in report-derived labels; do not present them as precise flood polygons or complete ground truth.
- Track source byte sizes, SHA-256 values, citations, attribution, and rights-review status in a checked source manifest.
- Add automated validator tests for malformed event records, duplicate IDs/districts, date-window mismatches, evidence hashes, and source-manifest integrity.
- Expand the library toward at least 20 source-verified events, prioritising events with consistent reports, district coverage, and matching rainfall data. Track progress and gaps in a manifest or inventory.

### Completion criteria

- The full event library passes the provenance gate and every verified label can be traced to a local source copy and public citation.
- New records have a written review procedure and reproducible validation.
- Dataset documentation and the actual event count agree; evidence gaps and low-confidence records remain explicit.

## Phase 3 — Historical forecast-skill evaluation

### Current status

- Implemented a standalone archived-forecast evaluator with strict run/observation matching, source-file SHA-256 and licence checks, event/centre/lead reporting, and an explicit five-event claim gate (`src/forecast_evaluation.py`, `scripts/evaluate_archived_forecasts.py`).
- Documented the forecast CSV contract and retrieval workflow in `data/input/forecast_archive.md`.
- Historical TIGGE retrieval and availability checks are not complete; no forecast-skill claim is currently supported. The ECDS account/token and archive selection remain external prerequisites.

### Work

- Retrieve archived operational forecasts for historical event windows, subject to access terms and licensing.
- Store forecast provenance by event, initialization time, centre, lead time, and source file hash.
- Pair forecast inputs with matching observations and event labels; exclude forecasts issued after the event start.
- Keep the observed-rainfall reconstruction as a separate diagnostic and prevent it from being reported as forecast skill.
- Compare against climatology and simple rainfall-only baselines; report results per event and lead time with sample sizes and uncertainty.
- Set a minimum evidence threshold before making forecast-accuracy claims; the current archive checkpoint proposes at least five eligible held-out events.

### Completion criteria

- Evaluation can be reproduced from versioned inputs and cannot silently substitute observations for missing forecast archives.
- Forecast skill and retrospective reconstruction are reported separately, with limitations and sample sizes visible.

## Phase 4 — Confidence calibration and abstention

### Current status

- Confidence is capped at Medium until empirical error calibration exists; low confidence and explicit ranking-status reasons remain available for abstention, missing features, out-of-range inputs, high spread heuristics, and scenario-sensitive rankings.
- Phase 3 run reports now retain district-level ensemble spread and absolute-error diagnostics. `scripts/build_confidence_calibration.py` bins these by forecast centre and lead, with a default readiness gate of 10 distinct events and 100 district-run samples per stratum.
- No archived forecast sample exists yet, so calibration remains pending. A diagnostic stratum marked ready is only a candidate for independent review and out-of-sample validation; it does not activate calibrated probabilities or High confidence.

### Work

- Measure forecast ensemble spread against archived forecast errors.
- Calibrate probabilities only after enough suitable cases are available.
- Evaluate confidence and abstention for missing, conflicting, and out-of-range inputs.
- Expose the evidence that drives each ranking and confidence label.

### Completion criteria

- Confidence labels have documented empirical support and the app communicates weak evidence clearly.

## Phase 5 — Hazard and exposure coverage

### Current status

- Added a reproducible source/coverage/limitations assessment at `scripts/assess_hazard_exposure.py` and a committed snapshot at `data/layers/hazard_exposure_assessment.json`; the API exposes it in the UI's data-quality panel.
- Current coverage audit: elevation, population, and OSM layers each cover 38/38 boundary districts; daily rainfall has 138,814 rows, 2015–2024 coverage, all 38 districts, and no invalid/negative values; OSM has no recorded query failures. This checks table coverage, not feature completeness or accuracy.
- River proximity, drainage, repeated observed inundation, road passability/travel time, and cropland exposure remain unavailable. Existing population, elevation, and OSM proxies still affect ranking but have not passed independent event-holdout ablation; no new signal has been added.
- Elevation and population source licences are not recorded in their layer metadata; resolve source terms and attribution before redistribution or operational pilot use.
- Phase 5 is not complete until layer value is independently assessed and unsupported proxies are either validated or excluded from ranking.

### Work

- Assess data quality and potential value for river proximity, drainage, observed inundation, road connectivity/passability, and cropland exposure.
- Add signals incrementally, retaining source dates, spatial resolution, licensing, and uncertainty.
- Test whether each new signal improves independent evaluation before it affects district ranking.
- Keep proxies within their evidential limits; for example, mapped road counts do not establish passability or travel time.

### Completion criteria

- Every ranking input has a traceable source, defined meaning, known limitations, and evidence of added value.

## Phase 6 — Pilot readiness

### Status (2026-10-31)

In progress. Local health checks, request IDs and duration logs, static and live
data-freshness visibility, live-source recovery affordances, and fail-closed
partial-coverage handling have been implemented with regression tests. A
repeatable readiness checklist is in [`docs/PILOT_READINESS.md`](docs/PILOT_READINESS.md).
Accessibility, map usability, and Tamil output still need intended-user review;
a limited pilot and feedback collection have not yet happened.

### Work

- Exercise live-data outages, stale inputs, partial district coverage, and recovery behavior.
- Add useful operational logs and data-freshness visibility.
- Review accessibility, map usability, and Tamil-language output with intended users.
- Pilot with a small group and record feedback before broadening use.
- Keep the prototype scope and official-warning guidance visible.

### Completion criteria

- Pilot users can understand the evidence, ranking, confidence, and limitations, including when live sources are unavailable.

## Recommended execution order

Complete phases 1 and 2 before relying on evaluation results. Then establish archived forecast skill (phase 3), calibrate confidence (phase 4), add and validate further hazard signals (phase 5), and prepare a limited pilot (phase 6).
