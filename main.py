# main.py
import os
import base64
import tempfile
import logging
import atexit
from contextlib import asynccontextmanager
from pathlib import Path
import uuid

import firebase_admin
from firebase_admin import credentials, firestore

from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base  # ensures models are imported for Alembic (no side-effects)
from app.db.session import get_db  # dependency that yields AsyncSession (async SQLAlchemy)
# NOTE: app.db.session must create the async engine and AsyncSessionLocal

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
        _cleanup_firebase_temp_files()
        return True
    except ValueError:
        pass

    cred = None
    source = "unknown"

    # 1) GOOGLE_APPLICATION_CREDENTIALS path
    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path and os.path.exists(gac_path):
        cred = credentials.Certificate(gac_path)
        source = f"GOOGLE_APPLICATION_CREDENTIALS from path: {gac_path}"

    # 2) Render / container secret file path
    render_secret_path = "/etc/secrets/FIREBASE_CREDENTIALS_JSON"
    if not cred and os.path.exists(render_secret_path):
        cred = credentials.Certificate(render_secret_path)
        source = f"Render secret file: {render_secret_path}"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = render_secret_path

    # 3) Explicit env var with JSON content
    env_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not cred and env_json:
        path = _write_temp_json(env_json)
        cred = credentials.Certificate(path)
        source = "FIREBASE_CREDENTIALS_JSON env content"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path

    # 4) Base64-encoded env var
    if not cred and os.environ.get("FIREBASE_CRED_BASE64"):
        path = _write_temp_base64(os.environ["FIREBASE_CRED_BASE64"])
        cred = credentials.Certificate(path)
        source = "FIREBASE_CRED_BASE64 env content"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path

    if cred:
        try:
            firebase_admin.initialize_app(cred)
            log.info(f"✅ Firebase initialized from {source}")
            _cleanup_firebase_temp_files()
            return True
        except ValueError as e:
            # default app exists
            if "The default Firebase app already exists." in str(e):
                log.info("Firebase already initialized, skipping.")
                _cleanup_firebase_temp_files()
                return True
            log.error(f"Failed Firebase init from {source}: {e}")
            return False
        except Exception as e:
            log.error(f"Unexpected Firebase init error from {source}: {e}")
            return False

    log.info("No Firebase credentials found; skipping Firebase initialization.")
    return False

# -------------------------
# Application lifespan
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialize firebase (if possible)
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
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# -------------------------
# CORS
# -------------------------
origins_raw = os.getenv("ALLOWED_ORIGINS") or settings.ALLOWED_ORIGINS or ""
if isinstance(origins_raw, str) and origins_raw.strip():
    # allow comma-separated entries in env
    allowed = [o.strip() for o in origins_raw.split(",") if o.strip()]
else:
    allowed = ["http://localhost"]

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
# Core routers (v1)
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
)

# API / payment & admin dashboards (new structure)
# payments router is under app.api.routers.payments (or app.api.routers)
try:
    from app.api.routers import payments as payments_module
    payments_router = getattr(payments_module, "router", None) or payments_module.router
except Exception:
    payments_router = None

# Admin and dashboard (app.api.admin, app.api.dashboard)
try:
    from app.api.admin import router as admin_router
except Exception:
    admin_router = None

try:
    from app.api.dashboard import router as dashboard_router
except Exception:
    dashboard_router = None

# Group API v1 routers
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

app.include_router(api_router)

# include payments/admin/dashboard if available
if payments_router:
    app.include_router(payments_router)
if admin_router:
    app.include_router(admin_router)
if dashboard_router:
    app.include_router(dashboard_router)

# -------------------------
# DB dependency (exposed here for quick usage)
# -------------------------
# Prefer importing get_db from app.db.session across the project.
# This is provided so routes can do: session: AsyncSession = Depends(get_db)
def get_db_dependency():
    return get_db

# -------------------------
# Health / test endpoints
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {"message": f"{settings.PROJECT_NAME} (API {settings.API_VERSION}) is up and running!"}

@app.get("/firebase-test", tags=["health"])
async def firebase_test():
    try:
        # will raise if firebase not initialized
        db = firestore.client()
        collections = [c.id for c in db.collections()]
        return {"collections": collections}
    except Exception as e:
        return {"error": str(e)}

@app.get("/db-test", tags=["health"])
async def db_test_route(session = Depends(get_db)):
    """
    Simple DB connectivity test. Uses get_db from app.db.session.
    """
    try:
        # raw SQL test (should work with async engine)
        result = await session.execute(text("SELECT 1 as is_connected"))
        return {"message": "PostgreSQL connection successful!", "result": int(result.scalar_one())}
    except Exception as e:
        return {"error": f"Database query failed: {e}"}

# -------------------------
# Simple call/session endpoints (example)
# -------------------------
call_router = APIRouter(prefix="/calls", tags=["calls"])

from pydantic import BaseModel

class CallRequestPayload(BaseModel):
    caller_id: str
    callee_id: str
    callee_type: str
    call_mode: str  # VOICE or VIDEO

class SessionResponse(BaseModel):
    session_id: str
    room_name: str
    token: str | None = None

@call_router.post("/session", response_model=SessionResponse)
async def create_call_session(payload: CallRequestPayload):
    room_name = f"call_{uuid.uuid4().hex}"
    session_id = str(uuid.uuid4())
    token = None
    return SessionResponse(session_id=session_id, room_name=room_name, token=token)

@call_router.post("/session/voice", response_model=SessionResponse)
async def create_voice_session(payload: CallRequestPayload):
    payload.call_mode = "VOICE"
    return await create_call_session(payload)

@call_router.post("/session/video", response_model=SessionResponse)
async def create_video_session(payload: CallRequestPayload):
    payload.call_mode = "VIDEO"
    return await create_call_session(payload)

class EndCallRequest(BaseModel):
    session_id: str

@call_router.post("/session/end")
async def end_call(request: EndCallRequest):
    return {"success": True, "message": f"Call {request.session_id} ended."}

app.include_router(call_router)

# -------------------------
# Nothing to run at import time (no uvicorn.run)
# -------------------------
