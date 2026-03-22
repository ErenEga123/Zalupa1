from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BookCreateResult(BaseModel):
    book_id: str
    duplicate: bool
    message: str


class ChapterOut(BaseModel):
    id: int
    title: str
    order_index: int
    chapter_type: Literal["html", "pdf_page"]


class ChapterContentOut(BaseModel):
    id: int
    title: str
    order_index: int
    chapter_type: Literal["html", "pdf_page"]
    content: str
    prev_chapter_id: int | None
    next_chapter_id: int | None


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    series: str | None
    file_type: Literal["epub", "fb2", "pdf"]
    visibility: Literal["private", "shared"]
    owner_id: str
    cover_path: str | None
    created_at: datetime
    status: Literal["pending", "processing", "ready", "failed"]
    favorite: bool = False


class PagedBooks(BaseModel):
    items: list[BookOut]
    page: int
    page_size: int
    total: int


class FavoriteToggleIn(BaseModel):
    book_id: str
    favorite: bool


class BookVisibilityIn(BaseModel):
    visibility: Literal["private", "shared"]


class SubscriptionIn(BaseModel):
    owner_id: str
