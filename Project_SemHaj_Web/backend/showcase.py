"""Данные для главной витрины и подбора города: лидеры, рейтинг и профили городов."""
from functools import wraps
from typing import Callable, Any
import numpy as np
import pandas as pd
from .database.models import db, ImportLog, Vacancy
from .services import frame, summary, competition_rows

EXPERIENCE = ["Без опыта", "1-3 года", "3-6 лет", "Более 6 лет"]
MIN_RELIABLE = 30

_cache: dict = {}

def data_version() -> tuple:
    """Определить версию данных: последний импорт и число вакансий."""
    return (db.session.scalar(db.select(db.func.max(ImportLog.id))), db.session.scalar(db.select(db.func.count(Vacancy.id))))

def cached(function: Callable) -> Callable:
    """Запомнить результат расчёта, пока данные не изменились, чтобы страницы открывались быстро."""
    @wraps(function)
    def wrapper(*args: Any) -> Any:
        """Вернуть сохранённый результат или рассчитать заново при новой версии данных."""
        version = data_version()
        key = (function.__name__, args)
        if key not in _cache or _cache[key][0] != version:
            _cache[key] = (version, function(*args))
        return _cache[key][1]
    return wrapper

def money(value: float) -> str:
    """Записать сумму по-русски: 120 000 ₽."""
    return f"{round(value):,}".replace(",", " ") + " ₽"

def plural(number: int, one: str, few: str, many: str) -> str:
    """Подобрать форму слова к числу: 1 вакансия, 2 вакансии, 5 вакансий."""
    tail = number % 100
    word = many if 11 <= tail <= 14 else one if tail % 10 == 1 else few if 2 <= tail % 10 <= 4 else many
    return f"{number:,}".replace(",", " ") + " " + word

def percent(value: float) -> str:
    """Записать долю в процентах: 4,5%."""
    return f"{value:.1f}".replace(".", ",") + "%"

@cached
def base_frame() -> pd.DataFrame:
    """Запомнить все вакансии, чтобы фильтры по профессии и опыту срабатывали сразу."""
    return frame()

@cached
def cached_summary(category: str = "") -> list[dict]:
    """Запомнить сводку по городам выбранной области."""
    return summary(category)

@cached
def rating_data(category: str = "", experience: str = "") -> list[dict]:
    """Собрать показатели городов для выбранной области и опыта."""
    population = base_frame()
    if experience:
        population = population[population.experience == experience]
    data = population[population.category == category] if category else population
    if data.empty:
        return []
    totals, total = population.groupby("city").size(), len(population)
    competition = {r["city"]: r for r in competition_rows(data)["rows"]}
    rows = []
    for city, group in data.groupby("city", sort=True):
        salary = group.salary.dropna()
        comp = competition.get(city)
        row = {"city": city, "count": len(group), "remote": round(float(group.remote.mean()) * 100, 1),
            "salary": round(float(salary.median())) if len(salary) else None, "salary_count": len(salary),
            "distribution": [round(float(v)) for v in np.percentile(salary, range(101))] if len(salary) else [],
            "competition": comp["index"] if comp else None, "week": round(comp["rate"] * 7) if comp else None,
            "share": round(100 * len(group) / int(totals[city]), 2) if category else round(100 * len(group) / total, 2),
            "coefficient": round(len(group) / int(totals[city]) / (len(data) / total), 2) if category else None}
        rows.append(row)
    return rows

def leaders(rows: list[dict]) -> list[dict]:
    """Выбрать три города с самыми заметными показателями."""
    reliable = [r for r in rows if r["count"] >= MIN_RELIABLE]
    if not reliable:
        return []
    result = []
    active = max(reliable, key=lambda r: r["count"])
    result.append({"title": "Самый активный рынок", "city": active["city"], "value": plural(active["count"], "вакансия", "вакансии", "вакансий")})
    paid = [r for r in reliable if r["salary"]]
    if paid:
        best = max(paid, key=lambda r: r["salary"])
        result.append({"title": "Выше всего зарплаты", "city": best["city"], "value": "обычно " + money(best["salary"])})
    known = [r for r in reliable if r["week"] is not None]
    if known:
        calm = min(known, key=lambda r: r["week"])
        result.append({"title": "Меньше всего откликов", "city": calm["city"], "value": "≈ " + plural(calm["week"], "отклик", "отклика", "откликов") + " в неделю на вакансию"})
    return result

@cached
def city_profiles(min_count: int = 150, top: int = 3) -> dict[str, dict]:
    """Для каждого города найти, что он ищет чаще других и какие профессии оплачиваются лучше всего."""
    data = base_frame()
    total = len(data)
    by_category = data.category.value_counts()
    profiles = {}
    for city, group in data.groupby("city", sort=True):
        counts = group.category.value_counts()
        famous = []
        for category, count in counts.items():
            coefficient = float((count / len(group)) / (by_category[category] / total))
            if count >= min_count and coefficient >= 1.1 and category != "Другое":
                famous.append({"category": category, "coefficient": round(coefficient, 2), "share": percent(100 * count / len(group)),
                    "average": percent(100 * by_category[category] / total), "average_width": round(100 / coefficient)})
        famous.sort(key=lambda i: i["coefficient"], reverse=True)
        paid = []
        for category, part in group.groupby("category"):
            salary = part.salary.dropna()
            if len(salary) >= 100:
                paid.append({"category": category, "salary": round(float(salary.median()), -3), "top": round(float(salary.quantile(.9)), -3)})
        paid.sort(key=lambda i: i["salary"], reverse=True)
        profiles[city] = {"famous": famous[:top], "paid": paid[:top]}
    return profiles

@cached
def city_notes() -> dict[str, dict]:
    """Составить для карточки города короткие факты без общих оценок."""
    rows = rating_data("")
    profiles = city_profiles()
    most = max(rows, key=lambda r: r["count"])["city"] if rows else None
    least = min(rows, key=lambda r: r["count"])["city"] if rows else None
    notes = {}
    for r in rows:
        p = profiles.get(r["city"], {"famous": [], "paid": []})
        badge = "Самый активный рынок" if r["city"] == most else "Самый спокойный рынок" if r["city"] == least else ""
        notes[r["city"]] = {"badge": badge, "famous": p["famous"][:2], "paid": [
            {"category": i["category"], "salary": money(i["salary"]), "top": money(i["top"])} for i in p["paid"][:2]]}
    return notes

@cached
def showcase_data(category: str = "") -> dict:
    """Собрать данные главной страницы."""
    rows = rating_data(category)
    profiles = city_profiles()
    cities = sorted(rating_data(""), key=lambda r: r["count"], reverse=True)
    return {"leaders": leaders(rows),
            "specialties": [{"city": r["city"], "items": profiles[r["city"]]["famous"]} for r in cities if r["city"] in profiles]}
