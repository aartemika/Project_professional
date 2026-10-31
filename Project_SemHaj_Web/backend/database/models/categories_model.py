"""Справочник профессиональных областей."""
from sqlalchemy.orm import Mapped, mapped_column
from ..db_session import db

class Category(db.Model):
    """Справочник профессиональных областей."""
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
