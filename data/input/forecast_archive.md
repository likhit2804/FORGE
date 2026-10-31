# Archived forecast data checkpoint

## Current gap

The current chronological evaluation is a retrospective event reconstruction: it uses observed IMD gridded rainfall from the held-out event. It is **not** an operational forecast-skill test. Do not describe its precision/recall as forecast accuracy.

## Candidate archive: TIGGE via ECMWF Data Store

The ECMWF TIGGE archive covers global ensemble forecasts from October 2006 onward and lists both the India Meteorological Department (IMD) and National Centre for Medium Range Weather Forecasting (NCMRWF) among its contributing centres. Typical forecasts extend 10–15 days, with ensemble sizes depending on the centre. The project should test historical availability for the event dates before designing a larger request.

- Dataset: <https://ecds.ecmwf.int/datasets/tigge-forecasts>
- Dataset documentation and access notes: <https://confluence.ecmwf.int/spaces/TIGGE/overview>
- Licence terms: <https://ecds.ecmwf.int/licences/tigge-licence>
- ECMWF archive access overview: <https://www.ecmwf.int/en/forecasts/access-forecasts/access-archive-datasets>

Access moved to the ECMWF Data Store in 2026; the old public-datasets Web API is no longer the access path. Registration is required. TIGGE data from IMD and NCMRWF is listed under CC BY-NC 4.0, so preserve provider attribution and treat any redistribution as non-commercial unless the relevant terms change or separate permission is obtained. Check the chosen centre, parameter, dates, and licence in the ECDS before downloading.

ECMWF Open Data is not a substitute for this historical test: its real-time files are retained on a short rolling archive (about 2–3 days). Reanalysis is also not a substitute for archived forecasts because it is not the forecast issued at the historical decision time.

## Retrieval protocol

1. Create/confirm an ECDS account and accept the TIGGE terms in the account used for retrieval. Never commit credentials or API keys.
2. In the dataset form, check availability for the existing event windows (start one or more forecast initialisation times before each event), the rainfall parameter, forecast lead times, and the IMD/NCMRWF centres. The interface and API may expose different fields; use the current dataset form as authoritative.
3. Start with one event and a Tamil Nadu/South India bounding box. Request ensemble precipitation fields only, at daily lead windows matching the app's 1–7 day horizon. Record the initialization time, centre/model, member, lead interval, units, grid, request ID, licence, and original-file SHA-256.
4. Convert accumulated precipitation to millimetres over a clearly defined lead window; do not treat cumulative values as daily totals or mix centres/resolutions without documenting the transformation.
5. Aggregate forecast members to the same district polygons used for observations. Compare the forecast issued at the chosen historical cutoff with the corresponding observed IMD gridded rainfall and report-label districts.
6. Add a forecast-input table keyed by event, initialization time, centre, and lead. The evaluator must use only forecast files initialized before that event; missing archive coverage is reported as missing, never filled with observed rainfall.
7. Keep the current observed-rainfall reconstruction as a separate diagnostic. Do not combine its scores with forecast-input scores.

## Acceptance checkpoint

The historical forecast evaluation is ready only when at least five held-out events have archived forecast runs issued before their event windows, matching observation windows, auditable provenance, and a documented licence. Until then, the app should label forecast validation as pending.
