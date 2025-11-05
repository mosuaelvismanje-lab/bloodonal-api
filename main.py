# app/main.py
from pathlib import Path
from contextlib import asynccontextmanager

import firebase_admin
from firebase_admin import credentials
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base


# ─── Initialize Firebase Admin ─────────────────────────────
def init_firebase() -> None:
    cred_path: Path | None = settings.GOOGLE_CREDENTIALS_PATH
    if cred_path and Path(cred_path).exists():
        try:
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
            print(" Firebase Admin initialized")
        except Exception as e:
            print(f" Firebase already initialized or error: {e}")
    else:
        print(" Firebase Admin not initialized. Check GOOGLE_APPLICATION_CREDENTIALS path.")


# ─── Lifespan (startup / shutdown) ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEBUG:  # dev only
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Startup logic
    init_firebase()
    yield
    # Shutdown logic (if needed)
    print("🛑 Application shutdown complete")


# ─── FastAPI app instance ───────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="Handles blood donation, consultations, notifications, and more.",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,   # disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None
)


# ─── CORS Middleware ────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Import and register routers ────────────────────────────
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


# ─── Health check endpoint ─────────────────────────────────
@app.get("/", tags=["health"])
async def root():
    return {
        "message": f"{settings.PROJECT_NAME} (API {settings.API_VERSION}) is up and running!"
    }
