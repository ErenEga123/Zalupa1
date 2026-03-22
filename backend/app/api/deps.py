from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services.jwt_service import decode_token


bearer = HTTPBearer(auto_error=False)
settings = get_settings()


def _telegram_admin_set() -> set[str]:
    raw = settings.telegram_admin_ids or ""
    return {x.strip() for x in raw.split(",") if x.strip()}


def is_admin_user(user: User) -> bool:
    return bool(user.telegram_id and user.telegram_id in _telegram_admin_set())


def _get_or_create_bot_service_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == settings.bot_service_email))
    if user:
        return user
    user = User(email=settings.bot_service_email, telegram_id="bot-service")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_or_create_telegram_user(db: Session, telegram_id: str) -> User:
    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        return user
    user = User(telegram_id=telegram_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Security(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = creds.credentials

    # Persistent service token path for Telegram bot integration.
    if settings.bot_api_token and token == settings.bot_api_token:
        tg_user_id = request.headers.get("X-Telegram-User-Id", "").strip()
        if tg_user_id:
            return _get_or_create_telegram_user(db, tg_user_id)
        return _get_or_create_bot_service_user(db)

    try:
        payload = decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
