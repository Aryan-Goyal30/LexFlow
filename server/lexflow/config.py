"""Application settings, read from environment variables and ``server/.env``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
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
    # Exact origins (scheme://host:port) allowed to make changes: the Vite dev
    # server and `vite preview`. JSON list. Anything else is refused (CSRF).
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        alias="LEXFLOW_ALLOWED_ORIGINS",
    )

    # --- sign-in and sessions ----------------------------------------------------
    # A session ends after this long without a request ...
    session_idle_minutes: int = Field(default=30, gt=0, alias="LEXFLOW_SESSION_IDLE_MINUTES")
    # ... and at the latest this long after sign-in.
    session_absolute_hours: int = Field(default=12, gt=0, alias="LEXFLOW_SESSION_ABSOLUTE_HOURS")
    # Send the session cookie only over HTTPS. Required (and enforced at start-up)
    # when LEXFLOW_ENV=production; off for http://localhost development.
    cookie_secure: bool = Field(default=False, alias="LEXFLOW_COOKIE_SECURE")
    # Consecutive failed sign-ins that lock an account, and for how long.
    login_max_failures: int = Field(default=5, ge=1, alias="LEXFLOW_LOGIN_MAX_FAILURES")
    lockout_minutes: int = Field(default=15, gt=0, alias="LEXFLOW_LOCKOUT_MINUTES")
    # How long a temporary password set by an administrator stays usable.
    temporary_password_hours: int = Field(
        default=72, gt=0, alias="LEXFLOW_TEMPORARY_PASSWORD_HOURS"
    )
    # Argon2id cost. "test-fast" exists only to keep the test suite quick and is
    # refused outside LEXFLOW_ENV=test.
    password_hash_profile: Literal["standard", "test-fast"] = Field(
        default="standard", alias="LEXFLOW_PASSWORD_HASH_PROFILE"
    )

    # --- document processing (Phase 3) ----------------------------------------------
    # Extraction runs in a child process that is stopped after this long.
    extraction_timeout_seconds: int = Field(
        default=120, gt=0, le=3600, alias="LEXFLOW_EXTRACTION_TIMEOUT_SECONDS"
    )
    # Larger documents are refused (failed, with the reason) rather than processed.
    extraction_max_pages: int = Field(default=1000, gt=0, alias="LEXFLOW_EXTRACTION_MAX_PAGES")
    extraction_max_text_bytes: int = Field(
        default=5_000_000, gt=0, alias="LEXFLOW_EXTRACTION_MAX_TEXT_BYTES"
    )
    # A .docx is a ZIP archive: refuse archives that would unpack to more than this.
    extraction_max_unpacked_bytes: int = Field(
        default=200_000_000, gt=0, alias="LEXFLOW_EXTRACTION_MAX_UNPACKED_BYTES"
    )
    chunk_size: int = Field(default=1200, ge=200, le=10_000, alias="LEXFLOW_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, ge=0, alias="LEXFLOW_CHUNK_OVERLAP")
    # The worker: how often it looks for work, how long a claimed job is reserved
    # for it (a crashed worker's job is taken over after this), and how many
    # times a job is tried before it is marked failed.
    worker_poll_seconds: float = Field(
        default=2.0, gt=0, le=60, alias="LEXFLOW_WORKER_POLL_SECONDS"
    )
    worker_lease_seconds: int = Field(default=300, gt=0, alias="LEXFLOW_WORKER_LEASE_SECONDS")
    worker_max_attempts: int = Field(default=3, ge=1, le=10, alias="LEXFLOW_WORKER_MAX_ATTEMPTS")
    # Embeddings: "disabled" (default) stores chunks without vectors. "local" runs
    # a model on this computer (nothing is sent to other services). It needs the
    # pgvector database (migration 0009) and the model files, downloaded only by
    # `python -m lexflow.cli.models download`; see lexflow/embeddings.py.
    embeddings: Literal["disabled", "local"] = Field(default="disabled", alias="LEXFLOW_EMBEDDINGS")
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="LEXFLOW_EMBEDDING_MODEL")
    model_dir: Path = Field(default=Path("var/models"), alias="LEXFLOW_MODEL_DIR")
    # Chunks embedded per model call, and CPU threads the model may use.
    embedding_batch_size: int = Field(
        default=16, ge=1, le=256, alias="LEXFLOW_EMBEDDING_BATCH_SIZE"
    )
    embedding_threads: int = Field(default=2, ge=1, le=64, alias="LEXFLOW_EMBEDDING_THREADS")

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown time zone: {value}") from exc
        return value

    @field_validator("upload_dir", "model_dir")
    @classmethod
    def _absolute_upload_dir(cls, value: Path) -> Path:
        # Relative paths are relative to server/, not to the current directory.
        return value if value.is_absolute() else (SERVER_ROOT / value).resolve()

    @field_validator("allowed_origins")
    @classmethod
    def _normalised_origins(cls, value: list[str]) -> list[str]:
        return [origin.strip().rstrip("/").lower() for origin in value if origin.strip()]

    @model_validator(mode="after")
    def _test_only_settings(self) -> Settings:
        # S105: "test-fast" names a hashing profile, it is not a password.
        if self.password_hash_profile == "test-fast" and self.env != "test":  # noqa: S105
            raise ValueError("LEXFLOW_PASSWORD_HASH_PROFILE=test-fast is only allowed in tests")
        if self.worker_lease_seconds <= self.extraction_timeout_seconds:
            raise ValueError(
                "LEXFLOW_WORKER_LEASE_SECONDS must be longer than "
                "LEXFLOW_EXTRACTION_TIMEOUT_SECONDS"
            )
        if self.chunk_overlap >= self.chunk_size // 2:
            raise ValueError("LEXFLOW_CHUNK_OVERLAP must be less than half of LEXFLOW_CHUNK_SIZE")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes browsers insist on Secure, Path=/ and no Domain.
        return "__Host-lexflow_session" if self.cookie_secure else "lexflow_session"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # DATABASE_URL comes from the environment or server/.env
