import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import get_settings


class AccessTokenError(ValueError):
    pass


def create_access_token(telegram_id: int) -> str:
    settings = get_settings()
    expires_at = int(time.time()) + settings.access_token_ttl_minutes * 60
    payload = f"{telegram_id}:{expires_at}:{secrets.token_urlsafe(8)}"
    signature = _sign(payload)
    raw_token = f"{payload}:{signature}".encode()
    return base64.urlsafe_b64encode(raw_token).decode().rstrip("=")


def verify_access_token(token: str) -> int:
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        telegram_id, expires_at, nonce, signature = decoded.split(":", maxsplit=3)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AccessTokenError("Invalid access key") from exc

    payload = f"{telegram_id}:{expires_at}:{nonce}"
    if not hmac.compare_digest(signature, _sign(payload)):
        raise AccessTokenError("Invalid access key")
    if int(expires_at) < int(time.time()):
        raise AccessTokenError("Access key expired")
    return int(telegram_id)


def _sign(payload: str) -> str:
    secret = get_settings().app_secret.encode()
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
