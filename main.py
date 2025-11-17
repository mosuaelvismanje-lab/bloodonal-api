import os
import base64
import tempfile
import logging
import atexit
from contextlib import asynccontextmanager
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
# === FORCED COMMIT FIX: Nov 2025 ===
from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# Assuming these imports exist and are necessary for your full application:

from app.database import engine, Base
from config import settings

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bloodonal")

# Global variable to track Firebase initialization status (Updated inside lifespan)
global firebase_ready
firebase_ready: bool = False

# List to keep track of temporary files created for Firebase credentials
_FIREBASE_TEMP_CRED_FILES = []

def _write_temp_json(json_str: str) -> str:
    """Write raw JSON string to a temporary file and return its path."""
    fd, path = tempfile.mkstemp(prefix="firebase_", suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)
    _FIREBASE_TEMP_CRED_FILES.append(path)
    return path

def _write_temp_base64(b64: str) -> str:
    """Decode base64 and write to a temp file, return path."""
    fd, path = tempfile.mkstemp(prefix="firebase_", suffix=".json")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    _FIREBASE_TEMP_CRED_FILES.append(path)
    return path

def _cleanup_firebase_temp_files():
    """Removes all temporary Firebase credential files created."""
    for path in _FIREBASE_TEMP_CRED_FILES:
        try:
            os.remove(path)
            log.debug(f"Cleaned up temporary credential file: {path}")
        except OSError as e:
            log.warning(f"Failed to clean up temporary file {path}: {e}")
    _FIREBASE_TEMP_CRED_FILES.clear()

# Register cleanup function to run at program exit
atexit.register(_cleanup_firebase_temp_files)


# -------------------------
# Firebase Initialization (robust & idempotent)
# -------------------------
def init_firebase() -> bool:
    """
    Attempt multiple strategies to initialize firebase_admin exactly once.
    """
    try:
        firebase_admin.get_app()
        log.info("Firebase default app already initialized (skipping initialization process).")
        _cleanup_firebase_temp_files()
        return True
    except ValueError:
        log.info("Firebase default app not found, attempting to initialize...")
        pass

    cred = None
    cred_source_description = "unknown source"

    # Strategy 2: GOOGLE_APPLICATION_CREDENTIALS env path
    gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac_path and os.path.exists(gac_path):
        try:
            cred = credentials.Certificate(gac_path)
            cred_source_description = f"GOOGLE_APPLICATION_CREDENTIALS from path: {gac_path}"
        except Exception as e:
            log.warning(f"Failed to load credentials from GOOGLE_APPLICATION_CREDENTIALS ('{gac_path}'): {e}")

    # Strategy 3: Render secret file path
    if not cred:
        render_secret_path = "/etc/secrets/FIREBASE_CREDENTIALS_JSON"
        if os.path.exists(render_secret_path):
            try:
                cred = credentials.Certificate(render_secret_path)
                cred_source_description = f"Render secret file: {render_secret_path}"
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = render_secret_path
            except Exception as e:
                log.warning(f"Failed to load credentials from Render secret file ('{render_secret_path}'): {e}")

    # Strategy 4: RAW JSON in FIREBASE_CREDENTIALS_JSON env var
    if not cred:
        firebase_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if firebase_json:
            try:
                path = _write_temp_json(firebase_json)
                cred = credentials.Certificate(path)
                cred_source_description = "FIREBASE_CREDENTIALS_JSON env content"
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            except Exception as e:
                log.warning(f"Failed to load credentials from FIREBASE_CREDENTIALS_JSON env: {e}")

    # Strategy 5: Base64 in FIREBASE_CRED_BASE64 env var
    if not cred:
        firebase_b64 = os.environ.get("FIREBASE_CRED_BASE64")
        if firebase_b64:
            try:
                path = _write_temp_base64(firebase_b64)
                cred = credentials.Certificate(path)
                cred_source_description = "FIREBASE_CRED_BASE64 env content"
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            except Exception as e:
                log.warning(f"Failed to load credentials from FIREBASE_CRED_BASE64 env: {e}")

    # Final initialization attempt if credentials were found
    if cred:
        try:
            firebase_admin.initialize_app(cred)
            log.info(f"✅ Firebase initialized successfully from {cred_source_description}.")
            _cleanup_firebase_temp_files()
            return True
        except ValueError as e:
            if "The default Firebase app already exists." in str(e):
                log.info(f"Firebase default app was initialized concurrently, handling idempotently.")
                _cleanup_firebase_temp_files()
                return True
            else:
                log.error(f"❌ Failed to initialize Firebase with {cred_source_description}: {e}")
                return False
        except Exception as e:
            log.error(f"❌ An unexpected error occurred during Firebase initialization from {cred_source_description}: {e}")
            return False
    else:
        log.error(f"❌ Firebase initialization failed: No valid credentials found after checking all strategies.")
        return False


# -------------------------
# Database Initialization
# -------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    log.critical("DATABASE_URL environment variable not set. Exiting.")
    raise RuntimeError("DATABASE_URL environment variable not set")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

log.info("✅ Async SQLAlchemy engine initialized")

# -------------------------
# Lifespan (startup / shutdown)
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP LOGIC: This runs ONCE at startup (The FIX)
    global firebase_ready
    firebase_ready = init_firebase()

    # NOTE: Uncomment if you need DB schema creation in debug mode
    # if settings.DEBUG:
    #     async with engine.begin() as conn:
    #         await conn.run_sync(Base.metadata.create_all)

    yield # Application starts here

    # SHUTDOWN LOGIC
    log.info("🛑 Application shutdown complete")


# -------------------------
# FastAPI App Instance
# -------------------------
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Handles blood donation, consultations, notifications, and more.",
    lifespan=lifespan, # CRITICAL: Associates startup/shutdown logic
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)


# -------------------------
# CORS Middleware
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Import and Register Routers
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

# Grouped includes
api_router.include_router(blood_donor.router)
api_router.include_router(blood_request.router)
api_router.include_router(health_provider.router)
api_router.include_router(health_request.router)

api_router.include_router(transport_offer.router)
api_router.include_router(transport_request.router)

api_router.include_router(chat.router)
api_router.include_router(notifications.router)
api_router.include_router(consultation.router)

# Register all routers
app.include_router(api_router)
app.include_router(payments.router)


# -------------------------
# Dependency for DB sessions
# -------------------------
async def get_db() -> AsyncSession:
    """Provides a transactional database session."""
    async with AsyncSessionLocal() as session:
        yield session


# -------------------------
# Health Check and Test Routes
# -------------------------
@app.get("/", tags=["health"])
async def root():
    return {
        "message": f"{settings.PROJECT_NAME} (API {settings.API_VERSION}) is up and running!"
    }


@app.get("/firebase-test")
async def firebase_test():
    global firebase_ready
    if not firebase_ready:
        return {"error": "Firebase Admin SDK not initialized."}
    try:
        # Access the default app implicitly
        db = firestore.client()
        collections = [col.id for col in db.collections()]
        return {"collections": collections}
    except Exception as e:
        return {"error": str(e)}

@app.get("/db-test")
async def db_test_route(session: AsyncSession = Depends(get_db)):
    """Tests the database connection and session using a simple query."""
    try:
        result = await session.execute(text("SELECT 1 as is_connected"))
        is_connected = result.scalar()
        return {"message": "PostgreSQL connection successful!", "status": "OK", "result": is_connected}
    except Exception as e:
        return {"error": f"Database query failed: {e}"}