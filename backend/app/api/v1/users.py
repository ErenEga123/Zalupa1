from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.users import UserLookupOut


router = APIRouter()


@router.get("/me", response_model=UserLookupOut)
def current_user(user: User = Depends(get_current_user)) -> UserLookupOut:
    return UserLookupOut(id=user.id, email=user.email, telegram_id=user.telegram_id)
