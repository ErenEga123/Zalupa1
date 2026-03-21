import asyncio
import logging

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.book import ProcessingStatus, ProcessingTask
from app.services.book_processor import claim_next_task, process_task


logger = logging.getLogger(__name__)
settings = get_settings()


class QueueRunner:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        with SessionLocal() as db:
            for row in db.query(ProcessingTask).filter(ProcessingTask.status == ProcessingStatus.processing).all():
                row.status = ProcessingStatus.pending
            db.commit()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            with SessionLocal() as db:
                task = claim_next_task(db)
                if task:
                    process_task(db, task)
            await asyncio.sleep(settings.processing_poll_interval_seconds)


queue_runner = QueueRunner()
