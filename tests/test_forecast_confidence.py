from app.domain.forecast_confidence import calculate_ensemble_confidence


def test_empty_ensemble_is_unavailable():
    assert calculate_ensemble_confidence([]) == []


def test_ensemble_spread_is_calculated():
    samples = []
    for hour in range(30):
        samples.append({
            "time": f"2026-11-01T{hour % 24:02d}:00" if hour < 24
                    else f"2026-11-02T{hour - 24:02d}:00",
            "member_pressures": [760 + member * 0.1 for member in range(10)],
        })
    result = calculate_ensemble_confidence(samples)
    assert result
    assert result[-1]["available"] is True
    assert result[-1]["score_lower"] <= result[-1]["score_median"] <= result[-1]["score_upper"]
    assert result[-1]["level"] in {"high", "medium", "low"}


def test_too_few_members_are_unavailable():
    samples = [{
        "time": "2026-11-01T00:00",
        "member_pressures": [760.0, 761.0, 762.0],
    }]
    result = calculate_ensemble_confidence(samples, min_members=5)
    assert result[0]["available"] is False
    assert result[0]["score_lower"] is None


def test_member_positions_are_preserved_when_values_are_missing():
    from app.providers.open_meteo_ensemble import parse_ensemble_response

    parsed = parse_ensemble_response({
        "hourly": {
            "time": ["2026-11-01T00:00", "2026-11-01T01:00"],
            "pressure_msl_member01": [1000.0, None],
            "pressure_msl_member02": [None, 1002.0],
        }
    })
    first, second = parsed["hours"]
    assert len(first["member_pressures"]) == 2
    assert len(second["member_pressures"]) == 2
    assert first["member_pressures"][1] is None
    assert second["member_pressures"][0] is None
