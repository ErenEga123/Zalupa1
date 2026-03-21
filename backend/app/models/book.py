import enum
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.session import Base


class BookVisibility(str, enum.Enum):
    private = "private"
    shared = "shared"


class BookFileType(str, enum.Enum):
    epub = "epub"
    fb2 = "fb2"
    pdf = "pdf"


class ChapterType(str, enum.Enum):
    html = "html"
    pdf_page = "pdf_page"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    author: Mapped[str] = mapped_column(String(300), nullable=False, default="Unknown")
    series: Mapped[str | None] = mapped_column(String(300), nullable=True)
    file_type: Mapped[BookFileType] = mapped_column(Enum(BookFileType), nullable=False)
    visibility: Mapped[BookVisibility] = mapped_column(Enum(BookVisibility), nullable=False, default=BookVisibility.private)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cover_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    owner = relationship("User", back_populates="books")
    file = relationship("BookFile", back_populates="book", uselist=False, cascade="all, delete-orphan")
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")


class BookFile(Base):
    __tablename__ = "book_files"
    __table_args__ = (UniqueConstraint("sha256", name="uq_book_files_sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, unique=True)
    original_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    book = relationship("Book", back_populates="file")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("book_id", "order_index", name="uq_chapter_book_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_path: Mapped[str] = mapped_column(String(500), nullable=False)
    chapter_type: Mapped[ChapterType] = mapped_column(Enum(ChapterType), nullable=False)

    book = relationship("Book", back_populates="chapters")


class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus), nullable=False, default=ProcessingStatus.pending)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
