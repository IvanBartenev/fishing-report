"""Deterministic hourly pressure forecast from Open-Meteo Forecast API."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.cache.memory import get_cache, set_cache
from app.providers.open_meteo import resolve_city

API_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Europe/Moscow"
HPA_TO_MMHG = 0.750061683


class HourlyForecastError(RuntimeError):
    """Raised when hourly forecast data is unavailable or malformed."""


def get_hourly_pressure(
    city: str,
    start: date,
    days: int = 3,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Return hourly pressure values for up to three local calendar days.

    Open-Meteo's hourly forecast is requested with a calendar-day horizon so
    that the selected dates are complete in Europe/Moscow, rather than using
    a rolling 72-hour window that may start mid-day.
    """
    if not 1 <= days <= 3:
        raise ValueError("days должен быть от 1 до 3")

    cache_key = f"hourly_pressure:{city.strip().lower()}:{start.isoformat()}:{days}:{TIMEZONE}"
    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    owns_client = client is None
    http_client = client or httpx.Client(timeout=20.0)
    try:
        latitude, longitude = resolve_city(city, http_client)
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "pressure_msl",
            "timezone": TIMEZONE,
            "forecast_days": 3,
            "past_days": 0,
        }
        response = http_client.get(API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HourlyForecastError(f"Не удалось получить почасовой прогноз: {exc}") from exc
    finally:
        if owns_client:
            http_client.close()

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise HourlyForecastError("Open-Meteo не вернул почасовые данные")

    times = hourly.get("time")
    pressures = hourly.get("pressure_msl")
    if not isinstance(times, list) or not isinstance(pressures, list):
        raise HourlyForecastError("В ответе отсутствуют time или pressure_msl")

    end_date = date.fromordinal(start.toordinal() + days - 1)
    points = []
    for timestamp, pressure_hpa in zip(times, pressures):
        if not isinstance(timestamp, str) or not isinstance(pressure_hpa, (int, float)):
            continue
        local_date = timestamp[:10]
        if start.isoformat() <= local_date <= end_date.isoformat():
            points.append({
                "time": timestamp,
                "pressure": round(float(pressure_hpa) * HPA_TO_MMHG, 2),
            })

    if not points:
        raise HourlyForecastError("Для выбранного периода нет почасовых значений давления")

    result = {
        "city": city,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": TIMEZONE,
        "hours": points,
    }
    set_cache(cache_key, result)
    return result
