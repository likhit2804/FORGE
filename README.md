# Monsoon Impact Navigator

An explainable, case-based retrieval prototype for rainfall-driven relief-preparation priorities in Tamil Nadu.

## Requirements

- Python 3.11 (see [`.python-version`](.python-version)).
- Node.js 22.14.0 and npm (see [`.nvmrc`](.nvmrc)).
- Git.

## Run locally

Create and activate a virtual environment, then install the project and its optional geospatial/rainfall dependencies plus the test tools:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[geo,rainfall]" -r requirements.txt
npm --prefix web ci
```

For local development, run the API and React client in two terminals:

```bash
python -m uvicorn api:app --reload
npm --prefix web run dev
```

Open <http://127.0.0.1:5173>. The Vite development server proxies `/api` requests to FastAPI on port 8000. To serve the production React build from FastAPI instead:

```bash
npm --prefix web run build
python -m uvicorn api:app
```

The project also includes `pyproject.toml` for standard Python tooling. Set `IMD_API_KEY` only when IMD API access requires credentials; do not commit secrets.

GitHub Actions runs the provenance gate, test suite, and Python compilation on every push and pull request.

Run the backend tests and provenance check, then build the frontend:

```bash
python -m pytest -q
python scripts/validate_events.py
npm --prefix web run build
```

CI runs these checks on pushes and pull requests. Use the versions in `.python-version` and `.nvmrc` for consistent local results.

## Important data note

`data/events.json` contains eleven curated records linked to official IMD, CWC, or NRSC/ISRO evidence. Each verified record is checked against its local source copy and SHA-256 by `python scripts/validate_events.py`. The December 2010 Kanyakumari case documents depression-associated rainfall, with the observed station maximum clearly distinguished from the affected-district label. The August 2019 Nilgiris record is based on the CWC flood situation report; it is a deep-depression-associated rainfall event, not a named-cyclone event. The November 2021 North Tamil Nadu record uses preliminary ALOS-2 satellite inundation mapping, explicitly marked medium confidence because NRSC reports no ground verification. Report-derived maxima and affected-district labels are traceable to local source copies and hashes. Supplementary district rainfall and antecedent features are reproducibly derived from the IMD grid; they do not replace report-derived event maxima or impact labels. Report labels remain imperfect ground truth and are not flood polygons. The retained source files total about 76 MB; their sizes, hashes, citations, and rights-review status are in [`data/sources/manifest.json`](data/sources/manifest.json). See [`data/input/README.md`](data/input/README.md) for the schema and review requirements and [`data/event_inventory.md`](data/event_inventory.md) for current coverage and gaps.

Regenerate the district feature source/coverage audit with `python -m scripts.assess_hazard_exposure --output data/layers/hazard_exposure_assessment.json`. It records per-layer file hashes, source metadata, boundary coverage, proxy limitations, and candidate signals not yet available. This is a data-quality inventory, not evidence that the active population/elevation/OSM ranking proxies improve independent event evaluation. See [`data/layers/README.md`](data/layers/README.md).

Archived operational forecasts are not yet downloaded, so forecast validation remains pending. Phase 3 now has a separate evaluator that requires pre-event archived runs, exact observation windows, original files with verified SHA-256 values, and recorded licences. Its input contract and current ECMWF TIGGE/ECDS retrieval protocol are in [`data/input/forecast_archive.md`](data/input/forecast_archive.md). To run it after preparing those inputs:

```bash
python scripts/evaluate_archived_forecasts.py --forecasts data/processed/archived_forecasts.csv --observations data/processed/imd_district_daily_rainfall_2015_2024.csv --output data/processed/archived_forecast_evaluation.json
```

The evaluator reports by centre and lead and keeps archived-forecast scores distinct from retrospective reconstructions. It will not mark a skill claim threshold as met until at least five eligible events are present. TIGGE data discovery is through the [ECMWF Data Store](https://ecds.ecmwf.int/datasets/tigge-forecasts); current ECDS instructions require an account and API token, and licences must be checked per selected contribution. The broader improvement roadmap is in [`PROJECT_PLAN.md`](PROJECT_PLAN.md).

Phase 6 operational smoke checks, outage/recovery cases, freshness semantics, and the intended-user pilot checklist are documented in [`docs/PILOT_READINESS.md`](docs/PILOT_READINESS.md). The health endpoint checks required local file presence only; it does not certify external-feed availability or operational readiness.

Confidence calibration is also pending until archived forecast errors are available. The app caps heuristic confidence at Medium and shows why a ranking is downgraded or treated as exploratory. Once Phase 3 has usable archive results, build a spread-versus-error diagnostic with:

```bash
python scripts/build_confidence_calibration.py --evaluation data/processed/archived_forecast_evaluation.json --output data/processed/confidence_calibration_candidate.json
```

The default gate is ten distinct events and 100 district-run samples for each forecast-centre/lead stratum. Passing it only produces a candidate for independent review and out-of-sample validation; it does not make ensemble spread a probability or enable High confidence.

## Full data workflow

1. Fetch versioned district boundaries from geoBoundaries gbOpen. The script keeps source attribution, license, retrieval time, and a file hash in the sidecar manifest:

   ```bash
   python -m scripts.fetch_district_boundaries
   ```

2. Download ten completed annual files from IMD Pune (2015–2024; the source page describes daily records from 1901–2024), then convert them to district-day means using district polygon grid-cell centres:

   ```bash
   python -m scripts.download_imd_gridded
   python -m scripts.convert_imd_gridded_to_district_csv --input-dir data/raw/imd_gridded
   ```

   The downloader verifies NetCDF signatures, writes SHA-256 checksums to a manifest, and stores raw files in a Git-ignored folder. The converter writes a district-day CSV in `data/processed/` and a metadata sidecar. Its values are 0.25° grid-derived district means, not station maxima; do not mix them with report maxima in the same feature series.

   Supplement the report-based event library with district-specific rainfall features, keeping report labels and station maxima unchanged:

   ```bash
   python -m scripts.enrich_event_district_features --rainfall-csv data/processed/imd_district_daily_rainfall_2015_2024.csv --source-metadata data/processed/imd_district_daily_rainfall_2015_2024.csv.metadata.json
   ```

   The app loads this generated sidecar when present and uses it for district-specific analogue matching. Sub-day duration is omitted because daily grids cannot support it.

   Then prepare event-label JSON following the schema in `data/input/README.md`. The builder refuses to compute features unless each event's cyclone-window exclusion was verified:

   ```bash
   python -m scripts.build_event_library --rainfall-csv data/input/daily_district_rainfall.csv --labels-json data/input/event_labels.json --rainfall-source-url SOURCE_URL --output data/events_built.json
   ```

   Validate a candidate event file before replacing the curated library:

   ```bash
   python scripts/validate_events.py --events data/events_built.json
   ```

3. To calculate population totals using WorldPop Global 2 and the downloaded district polygons:

   ```bash
   python -m scripts.enrich_district_population
   ```

   This writes source and retrieval metadata, year, resolution, each task result, and any per-district failures. It does not overwrite the event library.

4. To download per-district representative-point elevation samples:

   ```bash
   python -m scripts.enrich_district_terrain
   ```

5. Create same-month climatology distributions from the ten-year series:

   ```bash
   python -m scripts.build_rainfall_climatology --rainfall-csv data/processed/imd_district_daily_rainfall_2015_2024.csv --source-url https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html --source-metadata data/processed/imd_district_daily_rainfall_2015_2024.csv.metadata.json
   ```

Only replace `data/events.json` after checking the generated records and their provenance. Keep all source files and licenses with derived data.

## Implemented MVP logic

- Rank-normalised feature distance.
- Top-three-to-five historical analogue retrieval.
- 90th-percentile leave-one-out threshold.
- Out-of-range detection for rainfall intensity and duration.
- Similarity-weighted analogue hazard, per-run priority weights, and an alternative-weight sensitivity table.
- Transparent priority score.
- Confidence and abstention signals.
- Source visibility in the UI.
- Analogue-support counts in district rankings and input validation for invalid rainfall values.
- A live Open-Meteo precipitation adapter with timestamped provenance and graceful network errors.
- React live-ensemble/manual mode switch with visible forecast provenance, editable district context, map, ranking, and audit exports.
- Low/central/high scenario ranking and district stability flags in the UI; scenario spread is visibly identified as provisional until calibrated hindcast errors are supplied.
- Source-backed Tamil and English advisories with expandable provenance tags.
- An event-library inspector exposing report links, label confidence, affected districts, and cyclone-window screening evidence for each curated case.
- Downloadable audit JSON and district-priority CSV outputs.
- A live OpenStreetMap Overpass adapter for auditable pilot-area road and facility counts; district-level accessibility is not inferred from that pilot box.
- A source-attributed 38-district OSM enrichment layer for road, waterway, hospital, clinic, shelter, and school mapping proxies; the UI distinguishes mapped waterway density from actual river proximity.
- An optional read-only AGRISNET reservoir dashboard adapter, stale-date checks, and adjustable storage-threshold context flags; reservoir data does not change district scores or imply operational advice.
- Downloaded district-boundary polygons and representative-point elevation samples with source metadata.
- A traceable event builder for IMD or other daily district rainfall tables; it computes event maximum, 7/30-day antecedent rainfall, records hashes, and requires a verified cyclone exclusion.
- A geoBoundaries district-boundary downloader with license/attribution manifest and SHA-256.
- A WorldPop Global 2 polygon population enrichment pipeline with retrieval and per-district error records.
- FastAPI endpoints for bootstrap metadata, analysis, leave-one-event-out evaluation, and a past-events-only chronological hindcast with explicit cold-start skips.
- In-app comparison against rainfall-only and static historical flood-proneness baselines.
- A district-polygon priority map and ranking across all 38 available Tamil Nadu ADM2 polygons; polygons and markers are not flood extents.
- Open-Meteo ensemble 24-hour rainfall quantiles by district centroid, with per-district analogue retrieval enriched by IMD gridded event rainfall. The optional IMD categorical forecast is displayed as context; categories are never converted into fabricated millimetres.

The application does not predict exact flood depth, dispatch relief, route vehicles, or control reservoirs. WorldPop population, representative-point elevation, and OSM road/facility proxies prefill district context, with OSM coverage limitations shown. Live AGRISNET reservoir storage is optional context only: the source has no district association, and threshold flags are not flood warnings, release guidance, or controls. River proximity, cropland exposure, and travel-time/passability remain unmodelled. Forecast quantiles are live ensemble spreads, but forecast-error calibration is still needed before interpreting them as calibrated probabilities. The event library currently contains eleven source-verified events, still below the 20-event expansion target; report-based affected-district labels are uneven, and both hindcasts use observed rainfall from the held-out event rather than archived operational forecasts. Historical grids use contemporary 2021 district boundaries, so labels from before district splits require careful geographic crosswalk review.
