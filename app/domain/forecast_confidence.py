"""Ensemble-derived spread for the hourly conditions index."""
from __future__ import annotations

from typing import Any
import math

from app.domain.hourly_analysis import calculate_hourly_index


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def calculate_ensemble_confidence(
    ensemble_hours: list[dict[str, Any]],
    min_members: int = 5,
) -> list[dict[str, Any]]:
    """Calculate median and 10-90 percentile index range per timestamp.

    The range describes model-member disagreement; it is not a calibrated
    probability interval or a guarantee of forecast coverage.
    """
    if not ensemble_hours:
        return []

    # Build one pressure trajectory per member, preserving exact timestamps.
    member_ids = sorted({
        index
        for sample in ensemble_hours
        for index, value in enumerate(sample.get("member_pressures", []))
        if isinstance(value, (int, float))
    })
    trajectories = {}
    for member_index in member_ids:
        trajectory = []
        for sample in ensemble_hours:
            values = sample.get("member_pressures", [])
            if member_index < len(values) and isinstance(values[member_index], (int, float)):
                trajectory.append({
                    "time": sample["time"],
                    "pressure": float(values[member_index]),
                })
        trajectories[member_index] = calculate_hourly_index(trajectory)

    scores_by_time: dict[str, list[float]] = {}
    for trajectory in trajectories.values():
        for item in trajectory:
            scores_by_time.setdefault(item["time"], []).append(float(item["score"]))

    result = []
    for timestamp in sorted(scores_by_time):
        values = scores_by_time[timestamp]
        if len(values) < min_members:
            result.append({
                "time": timestamp, "available": False, "member_count": len(values),
                "score_lower": None, "score_median": None, "score_upper": None,
                "spread": None, "level": "unavailable",
            })
            continue
        lower = _percentile(values, 0.10)
        median = _percentile(values, 0.50)
        upper = _percentile(values, 0.90)
        spread = upper - lower
        if spread <= 8:
            level = "high"
        elif spread <= 16:
            level = "medium"
        else:
            level = "low"
        result.append({
            "time": timestamp,
            "available": True,
            "member_count": len(values),
            "score_lower": round(lower, 1),
            "score_median": round(median, 1),
            "score_upper": round(upper, 1),
            "spread": round(spread, 1),
            "level": level,
        })
    return result
