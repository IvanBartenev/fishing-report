import pytest
from app.domain.scoring import calculate_scores

def test_stable_pressure():
    # Идеальный график: 3 дня подряд давление 760 (ровно норма)
    series = [
        {"date": "2026-10-31", "pressure": 760.0},
        {"date": "2026-11-01", "pressure": 760.0},
        {"date": "2026-11-02", "pressure": 760.0},
    ]
    scores = calculate_scores(series)
    # Третий день (индекс 2) должен иметь 100 баллов, так как есть история за 3 дня и нет отклонений
    assert scores[2]["score"] == 100
    assert "стабильно 3 дня" in scores[2]["reason"]

def test_sharp_drop():
    # Резкое падение на 10 мм И сильное отклонение от нормы (но теперь нужно 3 дня для тренда)
    series = [
        {"date": "2026-10-31", "pressure": 765.0},
        {"date": "2026-11-01", "pressure": 765.0},
        {"date": "2026-11-02", "pressure": 750.0}, # Резкое падение и отклонение
    ]
    scores = calculate_scores(series)
    # 100 - 40 (сильный разброс) - 15 (отклонение) = 45
    assert scores[2]["score"] < 60
    assert "сильный разброс" in scores[2]["reason"]

def test_smooth_decrease():
    # Плавное снижение на 1.5 мм в сутки (в пределах нормы)
    series = [
        {"date": "2026-10-31", "pressure": 762.0},
        {"date": "2026-11-01", "pressure": 760.5},
        {"date": "2026-11-02", "pressure": 759.0},
    ]
    scores = calculate_scores(series)
    # Разброс 3 мм (умеренный), тренд -3 (плавное снижение)
    assert scores[2]["score"] >= 85
    assert "плавное снижение" in scores[2]["reason"]

def test_abnormal_pressure():
    # Давление стабильное, но аномально низкое (например, 720)
    series = [
        {"date": "2026-10-31", "pressure": 720.0},
        {"date": "2026-11-01", "pressure": 720.0},
        {"date": "2026-11-02", "pressure": 720.0},
    ]
    scores = calculate_scores(series)
    # 100 - 30 (сильное отклонение) = 70
    assert scores[2]["score"] < 75
    assert "сильное отклонение" in scores[2]["reason"]

#python -m pytest