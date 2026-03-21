from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str | None
    telegram_id: str | None
    created_at: datetime


class TelegramAuthIn(BaseModel):
    id: int
    first_name: str | None = None
    username: str | None = None
    auth_date: int
    hash: str


class GoogleCodeIn(BaseModel):
    code: str = Field(min_length=3)


class MagicLinkRequestIn(BaseModel):
    email: EmailStr


class MagicLinkConsumeIn(BaseModel):
    token: str = Field(min_length=12)


class RefreshIn(BaseModel):
    refresh_token: str
