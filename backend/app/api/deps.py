from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.session import get_db
from app.models.user import User
from app.services.jwt_service import decode_token


bearer = HTTPBearer(auto_error=False)
settings = get_settings()


def _get_or_create_bot_service_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == settings.bot_service_email))
    if user:
        return user
    user = User(email=settings.bot_service_email, telegram_id="bot-service")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Security(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = creds.credentials

    # Persistent service token path for Telegram bot integration.
    if settings.bot_api_token and token == settings.bot_api_token:
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
