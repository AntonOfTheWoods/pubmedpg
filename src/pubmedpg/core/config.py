from typing import Any, Dict, Optional
from pydantic import BaseSettings, PostgresDsn, validator


class AsyncPostgresDsn(PostgresDsn):
    allowed_schemes = {"postgres+asyncpg", "postgresql+asyncpg"}


class Settings(BaseSettings):
    LOG_LEVEL: str = "INFO"
    DATA_LOG_LEVEL: str = "ERROR"
    DEFAULT_LOG_LEVEL: str = "ERROR"

    @property
    def LOGGING(self):
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "verbose": {
                    "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                    "style": "{",
                },
                "simple": {"format": "{levelname} {message}", "style": "{"},
            },
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
            "loggers": {
                "app.data": {
                    "handlers": ["console"],
                    "level": self.DATA_LOG_LEVEL,
                    "propagate": False,
                },
                "": {
                    "handlers": ["console"],
                    "level": self.DEFAULT_LOG_LEVEL,
                    "propagate": False,
                },
            },
        }

    PROJECT_NAME: str = "PubMedPortable"

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: Optional[str]
    SQLALCHEMY_DATABASE_URI: Optional[AsyncPostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return AsyncPostgresDsn.build(
            scheme="postgresql+asyncpg",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT", "5432"),
            path=f"/{values.get('POSTGRES_DB', '')}",
        )

    DEBUG: bool = False
    DATA_ROOT: str = "/data/"

    SQLALCHEMY_POOL_SIZE: int = 10
    SQLALCHEMY_POOL_MAX_OVERFLOW: int = 20

    class Config:
        case_sensitive = True


settings = Settings()

if settings.DEBUG:
    print("Settings:", settings)
