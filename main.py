import os
import base64
import tempfile
import uvicorn
import logging
import atexit
from contextlib import asynccontextmanager
from pathlib import Path
import uuid

import firebase_admin
from firebase_admin import credentials, firestore

from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.database import Base  # declarative base for Alembic / async

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bloodonal")

# -------------------------
# Firebase helper functions
# -------------------------
global firebase_ready
firebase_ready: bool = False
_FIREBASE_TEMP_CRED_FILES = []

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
    for path in _FIREBASE_TEMP_CRED_FILES:
        try:
            os.remove(path)
            log.debug(f"Cleaned up temporary credential file: {path}")
        except OSError as e:
            log.warning(f"Failed to clean up temporary file {path}: {e}")
    _FIREBASE_TEMP_CRED_FILES.clear()

atexit.register(_cleanup_firebase_temp_files)

def init_firebase() -> bool:
    """Initialize Firebase Admin SDK."""
    global firebase_ready
    try:
        firebase_admin.get_app()
        log.info("Firebase default app already initialized.")
        _cleanup_firebase_temp_files()
        return True
    except ValueError:
        pass

    cred = None
    source = "unknown"

    # Try GOOGLE_APPLICATION_CREDENTIALS
    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path and os.path.exists(gac_path):
        cred = credentials.Certificate(gac_path)
        source = f"GOOGLE_APPLICATION_CREDENTIALS from path: {gac_path}"

    # Render secret
    render_secret_path = "/etc/secrets/FIREBASE_CREDENTIALS_JSON"
    if not cred and os.path.exists(render_secret_path):
        cred = credentials.Certificate(render_secret_path)
        source = f"Render secret file: {render_secret_path}"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = render_secret_path

    # FIREBASE_CREDENTIALS_JSON env
    if not cred and os.environ.get("FIREBASE_CREDENTIALS_JSON"):
        path = _write_temp_json(os.environ["FIREBASE_CREDENTIALS_JSON"])
        cred = credentials.Certificate(path)
        source = "FIREBASE_CREDENTIALS_JSON env content"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path

    # FIREBASE_CRED_BASE64 env
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
            if "The default Firebase app already exists." in str(e):
                log.info("Firebase already initialized, skipping.")
                _cleanup_firebase_temp_files()
                return True
            else:
                log.error(f"Failed Firebase init from {source}: {e}")
                return False
        except Exception as e:
            log.error(f"Unexpected Firebase init error from {source}: {e}")
            return False
    else:
        log.error("No valid Firebase credentials found.")
        return False

# -------------------------
# Database Engines
# -------------------------
# Async engine for FastAPI
ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL") or settings.ASYNC_DATABASE_URL
if not ASYNC_DATABASE_URL:
    raise RuntimeError("ASYNC_DATABASE_URL not set")
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
log.info("✅ Async SQLAlchemy engine initialized")

# Sync engine for Alembic / migrations
DATABASE_URL = os.getenv("DATABASE_URL") or settings.DATABASE_URL
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")
sync_engine = create_engine(DATABASE_URL, echo=settings.DEBUG)
log.info("✅ Sync SQLAlchemy engine initialized")

# -------------------------
# Lifespan
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global firebase_ready
    firebase_ready = init_firebase()
    yield
    log.info("🛑 Application shutdown complete")

# -------------------------
# FastAPI App
# -------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Handles blood donation, consultations, notifications, and more.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Import Routers
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
)
from app.api.routers import payments

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
app.include_router(payments.router)

# -------------------------
# DB Dependency
# -------------------------
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# -------------------------
# Health / Test
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {"message": f"{settings.PROJECT_NAME} (API {settings.API_VERSION}) is up and running!"}

@app.get("/firebase-test")
async def firebase_test():
    global firebase_ready
    if not firebase_ready:
        return {"error": "Firebase Admin SDK not initialized."}
    try:
        db = firestore.client()
        collections = [col.id for col in db.collections()]
        return {"collections": collections}
    except Exception as e:
        return {"error": str(e)}

@app.get("/db-test")
async def db_test_route(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(text("SELECT 1 as is_connected"))
        return {"message": "PostgreSQL connection successful!", "result": result.scalar()}
    except Exception as e:
        return {"error": f"Database query failed: {e}"}

# -------------------------
# Call / Video Endpoints
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
    token = None  # Add JWT if needed
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
# Run Uvicorn if executed directly
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Default 8000 if PORT not set
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
