import logging
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)


async def get_redis_client(request: Request):
    """
    2026 Standard Redis Dependency

    - Redis is initialized in FastAPI lifespan
    - Stored in app.state.redis
    - Always required (no Optional, no fallback)
    """

    redis = getattr(request.app.state, "redis", None)

    if redis is None:
        logger.error("❌ Redis not initialized in app.state")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service not available",
        )

    return redis