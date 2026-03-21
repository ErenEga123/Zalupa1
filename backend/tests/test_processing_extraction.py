from pathlib import Path

from sqlalchemy import select

from app.models.book import Book, BookFile, BookFileType, BookVisibility, Chapter
from app.models.user import User
from app.services.book_processor import BookProcessor, ProcessingError


def test_book_content_extraction_fb2(client, tmp_path):
    c, Session = client
    from tests.conftest import make_fb2

    source = tmp_path / "book.fb2"
    make_fb2(source)

    with Session() as db:
        user = db.scalar(select(User))
        book = Book(title="Sample", author="A", file_type=BookFileType.fb2, visibility=BookVisibility.private, owner_id=user.id)
        db.add(book)
        db.flush()
        processed_root = tmp_path / "processed"
        processed_root.mkdir()
        db.add(BookFile(book_id=book.id, original_path=str(source), processed_path=str(processed_root), file_size=source.stat().st_size, sha256="a" * 64))
        db.commit()

        BookProcessor(db).process_book(book, db.scalar(select(BookFile).where(BookFile.book_id == book.id)))
        chapters = db.scalars(select(Chapter).where(Chapter.book_id == book.id)).all()
        assert len(chapters) == 2


def test_invalid_epub_handling(client, tmp_path):
    _, Session = client
    source = tmp_path / "bad.epub"
    source.write_text("not a zip", encoding="utf-8")

    with Session() as db:
        user = db.scalar(select(User))
        book = Book(title="Bad", author="A", file_type=BookFileType.epub, visibility=BookVisibility.private, owner_id=user.id)
        db.add(book)
        db.flush()
        processed_root = tmp_path / "processed2"
        processed_root.mkdir()
        bfile = BookFile(book_id=book.id, original_path=str(source), processed_path=str(processed_root), file_size=10, sha256="b" * 64)
        db.add(bfile)
        db.commit()

        try:
            BookProcessor(db).process_book(book, bfile)
            assert False, "expected ProcessingError"
        except ProcessingError:
            assert True
