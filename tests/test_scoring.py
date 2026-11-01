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
    assert scores[2]["score"] == 100
    # Проверяем новый текст причины
    assert "стабильно" in scores[2]["reason"]

def test_sharp_drop():
    # Резкое падение на 15 мм И сильное отклонение от нормы
    series = [
        {"date": "2026-10-31", "pressure": 765.0},
        {"date": "2026-11-01", "pressure": 765.0},
        {"date": "2026-11-02", "pressure": 750.0}, # Резкое падение
    ]
    scores = calculate_scores(series)
    # 100 - 35 (за скачок) - 20 (за падение) - 15 (отклонение) = 30
    assert scores[2]["score"] < 60
    # Проверяем новый текст
    assert "резкий скачок" in scores[2]["reason"]

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