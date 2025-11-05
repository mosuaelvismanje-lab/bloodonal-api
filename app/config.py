# app/config.py
from typing import List, Optional, Union, Annotated
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode
from pathlib import Path

class Settings(BaseSettings):
    # === PostgreSQL DB Credentials ===
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str

    # === Firebase Admin SDK (Optional) ===
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # === CORS (List of Allowed Origins) ===
    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = []

    # === Optional API Keys ===
    WHO_API_KEY: Optional[str] = None
    CDC_API_KEY: Optional[str] = None

    # === General App Settings ===
    PROJECT_NAME: str = "Bloodonal Emergency Health Platform"
    API_VERSION: str = "v1"
    DEBUG: bool = True

    # synchronous URL (for legacy / Alembic)
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # async URL (for async SQLAlchemy / FastAPI)
    @property
    def ASYNC_DATABASE_URL(self) -> str:
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

    # return Path object for Firebase credentials
    @property
    def GOOGLE_CREDENTIALS_PATH(self) -> Optional[Path]:
        if self.GOOGLE_APPLICATION_CREDENTIALS:
            path = Path(self.GOOGLE_APPLICATION_CREDENTIALS)
            return path if path.is_file() else None
        return None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

settings = Settings()
