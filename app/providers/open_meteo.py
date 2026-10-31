import httpx
from datetime import date, timedelta
from app.cache.memory import get_cache, set_cache

# Норма давления для Воронежа (можно вынести в конфиг позже)
NORMAL_PRESSURE = 760

def get_pressure(city: str, start: date, end: date) -> list[dict]:
    """
    Возвращает список: [{"date": "2026-10-30", "pressure": 745.2}, ...]
    Использует Open-Meteo: геокодинг + forecast/archive.
    """
    # Формируем уникальный ключ для этого запроса
    cache_key = f"pressure_{city}_{start}_{end}"

    # Проверяем кэш
    cached_data = get_cache(cache_key)
    if cached_data:
        print(f"Взято из кэша: {cache_key}")
        return cached_data

    city_aliases = {
        "питер": "Санкт-Петербург",
        "спб": "Санкт-Петербург",
        "мск": "Москва",
        "екб": "Екатеринбург"
    }

    city_lower = city.strip().lower()
    actual_city = city_aliases.get(city_lower, city)

    # 1. Геокодинг города
    with httpx.Client(timeout=10.0) as client:
        geo = client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": actual_city, "count": 1, "language": "ru"},
        )
        geo_data = geo.json()
        if not geo_data.get("results"):
            raise ValueError(f"Город не найден: {city}")
        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]

        # 2. Запрос давления (прогноз + архив в одном эндпоинте)
        # Open-Meteo отдаёт pressure_msl (давление на уровне моря)
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": "pressure_msl",
            "timezone": "Europe/Moscow",
        }
        resp = client.get("https://api.open-meteo.com/v1/forecast", params=params)
        data = resp.json()

    # 3. Агрегируем по дням (среднее за день)
    hourly = data["hourly"]
    times = hourly["time"]
    pressures = hourly["pressure_msl"]

    daily: dict[str, list[float]] = {}
    for t, p in zip(times, pressures):
        if p is None:
            continue
        day = t[:10]
        daily.setdefault(day, []).append(p)

    result = []
    for d, vals in sorted(daily.items()):
        avg_hpa = sum(vals) / len(vals)
        # Переводим гектопаскали в мм ртутного столба
        avg_mmhg = avg_hpa * 0.75006
        result.append({"date": d, "pressure": round(avg_mmhg, 1)})

    set_cache(cache_key, result)
    return result

    return result