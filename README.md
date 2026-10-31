# Monsoon Impact Navigator

An explainable, case-based retrieval prototype for rainfall-driven relief-preparation priorities in Tamil Nadu.

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
pip install -e ".[geo,rainfall]"
npm --prefix web install
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

Run tests:

```bash
pytest
```

## Important data note

`data/events.json` contains ten curated records linked to official IMD, CWC, or NRSC/ISRO evidence. The August 2019 Nilgiris record is based on the CWC flood situation report; it is a deep-depression-associated rainfall event, not a named-cyclone event. The November 2021 North Tamil Nadu record uses preliminary ALOS-2 satellite inundation mapping, explicitly marked medium confidence because NRSC reports no ground verification. Report-derived maxima and affected-district labels are traceable to local source copies and hashes. Supplementary district rainfall and antecedent features are reproducibly derived from the IMD grid; they do not replace report-derived event maxima or impact labels. Report labels remain imperfect ground truth and are not flood polygons.

Archived operational forecast inputs are not yet downloaded. The TIGGE access/licensing constraint and a retrieval/validation protocol are documented in [`data/input/forecast_archive.md`](data/input/forecast_archive.md); current hindcasts use observed event rainfall and must not be presented as forecast skill.

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

The application does not predict exact flood depth, dispatch relief, route vehicles, or control reservoirs. WorldPop population, representative-point elevation, and OSM road/facility proxies prefill district context, with OSM coverage limitations shown. Live AGRISNET reservoir storage is optional context only: the source has no district association, and threshold flags are not flood warnings, release guidance, or controls. River proximity, cropland exposure, and travel-time/passability remain unmodelled. Forecast quantiles are live ensemble spreads, but forecast-error calibration is still needed before interpreting them as calibrated probabilities. The event library currently contains ten source-verified events, still below the 10–20-event target; report-based affected-district labels are uneven, and both hindcasts use observed rainfall from the held-out event rather than archived operational forecasts. Historical grids use contemporary 2021 district boundaries, so labels from before district splits require careful geographic crosswalk review.
