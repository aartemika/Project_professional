"""Справочник сочетаний форматов занятости из источника."""
from sqlalchemy.orm import Mapped, mapped_column
from ..db_session import db

class WorkFormat(db.Model):
    """Справочник сочетаний форматов занятости из источника."""
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
