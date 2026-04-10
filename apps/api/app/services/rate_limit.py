from fastapi import HTTPException, Request, status

from app.core.redis import redis_client


async def check_rate_limit(
    key: str, max_requests: int, window_seconds: int
) -> None:
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau.",
        )


async def rate_limit_by_ip(
    request: Request, route: str, max_requests: int, window_seconds: int
) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"rl:{route}:{ip}"
    await check_rate_limit(key, max_requests, window_seconds)


async def rate_limit_by_user(
    user_id: int, route: str, max_requests: int, window_seconds: int
) -> None:
    key = f"rl:{route}:u:{user_id}"
    await check_rate_limit(key, max_requests, window_seconds)
