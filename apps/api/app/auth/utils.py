import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import redis.asyncio as aioredis
from jose import JWTError, jwt

from app.core.config import settings

_redis = aioredis.from_url(settings.redis_url)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, shop_ids: list[int]) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload = {
        "sub": str(user_id),
        "shop_ids": shop_ids,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_expire_days)
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def consume_refresh_jti(jti: str, expire_days: int | None = None) -> bool:
    """Mark a refresh token JTI as used. Returns True if it was unused (valid).

    Uses Redis SETNX to ensure single-use: the first call returns True,
    subsequent calls return False (token replay detected).
    """
    ttl = (expire_days or settings.jwt_refresh_expire_days) * 86400
    key = f"rt_used:{jti}"
    was_new = await _redis.set(key, "1", nx=True, ex=ttl)
    return was_new is not None


def create_reset_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=1)
    payload = {
        "sub": str(user_id),
        "type": "reset",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_token_expiry_seconds() -> int:
    return settings.jwt_access_expire_minutes * 60
