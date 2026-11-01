from datetime import datetime, timedelta
from fastapi.testclient import TestClient

import app.api.hourly as hourly_api
from app.main import app


def make_hours(start, count=72):
    return [
        {"time": (start + timedelta(hours=i)).isoformat(timespec="minutes"),
         "pressure": 760.0 + (i % 5) * 0.1}
        for i in range(count)
    ]


def test_build_hourly_report_returns_one_calendar_day():
    start = datetime(2026, 11, 1)
    deterministic = {"hours": make_hours(start)}
    ensemble = {
        "model": "test-model",
        "hours": [
            {"time": (start + timedelta(hours=i)).isoformat(timespec="minutes"),
             "member_pressures": [760.0 + j * 0.05 for j in range(10)]}
            for i in range(72)
        ],
    }
    result = hourly_api.build_hourly_report(
        "Воронеж", start.date(), deterministic, ensemble
    )
    assert result["timezone"] == "Europe/Moscow"
    assert len(result["hours"]) == 24
    assert result["confidence"]["available"] is True
    assert result["hours"][0]["score_lower"] is not None


def test_build_hourly_report_without_ensemble_has_no_fake_band():
    start = datetime(2026, 11, 1)
    result = hourly_api.build_hourly_report(
        "Воронеж", start.date(), {"hours": make_hours(start)}, None
    )
    assert result["confidence"]["available"] is False
    assert result["confidence"]["level"] == "unavailable"
    assert all(p["score_lower"] is None and p["score_upper"] is None
               for p in result["hours"])


def test_endpoint_returns_hourly_data_and_degrades_without_ensemble(monkeypatch):
    from datetime import date
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    start = datetime.combine(today, datetime.min.time())
    monkeypatch.setattr(hourly_api, "get_hourly_pressure", lambda *a, **k: {
        "latitude": 51.66, "longitude": 39.20, "hours": make_hours(start)
    })
    def unavailable(*args, **kwargs):
        raise hourly_api.EnsembleUnavailableError("no ensemble")
    monkeypatch.setattr(hourly_api, "get_ensemble_pressure", unavailable)

    client = TestClient(app)
    response = client.get(f"/report/hourly?city=Воронеж&date={today.isoformat()}")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["hours"]) == 24
    assert payload["confidence"]["available"] is False


def test_endpoint_rejects_date_outside_three_day_horizon():
    from datetime import date
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    invalid_date = today + timedelta(days=3)
    client = TestClient(app)
    response = client.get(
        f"/report/hourly?city=Воронеж&date={invalid_date.isoformat()}"
    )
    assert response.status_code == 422
