from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.book import Book, BookVisibility, ProcessingTask
from app.models.user import Favorite, User
from app.schemas.books import BookOut, PagedBooks


router = APIRouter()


@router.get("", response_model=PagedBooks)
def list_library(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    visibility: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PagedBooks:
    offset = (page - 1) * page_size

    query = select(Book).where(or_(Book.owner_id == user.id, Book.visibility == BookVisibility.shared))
    if visibility in {"private", "shared"}:
        query = query.where(Book.visibility == visibility)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Book.title.ilike(like), Book.author.ilike(like), Book.series.ilike(like)))

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    books = db.scalars(query.order_by(Book.created_at.desc()).offset(offset).limit(page_size)).all()

    fav_ids = {x.book_id for x in db.scalars(select(Favorite).where(Favorite.user_id == user.id)).all()}
    status_map = {t.book_id: t.status.value for t in db.scalars(select(ProcessingTask)).all()}

    items = [
        BookOut(
            id=b.id,
            title=b.title,
            author=b.author,
            series=b.series,
            file_type=b.file_type.value,
            visibility=b.visibility.value,
            owner_id=b.owner_id,
            cover_path=b.cover_path,
            created_at=b.created_at,
            status=status_map.get(b.id, "pending"),
            favorite=b.id in fav_ids,
        )
        for b in books
    ]

    return PagedBooks(items=items, page=page, page_size=page_size, total=total or 0)
