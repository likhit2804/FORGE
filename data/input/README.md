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

The converter averages valid grid-cell-centre rainfall values within each district polygon, writes the standard CSV and a `.metadata.json` sidecar, and records the input SHA-256. This aggregation smooths local extremes and is not interchangeable with the station maxima cited in the existing eight event records. Retain IMD attribution and verify data-use terms on the source page before redistribution. Cite Pai et al. (2014), *MAUSAM*, 65(1), pp. 1–18, for the 0.25° dataset.

## Event-label JSON

Supply a JSON list. Each record must include:

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

`cyclone_window_verified_clear` and its evidence note must be checked against IMD records for the event's rain spell plus the configured buffer. The builder deliberately stops if either is absent or false. `analysis_buffer_days` defaults to two days before and after the event; override only when the project protocol explicitly changes.

The output stores the raw rainfall hash, report hash (from `local_evidence`), event analysis window, cyclone buffer, feature calculation method, and retrieval time. The eight event records retain report-derived maxima and impact labels; supplementary district rainfall and 7/30-day antecedent values are stored separately in the generated feature sidecar. Do not conflate the supplementary gridded district estimates with the report observations.

## OpenStreetMap district context

Run `python -m scripts.enrich_district_osm --resume` to query the public Overpass API for Tamil Nadu district road-way, waterway-way, hospital, clinic, shelter, and school counts. The resulting `data/layers/district_osm.json` includes query time, boundary identifier, ODbL attribution, district-level errors, and limitations. Use `--limit 1` for a smoke test and `--resume` to continue partial runs. Road-way density is only an isolation proxy; it is not road length, passability, travel time, or verified service coverage. Waterway counts do not measure river distance or flood extent. Review OSM attribution and ODbL terms before redistributing derived data.

The app can optionally read current storage context from the Government of Tamil Nadu AGRISNET reservoir dashboard. It validates the source report date, shows retrieval/staleness metadata, and labels reservoirs above a user-selected storage percentage as a prototype "buffer concern". This feed has no district association and is excluded from district ranking. The flag is not a flood forecast, dam-release recommendation, or operational control. Source: <https://www.tnagrisnet.tn.gov.in/home/reservoir/>.
