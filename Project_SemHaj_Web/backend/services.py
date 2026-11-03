"""Импорт, единые метрики и простая кластеризация городов."""
import numpy as np
import pandas as pd
from pathlib import Path
from sqlalchemy import delete
from .dataset import load_dataset
from .database.models import db, City, Category, WorkFormat, Vacancy, ImportLog

def import_dataset(path: Path) -> dict:
    """Атомарно заменить вакансии и справочники проверенным CSV."""
    data, report = load_dataset(path)
    if data.empty:
        raise ValueError("В наборе нет корректных вакансий")
    try:
        db.session.execute(delete(Vacancy))
        for model in [City, Category, WorkFormat]:
            db.session.execute(delete(model))
        maps = {}
        for model, col in [(City, "area_name"), (Category, "category"), (WorkFormat, "work_formats")]:
            objects = [model(name=name or "Не указан") for name in sorted(data[col].replace("", "Не указан").unique())]
            db.session.add_all(objects)
            db.session.flush()
            maps[col] = {item.name: item.id for item in objects}
        records = []
        for r in data.to_dict("records"):
            records.append({"id": r["vacancy_id"], "name": r["name"],
                "city_id": maps["area_name"][r["area_name"]], "category_id": maps["category"][r["category"]],
                "format_id": maps["work_formats"][r["work_formats"] or "Не указан"], "company": r["company"],
                "salary": None if pd.isna(r["salary"]) else float(r["salary"]),
                "responses": None if pd.isna(r["responses_count"]) else float(r["responses_count"]),
                "remote": r["is_remote"], "hybrid": r["is_hybrid"], "on_site": r["is_on_site"],
                "publication_time": r["publication_time"], "snapshot_date": r["snapshot_date"]})
        db.session.execute(db.insert(Vacancy), records)
        db.session.add(ImportLog(filename=path.name, rows=len(records)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return report

def frame(category: str = "", cities: list[str] | None = None) -> pd.DataFrame:
    """Получить вакансии по выбранной категории и городам."""
    query = db.select(Vacancy.id, Vacancy.name, City.name.label("city"), Category.name.label("category"),
        Vacancy.salary, Vacancy.responses, Vacancy.remote, Vacancy.hybrid, Vacancy.on_site,
        Vacancy.company, Vacancy.publication_time, Vacancy.snapshot_date).join(City, Vacancy.city_id == City.id).join(Category, Vacancy.category_id == Category.id)
    if category:
        query = query.where(Category.name == category)
    if cities:
        query = query.where(City.name.in_(cities))
    return pd.read_sql(query, db.session.connection())

def cluster_rows(rows: list[dict]) -> None:
    """Разделить города детерминированным k-means на три группы."""
    if not rows:
        return
    x = np.array([[r["count"], r["salary"] or 0, r["responses"] or 0, r["remote"]] for r in rows], dtype=float)
    x = (x - x.mean(axis=0)) / np.where(x.std(axis=0) == 0, 1, x.std(axis=0))
    k = min(3, len(np.unique(x, axis=0)))
    centers = x[np.linspace(0, len(x) - 1, k, dtype=int)].copy()
    for _ in range(50):
        labels = ((x[:, None] - centers) ** 2).sum(axis=2).argmin(axis=1)
        updated = np.array([x[labels == i].mean(axis=0) if np.any(labels == i) else centers[i] for i in range(k)])
        if np.allclose(centers, updated):
            break
        centers = updated
    for row, label in zip(rows, labels):
        row["cluster"] = "Группа " + str(int(label) + 1)

def summary(category: str = "", cities: list[str] | None = None) -> list[dict]:
    """Рассчитать метрики и относительный индекс спроса по городам."""
    data = frame(category)
    rows = []
    for city, group in data.groupby("city", sort=True):
        salary, responses = group.salary.dropna(), group.responses.dropna()
        rows.append({"city": city, "count": len(group),
            "salary": round(float(salary.median()), 2) if len(salary) else None,
            "responses": round(float(responses.mean()), 2) if len(responses) else None,
            "salary_known": len(salary), "responses_known": len(responses),
            "remote": round(float(group.remote.mean()) * 100, 2),
            "hybrid": round(float(group.hybrid.mean()) * 100, 2),
            "on_site": round(float(group.on_site.mean()) * 100, 2),
            "top_categories": group.category.value_counts().head(5).to_dict()})
    maximum = max((r["count"] for r in rows), default=1)
    for row in rows:
        row["indicator"] = round(100 * row["count"] / maximum, 2)
    cluster_rows(rows)
    return [r for r in rows if not cities or r["city"] in cities]

def recommendation(rows: list[dict]) -> str:
    """Сформировать описательное сравнение без оценки доступности кадров."""
    if not rows:
        return "Нет данных для рекомендации. Импортируйте CSV или измените фильтры."
    leader = max(rows, key=lambda r: r["count"])
    known = [r for r in rows if r["salary"] is not None]
    text = f"Наибольший объём опубликованного спроса: {leader['city']} ({leader['count']} вакансий). "
    if known:
        low = min(known, key=lambda r: r["salary"])
        text += f"Наименьшая медиана предлагаемой зарплаты: {low['city']} ({low['salary']:,.0f} руб./месяц). "
    return text + "Для выбора площадки дополнительно нужны данные о резюме, стоимости жизни и инфраструктуре."

def competition(category: str = "") -> dict:
    """Индекс конкуренции соискателей: медиана откликов в день на вакансию, 100 = как по всем городам."""
    data = frame(category)
    data = data[data.responses.notna()].copy()
    if data.empty:
        return {"rows": [], "overall": None}
    published = pd.to_datetime(data.publication_time, format="ISO8601", utc=True).dt.tz_convert(None).dt.normalize()
    age = (pd.to_datetime(data.snapshot_date) - published).dt.days.clip(lower=1)
    data["rate"] = data.responses / age
    overall = float(data.rate.median()) or float(data.rate.mean()) or 1.0
    rows = []
    for city, group in data.groupby("city", sort=True):
        salary = group.salary.dropna()
        index = round(100 * float(group.rate.median()) / overall, 1)
        rows.append({"city": city, "count": len(group), "rate": round(float(group.rate.median()), 2),
            "responses": round(float(group.responses.median()), 1), "no_response": round(float((group.responses == 0).mean()) * 100, 1),
            "salary": round(float(salary.median())) if len(salary) else None, "index": index,
            "level": "высокая" if index >= 120 else "низкая" if index <= 80 else "средняя"})
    rows.sort(key=lambda r: r["index"], reverse=True)
    return {"rows": rows, "overall": round(overall, 2)}

def competition_text(result: dict) -> str:
    """Описать крайние значения индекса конкуренции словами."""
    rows = result["rows"]
    if len(rows) < 2:
        return "Для сравнения нужно хотя бы два города с данными об откликах."
    top, low = rows[0], rows[-1]
    return (f"Больше всего соискателей на вакансию в городе {top['city']} (индекс {top['index']}), меньше всего — в городе {low['city']} "
            f"(индекс {low['index']}). Соискателю там, где индекс ниже, устроиться проще; работодателю там, где индекс выше, проще найти сотрудников.")

def city_totals() -> dict[str, int]:
    """Посчитать все вакансии каждого города независимо от фильтров."""
    query = db.select(City.name, db.func.count(Vacancy.id)).join(Vacancy, Vacancy.city_id == City.id).group_by(City.name)
    return {name: count for name, count in db.session.execute(query)}

def map_metrics(rows: list[dict], category: str = "") -> dict[str, dict]:
    """Рассчитать для карты долю вакансий и, при выбранной области, коэффициент специализации."""
    totals = city_totals()
    total = sum(totals.values())
    selected = sum(r["count"] for r in rows)
    counts = {r["city"]: r["count"] for r in rows}
    result = {}
    for city, city_total in totals.items():
        count = counts.get(city, 0)
        if category:
            result[city] = {"count": count, "share": round(100 * count / city_total, 2),
                "coefficient": round(count / city_total / (selected / total), 2) if selected else 0}
        else:
            result[city] = {"count": count, "share": round(100 * count / total, 2), "coefficient": None}
    return result

def references() -> dict:
    """Получить актуальные значения справочников."""
    return {name: list(db.session.scalars(db.select(model.name).order_by(model.name)))
            for name, model in [("cities", City), ("categories", Category), ("formats", WorkFormat)]}
