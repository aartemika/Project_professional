"""Единый CRUD для всех таблиц с проверкой связей и прав."""
from datetime import datetime
from typing import Any
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, abort
from sqlalchemy.exc import IntegrityError
from ..database.models import db, User, City, Category, WorkFormat, Vacancy, ImportLog
from .auth_api import admin_required, current_user
from .analytics_api import token_required
from ..forms.data_form import FIELDS, validated_values

bp = Blueprint("crud", __name__)
MODELS = {"users": User, "cities": City, "categories": Category, "formats": WorkFormat,
          "vacancies": Vacancy, "imports": ImportLog}
TITLES = {"users": "Пользователи", "cities": "Города", "categories": "Профессиональные области",
          "formats": "Форматы работы", "vacancies": "Вакансии", "imports": "Журнал импорта"}


def model_for(entity: str) -> Any:
    """Найти модель по разрешённому имени ресурса."""
    if entity not in MODELS:
        abort(404)
    return MODELS[entity]

def serialize(entity: str, item: Any) -> dict:
    """Преобразовать запись в безопасные для клиента поля."""
    result = {"id": item.id}
    for name, label, kind in FIELDS[entity]:
        if name != "password":
            value = getattr(item, name)
            result[name] = value.isoformat() if isinstance(value, datetime) else value
    return result

def schema_for(entity: str) -> list[dict]:
    """Описать поля формы и варианты внешних ключей."""
    result = []
    for name, label, kind in FIELDS[entity]:
        choices = []
        if kind in {"city", "category", "format"}:
            model = {"city": City, "category": Category, "format": WorkFormat}[kind]
            choices = [{"id": x.id, "name": x.name} for x in db.session.scalars(db.select(model).order_by(model.name))]
        result.append({"name": name, "label": label, "kind": kind, "choices": choices})
    return result

def get_page(entity: str, page: int, search: str) -> dict:
    """Получить страницу записей без загрузки всей таблицы."""
    model = model_for(entity)
    query = db.select(model)
    column = getattr(model, "name", None)
    if entity == "users":
        column = User.username
    if entity == "imports":
        column = ImportLog.filename
    if search and column is not None:
        query = query.where(column.contains(search, autoescape=True))
    total = db.session.scalar(db.select(db.func.count()).select_from(query.subquery()))
    pages = max(1, (total + 29) // 30)
    page = max(1, min(page, pages))
    records = db.session.scalars(query.order_by(model.id).offset((page-1)*30).limit(30)).all()
    return {"rows": [serialize(entity, row) for row in records], "total": total,
            "page": page, "pages": pages, "schema": schema_for(entity), "title": TITLES[entity]}



def save_record(entity: str, payload: dict, actor: User, identifier: str | None = None) -> dict:
    """Создать либо изменить запись с защитой текущего администратора."""
    model = model_for(entity)
    item = db.get_or_404(model, identifier) if identifier is not None else None
    values = validated_values(entity, payload, item)
    if entity == "users" and item and item.id == actor.id:
        if not values.get("active", item.active) or not values.get("is_admin", item.is_admin):
            raise ValueError("Нельзя отключить собственный административный доступ")
    try:
        if item is None:
            item = model(**values)
            db.session.add(item)
        else:
            for name, value in values.items():
                setattr(item, name, value)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Запись с таким ID или названием уже существует") from None
    return serialize(entity, item)

def delete_record(entity: str, identifier: str, actor: User) -> None:
    """Удалить запись, запретив потерю связанных вакансий и своего доступа."""
    item = db.get_or_404(model_for(entity), identifier)
    if entity == "users" and item.id == actor.id:
        raise ValueError("Нельзя удалить текущего пользователя")
    linked = {"cities": Vacancy.city_id, "categories": Vacancy.category_id, "formats": Vacancy.format_id}
    if entity in linked and db.session.scalar(db.select(Vacancy.id).where(linked[entity] == item.id).limit(1)):
        raise ValueError("Запись используется вакансиями. Сначала измените или удалите связанные вакансии.")
    db.session.delete(item)
    db.session.commit()

@bp.route("/admin/data/<entity>", methods=["GET", "POST"])
@admin_required
def browser_list(entity: str) -> Any:
    """Показать список и обработать создание записи из браузера."""
    model_for(entity)
    error = ""
    if request.method == "POST":
        try:
            save_record(entity, form_payload(entity), current_user())
            flash("Запись создана")
            return redirect(url_for("crud.browser_list", entity=entity))
        except ValueError as exception:
            error = str(exception)
    result = get_page(entity, request.args.get("page", 1, type=int), request.args.get("q", ""))
    return render_template("crud.html", entity=entity, result=result, titles=TITLES, error=error, item=None)

def form_payload(entity: str) -> dict:
    """Прочитать значения браузерной формы согласно схеме полей."""
    return {name: request.form.get(name, "") for name, label, kind in FIELDS[entity]}

@bp.route("/admin/data/<entity>/<identifier>/edit", methods=["GET", "POST"])
@admin_required
def browser_edit(entity: str, identifier: str) -> Any:
    """Показать и сохранить форму изменения выбранной записи."""
    item = db.get_or_404(model_for(entity), identifier)
    error = ""
    if request.method == "POST":
        try:
            save_record(entity, form_payload(entity), current_user(), identifier)
            flash("Запись изменена")
            return redirect(url_for("crud.browser_list", entity=entity))
        except ValueError as exception:
            error = str(exception)
    result = {"schema": schema_for(entity), "title": TITLES[entity]}
    return render_template("crud.html", entity=entity, result=result, titles=TITLES, error=error, item=serialize(entity,item))

@bp.post("/admin/data/<entity>/<identifier>/delete")
@admin_required
def browser_delete(entity: str, identifier: str) -> Any:
    """Удалить запись по защищённой форме."""
    try:
        delete_record(entity, identifier, current_user())
        flash("Запись удалена")
    except ValueError as exception:
        flash(str(exception))
    return redirect(url_for("crud.browser_list", entity=entity))

@bp.route("/api/admin/<entity>", methods=["GET", "POST"])
@bp.route("/api/admin/<entity>/<identifier>", methods=["GET", "PUT", "DELETE"])
@token_required
def api_records(entity: str, identifier: str | None = None) -> Any:
    """Выполнить административный CRUD запрос оконного клиента."""
    from flask import g
    actor = g.api_user
    if not actor.is_admin:
        abort(403)
    model = model_for(entity)
    try:
        if request.method == "GET":
            if identifier is not None:
                return jsonify(serialize(entity, db.get_or_404(model, identifier)))
            return jsonify(get_page(entity, request.args.get("page", 1, type=int), request.args.get("q", "")))
        if request.method == "DELETE":
            delete_record(entity, identifier, actor)
            return jsonify(message="Запись удалена")
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400, description="Ожидается JSON объект")
        return jsonify(save_record(entity, payload, actor, identifier)), 201 if identifier is None else 200
    except ValueError as exception:
        abort(400, description=str(exception))
