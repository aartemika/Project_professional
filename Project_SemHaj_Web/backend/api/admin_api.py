"""Управление импортом, справочниками и учётными записями."""
from pathlib import Path
from typing import Any
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from werkzeug.security import generate_password_hash
from .auth_api import admin_required, current_user
from ..database.models import db, User, City, Category, WorkFormat, ImportLog
from ..services import import_dataset

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.route("/", methods=["GET", "POST"])
@admin_required
def index() -> Any:
    """Обработать административную форму и показать состояние базы."""
    folder = Path(current_app.config["DATASET_DIR"])
    files = sorted(p.name for p in folder.glob("*.csv"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "import":
            name = request.form.get("filename", "")
            if name not in files:
                abort(400, description="Выберите CSV из списка")
            try:
                result = import_dataset(folder / name)
                flash(f"Импортировано {result['rows']} вакансий; исключено строк: {result['removed_rows']}")
            except (ValueError, OSError) as error:
                db.session.rollback()
                flash("Ошибка импорта: " + str(error))
        elif action == "create_user":
            name, password = request.form.get("username", "").strip(), request.form.get("password", "")
            if not 3 <= len(name) <= 40 or len(password) < 10:
                flash("Логин: 3–40 символов, пароль: не менее 10 символов")
            elif db.session.scalar(db.select(User).where(User.username == name)):
                flash("Логин уже занят")
            else:
                db.session.add(User(username=name, password_hash=generate_password_hash(password),
                    is_admin=request.form.get("is_admin") == "on", active=True))
                db.session.commit()
                flash("Учётная запись создана")
        elif action in {"toggle_user", "reset_password"}:
            user = db.get_or_404(User, request.form.get("user_id", type=int))
            if action == "toggle_user":
                if user.id == current_user().id:
                    flash("Нельзя заблокировать текущую учётную запись")
                else:
                    user.active = not user.active
                    db.session.commit()
            else:
                password = request.form.get("password", "")
                if len(password) < 10:
                    flash("Пароль должен содержать не менее 10 символов")
                else:
                    user.password_hash = generate_password_hash(password)
                    db.session.commit()
                    flash("Пароль изменён")
        elif action == "rename":
            models = {"city": City, "category": Category, "format": WorkFormat}
            model = models.get(request.form.get("table"))
            if model is None:
                abort(400)
            item = db.get_or_404(model, request.form.get("id", type=int))
            name = request.form.get("name", "").strip()
            if not name or len(name) > 150:
                flash("Введите название длиной от 1 до 150 символов")
            elif db.session.scalar(db.select(model).where(model.name == name, model.id != item.id)):
                flash("Такое название уже существует")
            else:
                item.name = name
                db.session.commit()
                flash("Справочник обновлён. Следующий импорт восстановит значения из CSV.")
        else:
            abort(400)
        return redirect(url_for("admin.index"))
    return render_template("admin.html", files=files,
        users=db.session.scalars(db.select(User).order_by(User.id)).all(),
        logs=db.session.scalars(db.select(ImportLog).order_by(ImportLog.id.desc()).limit(10)).all(),
        dictionaries=[("city", "Города", db.session.scalars(db.select(City)).all()),
                      ("category", "Профессиональные области", db.session.scalars(db.select(Category)).all()),
                      ("format", "Форматы работы", db.session.scalars(db.select(WorkFormat)).all())])
