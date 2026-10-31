import io

import pytest

from src.ensemble_weather import EnsembleWeatherError, fetch_ensemble_forecasts


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_partial_location_response_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "src.ensemble_weather.urlopen",
        lambda *args, **kwargs: FakeResponse(b"[{}]"),
    )

    with pytest.raises(EnsembleWeatherError, match="partial district coverage"):
        fetch_ensemble_forecasts({
            "Alpha": (11.0, 78.0), "Beta": (12.0, 79.0),
        })
