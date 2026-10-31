"""Read-only adapter for the Tamil Nadu AGRISNET reservoir dashboard."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from urllib.request import Request, urlopen


SOURCE_URL = "https://www.tnagrisnet.tn.gov.in/home/reservoir/"
API_URL_TEMPLATE = "https://www.tnagrisnet.tn.gov.in/uzhavan/reservoir/{date}"
DEFAULT_BUFFER_CONCERN_THRESHOLD_PCT = 80.0


class ReservoirDataError(RuntimeError):
    pass


def _number(value, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ReservoirDataError(f"invalid {field} value in AGRISNET response") from exc
    if amount < 0:
        raise ReservoirDataError(f"negative {field} value in AGRISNET response")
    return amount


def fetch_reservoir_status(as_of: date | None = None, lookback_days: int = 3,
                           timeout: int = 20) -> dict:
    """Fetch the most recent non-empty daily feed at or before ``as_of``."""
    requested_date = as_of or date.today()
    if lookback_days < 0 or lookback_days > 14:
        raise ValueError("lookback_days must be between 0 and 14")
    errors = []
    for offset in range(lookback_days + 1):
        target_date = requested_date - timedelta(days=offset)
        api_url = API_URL_TEMPLATE.format(date=target_date.isoformat())
        request = Request(api_url, headers={"User-Agent": "MonsoonImpactNavigator/0.1"})
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list) or not payload:
                continue
            rows = []
            for raw in payload:
                name = str(raw.get("reservoir_name", "")).strip()
                capacity = _number(raw.get("tot_capacity"), "total capacity")
                storage = _number(raw.get("current_storage"), "current storage")
                if not name:
                    raise ReservoirDataError("AGRISNET returned a reservoir without a name")
                if capacity is not None and capacity <= 0:
                    raise ReservoirDataError(f"non-positive capacity for {name}")
                rows.append({
                    "reservoir": name,
                    "total_capacity_mcft": capacity,
                    "current_storage_mcft": storage,
                    "current_level_ft": _number(raw.get("current_level"), "current level"),
                    "inflow_cusecs": _number(raw.get("inflow"), "inflow"),
                    "outflow_cusecs": _number(raw.get("outflow"), "outflow"),
                    "last_year_storage_mcft": _number(raw.get("lastyear_storage"), "last-year storage"),
                    "source_report_date": raw.get("updated_date"),
                })
            dates = {row["source_report_date"] for row in rows if row["source_report_date"]}
            if dates and dates != {target_date.isoformat()}:
                raise ReservoirDataError("AGRISNET response report date does not match requested date")
            if not dates:
                raise ReservoirDataError("AGRISNET response lacks source report dates")
            return {
                "source": "Department of Agriculture - Farmers Welfare, Government of Tamil Nadu (AGRISNET)",
                "source_url": SOURCE_URL,
                "api_url": api_url,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "data_date": target_date.isoformat(),
                "requested_date": requested_date.isoformat(),
                "staleness_days": offset,
                "units": {"storage": "million cubic feet (mcft)", "level": "feet", "flow": "cubic feet per second"},
                "scope_note": "The source dashboard returns Tamil Nadu major reservoirs and Cauvery-basin Karnataka reservoirs; it does not provide a district association in this feed.",
                "records": rows,
            }
        except ReservoirDataError:
            raise
        except Exception as exc:
            errors.append(f"{target_date.isoformat()}: {exc}")
    detail = "; ".join(errors[-3:])
    raise ReservoirDataError(f"No AGRISNET reservoir report found within {lookback_days} days. {detail}")


def apply_buffer_flags(snapshot: dict, threshold_pct: float = DEFAULT_BUFFER_CONCERN_THRESHOLD_PCT) -> dict:
    if not 0 <= threshold_pct <= 100:
        raise ValueError("buffer concern threshold must be between 0 and 100 percent")
    records = []
    for source_row in snapshot.get("records", []):
        row = dict(source_row)
        capacity, storage = row.get("total_capacity_mcft"), row.get("current_storage_mcft")
        if isinstance(capacity, (int, float)) and capacity > 0 and isinstance(storage, (int, float)):
            row["storage_pct_of_full_capacity"] = round(storage / capacity * 100.0, 2)
            row["buffer_concern"] = row["storage_pct_of_full_capacity"] >= threshold_pct
            row["status"] = "buffer_concern" if row["buffer_concern"] else "below_threshold"
        else:
            row["storage_pct_of_full_capacity"] = None
            row["buffer_concern"] = None
            row["status"] = "insufficient_source_data"
        records.append(row)
    return {**snapshot, "buffer_concern_threshold_pct": threshold_pct, "records": records,
            "flag_note": "Prototype storage-context flag only; not an inflow forecast, flood warning, dam-release instruction, or control recommendation."}
