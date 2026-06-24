from __future__ import annotations

from fastapi import Depends, Request

from app.dependencies.redis import get_redis_client
from app.core.container import Container


def get_container(
    request: Request,
    redis_client=Depends(get_redis_client),
) -> Container:
    """
    Returns the application container.

    Production behavior:
    - Reuses a single container per app process
    - Stores the container in app.state
    - Injects Redis from FastAPI lifespan
    - Avoids recreating shared services on every request
    """

    container = getattr(request.app.state, "container", None)

    if container is None:
        container = Container(redis_client=redis_client)
        request.app.state.container = container

    return container