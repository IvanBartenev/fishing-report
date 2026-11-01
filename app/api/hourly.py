"""Hourly report endpoint: deterministic pressure plus ensemble uncertainty."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from app.domain.hourly_analysis import calculate_hourly_index
from app.domain.forecast_confidence import calculate_ensemble_confidence
from app.providers.open_meteo_hourly import get_hourly_pressure, HourlyForecastError
from app.providers.open_meteo_ensemble import (
    get_ensemble_pressure,
    EnsembleUnavailableError,
)

router = APIRouter()
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def build_hourly_report(
    city: str,
    target_date: date,
    deterministic_data: dict,
    ensemble_data: dict | None,
) -> dict:
    """Join deterministic and ensemble results by exact local timestamp."""
    deterministic_hours = deterministic_data.get("hours", [])
    indexed = calculate_hourly_index(deterministic_hours)
    index_by_time = {point["time"]: point for point in indexed}

    confidence_by_time = {}
    if ensemble_data:
        confidence = calculate_ensemble_confidence(ensemble_data.get("hours", []))
        confidence_by_time = {point["time"]: point for point in confidence}

    day_prefix = target_date.isoformat()
    day_points = []
    for point in deterministic_hours:
        timestamp = point.get("time")
        if not isinstance(timestamp, str) or not timestamp.startswith(day_prefix):
            continue
        index_point = index_by_time.get(timestamp)
        if index_point is None:
            continue
        confidence_point = confidence_by_time.get(timestamp, {})
        day_points.append({
            "time": timestamp,
            "pressure": point.get("pressure"),
            "score": index_point["score"],
            "reason": index_point["reason"],
            "score_lower": confidence_point.get("score_lower"),
            "score_upper": confidence_point.get("score_upper"),
            "score_median": confidence_point.get("score_median"),
            "confidence_level": confidence_point.get("level", "unavailable"),
            "member_count": confidence_point.get("member_count", 0),
        })

    if not day_points:
        raise ValueError("Для выбранной даты нет почасовых данных")

    available = [
        p for p in day_points
        if p["score_lower"] is not None and p["score_upper"] is not None
    ]
    if available:
        average_spread = round(median(
            p["score_upper"] - p["score_lower"] for p in available
        ), 1)
        levels = [p["confidence_level"] for p in available]
        # Report a conservative daily summary: the weakest level occurring
        # in at least one quarter of the available hourly points.
        counts = {level: levels.count(level) for level in ("low", "medium", "high")}
        if counts["low"] >= max(1, len(levels) // 4):
            level = "low"
        elif counts["medium"] >= max(1, len(levels) // 4):
            level = "medium"
        else:
            level = "high"
        confidence_meta = {
            "available": True,
            "level": level,
            "method": "ensemble_member_percentiles_10_50_90",
            "model": ensemble_data.get("model"),
            "member_count": min(p["member_count"] for p in available),
            "median_spread": average_spread,
            "description": "Согласованность ансамблевых сценариев; диапазон не является откалиброванной вероятностью",
        }
    else:
        confidence_meta = {
            "available": False,
            "level": "unavailable",
            "method": None,
            "model": ensemble_data.get("model") if ensemble_data else None,
            "member_count": 0,
            "median_spread": None,
            "description": "Ансамблевый диапазон недоступен",
        }

    return {
        "city": city,
        "date": target_date.isoformat(),
        "timezone": "Europe/Moscow",
        "confidence": confidence_meta,
        "hours": day_points,
    }


@router.get("/report/hourly")
def hourly_report(
    city: str = Query(..., min_length=1, max_length=100),
    target_date: date = Query(..., alias="date"),
):
    today_moscow = datetime.now(MOSCOW_TZ).date()
    last_allowed_date = today_moscow + timedelta(days=2)
    if not today_moscow <= target_date <= last_allowed_date:
        raise HTTPException(
            status_code=422,
            detail=f"Почасовой прогноз доступен только на {today_moscow} — {last_allowed_date}",
        )

    try:
        deterministic = get_hourly_pressure(city, today_moscow, days=3)
    except (HourlyForecastError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    ensemble = None
    try:
        ensemble = get_ensemble_pressure(
            deterministic["latitude"],
            deterministic["longitude"],
            today_moscow,
            hours=72,
        )
    except (EnsembleUnavailableError, ValueError):
        # The deterministic hourly chart remains useful without an
        # ensemble; do not fabricate uncertainty bands.
        ensemble = None

    try:
        return build_hourly_report(city, target_date, deterministic, ensemble)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
