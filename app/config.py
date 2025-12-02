from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union, Annotated, Dict
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qs, urlencode
from tempfile import NamedTemporaryFile

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    """
    Application settings loaded from environment (or .env).
    """

    # General / runtime
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "please-change-me"
    PYTHONUNBUFFERED: int = 1

    # App meta
    PROJECT_NAME: str = "Bloodonal Emergency Health Platform"
    API_VERSION: str = "v1"

    # === Database ===
    DATABASE_URL: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None

    # === Firebase / Google credentials ===
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None  # store JSON content in env
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None  # legacy fallback

    # === CORS ===
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = []

    # === Payment provider keys & selection ===
    PAYMENT_GATEWAY: str = "mock"  # mock | stripe | flutterwave | mtn

    STRIPE_API_KEY: Optional[str] = None
    FLUTTERWAVE_SECRET: Optional[str] = None
    MTN_MOMO_API_KEY: Optional[str] = None
    MTN_MOMO_SUBSCRIPTION_KEY: Optional[str] = None
    MTN_MOMO_ENVIRONMENT: str = "sandbox"  # sandbox | production

    # === Free counts (per-service quotas) ===
    FREE_COUNTS_DOCTOR: int = 5
    FREE_COUNTS_NURSE: int = 3
    FREE_COUNTS_BIKER: int = 2
    FREE_COUNTS_TAXI: int = 2
    FREE_COUNTS_BLOOD: int = 10

    # === Fees (integer currency units, e.g. XAF) ===
    FEE_DOCTOR: int = 300
    FEE_NURSE: int = 200
    FEE_BIKER: int = 100
    FEE_TAXI: int = 150
    FEE_BLOOD: int = 0

    # === Background & cache ===
    REDIS_URL: str = "redis://localhost:6379/0"

    # === Logging / misc ===
    LOG_DIR: str = "logs"
    LOG_LEVEL: str = "INFO"

    # -------------------------
    # Helper properties
    # -------------------------

    # CRITICAL FIX: Ensures SSL is required for cloud database connections.
    def _add_ssl_mode(self, url: str) -> str:
        """Appends sslmode=require if connecting to a cloud database (e.g., Neon) and it's not present."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return url  # Return original if URL is invalid

        # Only proceed if we have a hostname
        if not parsed.hostname:
            return url

        query_params = parse_qs(parsed.query)
        # Only add if sslmode is not explicitly set
        if 'sslmode' not in query_params:
            query_params['sslmode'] = ['require']

        # Reconstruct the URL with the potentially updated query
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    @property
    def _effective_db_url(self) -> Optional[str]:
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        return None

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """
        Returns a sync SQLAlchemy URL that uses psycopg2 (postgresql+psycopg2://...).
        """
        url = self._effective_db_url

        if url:
            # --- START Original Logic ---
            if url.startswith("postgresql+") or url.startswith("postgresql://"):
                if url.startswith("postgresql://"):
                    rest = url.split("://", 1)[1]
                    processed_url = f"postgresql+psycopg2://{rest}"
                else:
                    # If it has a driver like +asyncpg, replace it with +psycopg2
                    scheme = url.split("://", 1)[0]
                    rest = url.split("://", 1)[1]
                    base = scheme.split("+")[0]
                    processed_url = f"{base}+psycopg2://{rest}"
            else:
                processed_url = url
            # --- END Original Logic ---

            # CRITICAL STEP: Add SSL requirement
            return self._add_ssl_mode(processed_url)

        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError(
                "Database credentials incomplete: set DATABASE_URL or DB_USER/DB_PASS/DB_HOST/DB_NAME"
            )
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASS)
        host = self.DB_HOST
        port = self.DB_PORT or 5432
        name = self.DB_NAME

        url_from_parts = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        return self._add_ssl_mode(url_from_parts)

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Returns an async SQLAlchemy URL that uses asyncpg (postgresql+asyncpg://...).
        Converts plain DATABASE_URL if necessary and ensures SSL is required.
        """
        url = self._effective_db_url

        if url:
            # --- START Original Logic ---
            if url.startswith("postgresql+asyncpg://"):
                processed_url = url
            elif url.startswith("postgresql://") or url.startswith("postgres://") or url.startswith("psql://"):
                rest = url.split("://", 1)[1]
                processed_url = f"postgresql+asyncpg://{rest}"
            elif "+" in url.split("://", 1)[0]:
                scheme = url.split("://", 1)[0]
                rest = url.split("://", 1)[1]
                base = scheme.split("+")[0]
                processed_url = f"{base}+asyncpg://{rest}"
            else:
                processed_url = url
            # --- END Original Logic ---

            # CRITICAL STEP: Add SSL requirement
            return self._add_ssl_mode(processed_url)

        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError(
                "Database credentials incomplete: set DATABASE_URL or DB_USER/DB_PASS/DB_HOST/DB_NAME"
            )
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASS)
        host = self.DB_HOST
        port = self.DB_PORT or 5432
        name = self.DB_NAME

        url_from_parts = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
        return self._add_ssl_mode(url_from_parts)

    @property
    def GOOGLE_CREDENTIALS_PATH(self) -> Optional[Path]:
        """
        Prefer JSON secret (FIREBASE_CREDENTIALS_JSON) or path env variables.
        Returns a Path to a temporary file if JSON content is provided.
        """
        if self.FIREBASE_CREDENTIALS_JSON:
            # write JSON to a temp file and return its path
            tmp_file = NamedTemporaryFile(delete=False, suffix=".json")
            # if user provided literal '\n' sequences, keep them as-is (providers usually expect \n-escaped)
            tmp_file.write(self.FIREBASE_CREDENTIALS_JSON.encode("utf-8"))
            tmp_file.close()
            return Path(tmp_file.name)

        path_str = self.FIREBASE_CREDENTIALS_PATH or self.GOOGLE_APPLICATION_CREDENTIALS
        if not path_str:
            return None
        p = Path(path_str)
        return p if p.is_file() else None

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # convenience mappings used by service layer
    @property
    def free_limits(self) -> Dict[str, int]:
        """Return a mapping of service -> free count."""
        return {
            "doctor": int(self.FREE_COUNTS_DOCTOR),
            "nurse": int(self.FREE_COUNTS_NURSE),
            "biker": int(self.FREE_COUNTS_BIKER),
            "taxi": int(self.FREE_COUNTS_TAXI),
            "blood_request": int(self.FREE_COUNTS_BLOOD),
        }

    @property
    def fee_map(self) -> Dict[str, int]:
        """Return a mapping of service -> fee (in integer currency units)."""
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
        extra="allow",
    )


# single settings instance to import everywhere
settings = Settings()