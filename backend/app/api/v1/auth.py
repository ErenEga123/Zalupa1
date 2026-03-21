from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import RefreshToken, User
from app.schemas.auth import (
    GoogleCodeIn,
    MagicLinkConsumeIn,
    MagicLinkRequestIn,
    RefreshIn,
    TelegramAuthIn,
    TokenPair,
)
from app.services.email_auth import consume_magic_link, create_or_get_user_by_email, issue_magic_link, send_magic_link
from app.services.google_auth import exchange_google_code
from app.services.jwt_service import create_access_token, create_refresh_token
from app.services.telegram_auth import verify_telegram_login


router = APIRouter()


@router.post("/telegram", response_model=TokenPair)
def telegram_auth(payload: TelegramAuthIn, db: Session = Depends(get_db)) -> TokenPair:
    data = payload.model_dump()
    if not verify_telegram_login(data):
        raise HTTPException(status_code=401, detail="Telegram hash verification failed")

    tg_id = str(payload.id)
    user = db.scalar(select(User).where(User.telegram_id == tg_id))
    if not user:
        user = User(telegram_id=tg_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    return TokenPair(access_token=create_access_token(user), refresh_token=create_refresh_token(db, user))


@router.post("/google", response_model=TokenPair)
async def google_auth(payload: GoogleCodeIn, db: Session = Depends(get_db)) -> TokenPair:
    profile = await exchange_google_code(payload.code)
    if not profile:
        raise HTTPException(status_code=401, detail="Google auth failed")
    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google profile has no email")

    user = create_or_get_user_by_email(db, email)
    return TokenPair(access_token=create_access_token(user), refresh_token=create_refresh_token(db, user))


@router.post("/magic/request")
def magic_request(payload: MagicLinkRequestIn, db: Session = Depends(get_db)) -> dict:
    user = create_or_get_user_by_email(db, payload.email)
    token = issue_magic_link(db, user)
    send_magic_link(payload.email, token)
    return {"ok": True}


@router.post("/magic/consume", response_model=TokenPair)
def magic_consume(payload: MagicLinkConsumeIn, db: Session = Depends(get_db)) -> TokenPair:
    user = consume_magic_link(db, payload.token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return TokenPair(access_token=create_access_token(user), refresh_token=create_refresh_token(db, user))


@router.get("/magic/consume", response_model=TokenPair)
def magic_consume_query(token: str = Query(...), db: Session = Depends(get_db)) -> TokenPair:
    user = consume_magic_link(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return TokenPair(access_token=create_access_token(user), refresh_token=create_refresh_token(db, user))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> TokenPair:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token == payload.refresh_token, RefreshToken.revoked == False))  # noqa: E712
    if not row:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")
    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    row.revoked = True
    db.commit()
    return TokenPair(access_token=create_access_token(user), refresh_token=create_refresh_token(db, user))


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"id": user.id, "email": user.email, "telegram_id": user.telegram_id}
