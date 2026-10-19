"""Application settings, read from environment variables and ``server/.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_ROOT = Path(__file__).resolve().parent.parent

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class Settings(BaseSettings):
    """Configuration for the API.

    Environment variables take precedence over ``server/.env``. Nothing here has
    a production-safe default for the database: ``DATABASE_URL`` must be set.
    """

    model_config = SettingsConfigDict(
        env_file=SERVER_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Defaults to "production" so that development-only behaviour (such as
    # loading sample data) has to be switched on deliberately.
    env: Literal["development", "test", "production"] = Field(
        default="production", alias="LEXFLOW_ENV"
    )
    database_url: str = Field(alias="DATABASE_URL")
    upload_dir: Path = Field(default=Path("var/uploads"), alias="LEXFLOW_UPLOAD_DIR")
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0, alias="LEXFLOW_MAX_UPLOAD_BYTES")
    timezone: str = Field(default="Asia/Kolkata", alias="LEXFLOW_TIMEZONE")
    api_host: str = Field(default="127.0.0.1", alias="LEXFLOW_API_HOST")
    api_port: int = Field(default=8000, ge=1, le=65535, alias="LEXFLOW_API_PORT")
    # Host names the API answers to (protection against DNS rebinding). JSON list.
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "::1"], alias="LEXFLOW_ALLOWED_HOSTS"
    )

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown time zone: {value}") from exc
        return value

    @field_validator("upload_dir")
    @classmethod
    def _absolute_upload_dir(cls, value: Path) -> Path:
        # Relative paths are relative to server/, not to the current directory.
        return value if value.is_absolute() else (SERVER_ROOT / value).resolve()

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # DATABASE_URL comes from the environment or server/.env
