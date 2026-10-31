# Archived forecast data checkpoint

## Current gap

The current chronological evaluation is a retrospective event reconstruction: it uses observed IMD gridded rainfall from the held-out event. It is **not** an operational forecast-skill test. Do not describe its precision/recall as forecast accuracy.

## Candidate archive: TIGGE via ECMWF Data Store

The ECMWF TIGGE archive covers global ensemble forecasts from October 2006 onward and lists both the India Meteorological Department (IMD) and National Centre for Medium Range Weather Forecasting (NCMRWF) among its contributing centres. Typical forecasts extend 10–15 days, with ensemble sizes depending on the centre. The project should test historical availability for the event dates before designing a larger request.

- Dataset: <https://ecds.ecmwf.int/datasets/tigge-forecasts>
- Dataset documentation and access notes: <https://confluence.ecmwf.int/spaces/TIGGE/overview>
- Licence terms: <https://ecds.ecmwf.int/licences/tigge-licence>
- ECMWF archive access overview: <https://www.ecmwf.int/en/forecasts/access-forecasts/access-archive-datasets>

Access moved to the ECMWF Data Store (ECDS) in 2026; the old public-datasets Web API is no longer the access path. ECDS uses an account and personal API token. TIGGE includes contributions from IMD and NCMRWF; check the selected centre's current licence in ECDS before downloading. The ECMWF TIGGE contribution is CC BY-NC 4.0, which requires attribution and restricts commercial use. Do not assume every contributing centre has identical terms.

ECMWF Open Data is not a substitute for this historical test: its real-time files are retained on a short rolling archive (about 2–3 days). Reanalysis is also not a substitute for archived forecasts because it is not the forecast issued at the historical decision time.

## Retrieval protocol

1. Create/confirm an ECDS account, configure its personal API token outside the repository, and accept the TIGGE terms in the account used for retrieval. Never commit credentials or API keys.
2. In the dataset form, check availability for the existing event windows (start one or more forecast initialisation times before each event), the rainfall parameter, forecast lead times, and the IMD/NCMRWF centres. The interface and API may expose different fields; use the current dataset form as authoritative.
3. Start with one event and a Tamil Nadu/South India bounding box. Request ensemble precipitation fields only, at daily lead windows matching the app's 1–7 day horizon. Record the initialization time, centre/model, member, lead interval, units, grid, request ID, licence, and original-file SHA-256.
4. Convert accumulated precipitation to millimetres over a clearly defined lead window; do not treat cumulative values as daily totals or mix centres/resolutions without documenting the transformation.
5. Aggregate forecast members to the same district polygons used for observations. Compare the forecast issued at the chosen historical cutoff with the corresponding observed IMD gridded rainfall and report-label districts.
6. Prepare the district/member CSV described below. Keep the original forecast file unchanged beside the CSV, and provide its SHA-256 on every row. The evaluator verifies the file hash, licence, source URL, issue time, members, lead interval, and matching observation coverage. Missing archive coverage is reported as missing, never filled with observed rainfall.
7. Keep the current observed-rainfall reconstruction as a separate diagnostic. Do not combine its scores with forecast-input scores.

## Evaluator input and run

Run `python scripts/evaluate_archived_forecasts.py --forecasts PATH --observations PATH --output PATH`; `--events` defaults to `data/events.json`. The forecast CSV must contain these columns:

`event_id,initialization_time_utc,centre,member,lead_start_days,lead_end_days,valid_start_date,valid_end_date,district,precipitation_mm,source_file,source_file_sha256,source_url,licence`

Each row is one district, ensemble member, event, and forecast valid window. `precipitation_mm` is the accumulated amount for that exact inclusive date window, already aggregated to the project's district polygons using a documented spatial method. `lead_start_days` and `lead_end_days` are inclusive UTC calendar-day offsets from the UTC calendar date of `initialization_time_utc`; the evaluator requires `valid_start_date` and `valid_end_date` to match those offsets exactly. All districts in a forecast run must have the same members. `source_file` is relative to the forecast CSV's directory; the original file must be present and its SHA-256 must match. Use ISO dates and timestamps with an explicit UTC offset. The daily observation CSV is `date,district,rainfall_mm`; it must cover every forecast district and every day in the exact forecast valid window.

The JSON report keeps runs separate by event, initialization, centre, and lead interval. It includes ensemble-mean precipitation MAE/RMSE, member spread and per-district absolute-error diagnostics, a same-calendar-month climatology baseline built only from observations before event start, top-k affected-district ranking metrics, district/member sample counts, event-bootstrap intervals, input hashes, and an explicit five-event claim gate for each centre/lead stratum. Runs missing observation coverage are listed as skipped; events with no evaluable run are listed separately. Impact recall uses the complete report-derived affected-district label set as its denominator; the report separately gives the fraction of those labels represented in forecasts. Interpret both with caution because report-derived labels are incomplete and imperfect. A report below the gate is pending and is not evidence of established forecast skill.

Phase 4 can summarize spread/error relationships after the Phase 3 report exists:

`python scripts/build_confidence_calibration.py --evaluation REPORT.json --output CANDIDATE.json`

The diagnostic keeps forecast centre and lead separate and defaults to requiring ten distinct events and 100 district-run samples per stratum. Passing this gate does not create a calibrated probability model: independent review and out-of-sample validation are still required, and a TIGGE-derived diagnostic must not be transferred to the live Open-Meteo forecast provider.

This evaluator checks that initialization precedes the event start, the forecast valid window is inside the event window, and the declared lead interval maps exactly to that window under the UTC calendar-day convention above. It does not download data, derive district polygons, or decide whether a particular model run was operationally available; those steps and their provenance must be reviewed and recorded before evaluation.

## Acceptance checkpoint

The historical forecast evaluation is ready only when at least five held-out events have archived forecast runs issued before their event windows, matching observation windows, auditable provenance, and documented licences. Until then, label forecast validation as pending. Current state: evaluator implemented; archive retrieval and authenticated availability checks remain outstanding.
