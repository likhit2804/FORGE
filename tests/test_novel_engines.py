"""Tests for novel scientific and agentic engines in Monsoon Impact Navigator."""

import pytest
from fastapi.testclient import TestClient

import api
from src.checkpoints import evaluate_all_checkpoints
from src.react_agent import run_react_disaster_agent
from src.reservoir_physics import RESERVOIR_SPECS, simulate_predischarge_cushion
from src.teleconnections import fetch_bob_sst, fetch_noaa_oni, get_teleconnection_summary


def test_teleconnections_returns_valid_provenance():
    oni = fetch_noaa_oni()
    assert oni["status"] in ("live", "cached_fallback")
    assert isinstance(oni["oni_anomaly_celsius"], (int, float))
    assert oni["enso_phase"]

    sst = fetch_bob_sst()
    assert sst["status"] in ("live", "cached_baseline")
    assert 25.0 <= sst["current_sst_celsius"] <= 35.0
    assert sst["convective_energy_status"]

    summary = get_teleconnection_summary()
    assert summary["provenance_status"] == "pass"
    assert "Coromandel Inversion" in summary["scientific_paradox_statement"]


def test_reservoir_predischarge_physics_reduces_peak_flooding():
    sim = simulate_predischarge_cushion(
        reservoir_key="chembarambakkam",
        forecast_storm_rainfall_mm=380.0,
        storm_duration_hours=48.0,
        predischarge_lead_time_hours=72.0,
    )

    spec = sim["reservoir"]
    assert spec["name"] == "Chembarambakkam"
    assert spec["safe_river_capacity_cusecs"] == 15000.0

    # Unmanaged scenario would have huge emergency dump
    unmanaged = sim["unmanaged_disaster_outcome"]
    assert unmanaged["peak_emergency_release_cusecs"] > 10000.0

    # Dynamic pre-discharge creates sufficient cushion
    sol = sim["dynamic_predischarge_solution"]
    assert sol["optimal_predischarge_rate_cusecs"] > 0
    assert sol["peak_flood_reduction_pct"] > 50.0
    assert sol["river_safe_compliance"] is True
    assert len(sim["hydrograph_comparison"]) == 13


def test_react_agent_autonomous_trace_and_order_generation():
    events = api._events()
    res = run_react_disaster_agent(
        reservoir_name="chembarambakkam",
        forecast_rainfall_mm=350.0,
        duration_hours=48.0,
        lead_time_hours=72.0,
        events=events,
    )

    assert res["status"] == "success"
    assert len(res["steps"]) == 4
    assert res["steps"][0]["phase"] == "TELECONNECTION_INGESTION"
    assert res["steps"][1]["phase"] == "HYDROLOGICAL_PREDISCHARGE_SOLVER"
    assert res["steps"][2]["phase"] == "HISTORICAL_ANALOGUE_MATCHING"
    assert res["steps"][3]["phase"] == "EXECUTIVE_ORDER_DRAFTING"

    order = res["executive_order"]
    assert order["status"] == "PENDING_CHIEF_ENGINEER_AUTHORIZATION"
    assert "OFFICIAL PRE-DISCHARGE" in order["english_text"]
    assert "அதிகாரப்பூர்வ" in order["tamil_text"]
    assert len(order["sha256_seal"]) == 64


def test_checkpoints_gate_evaluation_verifies_all_seven_gates():
    events = api._events()
    audits = evaluate_all_checkpoints(api.ROOT, events)
    assert len(audits) == 7
    checkpoint_names = [a["name"] for a in audits]
    assert any("Data Provenance Gate" in name for name in checkpoint_names)
    assert any("Event-Library Ground-Truth Gate" in name for name in checkpoint_names)
    assert any("Analogue Retrieval Gate" in name for name in checkpoint_names)
    assert any("Risk and Scenario Gate" in name for name in checkpoint_names)
    assert any("Source-Backed Advisory Gate" in name for name in checkpoint_names)
    assert any("Hindcast and Baseline Gate" in name for name in checkpoint_names)
    assert any("Live Demo Robustness Gate" in name for name in checkpoint_names)

    # Every gate must have evidence and pass condition
    for gate in audits:
        assert gate["status"] in ("PASS", "WARN")
        assert gate["pass_condition"]
        assert gate["evidence"]


def test_api_new_endpoints_integration():
    client = TestClient(api.app)

    # 1. Teleconnections
    res1 = client.get("/api/teleconnections")
    assert res1.status_code == 200
    assert "noaa_oni" in res1.json()

    # 2. Reservoir simulation
    res2 = client.post("/api/reservoir/simulate", json={
        "reservoir_key": "chembarambakkam",
        "forecast_storm_rainfall_mm": 300.0,
        "storm_duration_hours": 36.0,
        "predischarge_lead_time_hours": 48.0,
    })
    assert res2.status_code == 200
    assert "dynamic_predischarge_solution" in res2.json()

    # 3. Agent run
    res3 = client.post("/api/agent/run", json={
        "reservoir_name": "chembarambakkam",
        "forecast_rainfall_mm": 350.0,
        "duration_hours": 48.0,
        "lead_time_hours": 72.0,
    })
    assert res3.status_code == 200
    assert "executive_order" in res3.json()

    # 4. Checkpoints
    res4 = client.get("/api/checkpoints")
    assert res4.status_code == 200
    assert res4.json()["total_checkpoints"] == 7
