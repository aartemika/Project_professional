"""Главная страница с картой и раздел «Подбор города»."""
from typing import Any
from flask import Blueprint, render_template, request, jsonify, abort
from .auth_api import login_required
from .pages_api import selection, map_points
from ..services import references
from ..showcase import showcase_data, rating_data, city_profiles, city_notes, cached_summary, money, plural, EXPERIENCE

bp = Blueprint("showcase", __name__)

def chosen_experience() -> str:
    """Прочитать и проверить выбранный опыт работы."""
    experience = request.args.get("experience", "")
    if experience and experience not in EXPERIENCE:
        abort(400, description="Неизвестный опыт работы")
    return experience

@bp.get("/")
@bp.get("/panorama")
@login_required
def panorama() -> str:
    """Показать главную страницу: карту с карточками городов и яркие факты."""
    category, _ = selection()
    refs = references()
    notes = city_notes()
    rows = cached_summary(category)
    salary = {r["city"]: r["salary"] for r in rows}
    points = []
    for point in map_points(rows, refs["cities"], category):
        value = salary.get(point["city"])
        points.append({**point, **notes.get(point["city"], {"badge": "", "famous": [], "paid": []}),
            "vacancies": plural(point["count"], "вакансия", "вакансии", "вакансий"),
            "typical": money(value) if value else ""})
    return render_template("showcase.html", category=category, refs=refs, points=points, **showcase_data(category))

@bp.get("/navigator")
@login_required
def navigator_page() -> str:
    """Показать подбор города: режимы соискателя и бизнеса, анализ рынка и сравнение."""
    category, _ = selection()
    experience = chosen_experience()
    return render_template("navigator.html", data=rating_data(category, experience), profiles=city_profiles(),
        category=category, experience=experience, experience_options=EXPERIENCE, refs=references())

@bp.get("/navigator/data")
@login_required
def navigator_data() -> Any:
    """Вернуть показатели городов при смене профессии или опыта."""
    category, _ = selection()
    return jsonify(rating_data(category, chosen_experience()))
