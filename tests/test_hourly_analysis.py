from datetime import datetime, timedelta

from app.domain.hourly_analysis import calculate_hourly_index


def series(values):
    return [
        {"time": (datetime(2026, 11, 1) + timedelta(hours=hour)).isoformat(timespec="minutes"),
         "pressure": pressure}
        for hour, pressure in enumerate(values)
    ]


def test_empty_series():
    assert calculate_hourly_index([]) == []


def test_stable_pressure_does_not_penalize():
    result = calculate_hourly_index(series([760.0] * 30))
    assert result[-1]["score"] == 85
    assert "без заметных изменений" in result[-1]["reason"]


def test_abrupt_change_reduces_score():
    values = [760.0] * 8 + [764.0] * 3
    result = calculate_hourly_index(series(values))
    assert result[-1]["score"] < result[7]["score"]


def test_gradual_fall_is_weak_positive_signal():
    values = [760.0 - 0.15 * i for i in range(10)]
    result = calculate_hourly_index(series(values))
    assert result[-1]["score"] >= 85
    assert "плавное снижение" in result[-1]["reason"]


def test_missing_context_is_handled():
    result = calculate_hourly_index([{"time": "2026-11-01T12:00", "pressure": 759.8}])
    assert result[0]["score"] == 85
    assert result[0]["changes"]["24h"] is None
