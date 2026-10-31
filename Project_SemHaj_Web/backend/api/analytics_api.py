"""HTTP JSON API для оконного приложения."""
from functools import wraps
from typing import Callable, Any
from flask import Blueprint, request, current_app, jsonify, abort, g
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash
from ..database.models import db, User
from ..services import summary, references, recommendation

bp = Blueprint("api", __name__, url_prefix="/api")

def token_required(view: Callable) -> Callable:
    """Проверить подписанный токен с часовым сроком действия."""
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        """Проверить токен и активность учётной записи."""
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            abort(401)
        try:
            user_id = URLSafeTimedSerializer(current_app.secret_key, salt="desktop").loads(header[7:], max_age=3600)
        except (BadSignature, SignatureExpired):
            abort(401)
        user = db.session.get(User, user_id)
        if not user or not user.active:
            abort(401)
        g.api_user = user
        return view(*args, **kwargs)
    return wrapped

@bp.post("/login")
def login() -> Any:
    """Проверить пароль и выдать ограниченный по времени токен."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        abort(400, description="Ожидаются строковые username и password")
    user = db.session.scalar(db.select(User).where(User.username == data["username"]))
    if not user or not user.active or not check_password_hash(user.password_hash, data["password"]):
        abort(401)
    token = URLSafeTimedSerializer(current_app.secret_key, salt="desktop").dumps(user.id)
    return jsonify(token=token, expires_in=3600, username=user.username, is_admin=user.is_admin)

@bp.get("/references")
@token_required
def get_references() -> Any:
    """Вернуть справочники для фильтров клиента."""
    return jsonify(references())

@bp.get("/summary")
@token_required
def get_summary() -> Any:
    """Вернуть метрики, кластеры и описательную рекомендацию."""
    rows = summary(request.args.get("category", ""), request.args.getlist("city"))
    return jsonify(rows=rows, recommendation=recommendation(rows))
