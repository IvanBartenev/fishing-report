from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta
from app.providers.open_meteo import get_pressure
from app.domain.scoring import calculate_scores

app = FastAPI(title="Fishing Report")

# Указываем папку с HTML-шаблонами
templates = Jinja2Templates(directory="app/templates")

# 1. Эндпоинт для отдачи HTML-страницы
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # Новый правильный синтаксис: request передается отдельно, а не в словаре
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )

# 2. Эндпоинт для API (оставляем как было, он будет вызываться из JS)
@app.get("/report")
def report(city: str = Query(...), days: int = Query(7, ge=1, le=30)):
    # 1. Период, который хочет видеть пользователь
    start = date.today()
    end = start + timedelta(days=days - 1)

    # 2. Запрашиваем данные на 3 дня РАНЬШЕ, чтобы был контекст для первого дня
    fetch_start = start - timedelta(days=3)

    # Получаем полный список дней (включая 3 дня истории)
    series = get_pressure(city, fetch_start, end)

    # Считаем скоры для ВСЕХ дней (нам нужна история для расчетов)
    scores = calculate_scores(series)

    # 3. Объединяем данные
    combined_days = []
    for i in range(len(scores)):
        combined_days.append({
            "date": scores[i]["date"],
            "score": scores[i]["score"],
            "reason": scores[i]["reason"],
            "pressure": series[i]["pressure"]
        })

    # 4. Оставляем только те дни, которые попадают в запрошенный период (отрезаем историю)
    # Переводим дату начала в строку для сравнения
    start_str = start.isoformat()
    filtered_days = [day for day in combined_days if day["date"] >= start_str]

    return {
        "city": city,
        "period": {"start": start, "end": end},
        "days": filtered_days
    }

#uvicorn app.main:app --reload --host 127.0.0.1 --port 8001 - запуск в терминале