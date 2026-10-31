from datetime import datetime, timedelta

# Простейший кэш в памяти: {"ключ": (данные, время_создания)}
_cache = {}
CACHE_TTL_MINUTES = 60  # Храним данные 1 час

def get_cache(key: str):
    if key in _cache:
        data, timestamp = _cache[key]
        # Если данные старше TTL, удаляем их
        if datetime.now() - timestamp > timedelta(minutes=CACHE_TTL_MINUTES):
            del _cache[key]
            return None
        return data
    return None

def set_cache(key: str, data):
    _cache[key] = (data, datetime.now())