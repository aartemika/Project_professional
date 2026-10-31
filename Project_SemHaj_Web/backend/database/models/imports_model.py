"""История успешных замен набора данных."""
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from ..db_session import db

class ImportLog(db.Model):
    """История успешных замен набора данных."""
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    rows: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
