import redis.asyncio as redis
from app.config import settings

# Global pool to reuse connections
_redis_pool = None

def get_redis_client():
    """
    Returns a Redis client instance.
    In FastAPI, this is often used as a dependency.
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_pool