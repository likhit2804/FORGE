# Data pipeline inputs

The repository does not include district rainfall time series yet. Place source files here only after obtaining them from the documented provider and retain their original license and attribution.

## Daily district rainfall CSV

UTF-8 CSV with one row per district and local date:

```csv
date,district,rainfall_mm
2023-12-17,Thoothukudi,12.4
2023-12-18,Thoothukudi,950.0
```

The rainfall value must be a documented district-level daily value or a documented district aggregation from stations or a grid. Do not mix station maxima, district means, and gridded estimates in one series. Missing district-days must remain missing; do not fill them with zero. The builder requires complete antecedent windows for at least one district and records the input file's SHA-256.

### IMD gridded rainfall option

IMD Pune documents daily 0.25° gridded rainfall (1901–2024) at <https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html>. After obtaining a yearly NetCDF file, convert it with:

```bash
python -m scripts.download_imd_gridded --start-year 2015 --end-year 2024
python -m scripts.convert_imd_gridded_to_district_csv --input-dir data/raw/imd_gridded
```

The converter averages valid grid-cell-centre rainfall values within each district polygon, writes the standard CSV and a `.metadata.json` sidecar, and records the input SHA-256. This aggregation smooths local extremes and is not interchangeable with the station maxima cited in the existing ten event records. Retain IMD attribution and verify data-use terms on the source page before redistribution. Cite Pai et al. (2014), *MAUSAM*, 65(1), pp. 1–18, for the 0.25° dataset.

## Event-label JSON and review checklist

The curated library currently contains eleven records. Supply a JSON list when preparing additions; each event record must use the following fields. The machine-readable schema is [`../event.schema.json`](../event.schema.json). The provenance validator applies that schema, checks date-window consistency and duplicate IDs/districts, and confirms that verified evidence paths and hashes match repository files. Local source-file byte sizes, hashes, citations, and license-review status are tracked in [`../sources/manifest.json`](../sources/manifest.json).

```json
{
  "event_id": "stable-id",
  "name": "Human-readable event name",
  "start_date": "2023-12-17",
  "end_date": "2023-12-19",
  "affected_districts": ["Thoothukudi", "Tirunelveli"],
  "source": "https://official-source/report.pdf#page=3",
  "local_evidence": "data/sources/report.pdf",
  "evidence_notes": "What the cited report says about this event and districts.",
  "evidence_page": 3,
  "label_status": "verified_source_report",
  "label_confidence": "medium",
  "cyclone_window_verified_clear": true,
  "cyclone_window_evidence": "IMD cyclone records checked for the event window plus buffer; no named cyclone landfall."
}
```

Field rules:

- `event_id` is a stable, unique, non-empty identifier; do not reuse an ID for a different event.
- `start_date` and `end_date` use `YYYY-MM-DD`; `analysis_window` must match both dates.
- `features.intensity_mm` and `features.duration_hours` are required, finite, and non-negative. Optional antecedent/reservoir features must also be finite and non-negative when present. State the measurement method in `feature_method`.
- `affected_districts` is a non-empty list of unique district names. Use the boundary vintage and district spelling appropriate to the evidence, and document any crosswalk for boundary changes.
- `source` is the public HTTP(S) citation. For verified records, `local_evidence` points to the retained source copy under `data/`, with `evidence_page`, `evidence_notes`, a timezone-aware retrieval timestamp, and matching `raw_file_sha256`.
- `label_status` is `verified_source_report`, `verified_satellite_extent`, `verified_government_report`, `pending_review`, or `unverified`. `label_confidence` is `low`, `medium`, or `high`; confidence describes the evidence for the impact label.
- Verified records include cyclone-window screening and its evidence note. A record is not made “verified” by the validator alone; a person must review the report and screening evidence.

Before accepting an event, review:

1. Does the cited source support the dates, locations, and impact statement? Record exact pages or map references.
2. Are affected districts explicitly supported by the source, and are historical district names mapped carefully to the current boundary layer?
3. Is rainfall a station maximum, district aggregate, or gridded estimate? Keep measurement types distinct and explain how each feature was calculated.
4. Is the label confidence appropriate? Satellite products without ground verification and broad narrative reports should retain their uncertainty.
5. Was the event window plus configured buffer checked against cyclone records? Save the screening source and result; do not infer a clear window from the event description alone.
6. Is the original evidence retained, its hash correct, and its redistribution allowed under the source terms?

Validate the default library or a candidate JSON file before replacing `data/events.json`:

```bash
python scripts/validate_events.py
python scripts/validate_events.py --events data/events_built.json
```

`cyclone_window_verified_clear` and its evidence note must be checked against IMD records for the event's rain spell plus the configured buffer. The builder deliberately stops if either is absent or false. `analysis_buffer_days` defaults to two days before and after the event; override only when the project protocol explicitly changes.

The output stores the raw rainfall hash, report hash (from `local_evidence`), event analysis window, cyclone buffer, feature calculation method, and retrieval time. The eleven current event records retain report-derived maxima and impact labels; supplementary district rainfall and 7/30-day antecedent values are stored separately in the generated feature sidecar. Do not conflate the supplementary gridded district estimates with the report observations.

## OpenStreetMap district context

Run `python -m scripts.enrich_district_osm --resume` to query the public Overpass API for Tamil Nadu district road-way, waterway-way, hospital, clinic, shelter, and school counts. The resulting `data/layers/district_osm.json` includes query time, boundary identifier, ODbL attribution, district-level errors, and limitations. Use `--limit 1` for a smoke test and `--resume` to continue partial runs. Road-way density is only an isolation proxy; it is not road length, passability, travel time, or verified service coverage. Waterway counts do not measure river distance or flood extent. Review OSM attribution and ODbL terms before redistributing derived data.

The app can optionally read current storage context from the Government of Tamil Nadu AGRISNET reservoir dashboard. It validates the source report date, shows retrieval/staleness metadata, and labels reservoirs above a user-selected storage percentage as a prototype "buffer concern". This feed has no district association and is excluded from district ranking. The flag is not a flood forecast, dam-release recommendation, or operational control. Source: <https://www.tnagrisnet.tn.gov.in/home/reservoir/>.
