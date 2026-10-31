"""Первоначальная учётная запись администратора."""
import os
from werkzeug.security import generate_password_hash
from .models import db, User

def create_admin() -> None:
    """Создать администратора только при отсутствии пользователей."""
    if db.session.scalar(db.select(User).limit(1)):
        return
    password = os.getenv("ADMIN_PASSWORD")
    if not password or len(password) < 10:
        raise RuntimeError("Задайте ADMIN_PASSWORD длиной от 10 символов в .env")
    db.session.add(User(username=os.getenv("ADMIN_USERNAME", "admin"),
        password_hash=generate_password_hash(password), is_admin=True, active=True))
    db.session.commit()
