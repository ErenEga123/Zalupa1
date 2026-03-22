from pydantic import BaseModel


class UserLookupOut(BaseModel):
    id: str
    email: str | None
    telegram_id: str | None
    is_admin: bool = False
