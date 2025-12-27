from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Union, Annotated, Dict
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qs, urlencode
from tempfile import NamedTemporaryFile

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    """
    Application settings loaded from environment or .env.
    """

    # -------------------------
    # General / runtime
    # -------------------------
    ENVIRONMENT: str = "development"  # development | staging | production | ci
    DEBUG: bool = False
    SECRET_KEY: str = "please-change-me"
    PYTHONUNBUFFERED: int = 1

    # -------------------------
    # App meta
    # -------------------------
    PROJECT_NAME: str = "Bloodonal Emergency Health Platform"
    API_VERSION: str = "v1"

    # -------------------------
    # Database
    # -------------------------
    DATABASE_URL: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None

    # -------------------------
    # Firebase / Google credentials
    # -------------------------
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # -------------------------
    # CORS
    # -------------------------
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = []

    # -------------------------
    # Payment provider keys & selection
    # -------------------------
    PAYMENT_GATEWAY: str = "mock"  # mock | stripe | flutterwave | mtn
    STRIPE_API_KEY: Optional[str] = None
    FLUTTERWAVE_SECRET: Optional[str] = None
    MTN_MOMO_API_KEY: Optional[str] = None
    MTN_MOMO_SUBSCRIPTION_KEY: Optional[str] = None
    MTN_MOMO_ENVIRONMENT: str = "sandbox"

    # -------------------------
    # Free counts / quotas
    # -------------------------
    FREE_COUNTS_DOCTOR: int = 5
    FREE_COUNTS_NURSE: int = 3
    FREE_COUNTS_BIKER: int = 2
    FREE_COUNTS_TAXI: int = 2
    FREE_COUNTS_BLOOD: int = 10

    # -------------------------
    # Fees
    # -------------------------
    FEE_DOCTOR: int = 300
    FEE_NURSE: int = 200
    FEE_BIKER: int = 100
    FEE_TAXI: int = 150
    FEE_BLOOD: int = 0

    # -------------------------
    # Background & cache
    # -------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # -------------------------
    # Logging / misc
    # -------------------------
    LOG_DIR: str = "logs"
    LOG_LEVEL: str = "INFO"

    # -------------------------
    # Helper properties
    # -------------------------
    def _add_ssl_mode(self, url: str) -> str:
        """Append sslmode=require if missing."""
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
        """Synchronous SQLAlchemy URL for psycopg2."""
        url = self._effective_db_url
        if url:
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("+asyncpg", "+psycopg2")
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif "+" in url.split("://", 1)[0]:
                scheme, rest = url.split("://", 1)
                base = scheme.split("+")[0]
                url = f"{base}+psycopg2://{rest}"
            return self._add_ssl_mode(url)

        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError("Database credentials incomplete for sync URL")
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASS)
        host = self.DB_HOST
        port = self.DB_PORT
        name = self.DB_NAME
        return self._add_ssl_mode(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Asynchronous SQLAlchemy URL for asyncpg."""
        url = self._effective_db_url
        if url:
            if url.startswith("postgresql+asyncpg://"):
                pass
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif "+" in url.split("://", 1)[0]:
                scheme, rest = url.split("://", 1)
                base = scheme.split("+")[0]
                url = f"{base}+asyncpg://{rest}"
            return self._add_ssl_mode(url)

        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError("Database credentials incomplete for async URL")
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASS)
        host = self.DB_HOST
        port = self.DB_PORT
        name = self.DB_NAME
        return self._add_ssl_mode(f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}")

    @property
    def GOOGLE_CREDENTIALS_PATH(self) -> Optional[Path]:
        """Return path to Firebase JSON (temporary file if JSON string is provided)."""
        if self.FIREBASE_CREDENTIALS_JSON:
            tmp_file = NamedTemporaryFile(delete=False, suffix=".json")
            tmp_file.write(self.FIREBASE_CREDENTIALS_JSON.encode("utf-8"))
            tmp_file.close()
            return Path(tmp_file.name)
        path_str = self.FIREBASE_CREDENTIALS_PATH or self.GOOGLE_APPLICATION_CREDENTIALS
        p = Path(path_str) if path_str else None
        return p if p and p.is_file() else None

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def free_limits(self) -> Dict[str, int]:
        return {
            "doctor": int(self.FREE_COUNTS_DOCTOR),
            "nurse": int(self.FREE_COUNTS_NURSE),
            "biker": int(self.FREE_COUNTS_BIKER),
            "taxi": int(self.FREE_COUNTS_TAXI),
            "blood_request": int(self.FREE_COUNTS_BLOOD),
        }

    @property
    def fee_map(self) -> Dict[str, int]:
        return {
            "doctor": int(self.FEE_DOCTOR),
            "nurse": int(self.FEE_NURSE),
            "biker": int(self.FEE_BIKER),
            "taxi": int(self.FEE_TAXI),
            "blood_request": int(self.FEE_BLOOD),
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",  # allow additional env variables for CI/production
        case_sensitive=True,  # enforce proper case for production
    )


# Single settings instance
settings = Settings()
