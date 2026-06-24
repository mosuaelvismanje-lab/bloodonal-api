from __future__ import annotations

import atexit
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import List

import redis.asyncio as redis
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.dependencies import get_db
from app.config import settings
from app.core.api.exceptions import donor_exception_handler
from app.core.api.middleware import RequestTrackingMiddleware
from app.core.api.response import error
from app.db.database import init_db
from app.firebase_client import _init_firebase
from app.modules.auth.router.auth_router import router as auth_router
from app.modules.auth.users.router.user_router import router as user_router
from app.modules.blood.donors.exceptions import DonorDomainError
from app.modules.blood.donors.router import router as donor_router
from app.modules.blood.requests.router import router as blood_request_router
from app.modules.blood.wallet.router import router as wallet_router
from app.modules.hospital.subscriptions.router import (
    router as hospital_subscriptions_router,
)
from app.modules.notification.router import router as notifications
from app.modules.rewards.router import router as rewards_router
from app.admin.analytics.router import router as admin_analytics_router
from app.admin.operations.router import router as admin_operations_router
from app.api.endpoints import monitoring
from app.api.routes.dispatch_router import router as dispatch_router
from app.core.realtime.manager import RealtimeManager
from app.tasks.payment_tasks import run_payment_worker_loop

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("bloodonal")

# =========================================================
# GLOBAL STATE
# =========================================================
_FIREBASE_TEMP_FILES: List[str] = []


def _cleanup_firebase_temp_files() -> None:
    for path in list(_FIREBASE_TEMP_FILES):
        try:
            if os.path.exists(path):
                os.remove(path)
                log.info("🧹 Removed temp firebase file: %s", path)
        except OSError as e:
            log.warning("Cleanup error: %s", e)

    _FIREBASE_TEMP_FILES.clear()


atexit.register(_cleanup_firebase_temp_files)

# =========================================================
# LIFESPAN
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 Starting Bloodonal Platform")

    app.state.redis = None
    app.state.worker = None
    app.state.realtime_manager = RealtimeManager()

    # -------------------------
    # DB INIT
    # -------------------------
    try:
        await init_db()
        log.info("✅ Database initialized")
    except Exception as e:
        log.error("❌ DB init failed: %s", e, exc_info=True)

    # -------------------------
    # REDIS INIT
    # -------------------------
    redis_url = settings.REDIS_URL or os.getenv("REDIS_URL")

    if redis_url:
        try:
            app.state.redis = redis.from_url(
                redis_url,
                decode_responses=True,
                health_check_interval=30,
            )
            await app.state.redis.ping()
            log.info("✅ Redis connected")
        except Exception as e:
            log.warning("⚠️ Redis unavailable: %s", e)
            app.state.redis = None
    else:
        log.warning("⚠️ Redis URL not configured")

    # -------------------------
    # PAYMENT WORKER
    # -------------------------
    try:
        app.state.worker = asyncio.create_task(run_payment_worker_loop())
        log.info("🚀 Payment worker started")
    except Exception as e:
        log.warning("⚠️ Worker start failed: %s", e)

    # -------------------------
    # FIREBASE INIT
    # -------------------------
    try:
        _init_firebase()
        log.info("🔥 Firebase initialized")
    except Exception as e:
        log.warning("⚠️ Firebase init failed: %s", e)

    yield

    # =====================================================
    # SHUTDOWN
    # =====================================================
    log.info("🛑 Shutting down Bloodonal...")

    # Worker cleanup
    worker = getattr(app.state, "worker", None)
    if worker:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("Worker shutdown error: %s", e)

    # Redis cleanup
    redis_client = getattr(app.state, "redis", None)
    if redis_client:
        try:
            await redis_client.aclose()
        except Exception as e:
            log.warning("Redis close error: %s", e)

    # DB engine cleanup
    try:
        from app.db.session import engine
        await engine.dispose()
    except Exception as e:
        log.warning("DB engine dispose error: %s", e)

    _cleanup_firebase_temp_files()

    log.info("✅ Shutdown complete")


# =========================================================
# APP
# =========================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Bloodonal API — Modular Enterprise Architecture",
    lifespan=lifespan,
)

# -------------------------
# MIDDLEWARE
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestTrackingMiddleware)

# -------------------------
# EXCEPTION HANDLERS
# -------------------------
app.add_exception_handler(DonorDomainError, donor_exception_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error(message="Internal server error"),
    )


# =========================================================
# ROUTER REGISTRATION
# =========================================================
v1 = APIRouter(prefix=f"/{settings.API_VERSION}")

modules = [
    auth_router,
    user_router,
    donor_router,
    blood_request_router,
    wallet_router,
    notifications,
    rewards_router,
    hospital_subscriptions_router,
    admin_analytics_router,
    admin_operations_router,
    dispatch_router,
]

for router in modules:
    v1.include_router(router)
    log.info("Loaded router: %s", getattr(router, "prefix", "unknown"))

# Monitoring
v1.include_router(monitoring.router, prefix="/monitoring")

# =========================================================
# CALLS MODULE
# =========================================================
calls = APIRouter(prefix="/calls", tags=["Calls"])


@calls.post("/session")
async def create_call():
    return {
        "session_id": str(uuid.uuid4()),
        "room": f"bloodonal_{uuid.uuid4().hex[:8]}",
        "server": settings.JITSI_SERVER_URL,
    }


v1.include_router(calls)
app.include_router(v1)


# =========================================================
# ROOT
# =========================================================
@app.get("/")
async def root():
    return {
        "status": "ok",
        "version": settings.API_VERSION,
        "realtime": True,
        "dispatch": True,
    }


# =========================================================
# DB TEST
# =========================================================
@app.get("/db-test")
async def db_test(db=Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}


# =========================================================
# HEALTH / DIAGNOSTICS
# =========================================================
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.API_VERSION,
        "dispatch": "ready",
        "realtime": "ready",
    }


@app.get("/health/redis")
async def redis_health():
    redis_client = getattr(app.state, "redis", None)
    if redis_client is None:
        return {"redis": "unavailable"}

    try:
        await redis_client.ping()
        return {"redis": "ok"}
    except Exception:
        return {"redis": "down"}


# =========================================================
# DEV ENTRY
# =========================================================
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )