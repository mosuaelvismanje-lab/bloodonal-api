import os
import base64
import tempfile
import logging
import atexit
from contextlib import asynccontextmanager
from pathlib import Path
import uuid
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from fastapi import FastAPI, Depends, APIRouter, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from pydantic import BaseModel

from app.config import settings
from app.database import Base
# ✅ Keep get_db for health checks, but ensure routers use get_db_session for testing
from app.db.session import get_db

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bloodonal")

# -------------------------
# Firebase temp-file helpers
# -------------------------
_FIREBASE_TEMP_CRED_FILES: list[str] = []

def _write_temp_json(json_str: str) -> str:
    fd, path = tempfile.mkstemp(prefix="firebase_", suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)
    _FIREBASE_TEMP_CRED_FILES.append(path)
    return path

def _write_temp_base64(b64: str) -> str:
    fd, path = tempfile.mkstemp(prefix="firebase_", suffix=".json")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    _FIREBASE_TEMP_CRED_FILES.append(path)
    return path

def _cleanup_firebase_temp_files():
    for path in list(_FIREBASE_TEMP_CRED_FILES):
        try:
            os.remove(path)
            log.debug(f"Cleaned up temporary credential file: {path}")
        except OSError as e:
            log.warning(f"Failed to clean up temporary file {path}: {e}")
    _FIREBASE_TEMP_CRED_FILES.clear()

atexit.register(_cleanup_firebase_temp_files)

def init_firebase() -> bool:
    """Initialize Firebase Admin SDK if credentials are present."""
    try:
        firebase_admin.get_app()
        log.info("Firebase default app already initialized.")
        return True
    except ValueError:
        pass

    cred = None
    source = "unknown"

    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path and os.path.exists(gac_path):
        cred = credentials.Certificate(gac_path)
        source = f"GOOGLE_APPLICATION_CREDENTIALS from path: {gac_path}"

    render_secret_path = "/etc/secrets/FIREBASE_CREDENTIALS_JSON"
    if not cred and os.path.exists(render_secret_path):
        cred = credentials.Certificate(render_secret_path)
        source = f"Render secret file: {render_secret_path}"

    env_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not cred and env_json:
        path = _write_temp_json(env_json)
        cred = credentials.Certificate(path)
        source = "FIREBASE_CREDENTIALS_JSON env content"

    if not cred and os.environ.get("FIREBASE_CRED_BASE64"):
        path = _write_temp_base64(os.environ["FIREBASE_CRED_BASE64"])
        cred = credentials.Certificate(path)
        source = "FIREBASE_CRED_BASE64 env content"

    if cred:
        try:
            firebase_admin.initialize_app(cred)
            log.info(f"✅ Firebase initialized from {source}")
            return True
        except Exception as e:
            log.error(f"Failed Firebase init from {source}: {e}")
            return False

    log.info("No Firebase credentials found; skipping Firebase initialization.")
    return False

# -------------------------
# Application lifespan
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    firebase_ready = init_firebase()
    log.info("Lifespan startup complete (firebase_ready=%s)", firebase_ready)
    yield
    log.info("🛑 Application shutdown complete")
    _cleanup_firebase_temp_files()

# -------------------------
# FastAPI app instance
# -------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Bloodonal API — consultations, payments, notifications, and more.",
    lifespan=lifespan,
    # ✅ FIX: Enable documentation in production regardless of settings.DEBUG
    docs_url="/docs",
    redoc_url="/redoc",
)

# -------------------------
# CORS
# -------------------------
origins_raw = os.getenv("ALLOWED_ORIGINS") or settings.ALLOWED_ORIGINS or ""
if isinstance(origins_raw, str) and origins_raw.strip():
    allowed = [o.strip() for o in origins_raw.split(",") if o.strip()]
else:
    allowed = ["*"] # ✅ Temporarily allowing all for testing on mobile

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Include routers
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
    blood_request_payments
)

api_router = APIRouter(prefix=f"/{settings.API_VERSION}")

api_router.include_router(blood_donor.router)
api_router.include_router(blood_request.router)
api_router.include_router(health_provider.router)
api_router.include_router(health_request.router)
api_router.include_router(transport_offer.router)
api_router.include_router(transport_request.router)
api_router.include_router(chat.router)
api_router.include_router(notifications.router)
api_router.include_router(consultation.router)
api_router.include_router(bike_payment.router)
api_router.include_router(doctor_payments.router)
api_router.include_router(nurse_payments.router)
api_router.include_router(taxi_payment.router)
api_router.include_router(blood_request_payments.router)

app.include_router(api_router)

# Optional Dashboard/Admin Routers
try:
    from app.api.routers import payments as payments_module
    app.include_router(payments_module.router)
except (ImportError, AttributeError):
    log.debug("Payments module router not found, skipping.")

try:
    from app.api.admin import router as admin_router
    app.include_router(admin_router)
except (ImportError, AttributeError):
    log.debug("Admin router not found, skipping.")

try:
    from app.api.dashboard import router as dashboard_router
    app.include_router(dashboard_router)
except (ImportError, AttributeError):
    log.debug("Dashboard router not found, skipping.")

# -------------------------
# Health / test endpoints
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {
        "message": f"{settings.PROJECT_NAME} (API {settings.API_VERSION}) is up and running!",
        "docs": "/docs",
        "status": "online"
    }

@app.get("/db-test", tags=["health"])
async def db_test_route(session = Depends(get_db)):
    try:
        result = await session.execute(text("SELECT 1 as is_connected"))
        return {"message": "PostgreSQL connection successful!", "result": int(result.scalar_one())}
    except Exception as e:
        return {"error": f"Database query failed: {e}"}

# -------------------------
# Simple call/session endpoints
# -------------------------
call_router = APIRouter(prefix="/calls", tags=["calls"])

class CallRequestPayload(BaseModel):
    caller_id: str
    callee_id: str
    callee_type: str
    call_mode: str

class SessionResponse(BaseModel):
    session_id: str
    room_name: str
    token: Optional[str] = None

@call_router.post("/session", response_model=SessionResponse)
async def create_call_session(payload: CallRequestPayload):
    room_name = f"call_{uuid.uuid4().hex}"
    session_id = str(uuid.uuid4())
    return SessionResponse(session_id=session_id, room_name=room_name)

app.include_router(call_router)