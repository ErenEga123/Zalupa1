from datetime import datetime, timedelta, timezone
import secrets

import jwt
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.user import RefreshToken, User


settings = get_settings()


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "telegram_id": user.telegram_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_access_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(db: Session, user: User) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)
    raw = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user.id, token=raw, expires_at=expires_at, revoked=False))
    db.commit()
    return raw


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
