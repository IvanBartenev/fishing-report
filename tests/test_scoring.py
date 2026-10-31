import pytest
from app.domain.scoring import calculate_scores

def test_stable_pressure():
    # Идеальный график: давление ровное и близко к норме
    series = [
        {"date": "2026-10-31", "pressure": 745.0},
        {"date": "2026-11-01", "pressure": 745.0},
        {"date": "2026-11-02", "pressure": 745.0},
    ]
    scores = calculate_scores(series)
    assert scores[1]["score"] == 100
    assert scores[2]["score"] == 100

def test_sharp_drop():
    # Резкое падение на 10 мм И сильное отклонение от нормы
    series = [
        {"date": "2026-10-31", "pressure": 755.0},
        {"date": "2026-11-01", "pressure": 735.0},  # 735 сильно отличается от 745
    ]
    scores = calculate_scores(series)
    # 100 - 30 (за скачок) - 30 (сильное отклонение от нормы) = 40
    assert scores[1]["score"] < 60
    assert "резкий скачок" in scores[1]["reason"]

def test_smooth_decrease():
    # Плавное снижение на 1.5 мм в сутки - должно быть высоко
    series = [
        {"date": "2026-10-31", "pressure": 746.0},
        {"date": "2026-11-01", "pressure": 744.5},
    ]
    scores = calculate_scores(series)
    # 100 - 0 (за скачок) + 5 (за плавное снижение) = 100 (так как 105 обрезается до 100)
    assert scores[1]["score"] >= 95

def test_abnormal_pressure():
    # Давление стабильное, но аномально низкое (например, 720)
    series = [
        {"date": "2026-10-31", "pressure": 720.0},
        {"date": "2026-11-01", "pressure": 720.0},
    ]
    scores = calculate_scores(series)
    # 100 - 30 (сильное отклонение) = 70
    assert scores[1]["score"] < 75
    assert "сильное отклонение" in scores[1]["reason"]