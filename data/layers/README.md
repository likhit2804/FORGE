# District feature layers

## Current audit

Regenerate the machine-readable source, coverage, and limitation inventory from the committed layers and event labels:

```bash
python -m scripts.assess_hazard_exposure --output data/layers/hazard_exposure_assessment.json
```

The assessment records hashes, byte sizes, source/retrieval metadata, licences as recorded (or explicitly notes when absent), district coverage, current ranking use, missing candidate signals, and whether any independent added-value evaluation has been done. The API exposes this inventory to the UI's expandable data-quality panel.

At the current snapshot, elevation, population, and OSM files each contain one unique row for all 38 districts. The daily IMD-derived rainfall table contains 138,814 rows from 2015-01-01 to 2024-12-31, covers all 38 districts, and has no invalid or negative amounts. OSM has 38 district profiles and zero recorded query failures. Those figures establish file and district coverage only—not completeness of the mapped features or validity of the proxies.

## Interpretation and gaps

- Representative-point elevation from Copernicus DEM GLO-90 is a single-point relative low-elevation proxy, not a district mean, floodplain model, drainage metric, or flood depth.
- WorldPop 2025 at 1-km resolution is a district population-total proxy. It is not event-time population or population intersecting a flood footprint; its layer sidecar does not record a licence.
- OSM amenity counts are mapping-context proxies, not complete service inventories or capacity. OSM road-way density is not road length, connectivity, passability, closure status, or travel time. OSM waterway-way counts are not river distance, stream order, catchment, drainage capacity, or flood extent.
- The event library contains one preliminary, unground-verified satellite-extent case; there is no repeated, event-aligned inundation series.
- River proximity, drainage capacity, event-time road passability/travel time, and cropland exposure layers are absent.
- Population, elevation, and OSM proxy features currently influence the ranking, but their incremental value has not been measured with independent event-holdout ablations. Treat them as provisional context, not proven predictors.

Do not add a candidate signal to ranking weights until its source date, spatial resolution, licence, transformation, missingness, and uncertainty are recorded and a same-event chronological ablation demonstrates improvement over the locked baseline.
