"""Live integration check for Open-Meteo Forecast and Ensemble APIs.

Run from the project root:
    python scripts/smoke_open_meteo.py [city]
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.open_meteo_hourly import get_hourly_pressure
from app.providers.open_meteo_ensemble import get_ensemble_pressure

TIMEZONE = ZoneInfo("Europe/Moscow")


def main() -> int:
    city = " ".join(sys.argv[1:]).strip() or "Воронеж"
    today = datetime.now(TIMEZONE).date()
    print(f"Город: {city}")
    print(f"Дата начала: {today.isoformat()} (Europe/Moscow)")

    try:
        deterministic = get_hourly_pressure(city, today, days=3)
        ensemble = get_ensemble_pressure(
            deterministic["latitude"],
            deterministic["longitude"],
            today,
            hours=72,
        )
    except Exception as exc:
        print(f"FAIL: запрос к Open-Meteo завершился ошибкой: {type(exc).__name__}: {exc}")
        return 1

    deterministic_by_time = {p["time"]: p for p in deterministic["hours"]}
    ensemble_by_time = {p["time"]: p for p in ensemble["hours"]}
    common_times = sorted(set(deterministic_by_time) & set(ensemble_by_time))
    member_counts = [
        len([v for v in ensemble_by_time[t]["member_pressures"] if isinstance(v, (int, float))])
        for t in common_times
    ]

    print(f"Координаты: {deterministic['latitude']:.4f}, {deterministic['longitude']:.4f}")
    print(f"Часовых точек Forecast: {len(deterministic_by_time)}")
    print(f"Часовых точек Ensemble: {len(ensemble_by_time)}")
    print(f"Совпадающих временных меток: {len(common_times)}")
    print(f"Модель: {ensemble.get('model')}")
    print(f"Участников модели (полей): {ensemble.get('member_count')}")
    print(f"Минимум числовых участников на совпадающий час: {min(member_counts) if member_counts else 0}")

    if not common_times:
        print("FAIL: временные метки Forecast и Ensemble не совпадают.")
        return 2
    if len(common_times) < 60:
        print("WARN: совпало менее 60 часов из ожидаемых 72.")
    if not member_counts or min(member_counts) < 5:
        print("WARN: для части часов недостаточно числовых участников ансамбля.")
    if deterministic.get("timezone") != "Europe/Moscow" or ensemble.get("timezone") != "Europe/Moscow":
        print("FAIL: один из провайдеров вернул неожиданный часовой пояс.")
        return 3

    print("PASS: получены реальные ответы обоих сервисов и рассчитана совместимость по времени.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
