"""Вакансия одного снимка с измеряемыми показателями."""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from ..db_session import db

class Vacancy(db.Model):
    """Вакансия одного снимка с измеряемыми показателями."""
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), index=True)
    format_id: Mapped[int] = mapped_column(ForeignKey("work_format.id"))
    company: Mapped[str]
    salary: Mapped[float | None]
    responses: Mapped[float | None]
    remote: Mapped[bool]
    hybrid: Mapped[bool]
    on_site: Mapped[bool]
    publication_time: Mapped[str]
    snapshot_date: Mapped[str]
