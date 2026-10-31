import json
from datetime import date

import pytest

from src.reservoirs import (ReservoirDataError, apply_buffer_flags,
                            fetch_reservoir_status)


def test_fetch_reservoir_status_parses_and_records_source_date(monkeypatch):
    payload = [{"reservoir_name": "Test Reservoir", "tot_capacity": "100",
                "current_storage": "82", "current_level": "12.5", "inflow": "3",
                "outflow": "4", "lastyear_storage": "75",
                "updated_date": "2026-10-30"}]

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(payload).encode()

    monkeypatch.setattr("src.reservoirs.urlopen", lambda request, timeout: Response())
    result = fetch_reservoir_status(date(2026, 10, 30), lookback_days=0)
    assert result["data_date"] == "2026-10-30"
    assert result["records"][0]["current_storage_mcft"] == 82


def test_buffer_flags_are_threshold_based_and_non_prescriptive():
    snapshot = {"records": [
        {"reservoir": "High", "total_capacity_mcft": 100, "current_storage_mcft": 80},
        {"reservoir": "Low", "total_capacity_mcft": 100, "current_storage_mcft": 79},
        {"reservoir": "Missing", "total_capacity_mcft": None, "current_storage_mcft": 3},
    ]}
    result = apply_buffer_flags(snapshot, 80)
    assert [row["status"] for row in result["records"]] == [
        "buffer_concern", "below_threshold", "insufficient_source_data"]
    assert "not an inflow forecast" in result["flag_note"]


def test_reservoir_feed_rejects_mismatched_report_date(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return b'[{"reservoir_name":"Test","tot_capacity":"10","current_storage":"5","updated_date":"2026-10-29"}]'

    monkeypatch.setattr("src.reservoirs.urlopen", lambda request, timeout: Response())
    with pytest.raises(ReservoirDataError, match="does not match"):
        fetch_reservoir_status(date(2026, 10, 30), lookback_days=0)
