from __future__ import annotations

import os
import logging
import atexit
import uuid
import time
import asyncio
from contextlib import asynccontextmanager
from typing import List

import uvicorn
import redis.asyncio as redis
from fastapi import FastAPI, Depends, APIRouter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Core Infrastructure
from app.api.endpoints import monitoring
from app.config import settings
from app.database import init_db
from app.db.session import get_db, engine

# 2026 Service & Task Imports
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
# Firebase cleanup
# -------------------------
_FIREBASE_TEMP_CRED_FILES: List[str] = []


def _cleanup_firebase_temp_files():
    """Purge temporary credential files on exit."""
    for path in list(_FIREBASE_TEMP_CRED_FILES):
        try:
            if os.path.exists(path):
                os.remove(path)
                log.info("🗑️ Purged: %s", path)
        except OSError as e:
            log.warning("⚠️ Cleanup failed: %s", e)
    _FIREBASE_TEMP_CRED_FILES.clear()


atexit.register(_cleanup_firebase_temp_files)

# -------------------------
# LIFESPAN
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 STARTING BLOODONAL PLATFORM (2026)")

    # Keep optional services safe by default
    app.state.redis = None
    app.state.background_worker = None

    # DB
    try:
        await init_db()
        log.info("✅ Database ready")
    except Exception as e:
        log.error("❌ Database init failed: %s", e, exc_info=True)

    # Redis (optional but preferred)
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
            log.warning("⚠️ Redis unavailable, continuing without Redis: %s", e)
            app.state.redis = None
    else:
        log.warning("⚠️ No REDIS_URL provided, skipping Redis")
        app.state.redis = None

    # Background worker
    try:
        app.state.background_worker = asyncio.create_task(run_payment_worker_loop())
        log.info("🚀 Payment worker started")
    except Exception as e:
        log.warning("⚠️ Payment worker failed to start: %s", e, exc_info=True)
        app.state.background_worker = None

    # Firebase
    try:
        _init_firebase()
        log.info("🔥 Firebase ready")
    except Exception as e:
        log.warning("⚠️ Firebase init failed: %s", e, exc_info=True)

    yield

    log.info("🛑 SHUTDOWN STARTING")

    if getattr(app.state, "background_worker", None) is not None:
        app.state.background_worker.cancel()
        try:
            await app.state.background_worker
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("⚠️ Background worker shutdown issue: %s", e)

    if getattr(app.state, "redis", None) is not None:
        try:
            await app.state.redis.aclose()
        except Exception as e:
            log.warning("⚠️ Redis close failed: %s", e)

    try:
        await engine.dispose()
    except Exception as e:
        log.warning("⚠️ Engine dispose failed: %s", e)

    _cleanup_firebase_temp_files()
    log.info("🛑 CLEAN SHUTDOWN COMPLETE")


# -------------------------
# APP
# -------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Bloodonal API — 2026 Modular Service Architecture",
    lifespan=lifespan,
)

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# MIDDLEWARE
# -------------------------
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("CRASH: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "INTERNAL_SERVER_ERROR"}
    )

# -------------------------
# ROUTERS IMPORTS
# -------------------------
from app.routers import (
    blood_donor,
    blood_request,
    health_provider,
    health_request,
    transport_offer,
    transport_request,
    chat,
    notifications,
    consultation,
    bike_payment,
    doctor_payments,
    nurse_payments,
    taxi_payment,
    webhook_payment,
    servicerouter,
    blood_request_payments,
)

from app.api.admin import router as admin_router

# -------------------------
# VERSION ROUTER
# -------------------------
v1 = APIRouter(prefix=f"/{settings.API_VERSION}")

router_modules = [
    blood_donor,
    blood_request,
    blood_request_payments,
    health_provider,
    health_request,
    transport_offer,
    transport_request,
    chat,
    notifications,
    consultation,
    bike_payment,
    doctor_payments,
    nurse_payments,
    taxi_payment,
    webhook_payment,
    servicerouter,
]

for mod in router_modules:
    v1.include_router(mod.router)
    log.info("✅ Loaded router: %s", mod.__name__)

# Admin + monitoring
v1.include_router(admin_router, prefix="/admin")
v1.include_router(monitoring.router, prefix="/monitoring")

# Calls system
calls = APIRouter(prefix="/calls", tags=["calls"])


@calls.post("/session")
async def call_session(payload: dict):
    return {
        "session_id": str(uuid.uuid4()),
        "room": f"bloodonal_{uuid.uuid4().hex[:8]}",
        "jitsi_server": settings.JITSI_SERVER_URL,
    }


v1.include_router(calls)

# Attach v1
app.include_router(v1)

# -------------------------
# HEALTH CHECK
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {
        "status": "online",
        "version": settings.API_VERSION
    }


@app.get("/db-test", tags=["health"])
async def db_test(db=Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"db": "ok"}


# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)