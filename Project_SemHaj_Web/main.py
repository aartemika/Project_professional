"""Создание и запуск Flask приложения кадрового навигатора."""
import os
import secrets
from pathlib import Path
from flask import Flask, session, request, abort
from dotenv import load_dotenv
from backend.database.models import db, User
from backend.database.default_data import create_admin

APP_ROOT = Path(__file__).resolve().parent

def create_app(config: dict | None = None) -> Flask:
    """Создать сервер, подключить БД, обработчики и блупринты."""
    load_dotenv(APP_ROOT / ".env", override=False)
    (APP_ROOT / "data").mkdir(exist_ok=True)
    app = Flask(__name__, template_folder=str(APP_ROOT / "templates"), static_folder=str(APP_ROOT / "static"))
    app.config.update(SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + (APP_ROOT / "data/navigator.db").as_posix(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False, MAX_CONTENT_LENGTH=1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        DATASET_DIR=str(APP_ROOT / "data"))
    if config:
        app.config.update(config)
    db.init_app(app)
    from backend.api.auth_api import bp as auth
    from backend.api.pages_api import bp as pages
    from backend.api.analytics_api import bp as api
    from backend.api.admin_api import bp as admin
    from backend.api.crud_api import bp as crud
    from backend.errors import register_errors
    for blueprint in [auth, pages, api, admin, crud]:
        app.register_blueprint(blueprint)
    register_errors(app)
    app.before_request(protect_forms)
    app.context_processor(template_context)
    with app.app_context():
        db.create_all()
        create_admin()
    return app

def protect_forms() -> None:
    """Проверить CSRF для браузерных форм с изменением состояния."""
    if request.method == "POST" and not request.path.startswith("/api/"):
        expected = session.get("csrf", "")
        if not expected or not secrets.compare_digest(expected, request.form.get("csrf_token", "")):
            abort(400, description="Форма устарела. Обновите страницу и повторите действие.")

def template_context() -> dict:
    """Передать шаблонам пользователя и токен формы."""
    session.setdefault("csrf", secrets.token_urlsafe(32))
    user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    return {"viewer": user if user and user.active else None, "csrf_token": session["csrf"]}


def main() -> None:
    """Запустить локальный HTTP сервер с настройками из .env."""
    app = create_app()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=False)

if __name__ == "__main__":
    main()
