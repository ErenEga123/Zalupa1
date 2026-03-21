from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import Favorite, User
from app.schemas.books import FavoriteToggleIn


router = APIRouter()


@router.get("")
def list_favorites(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rows = db.scalars(select(Favorite).where(Favorite.user_id == user.id)).all()
    return {"items": [x.book_id for x in rows]}


@router.post("")
def toggle_favorite(payload: FavoriteToggleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.book_id == payload.book_id))
    if payload.favorite and not row:
        db.add(Favorite(user_id=user.id, book_id=payload.book_id))
    if not payload.favorite and row:
        db.delete(row)
    db.commit()
    return {"ok": True}
