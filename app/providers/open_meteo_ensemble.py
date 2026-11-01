"""Open-Meteo Ensemble provider for hourly sea-level pressure forecasts."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

import httpx

from app.cache.memory import get_cache, set_cache

API_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
DEFAULT_MODEL = "dwd_icon_seamless_eps"
TIMEZONE = "Europe/Moscow"
HPA_TO_MMHG = 0.750061683


class EnsembleUnavailableError(RuntimeError):
    """Raised when the ensemble forecast cannot be retrieved or parsed."""


def _member_pressure_keys(hourly: dict[str, Any]) -> list[str]:
    """Return individual ensemble-member pressure fields only."""
    return sorted(
        key for key in hourly
        if re.fullmatch(r"pressure_msl_member\d+", key)
    )


def parse_ensemble_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize ensemble member arrays into timestamped pressure samples.

    Values are converted from hPa to mmHg. Missing member values are skipped;
    no temporal or spatial interpolation is performed.
    """
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise EnsembleUnavailableError("Open-Meteo Ensemble не вернул hourly данные")

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise EnsembleUnavailableError("В ансамблевом ответе отсутствуют временные метки")

    member_keys = _member_pressure_keys(hourly)
    if not member_keys:
        raise EnsembleUnavailableError("В ответе нет отдельных участников pressure_msl")

    samples = []
    for index, timestamp in enumerate(times):
        values = []
        for key in member_keys:
            series = hourly.get(key)
            value = series[index] if isinstance(series, list) and index < len(series) else None
            if isinstance(value, (int, float)):
                values.append(round(float(value) * HPA_TO_MMHG, 2))
            else:
                # Keep the member slot: removing nulls would shift member IDs
                # between timestamps and corrupt member-by-member trajectories.
                values.append(None)
        samples.append({"time": timestamp, "member_pressures": values})

    return {
        "timezone": payload.get("timezone", TIMEZONE),
        "member_count": len(member_keys),
        "hours": samples,
    }


def get_ensemble_pressure(
    latitude: float,
    longitude: float,
    start_date: date,
    hours: int = 72,
    model: str = DEFAULT_MODEL,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch hourly ensemble pressure scenarios for a location.

    ``client`` is injectable to make provider behavior testable without network.
    The model identifier defaults to DWD ICON EPS Seamless (global coverage).
    """
    if not 1 <= hours <= 120:
        raise ValueError("hours должен быть от 1 до 120")

    cache_key = (
        f"ensemble_pressure:{latitude:.4f}:{longitude:.4f}:"
        f"{start_date.isoformat()}:{hours}:{model}:{TIMEZONE}"
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "models": model,
        "hourly": "pressure_msl",
        "timezone": TIMEZONE,
        # Ensemble API time series starts at local 00:00; request three
        # calendar days so the UI can show complete day panels.
        "forecast_days": 3,
    }

    owns_client = client is None
    http_client = client or httpx.Client(timeout=20.0)
    try:
        response = http_client.get(API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise EnsembleUnavailableError(f"Не удалось получить Ensemble прогноз: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    result = parse_ensemble_response(payload)
    start_at = datetime.combine(start_date, time.min)
    end_at = start_at + timedelta(hours=hours)
    result["hours"] = [
        item for item in result["hours"]
        if start_at <= datetime.fromisoformat(str(item["time"])) < end_at
    ]
    if not result["hours"]:
        raise EnsembleUnavailableError("Ensemble не вернул данные для выбранных трёх дней")
    result["model"] = model
    set_cache(cache_key, result)
    return result
