"""Браузерная авторизация и проверка прав доступа."""
from functools import wraps
from typing import Callable, Any
from flask import Blueprint, request, session, render_template, redirect, url_for, abort
from werkzeug.security import check_password_hash
from ..database.models import db, User

bp = Blueprint("auth", __name__)

def current_user() -> User | None:
    """Найти активного пользователя браузерной сессии."""
    user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    return user if user and user.active else None

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
    """Показать форму входа и открыть браузерную сессию."""
    error = ""
    if request.method == "POST":
        user = db.session.scalar(db.select(User).where(User.username == request.form.get("username", "")))
        if user and user.active and check_password_hash(user.password_hash, request.form.get("password", "")):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("pages.index"))
        error = "Неверный логин или пароль"
    return render_template("login.html", error=error)

@bp.post("/logout")
def logout() -> Any:
    """Закрыть браузерную сессию."""
    session.clear()
    return redirect(url_for("auth.login"))
