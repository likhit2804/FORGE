# Event library inventory

This inventory describes the curated records in [`events.json`](events.json). It is a snapshot for review; run `python scripts/validate_events.py` after changing the library.

## Current coverage

- Total records: 11.
- Verified source reports: 8.
- Verified government reports: 2.
- Verified satellite extent: 1.
- Label confidence: 4 high, 7 medium.
- Operational archived forecast inputs: 0; do not interpret observed-rainfall hindcasts as forecast skill.

| Event ID | Label status | Confidence |
| --- | --- | --- |
| `tn-rain-2015-chennai` | Verified source report | Medium |
| `tn-rain-2023-south` | Verified source report | High |
| `tn-rain-2022-mayiladuthurai` | Verified source report | High |
| `tn-rain-2022-north-coast` | Verified source report | Medium |
| `tn-rain-2024-october-depression` | Verified source report | Medium |
| `tn-rain-2021-kanyakumari` | Verified source report | High |
| `tn-rain-2021-chennai-december` | Verified source report | Medium |
| `tn-rain-2024-december-flood` | Verified source report | Medium |
| `tn-rain-2019-nilgiris-august` | Verified government report | High |
| `tn-rain-2021-north-inundation` | Verified satellite extent | Medium |
| `tn-rain-2010-kanyakumari-december-depression` | Verified government report | Medium |

## Known review gaps

- Eleven events are still a small library for generalising across Tamil Nadu rainfall and impact patterns.
- Labels are report-derived and uneven in geographic detail; they are not complete flood polygons or uniform ground truth.
- The November 2021 satellite inundation record is preliminary and has no ground verification, so it remains medium confidence.
- Historical district names and labels may predate the 2021 district boundaries used for gridded rainfall. Review crosswalks before using these cases in district-level evaluation.
- Supplementary gridded rainfall features are district means and must remain distinct from station maxima or impact labels extracted from reports.
- The December 2010 Kanyakumari case is depression-associated. Its rainfall input is a single district observatory's 24-hour maximum, while the event impact comes from an IMD annual report; it should not be treated as a district-average rainfall record.
- The inventory does not claim archived forecast coverage. Historical forecast evaluation remains pending until eligible pre-event forecast runs are obtained and validated.

## Intake target

Grow toward at least 20 source-verified events. Prioritise candidate events only when reports identify dates and affected areas clearly, compatible rainfall observations are available, cyclone-window screening can be documented, source terms permit retention/use, and district boundary changes can be reviewed. Keep candidates in a separate intake file until reviewed and validated; do not lower evidence standards to reach the count target.

For each addition, follow the schema and review checklist in [`input/README.md`](input/README.md), retain the evidence under `data/sources/`, update `events.json`, and run the provenance gate.
