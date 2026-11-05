"""Браузерная авторизация и проверка прав доступа."""
from functools import wraps
from typing import Callable, Any
from flask import Blueprint, request, session, render_template, redirect, url_for, abort, current_app
from werkzeug.security import check_password_hash
from ..database.models import db, User

bp = Blueprint("auth", __name__)

def current_user() -> User | None:
    """Найти активного пользователя браузерной сессии."""
    if session.get("boot") != current_app.config["BOOT_ID"]:
        session.clear()
        session["boot"] = current_app.config["BOOT_ID"]
    user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    return user if user and user.active else None

def auto_login_user() -> User | None:
    """Найти администратора для автовхода, разрешённого только с этого компьютера."""
    if not current_app.config.get("AUTO_LOGIN") or request.remote_addr not in {"127.0.0.1", "::1"}:
        return None
    return db.session.scalar(db.select(User).where(User.is_admin, User.active).order_by(User.id).limit(1))

def login_required(view: Callable) -> Callable:
    """Ограничить маршрут авторизованными пользователями."""
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        """Проверить сессию перед вызовом страницы."""
        if not current_user():
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view: Callable) -> Callable:
    """Ограничить маршрут ролью администратора."""
    @wraps(view)
    @login_required
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        """Проверить административные права."""
        if not current_user().is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped

@bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    """Показать приветствие или форму входа и открыть браузерную сессию."""
    current_user()
    if request.method == "GET" and auto_login_user() and not session.get("manual_login"):
        return redirect(url_for("showcase.panorama")) if current_user() else render_template("welcome.html")
    error = ""
    if request.method == "POST":
        user = db.session.scalar(db.select(User).where(User.username == request.form.get("username", "")))
        if user and user.active and check_password_hash(user.password_hash, request.form.get("password", "")):
            session.clear()
            session["boot"] = current_app.config["BOOT_ID"]
            session["user_id"] = user.id
            return redirect(url_for("showcase.panorama"))
        error = "Неверный логин или пароль"
    return render_template("login.html", error=error)

@bp.post("/enter")
def enter() -> Any:
    """Открыть сессию по кнопке приветствия, если автовход разрешён."""
    user = auto_login_user()
    if not user or session.get("manual_login"):
        return redirect(url_for("auth.login"))
    session["user_id"] = user.id
    return redirect(url_for("showcase.panorama"))

@bp.post("/logout")
def logout() -> Any:
    """Закрыть браузерную сессию и не входить снова автоматически."""
    session.clear()
    session["boot"] = current_app.config["BOOT_ID"]
    session["manual_login"] = True
    return redirect(url_for("auth.login"))
