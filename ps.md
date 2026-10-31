# Monsoon Impact Navigator

## Problem

Monsoon Impact Navigator is an explainable decision-support system for rainfall-driven flooding in Tamil Nadu. It converts a rainfall forecast into district-level relief-preparation priorities by comparing the forecast with a curated library of historical rainfall events.

Existing systems may forecast rainfall or flood depth, but field officers still need to know which districts should receive preparation and relief attention first.

## Track 2 Alignment

- **Predictive Climate & Micro-Location Engine:** partial match through location-specific, district-level rainfall impact analysis; micro-location analysis is a future phase.
- **Emergency Response & Logistics:** prioritisation of areas for relief preparation; the system does not dispatch or route supplies.
- **Extreme Weather Resilience:** rainfall-driven flood preparedness.
- **Regional-Language Access:** Tamil and English advisories.

## Ground-Truth Event Library

The prototype will use approximately 10–20 clearly labelled rainfall events. Each event will contain:

- observed rainfall from IMD gridded data, IMERG, or ERA5;
- affected districts from SDMA or NDMA reports;
- Sentinel-1 flood extent where available;
- verified government or news reports;
- reservoir storage only when reliable public data exists.

Each affected-district label records its source so that the ground truth is traceable.

The MVP focuses on rainfall-driven flooding. An event is included only when there is no named cyclone landfall during the event's observed rain spell plus a fixed analysis buffer. Events dominated by storm surge or cyclone wind are excluded. Event dates and the buffer are verified against IMD records.

## Forecast Uncertainty

Historical events use observed rainfall, while the current query uses forecast rainfall. The system explicitly shows this difference and evaluates three scenarios derived from forecast uncertainty: low, central, and high rainfall. Where ensemble forecasts are available, these use lower-quantile, median, and upper-quantile ensemble members. Otherwise, they use calibrated forecast-error percentiles estimated from historical hindcasts.

```text
Low rainfall forecast
Central rainfall forecast
High rainfall forecast
```

Confidence decreases when forecast uncertainty is high. As a default, high spread means the high-to-low rainfall range is greater than 75% of the central-scenario rainfall, using a minimum 1 mm denominator for dry cases. These prototype thresholds will be frozen in the project configuration before the leave-one-out evaluation. If the central forecast indicates no significant rainfall, the system reports a dry/no-significant-rainfall condition instead of running flood retrieval.

## Historical Analogue Retrieval

The system compares the current forecast with past events using:

- rainfall intensity;
- rainfall duration;
- 7-day antecedent rainfall;
- 30-day antecedent rainfall;
- affected-area footprint;
- reservoir storage, when available.

If features are missing, the similarity score is normalised by the number of available features. The interface displays the features used and applies a confidence penalty.

The system retrieves the top three to five analogues. Features are rank-normalised per variable, with scaling calculated without the held-out event during evaluation. A close analogue is defined by the best-match distance being at or below the 90th percentile of best-match distances from leave-one-event-out testing. This is a coarse threshold for a small library: approximately one in ten library events may abstain by construction. The system reports which events abstained and why, and recalculates the threshold as the library grows. A genuinely novel query is judged against this library-internal yardstick. A single close match can produce a provisional result, but confidence is reduced when fewer than three analogues support the same district impact.

If a key feature falls outside the library's min–max range, the query is flagged out-of-range and receives Low confidence even if its rank-based distance appears close. Key features are rainfall intensity and duration. During leave-one-out testing, the range is recomputed without the held-out event; the heaviest held-out event may therefore be honestly flagged out-of-range, and this is reported.

The central forecast scenario determines the primary ranking. The low and high scenarios are also ranked. A district that remains in the top five across all three scenarios is marked scenario-stable. A district that drops out of the top five in any one scenario is marked scenario-sensitive and overall confidence is lowered.

If no close analogue exists, the system abstains:

> No sufficiently similar historical event found. Low-confidence assessment.

The system still displays the calculated partial ranking beneath the message, but marks it as low-confidence and unsuitable as a standalone operational recommendation.

## Hazard and Priority Score

Hazard connects analogue retrieval to the priority score. For each district, hazard is the similarity-weighted share of the top-k historical analogues in which that district was affected, blended with the district's forecast rainfall percentile:

```text
hazard = 0.60 × similarity-weighted analogue impact
       + 0.40 × forecast rainfall percentile
```

The analogue component estimates where similar events caused recorded impacts, while the forecast percentile reflects where rainfall is occurring now. The forecast percentile is calculated against each district's own historical rainfall climatology for the same calendar period. This intentionally combines historical impact location with current-event intensity; the 0.60/0.40 split is an expert default included in sensitivity analysis.

Because the top-k library is small, the analogue-impact term is deliberately coarse. The forecast-percentile term provides finer ordering within districts with similar analogue support.

The other score inputs are defined as follows:

- **Exposure:** low elevation, river or water-body proximity, and cropland share.
- **Vulnerability:** population and critical facilities such as hospitals and shelters.
- **Isolation:** low road density, limited connectivity, or estimated travel difficulty.

Exposure and isolation are checked using Spearman rank correlation. If the absolute correlation exceeds 0.70, one is merged or down-weighted. Road-density isolation can also be higher in rural districts with lower population, so it is kept separate from vulnerability and interpreted cautiously.

The default expert-set priority score is:

```text
Priority =
0.40 × hazard
+ 0.25 × exposure
+ 0.20 × vulnerability
+ 0.15 × isolation
```

The weights are not claimed to be learned. Rank-percentile normalisation is used, and a sensitivity view shows how rankings change when weights are adjusted.

Reservoir storage is used in two ways: as an optional similarity feature when historical data exists, and as a separate buffer-concern flag when current storage exceeds a documented threshold. The system does not forecast inflow or control gates.

Confidence is shown as a three-level label. More than 30% of required features missing is the default threshold for substantial missing data. Each district receives its own confidence and scenario flag; the overall run label is the worst confidence among the five highest-priority districts:

- **High:** close analogues, at least three supporting events, complete key features, and scenario-stable ranking.
- **Medium:** a usable analogue exists, but some features are missing, fewer than three events support the result, or scenario rankings vary without the district dropping out of the top five.
- **Low:** no close analogue, high forecast spread, more than 30% of required features missing, an out-of-range key feature, or scenario-sensitive ranking. The partial ranking remains visible but is not an operational recommendation.

Population estimates use Census 2011 or another clearly identified public proxy, and this limitation is shown in the dashboard.

The MVP operates at district level. Taluk- and block-level analysis is the next phase because flooding is often highly localised.

## AI and Advisory Layer

The core AI method is case-based historical analogue retrieval. The AI retrieves similar historical events and explains the structured results. All numerical scores and district rankings are calculated by the application. A constrained language model generates Tamil and English advisories only from those verified outputs.

Every advisory statement carries a source tag, such as an IMD forecast, analogue event, reservoir bulletin, terrain layer, or population dataset.

Official IMD and district-administration warnings always take precedence.

## Prototype Workflow

```text
Rainfall forecast
        ↓
Historical analogue retrieval
        ↓
Terrain and exposure analysis
        ↓
Transparent priority ranking
        ↓
Tamil/English advisory
        ↓
Confidence or abstention
```

## Evaluation Plan

- Leave-one-event-out retrieval testing, with results reported per event because the library is small.
- Recompute normalisation, percentiles, and distance thresholds without the held-out event to prevent evaluation leakage. Ground truth reflects officially recorded impacts, which may be uneven across districts.
- Comparison against a rainfall-only ranking baseline.
- Comparison against a static historical flood-proneness ranking baseline.
- Precision and recall for the top-priority districts.
- Abstention testing for unusual events, using the 90th percentile of the leave-one-out distance distribution rather than a threshold tuned on demo events.
- Sensitivity analysis for priority-score weights.
- Human review of Tamil advisories.

## Limitations

- The event library is a curated prototype dataset, not a complete historical record.
- Forecasts and observed rainfall have different uncertainties.
- Reservoir data may be missing or periodic.
- Population data may rely on Census 2011.
- District-level analysis does not capture every local flood.
- The system provides preparation guidance, not guaranteed flood prediction or dam-control commands.

## Final Pitch

> **Monsoon Impact Navigator is a prototype that compares rainfall forecasts with a curated library of verified Tamil Nadu rainfall events and produces transparent district-level relief-preparation priorities. It accounts for forecast uncertainty, missing data, and unusual events, and abstains when no reliable historical analogue exists.**

## Required Datasets

### Minimum viable dataset stack

| Purpose | Dataset/source | Use in the prototype |
|---|---|---|
| Live district forecast and warnings | [IMD API](https://api.imd.gov.in/public/api_reference.html) | Current rainfall forecast, district rainfall, warnings, and basin QPF |
| Historical rainfall | IMD rainfall products; [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) as a consistent fallback | Event rainfall, intensity, duration, and 7/30-day antecedent rainfall |
| Flood-event verification | SDMA/NDMA reports and official district reports | Affected-district labels and source traceability |
| Flood extent | [Copernicus Sentinel-1](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-1) or Copernicus Global Flood Monitoring | Observed flood extent where cloud-free optical imagery is unavailable |
| Terrain and exposure | [USGS SRTM](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission) | Elevation, low-lying areas, and river/water-body proximity |
| Roads and facilities | OpenStreetMap via Overpass or Geofabrik extracts | Road density, hospitals, shelters, and accessibility proxies |
| Population and vulnerability | Census 2011 or WorldPop | Population and vulnerability proxy, clearly labelled by vintage |
| Reservoir context | CWC reservoir bulletins or India-WRIS where available | Storage percentage and buffer-concern flag; never used as invented live telemetry |

The event library must be generated from these real sources. It must not contain synthetic, manually invented, or placeholder values. Each event record stores its source URLs, retrieval date, analysis window, features used, and confidence of the affected-district label.

## Tools and Technology

### Recommended stack

- Python 3.11+
- FastAPI for the data and scoring backend
- React and TypeScript with Vite for the user interface
- pandas, NumPy, scikit-learn, GeoPandas, Shapely, rasterio, xarray, and rioxarray
- SciPy for rank correlation and distance calculations
- Leafmap, Folium, or Leaflet for maps
- SQLite for the prototype event library; PostgreSQL/PostGIS for scale
- GitHub Actions for tests and data-pipeline checks
- Structured JSON outputs with Pydantic validation
- An LLM only for constrained Tamil/English advisory phrasing

### Reference repositories

- [leafmap](https://github.com/opengeos/leafmap) — interactive geospatial analysis and map layers.
- [STURM-Flood](https://github.com/STURM-WEO/STURM-Flood) — reference flood-extent data and Sentinel-1 processing workflow.
- [Microsoft AI4G Flood](https://github.com/microsoft/ai4g-flood) — reference for Sentinel-1 flood-detection workflows.
- [Sentinel Hub flood-mapping scripts](https://github.com/sentinel-hub/custom-scripts/tree/main/sentinel-1/flood_mapping) — reference for radar flood visualisation and thresholding.
- [GeoPandas](https://github.com/geopandas/geopandas) — vector geospatial processing.
- [Rasterio](https://github.com/rasterio/rasterio) — raster and GeoTIFF processing.

These repositories are references, not copied application logic. The project's core analogue retrieval, hazard formula, priority score, confidence rules, and abstention behaviour must be implemented by the team.

## Implementation Plan

### Phase 1: Data audit and event library

1. Select a pilot area and define the fixed event analysis window and buffer.
2. Build three to five event records first.
3. Download observed rainfall and calculate intensity, duration, and 7/30-day antecedent rainfall.
4. Attach affected-district labels with source URLs.
5. Add terrain, roads, facilities, population, and reservoir fields where available.
6. Expand to 10–20 events after the pipeline works.

### Phase 2: Feature and retrieval pipeline

1. Create one canonical event schema.
2. Rank-normalise each feature.
3. Implement missing-feature-aware distance calculation.
4. Retrieve the top three to five analogues.
5. Compute the 90th-percentile leave-one-out abstention threshold.
6. Add out-of-range detection for rainfall intensity and duration.

### Phase 3: Risk and priority engine

1. Generate low, central, and high rainfall scenarios.
2. Compute each district's rainfall percentile against its own climatology.
3. Calculate analogue-supported hazard.
4. Calculate exposure, vulnerability, and isolation features.
5. Produce central-scenario rankings and scenario-stability flags.
6. Generate High/Medium/Low confidence labels.

### Phase 4: Advisory and interface

1. Display the map, top-priority districts, analogue events, and confidence.
2. Show every feature used and every missing feature.
3. Attach source tags to each advisory statement.
4. Use the LLM only to phrase verified structured output.
5. Review Tamil text with a native Tamil speaker.
6. Add a visible notice that official IMD and district warnings take precedence.

### Phase 5: Evaluation and deployment

1. Run leave-one-event-out testing without leakage.
2. Compare against rainfall-only and static flood-proneness baselines.
3. Test one stable analogue, one scenario-sensitive event, and one abstention.
4. Deploy the backend and dashboard.
5. Record the end-to-end demo.

## MVP Definition

The MVP is complete when it can:

- ingest one live rainfall forecast;
- process at least five real historical events;
- retrieve three to five analogues;
- calculate district-level hazard and priority scores;
- display low/central/high scenario stability;
- flag missing and out-of-range features;
- abstain when the analogue threshold is not met;
- show a map with source-backed district labels;
- generate a Tamil and English advisory from structured outputs;
- reproduce one hindcast evaluation from the interface.

The MVP does not include autonomous dispatch, dam control, exact flood-depth prediction, or taluk-level operational forecasting.

## Verifiable Checkpoints

### Checkpoint 1 — Data Provenance Gate

**Pass condition:** Every live input and historical event has a source URL, timestamp, analysis window, and schema-valid record.

**Displayed evidence:** source table, retrieval time, event count, missing-field report, and raw-data hash.

### Checkpoint 2 — Event-Library Ground-Truth Gate

**Pass condition:** At least five events contain observed rainfall and traceable affected-district labels; each label identifies its official report, satellite extent, or other evidence.

**Displayed evidence:** event cards showing rainfall, affected districts, source links, and label confidence.

### Checkpoint 3 — Analogue Retrieval Gate

**Pass condition:** A test query returns the top three to five analogues, feature-level distances, features used, and the 90th-percentile abstention decision.

**Displayed evidence:** analogue ranking, similarity explanation, missing-feature penalty, and out-of-range warning.

### Checkpoint 4 — Risk and Scenario Gate

**Pass condition:** The system produces central-scenario district rankings, low/high scenario rankings, a stable or scenario-sensitive flag, and High/Medium/Low confidence.

**Displayed evidence:** side-by-side scenario rankings and the hazard/exposure/vulnerability/isolation breakdown.

### Checkpoint 5 — Source-Backed Advisory Gate

**Pass condition:** Every number, district, and recommendation in the advisory can be traced to structured output and a source tag.

**Displayed evidence:** Tamil and English advisories with expandable citations and an official-warning precedence notice.

### Checkpoint 6 — Hindcast and Baseline Gate

**Pass condition:** One held-out historical event is evaluated against rainfall-only and static flood-proneness baselines, with per-event results shown honestly.

**Displayed evidence:** precision/recall or top-k overlap, abstention status, baseline comparison, and failure explanation.

### Checkpoint 7 — Live Demo Robustness Gate

**Pass condition:** The application handles missing APIs, incomplete event features, no close analogue, out-of-range rainfall, and a dry forecast without crashing or inventing data.

**Displayed evidence:** graceful error state, abstention state, dry-case state, and last successful data timestamp.
