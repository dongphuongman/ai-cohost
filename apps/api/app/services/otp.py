import secrets

from app.core.redis import redis_client

OTP_TTL = 600  # 10 minutes
OTP_LENGTH = 6


def generate_otp() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(OTP_LENGTH))


async def store_otp(user_id: int, otp: str) -> None:
    key = f"otp:{user_id}"
    await redis_client.setex(key, OTP_TTL, otp)


async def verify_otp(user_id: int, otp: str) -> bool:
    key = f"otp:{user_id}"
    stored = await redis_client.get(key)
    if stored and stored == otp:
        await redis_client.delete(key)
        return True
    return False


async def delete_otp(user_id: int) -> None:
    await redis_client.delete(f"otp:{user_id}")
