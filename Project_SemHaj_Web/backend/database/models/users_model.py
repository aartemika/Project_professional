"""Учётная запись аналитика или администратора."""
from sqlalchemy.orm import Mapped, mapped_column
from ..db_session import db

class User(db.Model):
    """Учётная запись аналитика или администратора."""
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    is_admin: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True)
