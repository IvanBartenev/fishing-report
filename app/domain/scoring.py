NORMAL_PRESSURE = 760.0


def calculate_scores(pressure_series: list[dict]) -> list[dict]:
    if not pressure_series:
        return []

    result = []

    for i, point in enumerate(pressure_series):
        score = 100
        reasons = []

        # 1. Оцениваем стабильность по окну в 3 дня (сегодня и два предыдущих)
        if i >= 2:
            p_today = point["pressure"]
            p_yesterday = pressure_series[i - 1]["pressure"]
            p_day_before = pressure_series[i - 2]["pressure"]

            # Считаем общий разброс (максимальное минус минимальное за 3 дня)
            max_p = max(p_today, p_yesterday, p_day_before)
            min_p = min(p_today, p_yesterday, p_day_before)
            spread = max_p - min_p

            if spread > 6:
                score -= 40
                reasons.append(f"сильный разброс за 3 дня ({spread:.1f} мм)")
            elif spread > 3:
                score -= 15
                reasons.append(f"умеренный разброс ({spread:.1f} мм)")
            else:
                reasons.append("стабильно 3 дня")

            # 2. Смотрим на общий тренд (куда движемся от позавчера к сегодня)
            trend = p_today - p_day_before
            if -4.0 <= trend < -1.0:
                score += 5
                reasons.append("плавное снижение")
            elif trend <= -4.0:
                score -= 20
                reasons.append("резкое падение")

        else:
            # Для первых двух дней истории еще нет, оцениваем мягко
            if i > 0:
                diff = abs(point["pressure"] - pressure_series[i - 1]["pressure"])
                if diff > 3: score -= 15
            reasons.append("мало данных для тренда")

        # 3. Отклонение от нормы (без изменений)
        deviation = abs(point["pressure"] - NORMAL_PRESSURE)
        if deviation > 15:
            score -= 30
            reasons.append(f"сильное отклонение ({point['pressure']} мм)")
        elif deviation > 8:
            score -= 15
            reasons.append(f"отклонение ({point['pressure']} мм)")

        final_score = max(0, min(100, score))

        result.append({
            "date": point["date"],
            "score": final_score,
            "reason": ", ".join(reasons) if reasons else "отличный день"
        })

    return result