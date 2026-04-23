from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Dict, List, Optional, Union
from urllib.parse import quote_plus, urlencode, urlparse, urlunparse, parse_qs

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    """
    Application settings loaded from environment or .env.
    Unified for Bloodonal Emergency Health Platform 2026.
    Optimized for high-concurrency (Modular Services).
    """

    # -------------------------
    # General / Runtime
    # -------------------------
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "please-change-me-at-all-costs-2026"

    # SECURITY: Admin & Worker Protection
    ADMIN_SECRET_TOKEN: str = "bloodonal-admin-secure-2026-x9z-secret"
    WEBHOOK_SECRET: str = "bloodonal-webhook-secure-2026-w9y-secret"

    PYTHONUNBUFFERED: int = 1

    # -------------------------
    # App Meta
    # -------------------------
    PROJECT_NAME: str = "Bloodonal Emergency Health Platform"
    API_VERSION: str = "v1"

    # -------------------------
    # Database Configuration & Scaling
    # -------------------------
    DATABASE_URL: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None

    DB_POOL_SIZE: int = 100
    DB_MAX_OVERFLOW: int = 50

    # -------------------------
    # Redis & Background Tasks
    # -------------------------
    REDIS_URL: Optional[str] = None

    # Worker Settings
    WORKER_CLEANUP_INTERVAL_SECONDS: int = 300
    DAILY_REPORT_HOUR_UTC: int = 23

    # -------------------------
    # Firebase / Google Credentials
    # -------------------------
    FIREBASE_PROJECT_ID: str = "bloodonalfirebase"
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # -------------------------
    # CORS Configuration
    # -------------------------
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = ["*"]

    # -------------------------
    # Payment Providers & Merchant Accounts
    # -------------------------
    PAYMENT_GATEWAY: str = "mock"

    ADMIN_MTN_NUMBER: str = "670556320"
    ADMIN_ORANGE_NUMBER: str = "690000000"

    STRIPE_API_KEY: Optional[str] = None
    FLUTTERWAVE_SECRET: Optional[str] = None
    MTN_MOMO_API_KEY: Optional[str] = None
    MTN_MOMO_SUBSCRIPTION_KEY: Optional[str] = None
    MTN_MOMO_ENVIRONMENT: str = "sandbox"

    GATEWAY_TIMEOUT: float = 30.0

    # -------------------------
    # Calls & Video
    # -------------------------
    JITSI_SERVER_URL: str = "https://meet.jit.si"
    CALL_SESSION_TIMEOUT_MINUTES: int = 60
    CALL_SIGNALING_TTL_SECONDS: int = 45

    # -------------------------
    # Monitoring & Analytics
    # -------------------------
    ENABLE_MONITORING: bool = True
    PROMETHEUS_METRICS_ENABLED: bool = True
    STATS_CACHE_TTL: int = 300

    # -------------------------
    # Usage Limits (Quotas)
    # -------------------------
    LIMIT_DOCTOR_CONSULT: int = 5
    LIMIT_NURSE_CONSULT: int = 5
    LIMIT_BIKE_REQUEST: int = 5
    LIMIT_TAXI_REQUEST: int = 5
    LIMIT_BLOOD_REQUEST: int = 5

    # -------------------------
    # Fees (XAF)
    # -------------------------
    FEE_DOCTOR_CONSULT: int = 200
    FEE_NURSE_CONSULT: int = 150
    FEE_BIKE_REQUEST: int = 100
    FEE_TAXI_REQUEST: int = 100
    FEE_BLOOD_REQUEST: int = 500

    # -------------------------
    # Global Switches
    # -------------------------
    PAYMENT_ENABLED_BLOOD_REQUEST: bool = True
    PAYMENT_ENABLED_DOCTOR_CONSULT: bool = True
    PAYMENT_ENABLED_NURSE_CONSULT: bool = True
    PAYMENT_ENABLED_BIKE_REQUEST: bool = True
    PAYMENT_ENABLED_TAXI_REQUEST: bool = True

    # -------------------------
    # Promo Messages
    # -------------------------
    BLOOD_PROMO_MESSAGE: str = ""
    DOCTOR_PROMO_MESSAGE: str = ""
    NURSE_PROMO_MESSAGE: str = ""
    BIKE_PROMO_MESSAGE: str = ""
    TAXI_PROMO_MESSAGE: str = ""

    # -------------------------
    # Logging
    # -------------------------
    LOG_DIR: str = "logs"
    LOG_LEVEL: str = "INFO"

    # -------------------------
    # Helper Properties
    # -------------------------
    def _add_ssl_mode(self, url: str) -> str:
        """Append sslmode=require if missing for cloud DBs like Render/Neon."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return url

        if not parsed.hostname:
            return url

        query_params = parse_qs(parsed.query)
        if "sslmode" not in query_params:
            query_params["sslmode"] = ["require"]

        return urlunparse(parsed._replace(query=urlencode(query_params, doseq=True)))

    @property
    def _effective_db_url(self) -> Optional[str]:
        return self.DATABASE_URL.strip() if self.DATABASE_URL else None

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Synchronous SQLAlchemy URL for migrations and health checks."""
        url = self._effective_db_url
        if url:
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("+asyncpg", "+psycopg2")
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return self._add_ssl_mode(url)

        user = quote_plus(self.DB_USER or "")
        pw = quote_plus(self.DB_PASS or "")
        host = self.DB_HOST or ""
        port = self.DB_PORT
        name = self.DB_NAME or ""
        return self._add_ssl_mode(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{name}")

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Asynchronous SQLAlchemy URL for primary API operations."""
        url = self._effective_db_url
        if url:
            if "asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self._add_ssl_mode(url)

        user = quote_plus(self.DB_USER or "")
        pw = quote_plus(self.DB_PASS or "")
        host = self.DB_HOST or ""
        port = self.DB_PORT
        name = self.DB_NAME or ""
        return self._add_ssl_mode(f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{name}")

    @property
    def GOOGLE_CREDENTIALS_PATH(self) -> Optional[Path]:
        """Dynamic Firebase path resolver."""
        if self.FIREBASE_CREDENTIALS_JSON:
            tmp_file = NamedTemporaryFile(delete=False, suffix=".json")
            tmp_file.write(self.FIREBASE_CREDENTIALS_JSON.encode("utf-8"))
            tmp_file.close()
            return Path(tmp_file.name)

        path_str = self.FIREBASE_CREDENTIALS_PATH or self.GOOGLE_APPLICATION_CREDENTIALS
        p = Path(path_str) if path_str else None
        return p if p and p.is_file() else None

    @property
    def effective_redis_url(self) -> Optional[str]:
        """Normalized Redis URL for startup logic."""
        return self.REDIS_URL.strip() if self.REDIS_URL else None

    # -------------------------
    # Registry Mappings
    # -------------------------
    @property
    def free_limits(self) -> Dict[str, int]:
        return {
            "doctor-consult": self.LIMIT_DOCTOR_CONSULT,
            "nurse-consult": self.LIMIT_NURSE_CONSULT,
            "bike-request": self.LIMIT_BIKE_REQUEST,
            "taxi-request": self.LIMIT_TAXI_REQUEST,
            "blood-request": self.LIMIT_BLOOD_REQUEST,
        }

    @property
    def fee_map(self) -> Dict[str, int]:
        return {
            "doctor-consult": self.FEE_DOCTOR_CONSULT,
            "nurse-consult": self.FEE_NURSE_CONSULT,
            "bike-request": self.FEE_BIKE_REQUEST,
            "taxi-request": self.FEE_TAXI_REQUEST,
            "blood-request": self.FEE_BLOOD_REQUEST,
        }

    @property
    def admin_wallets(self) -> Dict[str, str]:
        return {
            "MTN": self.ADMIN_MTN_NUMBER,
            "ORANGE": self.ADMIN_ORANGE_NUMBER,
        }

    @property
    def payment_switches(self) -> Dict[str, bool]:
        return {
            "doctor-consult": self.PAYMENT_ENABLED_DOCTOR_CONSULT,
            "nurse-consult": self.PAYMENT_ENABLED_NURSE_CONSULT,
            "bike-request": self.PAYMENT_ENABLED_BIKE_REQUEST,
            "taxi-request": self.PAYMENT_ENABLED_TAXI_REQUEST,
            "blood-request": self.PAYMENT_ENABLED_BLOOD_REQUEST,
        }

    @property
    def promo_messages(self) -> Dict[str, str]:
        return {
            "doctor-consult": self.DOCTOR_PROMO_MESSAGE,
            "nurse-consult": self.NURSE_PROMO_MESSAGE,
            "bike-request": self.BIKE_PROMO_MESSAGE,
            "taxi-request": self.TAXI_PROMO_MESSAGE,
            "blood-request": self.BLOOD_PROMO_MESSAGE,
        }

    @property
    def call_config(self) -> Dict[str, Union[str, int]]:
        return {
            "server_url": self.JITSI_SERVER_URL,
            "timeout_minutes": self.CALL_SESSION_TIMEOUT_MINUTES,
            "signaling_ttl": self.CALL_SIGNALING_TTL_SECONDS,
        }

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=True,
    )


settings = Settings()