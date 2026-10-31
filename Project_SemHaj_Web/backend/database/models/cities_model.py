"""Справочник городов из импортированной выгрузки."""
from sqlalchemy.orm import Mapped, mapped_column
from ..db_session import db

class City(db.Model):
    """Справочник городов из импортированной выгрузки."""
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
