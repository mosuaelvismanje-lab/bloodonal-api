# app/config.py
from typing import List, Optional, Union, Annotated
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode
from pathlib import Path
from urllib.parse import urlparse

class Settings(BaseSettings):
    # === PostgreSQL DB Credentials (individual vars) ===
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None

    # Optional single connection string (psql://... or postgresql://...)
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
    DEBUG: bool = True

    # Helper: return synchronous DB URL (for Alembic / SQLAlchemy sync)
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
            # if driver already present, return as-is
            if "+" in url.split("://", 1)[0]:
                return url
            # convert 'postgresql://' or 'psql://' to 'postgresql+psycopg2://'
            if url.startswith("postgresql://") or url.startswith("psql://") or url.startswith("postgres://"):
                rest = url.split("://", 1)[1]
                return f"postgresql+psycopg2://{rest}"
            return url

        # fallback to individual env vars
        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError("Database credentials incomplete: set DATABASE_URL or DB_USER/DB_PASS/DB_HOST/DB_NAME")
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # Helper: return async DB URL (for async SQLAlchemy / asyncpg)
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Return an async DB URL suitable for asyncpg (postgresql+asyncpg://...).
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # if already has driver return converted form or as-is
            if url.startswith("postgresql+asyncpg://"):
                return url
            # convert generic postgres url to asyncpg scheme
            if url.startswith("postgresql://") or url.startswith("psql://") or url.startswith("postgres://"):
                rest = url.split("://", 1)[1]
                return f"postgresql+asyncpg://{rest}"
            # if it contains a + but not asyncpg, replace driver part
            if "+" in url.split("://", 1)[0]:
                scheme = url.split("://", 1)[0]
                rest = url.split("://", 1)[1]
                # swap whatever driver to asyncpg
                base = scheme.split("+")[0]
                return f"{base}+asyncpg://{rest}"
            return url

        # fallback to individual env vars
        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError("Database credentials incomplete: set DATABASE_URL or DB_USER/DB_PASS/DB_HOST/DB_NAME")
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # convert comma-separated string to list for ALLOWED_ORIGINS
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # return Path object for Firebase credentials (checks both env names)
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

settings = Settings()
