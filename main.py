from __future__ import annotations

import os
import logging
import atexit
import uuid
import time
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

import uvicorn
import redis.asyncio as redis
from fastapi import FastAPI, Depends, APIRouter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text
from pydantic import BaseModel

from app.api.endpoints import monitoring
from app.config import settings
from app.database import Base, init_db
from app.db.session import get_db, engine

# Models discovery for SQLAlchemy reflection
from app.models.payment import Payment
from app.models.wallet import Wallet
from app.models.usage_counter import UsageCounter

# ✅ 2026 Service & Task Imports
from app.services.registry import registry
from app.tasks.payment_tasks import run_payment_worker_loop
from app.firebase_client import _init_firebase

# -------------------------
# Logging Configuration
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("bloodonal")

# -------------------------
# Firebase temp-file helpers
# -------------------------
_FIREBASE_TEMP_CRED_FILES: List[str] = []


def _cleanup_firebase_temp_files():
    """Securely purges temporary credential files on exit to prevent key leakage."""
    for path in list(_FIREBASE_TEMP_CRED_FILES):
        try:
            if os.path.exists(path):
                os.remove(path)
                log.info(f"🗑️ Cleaned up temporary credential file: {path}")
        except OSError as e:
            log.warning(f"⚠️ Failed to clean up temporary file {path}: {e}")
    _FIREBASE_TEMP_CRED_FILES.clear()


atexit.register(_cleanup_firebase_temp_files)


# -------------------------
# Application lifespan (2026 Production Standard)
# -------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Orchestrates the platform startup and shutdown sequence.
    Ensures all stateful connections (DB, Redis, Firebase) are synchronized.
    """
    log.info("--- STARTING BLOODONAL EMERGENCY HEALTH PLATFORM (2026) ---")

    # 1. ✅ DATABASE SYNC
    try:
        await init_db()
        log.info("✅ Database tables synced successfully.")
    except Exception as e:
        log.error(f"❌ Database sync failed: {e}")

    # 2. ✅ REDIS INITIALIZATION
    try:
        # Utilizing settings.REDIS_URL for consistent environment management
        app.state.redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            health_check_interval=30
        )
        await app.state.redis.ping()
        log.info("✅ Redis connection established and verified.")
    except Exception as e:
        log.error(f"⚠️ Redis initialization failed: {e}")

    # 3. ✅ SERVICE REGISTRY VALIDATION
    try:
        # Load modular service fees/switches (Doctor, Nurse, Blood, etc.)
        log.info(f"✅ Registry loaded with {len(registry._services)} active platform services.")
    except Exception as e:
        log.error(f"⚠️ Registry failed to initialize: {e}")

    # 4. ✅ BACKGROUND WORKER INITIALIZATION
    try:
        # 2026 Logic: Janitor tasks handle pending payment expirations and daily reports
        app.state.background_worker = asyncio.create_task(run_payment_worker_loop())
        log.info("🚀 Background Payment Janitor & Reporting Task started.")
    except Exception as e:
        log.error(f"⚠️ Failed to start background worker: {e}")

    # 5. ✅ FIREBASE INIT
    firebase_ready = _init_firebase()
    log.info("Lifespan startup complete (firebase_ready=%s)", firebase_ready)

    # 6. ✅ ROUTE AUDIT (Debugging)
    log.info("--- REGISTERED API ROUTES ---")
    for route in app.routes:
        if hasattr(route, "path"):
            methods = getattr(route, "methods", "N/A")
            log.info(f"Route: {route.path} | Methods: {methods}")
    log.info("------------------------------")

    yield
    # 🛑 SHUTDOWN LOGIC
    log.info("🛑 Application shutdown starting...")

    # Stop the background worker task
    if hasattr(app.state, "background_worker"):
        app.state.background_worker.cancel()
        try:
            await app.state.background_worker
        except asyncio.CancelledError:
            log.info("✅ Background worker task cancelled.")

    # Gracefully close Redis
    if hasattr(app.state, "redis"):
        await app.state.redis.close()
        log.info("✅ Redis connection closed.")

    # Dispose of SQLAlchemy engine connections
    await engine.dispose()
    log.info("✅ Database engine disposed.")

    _cleanup_firebase_temp_files()
    log.info("🛑 Bloodonal backend shutdown complete.")


# -------------------------
# FastAPI app instance
# -------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Bloodonal API — 2026 SMS Bypass & Modular Payment Architecture",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------
# ✅ Exception Handling & Middleware
# ---------------------------------------------------------

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Adds X-Process-Time header for monitoring performance."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Intercepts unhandled exceptions to prevent 500 crashes on Android frontend."""
    log.error(f"GLOBAL EXCEPTION INTERCEPTED: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred in the health engine."},
    )


# ---------------------------------------------------------
# ✅ Swagger Security Configuration
# ---------------------------------------------------------
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    # Set security globally for all endpoints in the UI
    openapi_schema["security"] = [{"HTTPBearer": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# -------------------------
# CORS Configuration
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Include Routers
# -------------------------
from app.routers import (
    blood_donor, blood_request, health_provider, health_request,
    transport_offer, transport_request, chat, notifications,
    consultation, bike_payment, doctor_payments, nurse_payments,
    taxi_payment, blood_request_payments, webhook_payment
)
from app.api.admin import router as admin_router
# ✅ FIX: Importing internal local monitoring router, NOT sys.monitoring


# ✅ Centralized Versioned Router (v1)
api_router = APIRouter(prefix=f"/{settings.API_VERSION}")

router_modules = [
    blood_donor, blood_request, health_provider, health_request,
    transport_offer, transport_request, chat, notifications,
    consultation, bike_payment, doctor_payments, nurse_payments,
    taxi_payment, blood_request_payments, webhook_payment
]

for module in router_modules:
    if hasattr(module, "router"):
        api_router.include_router(module.router)
    else:
        log.error(f"❌ Critical: Module {module.__name__} is missing a router object!")

# Prefix the Admin & Monitoring Routers
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])

# -------------------------
# Versioned Calls Router (Enhanced Logic)
# -------------------------
call_router = APIRouter(prefix="/calls", tags=["calls"])


class CallRequestPayload(BaseModel):
    caller_id: str
    callee_id: str
    callee_type: str
    call_mode: str  # 'voice' | 'video'


class SessionResponse(BaseModel):
    session_id: str
    room_name: str
    jitsi_server: str
    token: Optional[str] = None


@call_router.post("/session", response_model=SessionResponse)
async def create_call_session(payload: CallRequestPayload):
    """
    Creates a unique Jitsi Room and Call Session for RTC.
    Tracks session IDs for monitoring purposes.
    """
    room_name = f"bloodonal_{uuid.uuid4().hex[:12]}"
    session_id = str(uuid.uuid4())

    # Store pending call in Redis for signaling TTL (45s)
    if hasattr(app.state, "redis"):
        await app.state.redis.setex(f"call:pending:{session_id}", 45, payload.caller_id)

    return SessionResponse(
        session_id=session_id,
        room_name=room_name,
        jitsi_server=settings.JITSI_SERVER_URL
    )


api_router.include_router(call_router)

# Mount the centralized v1 router
app.include_router(api_router)


# -------------------------
# Health Endpoints (PUBLIC)
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {
        "status": "online",
        "message": f"{settings.PROJECT_NAME} 2026 Core Service",
        "version": settings.API_VERSION,
        "date": "2026-02-27",
        "timestamp": time.time(),
        "worker_active": True
    }


@app.get("/db-test", tags=["health"])
async def db_test_route(session=Depends(get_db)):
    """Validates connectivity to the PostgreSQL health cluster."""
    try:
        result = await session.execute(text("SELECT 1 as is_connected"))
        return {"db_status": "connected", "result": int(result.scalar_one())}
    except Exception as e:
        log.error(f"DATABASE TEST FAILED: {e}")
        return {"db_status": "error", "error": str(e)}



# ---------------------------------------------------------
# ✅ PRODUCTION ENTRY POINT
# ---------------------------------------------------------
if __name__ == "__main__":
    # Host 0.0.0.0 for external device access
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)