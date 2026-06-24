from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.realtime.manager import RealtimeManager

from app.modules.dispatch.repository import DispatchRepository
from app.modules.dispatch.service import DispatchService

from app.modules.dispatch.schemas import (
    AssignmentRequestSchema,
    AssignmentResponse,
    ClusterResponse,
    NearbyRequestsResponse,
    LocationUpdateDTO,
    LocationUpdateResponse,
    DispatchEventResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dispatch",
    tags=["Dispatch"],
)

# =========================================================
# DEPENDENCIES
# =========================================================

def get_dispatch_service(
    db: AsyncSession = Depends(get_db_session),
) -> DispatchService:
    repo = DispatchRepository(db)
    return DispatchService(repo)


def get_realtime_manager(request: Request) -> RealtimeManager:
    manager = getattr(request.app.state, "realtime_manager", None)
    if not manager:
        raise HTTPException(status_code=503, detail="Realtime unavailable")
    return manager


# =========================================================
# NEARBY REQUESTS
# =========================================================

@router.get("/nearby", response_model=NearbyRequestsResponse)
async def get_nearby_requests(
    service_type: str,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 50.0,
    blood_group: str | None = None,
    limit: int = 200,
    include_clusters: bool = False,
    cluster_precision_km: float = 1.0,
    service: DispatchService = Depends(get_dispatch_service),
):
    try:
        return await service.get_nearby_requests(
            service_type=service_type,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            blood_group=blood_group,
            limit=limit,
            include_clusters=include_clusters,
            cluster_precision_km=cluster_precision_km,
        )
    except Exception as exc:
        logger.exception("Nearby requests failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch nearby requests")


# =========================================================
# CLUSTERS
# =========================================================

@router.get("/clusters", response_model=ClusterResponse)
async def get_clusters(
    service_type: str,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 50.0,
    blood_group: str | None = None,
    limit: int = 200,
    cluster_precision_km: float = 1.0,
    service: DispatchService = Depends(get_dispatch_service),
):
    try:
        return await service.get_clusters(
            service_type=service_type,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            blood_group=blood_group,
            limit=limit,
            cluster_precision_km=cluster_precision_km,
        )
    except Exception as exc:
        logger.exception("Cluster fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch clusters")


# =========================================================
# ASSIGNMENT (IMPORTANT FIX)
# =========================================================

@router.post("/assign", response_model=AssignmentResponse)
async def assign_request(
    payload: AssignmentRequestSchema,
    service: DispatchService = Depends(get_dispatch_service),
):
    try:
        # FIXED: match service method signature style
        return await service.assign_best_match(
            request_id=payload.request_id,
            candidates=payload.candidates,
        )
    except Exception as exc:
        logger.exception("Assignment failed: %s", exc)
        raise HTTPException(status_code=500, detail="Assignment failed")


# =========================================================
# LOCATION UPDATE
# =========================================================

@router.post("/location/update", response_model=LocationUpdateResponse)
async def update_location(
    payload: LocationUpdateDTO,
    service: DispatchService = Depends(get_dispatch_service),
):
    try:
        return await service.update_location(payload)
    except Exception as exc:
        logger.exception("Location update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Location update failed")


# =========================================================
# EVENTS
# =========================================================

@router.post("/event", response_model=DispatchEventResponse)
async def publish_event(
    payload: Dict[str, Any],
    service: DispatchService = Depends(get_dispatch_service),
):
    try:
        return await service.publish_event(payload)
    except Exception as exc:
        logger.exception("Event publish failed: %s", exc)
        raise HTTPException(status_code=500, detail="Event publish failed")


# =========================================================
# WEBSOCKET (MOVE LATER)
# =========================================================

@router.websocket("/ws/{service_type}")
async def dispatch_websocket(websocket: WebSocket, service_type: str):
    """
    TEMPORARY: should move to:
    app/modules/dispatch/websocket.py
    """
    await websocket.accept()

    while True:
        msg = await websocket.receive_text()

        if msg == "ping":
            await websocket.send_json({"type": "pong"})