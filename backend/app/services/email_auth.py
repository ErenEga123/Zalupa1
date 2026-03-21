from datetime import datetime, timedelta, timezone
import secrets
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.user import EmailMagicLinkToken, User


settings = get_settings()


def create_or_get_user_by_email(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_magic_link(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.email_magic_link_ttl_seconds)
    db.add(EmailMagicLinkToken(user_id=user.id, token=token, expires_at=expires))
    db.commit()
    return token


def consume_magic_link(db: Session, token: str) -> User | None:
    row = db.scalar(select(EmailMagicLinkToken).where(EmailMagicLinkToken.token == token))
    now = datetime.now(timezone.utc)
    if not row or row.used_at is not None or row.expires_at < now:
        return None
    row.used_at = now
    user = db.get(User, row.user_id)
    db.commit()
    return user


def send_magic_link(email: str, token: str) -> None:
    link = f"{settings.app_base_url}/api/v1/auth/magic/consume?token={token}"
    msg = EmailMessage()
    msg["Subject"] = "Your Reader System sign-in link"
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg.set_content(f"Sign in: {link}")

    if not settings.smtp_host:
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
