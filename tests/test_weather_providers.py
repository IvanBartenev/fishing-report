from datetime import date

import pytest

from app.cache import memory
from app.providers.open_meteo_ensemble import (
    EnsembleUnavailableError,
    parse_ensemble_response,
)
from app.providers.open_meteo_hourly import get_hourly_pressure


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def setup_function():
    memory._cache.clear()


def test_parse_ensemble_pressure_members_and_convert_units():
    payload = {
        "timezone": "Europe/Moscow",
        "hourly": {
            "time": ["2026-11-01T00:00", "2026-11-01T01:00"],
            "pressure_msl_member01": [1000.0, 1001.0],
            "pressure_msl_member02": [1002.0, None],
        },
    }

    result = parse_ensemble_response(payload)

    assert result["member_count"] == 2
    assert result["timezone"] == "Europe/Moscow"
    assert result["hours"][0]["member_pressures"] == [750.06, 751.56]
    assert len(result["hours"][1]["member_pressures"]) == 2
    assert result["hours"][1]["member_pressures"][1] is None


def test_parse_ensemble_rejects_missing_members():
    with pytest.raises(EnsembleUnavailableError):
        parse_ensemble_response({"hourly": {"time": ["2026-11-01T00:00"], "pressure_msl": [1000]}})


def test_get_hourly_pressure_returns_selected_local_days():
    geo = FakeResponse({"results": [{"latitude": 51.66, "longitude": 39.20}]})
    forecast = FakeResponse({
        "hourly": {
            "time": [
                "2026-11-01T00:00", "2026-11-01T01:00",
                "2026-11-02T00:00", "2026-11-03T00:00",
                "2026-11-04T00:00",
            ],
            "pressure_msl": [1000.0, 1001.0, 1002.0, 1003.0, 1004.0],
        }
    })
    client = FakeClient([geo, forecast])

    result = get_hourly_pressure("Воронеж", date(2026, 11, 1), days=3, client=client)

    assert result["timezone"] == "Europe/Moscow"
    assert len(result["hours"]) == 4
    assert result["hours"][0]["pressure"] == 750.06
    assert result["hours"][-1]["time"] == "2026-11-03T00:00"
    assert client.calls[1][1]["timezone"] == "Europe/Moscow"


def test_get_hourly_pressure_validates_day_limit():
    with pytest.raises(ValueError):
        get_hourly_pressure("Воронеж", date(2026, 11, 1), days=4, client=FakeClient([]))


def test_get_ensemble_pressure_uses_three_day_horizon_and_filters_hours():
    from app.providers.open_meteo_ensemble import get_ensemble_pressure

    times = [
        "2026-11-01T00:00", "2026-11-01T01:00",
        "2026-11-02T00:00", "2026-11-03T23:00",
        "2026-11-04T00:00",
    ]
    payload = {
        "hourly": {
            "time": times,
            "pressure_msl_member01": [1000, 1001, 1002, 1003, 1004],
            "pressure_msl_member02": [1001, 1002, 1003, 1004, 1005],
        }
    }
    client = FakeClient([FakeResponse(payload)])

    result = get_ensemble_pressure(
        51.66, 39.20, date(2026, 11, 1), hours=72, client=client
    )

    assert len(result["hours"]) == 4
    assert result["model"] == "dwd_icon_seamless_eps"
    assert client.calls[0][1]["forecast_days"] == 3
    assert client.calls[0][1]["timezone"] == "Europe/Moscow"
    assert client.calls[0][1]["models"] == "dwd_icon_seamless_eps"
    assert client.calls[0][1]["hourly"] == "pressure_msl"
    # Open-Meteo documents native hourly output without a temporal_resolution
    # request parameter; do not send undocumented values.
    assert "temporal_resolution" not in client.calls[0][1]
