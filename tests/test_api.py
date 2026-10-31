from fastapi.testclient import TestClient

import api
from src.navigator import Event


def test_bootstrap_exposes_districts_events_and_geojson():
    client = TestClient(api.app)
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["districts"]) == 38
    assert payload["events"]
    assert all(event["source"] and event["label_status"] and event["cyclone_window_evidence"]
               for event in payload["events"])
    assert payload["boundaries"]["type"] == "FeatureCollection"


def test_analysis_api_returns_ranking_scenarios_baselines_and_advisory(monkeypatch):
    sample_events = [
        Event("a", "Case A", "2020-01-01", "2020-01-02",
              {"intensity_mm": 200, "duration_hours": 24, "antecedent_7d_mm": 50,
               "antecedent_30d_mm": 120}, ("Alpha",), "https://example.org/a"),
        Event("b", "Case B", "2021-01-01", "2021-01-02",
              {"intensity_mm": 300, "duration_hours": 48, "antecedent_7d_mm": 80,
               "antecedent_30d_mm": 180}, ("Beta",), "https://example.org/b"),
        Event("c", "Case C", "2022-01-01", "2022-01-02",
              {"intensity_mm": 400, "duration_hours": 72, "antecedent_7d_mm": 100,
               "antecedent_30d_mm": 250}, ("Gamma",), "https://example.org/c"),
    ]
    layers = {"source_names": {name.lower(): name for name in ("Alpha", "Beta", "Gamma")},
              "centroids": {}, "exposure": {}, "vulnerability": {}, "isolation": {},
              "osm_features": {}, "sources": {}, "geojson": None}
    monkeypatch.setattr(api, "_events", lambda: sample_events)
    monkeypatch.setattr(api, "_district_layers", lambda: layers)
    client = TestClient(api.app)
    response = client.post("/api/run", json={"intensity_mm": 300, "duration_hours": 48})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ok"
    assert {"Alpha", "Beta", "Gamma"}.issubset({row["district"] for row in result["ranking"]})
    assert set(result["scenarios"]) == {"low", "central", "high"}
    assert "rainfall_only" in result["baselines"]
    assert result["advisory"]["english"]["source_tags"]["analogue_events"]
    assert result["advisory"]["tamil"]["language"] == "ta"


def test_analysis_api_short_circuits_dry_forecast(monkeypatch):
    monkeypatch.setattr(api, "_events", lambda: [])
    monkeypatch.setattr(api, "_district_layers", lambda: {
        "source_names": {"alpha": "Alpha"}, "centroids": {}, "exposure": {},
        "vulnerability": {}, "isolation": {}, "osm_features": {}, "sources": {},
        "geojson": None,
    })
    response = TestClient(api.app).post("/api/run", json={"intensity_mm": 0})
    assert response.status_code == 200
    assert response.json()["status"] == "dry_or_no_significant_rain"


def test_evaluation_api_reports_macro_precision_and_recall(monkeypatch):
    monkeypatch.setattr(api, "_events", lambda: [])
    monkeypatch.setattr(api, "evaluate_leave_one_out", lambda events: [{
        "event_id": "held-out", "event": "Held-out event",
        "analogue": {"hits": 2, "precision_at_k": 0.4, "recall_at_k": 0.5},
        "rainfall_only": {"hits": 1, "precision_at_k": 0.2, "recall_at_k": 0.25},
        "static_flood_proneness": {"hits": 3, "precision_at_k": 0.6, "recall_at_k": 0.75},
        "abstained": False,
    }])

    response = TestClient(api.app).get("/api/evaluation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["macro_average"]["analogue"] == {
        "precision_at_k": 0.4, "recall_at_k": 0.5}
    assert payload["macro_average"]["rainfall_only"]["evaluated_events"] == 1
    assert payload["macro_average"]["static_flood_proneness"]["recall_at_k"] == 0.75


def test_forward_evaluation_marks_cold_start_and_averages_scored_events(monkeypatch):
    rows = [
        {"event_id": "early", "event": "Early event",
         "status": "not_evaluated_insufficient_prior_events", "prior_event_count": 1,
         "required_prior_events": 3},
        {"event_id": "later", "event": "Later event", "training_event_count": 3,
         "analogue": {"precision_at_k": 0.4, "recall_at_k": 0.5},
         "rainfall_only": {"precision_at_k": 0.6, "recall_at_k": 0.75},
         "static_flood_proneness": {"precision_at_k": 0.2, "recall_at_k": 0.25},
         "abstained": False},
    ]
    monkeypatch.setattr(api, "_events", lambda: [])
    monkeypatch.setattr(api, "evaluate_forward_chaining", lambda events: rows)

    response = TestClient(api.app).get("/api/forward-evaluation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_count"] == 2
    assert payload["evaluated_event_count"] == 1
    assert payload["events"][0]["status"] == "not_evaluated_insufficient_prior_events"
    assert payload["macro_average"]["analogue"]["recall_at_k"] == 0.5
