from datetime import datetime

from pydantic import BaseModel


class ProgressIn(BaseModel):
    book_id: str
    chapter_id: int | None = None
    position: float
    updated_at: datetime


class ProgressOut(BaseModel):
    accepted: bool
    server_progress: dict | None = None
