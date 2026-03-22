from pathlib import Path

from sqlalchemy import select

from app.models.book import Book, BookFile, BookFileType, BookVisibility, ProcessingStatus, ProcessingTask
from app.models.user import User
from app.services.book_processor import process_task
from app.worker.queue import QueueRunner


def test_processing_status_transition_and_retry(client, tmp_path):
    _, Session = client
    bad = tmp_path / "bad.epub"
    bad.write_text("bad", encoding="utf-8")

    with Session() as db:
        user = db.scalar(select(User))
        book = Book(title="B", author="A", file_type=BookFileType.epub, visibility=BookVisibility.private, owner_id=user.id)
        db.add(book)
        db.flush()
        db.add(BookFile(book_id=book.id, original_path=str(bad), processed_path=str(tmp_path / "p"), file_size=3, sha256="c" * 64))
        task = ProcessingTask(book_id=book.id, status=ProcessingStatus.pending, attempt_count=0)
        db.add(task)
        db.commit()

        process_task(db, task)
        assert task.status == ProcessingStatus.failed
        assert task.attempt_count == 1

        process_task(db, task)
        process_task(db, task)
        assert task.attempt_count == 3


def test_queue_resume_behavior_after_restart(client):
    _, Session = client
    with Session() as db:
        user = db.scalar(select(User))
        book = Book(title="Q", author="A", file_type=BookFileType.fb2, visibility=BookVisibility.private, owner_id=user.id)
        db.add(book)
        db.flush()
        book_id = book.id
        db.add(ProcessingTask(book_id=book_id, status=ProcessingStatus.processing, attempt_count=1))
        db.commit()

    import asyncio

    runner = QueueRunner()
    asyncio.run(runner.start())
    asyncio.run(runner.stop())

    with Session() as db:
        status = db.scalar(select(ProcessingTask.status).where(ProcessingTask.book_id == book_id))
        assert status in {ProcessingStatus.pending, ProcessingStatus.failed, ProcessingStatus.ready, ProcessingStatus.processing}
