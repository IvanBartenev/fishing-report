NORMAL_PRESSURE = 760.0


def calculate_scores(pressure_series: list[dict]) -> list[dict]:
    if not pressure_series:
        return []

    result = []

    for i, point in enumerate(pressure_series):
        score = 100
        reasons = []
        p_today = point["pressure"]

        # --- 1. Оцениваем СКАЧОК (Волатильность) ---
        # Сравниваем только с предыдущим днем! Это самое важное для рыбы.
        if i > 0:
            p_yesterday = pressure_series[i - 1]["pressure"]
            daily_diff = abs(p_today - p_yesterday)

            if daily_diff > 5:
                score -= 35
                reasons.append(f"резкий скачок {daily_diff:.1f} мм")
            elif daily_diff > 2.5:
                score -= 15
                reasons.append(f"умеренный скачок {daily_diff:.1f} мм")
            else:
                reasons.append("стабильно")

        # --- 2. Оцениваем ТРЕНД (Направление за 2 дня) ---
        if i >= 2:
            p_day_before = pressure_series[i - 2]["pressure"]
            trend = p_today - p_day_before

            # Плавное снижение (от -1 до -3 мм за 2 дня) - это идеал
            if -3.0 <= trend < -0.5:
                reasons.append("плавное снижение")
            # Резкое падение (больше 4 мм за 2 дня) - рыба замирает
            elif trend < -4.0:
                score -= 20
                reasons.append("затяжное падение")
            # Активный рост - тоже плохо
            elif trend >= 4.0:
                score -= 20
                reasons.append("активный рост")
        elif i == 1:
            reasons.append("мало данных для тренда")

        # --- 3. Отклонение от нормы ---
        deviation = abs(p_today - NORMAL_PRESSURE)
        if deviation > 15:
            score -= 30
            reasons.append(f"сильное отклонение от нормы")
        elif deviation > 8:
            score -= 15
            reasons.append(f"отклонение от нормы")

        final_score = max(0, min(100, score))

        result.append({
            "date": point["date"],
            "score": final_score,
            "reason": ", ".join(reasons) if reasons else "идеально"
        })

    return result