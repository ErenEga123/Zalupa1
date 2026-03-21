import hashlib
import hmac
from urllib.parse import urlencode

from app.core.settings import get_settings


settings = get_settings()


def verify_telegram_login(payload: dict) -> bool:
    incoming_hash = payload.get("hash", "")
    data = {k: v for k, v in payload.items() if k != "hash" and v is not None}
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret_key = hashlib.sha256(settings.bot_token.encode()).digest()
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, incoming_hash)
