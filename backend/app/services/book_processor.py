from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import zipfile
from xml.etree import ElementTree as ET

from ebooklib import epub
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.book import Book, BookFile, Chapter, ChapterType, ProcessingStatus, ProcessingTask


settings = get_settings()


class ProcessingError(Exception):
    pass


@dataclass
class ProcessResult:
    chapter_count: int
    cover_path: str | None = None


class BookProcessor:
    def __init__(self, db: Session):
        self.db = db

    def process_book(self, book: Book, book_file: BookFile) -> ProcessResult:
        source = Path(book_file.original_path)
        processed_root = Path(book_file.processed_path)
        processed_root.mkdir(parents=True, exist_ok=True)

        for old in self.db.scalars(select(Chapter).where(Chapter.book_id == book.id)).all():
            self.db.delete(old)
        self.db.flush()

        if book.file_type.value == "epub":
            return self._process_epub(book, source, processed_root)
        if book.file_type.value == "fb2":
            return self._process_fb2(book, source, processed_root)
        if book.file_type.value == "pdf":
            return self._process_pdf(book, source, processed_root)
        raise ProcessingError("Unsupported file type")

    def _process_epub(self, book: Book, source: Path, processed_root: Path) -> ProcessResult:
        self._check_epub_unpacked_limit(source)
        try:
            epub_book = epub.read_epub(str(source))
        except Exception as exc:  # noqa: BLE001
            raise ProcessingError(f"Invalid EPUB: {exc}") from exc

        chapter_index = 0
        cover_path = None
        for item in epub_book.get_items():
            media_type = getattr(item, "media_type", "")
            if media_type == "application/xhtml+xml":
                chapter_index += 1
                filename = f"chapter_{chapter_index:05d}.html"
                out_path = processed_root / filename
                out_path.write_bytes(item.get_body_content())
                chapter = Chapter(
                    book_id=book.id,
                    title=getattr(item, "title", None) or f"Chapter {chapter_index}",
                    order_index=chapter_index,
                    content_path=str(out_path),
                    chapter_type=ChapterType.html,
                )
                self.db.add(chapter)
            elif getattr(item, "get_name", lambda: "")().lower().startswith("cover") and not cover_path:
                cpath = processed_root.parent / "cover.jpg"
                cpath.write_bytes(item.get_content())
                cover_path = str(cpath)

        if chapter_index == 0:
            raise ProcessingError("EPUB has no readable chapters")

        self.db.commit()
        return ProcessResult(chapter_count=chapter_index, cover_path=cover_path)

    def _process_fb2(self, book: Book, source: Path, processed_root: Path) -> ProcessResult:
        try:
            tree = ET.parse(source)
            root = tree.getroot()
        except Exception as exc:  # noqa: BLE001
            raise ProcessingError(f"Invalid FB2: {exc}") from exc

        ns = "{http://www.gribuser.ru/xml/fictionbook/2.0}"
        sections = root.findall(f".//{ns}body/{ns}section")
        if not sections:
            raise ProcessingError("FB2 has no sections")

        chapter_index = 0
        for section in sections:
            chapter_index += 1
            title = section.find(f"{ns}title/{ns}p")
            title_text = (title.text or "").strip() if title is not None else f"Section {chapter_index}"
            paragraphs = ["<p>" + "".join(p.itertext()).strip() + "</p>" for p in section.findall(f"{ns}p") if "".join(p.itertext()).strip()]
            html = "\n".join(paragraphs) if paragraphs else "<p>(empty section)</p>"
            out_path = processed_root / f"chapter_{chapter_index:05d}.html"
            out_path.write_text(html, encoding="utf-8")
            self.db.add(
                Chapter(
                    book_id=book.id,
                    title=title_text,
                    order_index=chapter_index,
                    content_path=str(out_path),
                    chapter_type=ChapterType.html,
                )
            )

        self.db.commit()
        return ProcessResult(chapter_count=chapter_index)

    def _process_pdf(self, book: Book, source: Path, processed_root: Path) -> ProcessResult:
        try:
            reader = PdfReader(str(source))
        except Exception as exc:  # noqa: BLE001
            raise ProcessingError(f"Invalid PDF: {exc}") from exc

        if len(reader.pages) == 0:
            raise ProcessingError("PDF has no pages")

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            html = f"<pre>{text}</pre>"
            out_path = processed_root / f"page_{idx:05d}.html"
            out_path.write_text(html, encoding="utf-8")
            self.db.add(
                Chapter(
                    book_id=book.id,
                    title=f"Page {idx}",
                    order_index=idx,
                    content_path=str(out_path),
                    chapter_type=ChapterType.pdf_page,
                )
            )

        self.db.commit()
        return ProcessResult(chapter_count=len(reader.pages))

    def _check_epub_unpacked_limit(self, source: Path) -> None:
        max_unpacked_bytes = settings.max_epub_unpacked_mb * 1024 * 1024
        try:
            with zipfile.ZipFile(source, "r") as zf:
                total = sum(zinfo.file_size for zinfo in zf.infolist())
                if total > max_unpacked_bytes:
                    raise ProcessingError("EPUB unpacked size exceeds configured limit")
        except zipfile.BadZipFile as exc:
            raise ProcessingError(f"Invalid EPUB archive: {exc}") from exc


def claim_next_task(db: Session) -> ProcessingTask | None:
    task = db.scalar(
        select(ProcessingTask)
        .where(
            ProcessingTask.status.in_([ProcessingStatus.pending, ProcessingStatus.failed]),
            ProcessingTask.attempt_count < settings.processing_max_attempts,
        )
        .order_by(ProcessingTask.updated_at.asc())
        .with_for_update(skip_locked=True)
    )
    if not task:
        return None
    task.status = ProcessingStatus.processing
    db.commit()
    db.refresh(task)
    return task


def process_task(db: Session, task: ProcessingTask) -> None:
    book = db.get(Book, task.book_id)
    if not book:
        task.status = ProcessingStatus.failed
        task.error_message = "Book not found"
        db.commit()
        return

    book_file = db.scalar(select(BookFile).where(BookFile.book_id == book.id))
    if not book_file:
        task.status = ProcessingStatus.failed
        task.error_message = "Book file not found"
        db.commit()
        return

    task.attempt_count += 1
    db.commit()

    try:
        result = BookProcessor(db).process_book(book, book_file)
        if result.cover_path:
            book.cover_path = result.cover_path
        task.status = ProcessingStatus.ready
        task.error_message = None
        db.commit()
    except ProcessingError as exc:
        task.status = ProcessingStatus.failed
        task.error_message = str(exc)
        db.commit()
