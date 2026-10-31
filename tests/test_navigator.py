import json
from pathlib import Path

from src.navigator import (Event, Query, adjust_correlated_weights, best_match_threshold,
                           confidence, priority_ranking, retrieve, scenario_analysis,
                           spearman_correlation)
from scripts.validate_events import validate, verified_count
from src.advisory import build_advisory
from src.evaluation import (evaluate_forward_chaining, evaluate_leave_one_out,
                            top_k_metrics)
from src.live_weather import fetch_open_meteo_forecast
from src.osm_layers import fetch_osm_profile
from src.terrain import fetch_elevation
from src.geocoding import geocode_tamil_nadu_district
from src.imd_client import fetch_imd_district_forecast


def events():
    records = json.loads((Path(__file__).parents[1] / "data" / "events.json").read_text())
    return [Event(r["event_id"], r["name"], r["start_date"], r["end_date"], r["features"], tuple(r["affected_districts"]), r["source"]) for r in records]


def query(intensity=300.0):
    ds = ["Chennai", "Tiruvallur", "Kancheepuram", "Thoothukudi", "Tirunelveli", "Tenkasi"]
    return Query({"intensity_mm": intensity, "duration_hours": 48, "antecedent_7d_mm": 120, "antecedent_30d_mm": 320}, {d: .7 for d in ds}, {d: .6 for d in ds}, {d: .6 for d in ds}, {d: .4 for d in ds})


def test_retrieval_returns_top_k_and_threshold():
    lib = events()
    result = retrieve(query(), lib)
    assert 3 <= len(result["analogues"]) <= 5
    assert result["threshold"] >= 0


def test_forward_chaining_uses_only_prior_events_and_marks_cold_start():
    library = [
        Event(str(year), f"Event {year}", f"{year}-01-01", f"{year}-01-02",
              {"intensity_mm": float(year - 2000), "duration_hours": 24.0},
              ("Alpha",), f"https://example.org/{year}")
        for year in (2020, 2021, 2022, 2023)
    ]

    rows = evaluate_forward_chaining(library, min_training_events=2)

    assert [row.get("status") for row in rows[:2]] == [
        "not_evaluated_insufficient_prior_events",
        "not_evaluated_insufficient_prior_events",
    ]
    assert rows[2]["training_event_count"] == 2
    assert rows[3]["training_event_count"] == 3


def test_out_of_range_is_low_confidence():
    lib = events()
    result = retrieve(query(1000), lib)
    ranking = priority_ranking(query(1000), result)
    assert result["out_of_range"]
    assert confidence(result, ranking) == "Low"


def test_negative_query_features_are_rejected():
    import pytest
    q = query()
    q = Query({**q.features, "intensity_mm": -1}, q.forecast_percentile_by_district, q.exposure_by_district, q.vulnerability_by_district, q.isolation_by_district)
    with pytest.raises(ValueError, match="non-negative"):
        retrieve(q, events())


def test_priority_exposes_analogue_support():
    q = query()
    ranking = priority_ranking(q, retrieve(q, events()))
    assert ranking
    assert all("analogue_support" in row for row in ranking)


def test_retrieval_exposes_auditable_features():
    result = retrieve(query(), events(), top_k=5)
    assert result["analogues"]
    assert all(item["features_used"] > 0 for item in result["analogues"])
    assert "threshold" in result
    assert "abstained" in result
    assert "out_of_range" in result


def test_scenario_analysis_returns_rankings_and_stability():
    library = events()
    result = scenario_analysis({"low": query(220), "central": query(300), "high": query(450)}, library)
    assert {"low", "central", "high", "stability"}.issubset(result)
    assert result["low"]["ranking"]
    assert all("positions" in item and "stable" in item for item in result["stability"].values())


def test_district_retrieval_uses_district_rainfall_features():
    first = Event("first", "First event", "2020-01-01", "2020-01-02",
                  {"intensity_mm": 20, "duration_hours": 48}, ("Chennai",), "https://example.test/1",
                  district_features={"Chennai": {"intensity_mm": 10, "antecedent_7d_mm": 5,
                                                  "antecedent_30d_mm": 12}})
    second = Event("second", "Second event", "2021-01-01", "2021-01-02",
                   {"intensity_mm": 20, "duration_hours": 48}, (), "https://example.test/2",
                   district_features={"Chennai": {"intensity_mm": 30, "antecedent_7d_mm": 5,
                                                   "antecedent_30d_mm": 12}})
    q = Query({"intensity_mm": 20, "duration_hours": 48, "antecedent_7d_mm": 5,
               "antecedent_30d_mm": 12}, {"Chennai": 0.5}, {"Chennai": 0.5},
              {"Chennai": 0.5}, {"Chennai": 0.5}, {"Chennai": 11}, {"Chennai": 48},
              {"Chennai": {"antecedent_7d_mm": 5, "antecedent_30d_mm": 12}})
    result = retrieve(q, [first, second])
    assert result["district_analogues"]["Chennai"]["analogues"][0]["event"].event_id == "first"


def test_priority_is_descending():
    lib = events()
    q = query()
    ranking = priority_ranking(q, retrieve(q, lib))
    assert ranking == sorted(ranking, key=lambda row: row["priority"], reverse=True)


def test_event_library_passes_provenance_gate():
    path = Path(__file__).parents[1] / "data" / "events.json"
    assert validate(path) == []
    records = json.loads(path.read_text())
    assert verified_count(path) == len(records)


def test_correlated_exposure_and_isolation_weights_are_adjusted():
    exposure = {"A": 0.1, "B": 0.4, "C": 0.8, "D": 1.0}
    isolation = {"A": 0.0, "B": 0.3, "C": 0.7, "D": 1.0}
    weights, rho, adjusted = adjust_correlated_weights(
        {"hazard": 0.4, "exposure": 0.25, "vulnerability": 0.2, "isolation": 0.15},
        exposure, isolation)
    assert rho is not None and rho > 0.99
    assert adjusted
    assert weights["isolation"] == 0.075
    assert weights["exposure"] == 0.325


def test_rank_correlation_is_undefined_for_constant_or_tiny_inputs():
    assert spearman_correlation({"A": 1, "B": 1, "C": 1}, {"A": 1, "B": 2, "C": 3}) is None
    assert spearman_correlation({"A": 1, "B": 2}, {"A": 1, "B": 2}) is None


def test_advisory_is_source_backed_and_bilingual():
    q = query()
    retrieval = retrieve(q, events())
    ranking = priority_ranking(q, retrieval)
    english = build_advisory(ranking, retrieval, "en")
    tamil = build_advisory(ranking, retrieval, "ta")
    assert english["source_tags"]["analogue_events"]
    assert english["source_tags"]["official_precedence"].startswith("https://")
    assert tamil["language"] == "ta"


def test_leave_one_out_evaluation_has_per_event_baselines():
    rows = evaluate_leave_one_out(events())
    assert len(rows) == len(events())
    assert all("analogue" in row and "rainfall_only" in row and "static_flood_proneness" in row for row in rows)
    assert all(0.0 <= row["analogue"]["recall_at_k"] <= 1.0 for row in rows)


def test_top_k_metrics_are_bounded():
    metrics = top_k_metrics(["A", "B"], ("B", "C"), 2)
    assert metrics["hits"] == 1
    assert metrics["precision_at_k"] == 0.5


def test_empty_library_fails_with_clear_error():
    import pytest
    with pytest.raises(ValueError, match="event library is empty"):
        retrieve(query(), [])


def test_partial_features_still_return_auditable_result():
    q = Query({"intensity_mm": 300}, query().forecast_percentile_by_district, query().exposure_by_district, query().vulnerability_by_district, query().isolation_by_district)
    result = retrieve(q, events())
    assert result["analogues"]
    assert all(item["features_used"] == 1 for item in result["analogues"])


def test_priority_ranking_canonicalizes_historical_district_aliases():
    q = Query({"intensity_mm": 300, "duration_hours": 48},
              {"Kanchipuram": 0.7}, {"Kanchipuram": 0.5},
              {"Kanchipuram": 0.5}, {"Kanchipuram": 0.5})
    historical = [Event("old", "Older label", "2020-01-01", "2020-01-02",
                        {"intensity_mm": 300, "duration_hours": 48},
                        ("Kancheepuram",), "https://example.org")]
    result = retrieve(q, historical)
    ranking = priority_ranking(q, result)
    assert [row["district"] for row in ranking] == ["Kanchipuram"]


def test_live_forecast_adapter_parses_payload(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"hourly":{"precipitation":[1.5, 0, 2.25]}}'

    monkeypatch.setattr("src.live_weather.urlopen", lambda request, timeout: Response())
    result = fetch_open_meteo_forecast(13.08, 80.27, days=1)
    assert result["total_precipitation_mm"] == 3.75
    assert result["source"] == "Open-Meteo forecast API"


def test_osm_profile_adapter_parses_count(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"elements":[{"tags":{"total":"42"}}]}'

    monkeypatch.setattr("src.osm_layers.urlopen", lambda request, timeout: Response())
    result = fetch_osm_profile("Chennai", 12.9, 80.1, 13.2, 80.4)
    assert result["osm_elements"] == 42
    assert result["source"] == "OpenStreetMap Overpass API"


def test_elevation_adapter_parses_value(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"elevation":[7.5]}'

    monkeypatch.setattr("src.terrain.urlopen", lambda request, timeout: Response())
    result = fetch_elevation(13.08, 80.27)
    assert result["elevation_m"] == 7.5
    assert result["source"] == "Open-Meteo elevation API (Copernicus DEM GLO-90)"


def test_geocoder_parses_coordinate(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'[{"lat":"13.08","lon":"80.27","display_name":"Chennai, Tamil Nadu, India"}]'

    monkeypatch.setattr("src.geocoding.urlopen", lambda request, timeout: Response())
    result = geocode_tamil_nadu_district("Chennai")
    assert result["latitude"] == 13.08
    assert result["source"] == "OpenStreetMap Nominatim"


def test_imd_adapter_preserves_source_and_records(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'[{"District":"Chennai","day1_distribution":"Widespread"}]'

    monkeypatch.setattr("src.imd_client.urlopen", lambda request, timeout: Response())
    result = fetch_imd_district_forecast(endpoint="https://example.test/imd")
    assert result["source"] == "India Meteorological Department"
    assert result["records"][0]["District"] == "Chennai"
