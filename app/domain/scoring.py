# Норма давления для Центрального Черноземья (Воронеж)
NORMAL_PRESSURE = 745.0


def calculate_scores(pressure_series: list[dict]) -> list[dict]:
    """
    pressure_series: [{"date": "2026-10-30", "pressure": 745.2}, ...]
    Возвращает: [{"date": ..., "score": 0-100, "reason": "..."}]
    """
    if not pressure_series:
        return []

    result = []

    for i, point in enumerate(pressure_series):
        score = 100  # Начинаем со 100 баллов и штрафуем
        reasons = []

        # 1. Штраф за скачок по сравнению с прошлым днем (Стабильность)
        if i > 0:
            diff = abs(point["pressure"] - pressure_series[i - 1]["pressure"])
            if diff > 5:
                score -= 30
                reasons.append(f"резкий скачок {diff:.1f} мм")
            elif diff > 2:
                score -= 10
                reasons.append(f"умеренное изменение {diff:.1f} мм")
            else:
                reasons.append("стабильно")
        else:
            reasons.append("нет данных за вчера")

        # 2. Штраф за отклонение от нормы региона
        deviation = abs(point["pressure"] - NORMAL_PRESSURE)
        if deviation > 15:
            score -= 30
            reasons.append(f"сильное отклонение от нормы ({point['pressure']} мм)")
        elif deviation > 8:
            score -= 15
            reasons.append(f"отклонение от нормы ({point['pressure']} мм)")

        # 3. Бонус за плавное снижение (если оно есть и оно небольшое)
        if i > 0:
            trend = point["pressure"] - pressure_series[i - 1]["pressure"]
            if -2.0 <= trend < 0:
                score += 5
                reasons.append("плавное снижение (хорошо)")
            elif trend >= 2.0:
                score -= 10
                reasons.append("активный рост давления (плохо)")

        # Ограничиваем скор рамками от 0 до 100
        final_score = max(0, min(100, score))

        result.append({
            "date": point["date"],
            "score": final_score,
            "reason": ", ".join(reasons)
        })

    return result