"""Создание и запуск Flask приложения кадрового навигатора."""
import os
import secrets
import socket
import threading
import webbrowser
from pathlib import Path
from flask import Flask, session, request, abort
from dotenv import load_dotenv
from backend.database.models import db, User
from backend.database.default_data import create_admin
from backend.services import upgrade_vacancy_table

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
        DATASET_DIR=str(APP_ROOT / "data"), AUTO_LOGIN=os.getenv("AUTO_LOGIN", "0") == "1",
        BOOT_ID=secrets.token_hex(8))
    if config:
        app.config.update(config)
    db.init_app(app)
    from backend.api.auth_api import bp as auth
    from backend.api.pages_api import bp as pages
    from backend.api.analytics_api import bp as api
    from backend.api.admin_api import bp as admin
    from backend.api.crud_api import bp as crud
    from backend.api.showcase_api import bp as showcase
    from backend.errors import register_errors
    for blueprint in [auth, pages, api, admin, crud, showcase]:
        app.register_blueprint(blueprint)
    register_errors(app)
    app.before_request(protect_forms)
    app.context_processor(template_context)
    with app.app_context():
        db.create_all()
        upgrade_vacancy_table(Path(app.config["DATASET_DIR"]))
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


def port_is_busy(host: str, port: int) -> bool:
    """Проверить, отвечает ли на этом адресе уже запущенный сервер."""
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex((host, port)) == 0

def main() -> None:
    """Запустить локальный HTTP сервер с настройками из .env и открыть сайт в браузере."""
    app = create_app()
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "5000"))
    local = "127.0.0.1" if host == "0.0.0.0" else host
    if port_is_busy(local, port):
        print(f"Сервер уже запущен на http://{local}:{port}. Закройте старое чёрное окно и запустите run.bat снова.")
        return
    threading.Timer(1.0, webbrowser.open, [f"http://{local}:{port}"]).start()
    app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    main()
