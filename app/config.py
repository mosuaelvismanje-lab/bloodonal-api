# app/config.py
from typing import List, Optional, Union, Annotated
from pathlib import Path
from urllib.parse import urlparse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    # === PostgreSQL DB Credentials (individual vars) ===
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None

    # Optional single connection string (psql://... or postgresql://... or postgres://...)
    DATABASE_URL: Optional[str] = None

    # === Firebase Admin SDK (Optional) ===
    # Render will supply FIREBASE_CREDENTIALS_PATH as a mounted secret path
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None  # legacy name fallback

    # === CORS (List of Allowed Origins) ===
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = []

    # === Optional API Keys ===
    WHO_API_KEY: Optional[str] = None
    CDC_API_KEY: Optional[str] = None

    # === General App Settings ===
    PROJECT_NAME: str = "Bloodonal Emergency Health Platform"
    API_VERSION: str = "v1"
    DEBUG: bool = False

    # -----------------------
    # Validators / helpers
    # -----------------------

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: Optional[str]) -> Optional[str]:
        """
        Accept DATABASE_URL in various forms and normalize a bit:
        - Accepts values wrapped in quotes (strips them)
        - Convert short forms like 'postgres://' or 'psql://' to 'postgresql://'
        """
        if not v:
            return None
        if isinstance(v, str):
            v = v.strip().strip('"').strip("'")
            # normalize scheme names
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://", 1)
            if v.startswith("psql://"):
                v = v.replace("psql://", "postgresql://", 1)
            return v
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Support comma-separated origins from an env var."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # -----------------------
    # Derived properties
    # -----------------------

    def _ensure_individual_db_vars(self) -> None:
        """Raise clear error if individual DB vars are incomplete."""
        missing = [k for k, val in (("DB_USER", self.DB_USER), ("DB_PASS", self.DB_PASS),
                                     ("DB_HOST", self.DB_HOST), ("DB_NAME", self.DB_NAME)) if not val]
        if missing:
            raise RuntimeError(
                "Database credentials incomplete. Set a full DATABASE_URL or the env vars: "
                "DB_USER, DB_PASS, DB_HOST, DB_NAME (missing: %s)" % ", ".join(missing)
            )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """
        Return a sync DB URL suitable for psycopg2 (postgresql+psycopg2://...).
        Priority:
          1. If DATABASE_URL provided, convert to psycopg2 form if needed.
          2. Else build from DB_USER/DB_PASS/DB_HOST/DB_PORT/DB_NAME.
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # If driver already present (postgresql+...) return as-is
            scheme_part = url.split("://", 1)[0]
            if "+" in scheme_part:
                return url
            # Convert plain postgres scheme to psycopg2 driver
            if url.startswith("postgresql://"):
                rest = url.split("://", 1)[1]
                return f"postgresql+psycopg2://{rest}"
            # If any other form, just return it (best-effort)
            return url

        # fallback to individual env vars (raise clear error if missing)
        self._ensure_individual_db_vars()
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Return an async DB URL suitable for asyncpg (postgresql+asyncpg://...).
        Priority same as DATABASE_URL_SYNC.
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Already async driver
            if url.startswith("postgresql+asyncpg://"):
                return url
            # Convert generic postgres url to asyncpg scheme
            if url.startswith("postgresql://"):
                rest = url.split("://", 1)[1]
                return f"postgresql+asyncpg://{rest}"
            # If url contains a + (driver) but not asyncpg, replace driver part
            scheme_part = url.split("://", 1)[0]
            if "+" in scheme_part:
                base = scheme_part.split("+")[0]  # e.g. "postgresql"
                rest = url.split("://", 1)[1]
                return f"{base}+asyncpg://{rest}"
            # Otherwise return url as-is (best-effort)
            return url

        # fallback to individual env vars
        self._ensure_individual_db_vars()
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def GOOGLE_CREDENTIALS_PATH(self) -> Optional[Path]:
        """
        Prefer FIREBASE_CREDENTIALS_PATH, fall back to GOOGLE_APPLICATION_CREDENTIALS.
        Returns a Path only if the file exists, otherwise None.
        """
        path_str = self.FIREBASE_CREDENTIALS_PATH or self.GOOGLE_APPLICATION_CREDENTIALS
        if path_str:
            p = Path(path_str)
            return p if p.is_file() else None
        return None

    # -----------------------
    # Pydantic settings
    # -----------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


# Instantiate once for the app
settings = Settings()
