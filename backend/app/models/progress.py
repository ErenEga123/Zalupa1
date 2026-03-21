from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.session import Base


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_progress_user_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
