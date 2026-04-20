from __future__ import annotations

import os
import logging
import atexit
import uuid
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List

import uvicorn
import redis.asyncio as redis
from fastapi import FastAPI, Depends, APIRouter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from pydantic import BaseModel

# Core Infrastructure
from app.api.endpoints import monitoring
from app.config import settings
from app.database import init_db
from app.db.session import get_db, engine

# ✅ 2026 Service & Task Imports
from app.services.registry import registry
from app.tasks.payment_tasks import run_payment_worker_loop
from app.firebase_client import _init_firebase

# -------------------------
# Logging Configuration
# -------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("bloodonal")

# -------------------------
# Firebase cleanup
# -------------------------
_FIREBASE_TEMP_CRED_FILES: List[str] = []


def _cleanup_firebase_temp_files():
    """Purge temporary credential files on exit to prevent leakage."""
    for path in list(_FIREBASE_TEMP_CRED_FILES):
        try:
            if os.path.exists(path):
                os.remove(path)
                log.info(f"🗑️ Purged: {path}")
        except OSError as e:
            log.warning(f"⚠️ Cleanup failed: {e}")
    _FIREBASE_TEMP_CRED_FILES.clear()


atexit.register(_cleanup_firebase_temp_files)


# -------------------------
# Lifespan (Startup/Shutdown)
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("--- STARTING BLOODONAL PLATFORM (2026) ---")

    # 1. Database Initialization
    try:
        await init_db()
        log.info("✅ Database tables synced successfully.")
    except Exception as e:
        log.error(f"❌ Database sync failed: {e}")

    # 2. Redis Initialization (Async)
    if settings.REDIS_URL:
        try:
            app.state.redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                health_check_interval=30
            )
            await app.state.redis.ping()
            log.info("✅ Redis connection established.")
        except Exception as e:
            log.error(f"⚠️ Redis initialization failed: {e}")

    # 3. Background Task Runner
    # Handles payment expirations, janitor tasks, and modular reporting
    app.state.background_worker = asyncio.create_task(run_payment_worker_loop())
    log.info("🚀 Background Payment Janitor & Worker started.")

    # 4. Firebase Initialization
    _init_firebase()

    yield
    # 🛑 SHUTDOWN LOGIC
    log.info("🛑 Application shutdown starting...")
    if hasattr(app.state, "background_worker"):
        app.state.background_worker.cancel()
        log.info("✅ Background worker task cancelled.")

    if hasattr(app.state, "redis"):
        await app.state.redis.close()
        log.info("✅ Redis connection closed.")

    await engine.dispose()
    log.info("✅ Database engine connections disposed.")

    _cleanup_firebase_temp_files()
    log.info("🛑 Bloodonal backend shutdown complete.")


# -------------------------
# FastAPI App Instance
# -------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Bloodonal API — 2026 Modular Service Architecture",
    lifespan=lifespan
)

# -------------------------
# Middlewares
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    """Calculates performance overhead for each request."""
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevents backend crashes from exposing raw errors to Android clients."""
    log.error(f"CRASH INTERCEPTED: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred."}
    )


# -------------------------
# Routers Registration
# -------------------------
from app.routers import (
    blood_donor, blood_request, health_provider, health_request,
    transport_offer, transport_request, chat, notifications,
    consultation, bike_payment, doctor_payments, nurse_payments,
    taxi_payment, webhook_payment, servicerouter  # ✅ New Search Router Included
)
from app.api.admin import router as admin_router

# ✅ Centralized Versioned Router (v1)
v1 = APIRouter(prefix=f"/{settings.API_VERSION}")

# Modular route distribution
router_modules = [
    blood_donor, blood_request, health_provider, health_request,
    transport_offer, transport_request, chat, notifications,
    consultation, bike_payment, doctor_payments, nurse_payments,
    taxi_payment, webhook_payment, servicerouter
]

for mod in router_modules:
    if hasattr(mod, "router"):
        v1.include_router(mod.router)
    else:
        log.error(f"❌ Error: {mod.__name__} has no 'router' attribute.")

# Admin and Monitoring
v1.include_router(admin_router, prefix="/admin", tags=["admin"])
v1.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])

# Signaling/RTC Hub
calls = APIRouter(prefix="/calls", tags=["calls"])


@calls.post("/session")
async def call_session(payload: dict):
    """Generates a secure room name for RTC signaling."""
    return {
        "session_id": str(uuid.uuid4()),
        "room": f"bloodonal_{uuid.uuid4().hex[:8]}",
        "jitsi_server": settings.JITSI_SERVER_URL
    }


v1.include_router(calls)
app.include_router(v1)


# -------------------------
# Health Endpoints (Public)
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {
        "status": "online",
        "v": settings.API_VERSION,
        "service": settings.PROJECT_NAME
    }


@app.get("/db-test", tags=["health"])
async def db_test(db=Depends(get_db)):
    """Validates connectivity to the PostgreSQL health cluster."""
    try:
        await db.execute(text("SELECT 1"))
        return {"db": "connected"}
    except Exception as e:
        return {"db": "error", "detail": str(e)}


# -------------------------
# Production Entry Point
# -------------------------
if __name__ == "__main__":
    # Ensure uvicorn calls main:app for the reload functionality
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)