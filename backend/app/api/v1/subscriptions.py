from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import Subscription, User
from app.schemas.books import SubscriptionIn


router = APIRouter()


@router.get("")
def list_subscriptions(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rows = db.scalars(select(Subscription).where(Subscription.follower_id == user.id)).all()
    return {"items": [x.owner_id for x in rows]}


@router.post("")
def create_subscription(payload: SubscriptionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    row = db.scalar(
        select(Subscription).where(Subscription.follower_id == user.id, Subscription.owner_id == payload.owner_id)
    )
    if not row:
        db.add(Subscription(follower_id=user.id, owner_id=payload.owner_id))
        db.commit()
    return {"ok": True}
