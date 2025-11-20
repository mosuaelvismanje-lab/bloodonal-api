from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union, Annotated
from urllib.parse import quote_plus
from tempfile import NamedTemporaryFile

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode


class Settings(BaseSettings):
    """
    Application settings loaded from environment (or .env).
    - Supports DATABASE_URL (full) OR DB_USER/DB_PASS/DB_HOST/DB_NAME
    - Exposes sync and async SQLAlchemy URLs
    - Exposes GOOGLE_CREDENTIALS_PATH (prefers FIREBASE_CREDENTIALS_PATH or JSON secret)
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

    # Optional external API keys
    WHO_API_KEY: Optional[str] = None
    CDC_API_KEY: Optional[str] = None

    # -------------------------
    # Helper properties
    # -------------------------
    @property
    def _effective_db_url(self) -> Optional[str]:
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        return None

    @property
    def SYNC_DATABASE_URL(self) -> str:
        url = self._effective_db_url
        if url:
            if url.startswith("postgresql+"):
                return url
            if url.startswith(("postgresql://", "postgres://", "psql://")):
                rest = url.split("://", 1)[1]
                return f"postgresql+psycopg2://{rest}"
            return url

        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError(
                "Database credentials incomplete: set DATABASE_URL or DB_USER/DB_PASS/DB_HOST/DB_NAME"
            )
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASS)
        host = self.DB_HOST
        port = self.DB_PORT or 5432
        name = self.DB_NAME
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        url = self._effective_db_url
        if url:
            if url.startswith("postgresql+asyncpg://"):
                return url
            if url.startswith(("postgresql://", "postgres://", "psql://")):
                rest = url.split("://", 1)[1]
                return f"postgresql+asyncpg://{rest}"
            if "+" in url.split("://", 1)[0]:
                scheme = url.split("://", 1)[0]
                rest = url.split("://", 1)[1]
                base = scheme.split("+")[0]
                return f"{base}+asyncpg://{rest}"
            return url

        if not all([self.DB_USER, self.DB_PASS, self.DB_HOST, self.DB_NAME]):
            raise RuntimeError(
                "Database credentials incomplete: set DATABASE_URL or DB_USER/DB_PASS/DB_HOST/DB_NAME"
            )
        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASS)
        host = self.DB_HOST
        port = self.DB_PORT or 5432
        name = self.DB_NAME
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    @property
    def GOOGLE_CREDENTIALS_PATH(self) -> Optional[Path]:
        """
        Prefer JSON secret (FIREBASE_CREDENTIALS_JSON) or path env variables.
        Returns a Path to a temporary file if JSON content is provided.
        """
        if self.FIREBASE_CREDENTIALS_JSON:
            tmp_file = NamedTemporaryFile(delete=False, suffix=".json")
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

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="allow",
    )


# single settings instance to import everywhere
settings = Settings()
