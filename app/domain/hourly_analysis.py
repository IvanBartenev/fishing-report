"""Explainable heuristic for hourly pressure-condition favorability.

This is a relative conditions index, not a probability of catching fish.
Pressure changes are evaluated over overlapping windows so adjacent hourly
observations are treated as a continuous process rather than isolated events.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _pressure_at_or_before(points: list[dict[str, Any]], target: datetime):
    candidates = []
    for point in points:
        try:
            timestamp = _parse_time(point["time"])
            pressure = point.get("pressure")
        except (KeyError, TypeError, ValueError):
            continue
        if timestamp <= target and isinstance(pressure, (int, float)):
            candidates.append((timestamp, float(pressure)))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _window_change(points: list[dict[str, Any]], current_time: datetime,
                   current_pressure: float, window_hours: int):
    previous = _pressure_at_or_before(
        points, current_time - timedelta(hours=window_hours)
    )
    if previous is None:
        return None
    return current_pressure - previous


def calculate_hourly_index(pressure_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calculate a 0-100 conditions index from rolling pressure changes."""
    if not pressure_series:
        return []

    valid = sorted(
        [p for p in pressure_series
         if isinstance(p.get("time"), str) and isinstance(p.get("pressure"), (int, float))],
        key=lambda p: p["time"],
    )
    result = []
    for point in valid:
        now = _parse_time(point["time"])
        pressure = float(point["pressure"])
        score = 85
        reasons = []
        changes = {
            window: _window_change(valid, now, pressure, window)
            for window in (3, 6, 12, 24)
        }

        # Short-term instability is most relevant to abrupt local changes.
        d3 = changes[3]
        if d3 is not None:
            magnitude = abs(d3)
            if magnitude >= 3.0:
                score -= 18
                reasons.append(f"резкое изменение за 3 ч: {d3:+.1f} мм")
            elif magnitude >= 1.5:
                score -= 9
                reasons.append(f"заметное изменение за 3 ч: {d3:+.1f} мм")

        d6 = changes[6]
        if d6 is not None:
            magnitude = abs(d6)
            if magnitude >= 5.0:
                score -= 18
                reasons.append(f"значительное изменение за 6 ч: {d6:+.1f} мм")
            elif magnitude >= 2.5:
                score -= 9
                reasons.append(f"изменение за 6 ч: {d6:+.1f} мм")

        d12 = changes[12]
        if d12 is not None and abs(d12) >= 8.0:
            score -= 10
            reasons.append(f"выраженный тренд за 12 ч: {d12:+.1f} мм")

        d24 = changes[24]
        if d24 is not None and abs(d24) >= 12.0:
            score -= 10
            reasons.append(f"выраженный тренд за 24 ч: {d24:+.1f} мм")

        # A slow, modest fall is a weak positive signal, not a guarantee.
        if d6 is not None and -3.0 <= d6 <= -0.5 and (d3 is None or abs(d3) < 1.5):
            score += 5
            reasons.append("плавное снижение давления")

        if not reasons:
            reasons.append("без заметных изменений на доступном интервале")

        result.append({
            "time": point["time"],
            "pressure": round(pressure, 2),
            "score": max(0, min(100, score)),
            "reason": "; ".join(reasons),
            "changes": {f"{window}h": None if value is None else round(value, 2)
                        for window, value in changes.items()},
        })
    return result
