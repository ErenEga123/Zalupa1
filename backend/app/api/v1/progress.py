from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.progress import Progress
from app.models.user import User
from app.schemas.progress import ProgressIn, ProgressOut


router = APIRouter()


@router.post("", response_model=ProgressOut)
def upsert_progress(payload: ProgressIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ProgressOut:
    incoming_ts = payload.updated_at.astimezone(timezone.utc)
    existing = db.scalar(select(Progress).where(Progress.user_id == user.id, Progress.book_id == payload.book_id))

    if existing and existing.updated_at >= incoming_ts:
        return ProgressOut(
            accepted=False,
            server_progress={
                "book_id": existing.book_id,
                "chapter_id": existing.chapter_id,
                "position": existing.position,
                "updated_at": existing.updated_at.isoformat(),
            },
        )

    if not existing:
        existing = Progress(user_id=user.id, book_id=payload.book_id)
        db.add(existing)

    existing.chapter_id = payload.chapter_id
    existing.position = payload.position
    existing.updated_at = incoming_ts
    db.commit()

    return ProgressOut(
        accepted=True,
        server_progress={
            "book_id": existing.book_id,
            "chapter_id": existing.chapter_id,
            "position": existing.position,
            "updated_at": existing.updated_at.isoformat(),
        },
    )


@router.get("/{book_id}")
def get_progress(book_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = db.scalar(select(Progress).where(Progress.user_id == user.id, Progress.book_id == book_id))
    if not row:
        return {"book_id": book_id, "chapter_id": None, "position": 0, "updated_at": None}
    return {
        "book_id": book_id,
        "chapter_id": row.chapter_id,
        "position": row.position,
        "updated_at": row.updated_at.isoformat(),
    }
