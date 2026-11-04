from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value has a safe default; env vars use YTP_ prefix."""

    model_config = SettingsConfigDict(
        env_prefix="YTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("./data")
    max_concurrent_jobs: int = Field(default=1, ge=1, le=8)
    max_queued_jobs: int = Field(default=20, ge=1)
    job_ttl_hours: int = Field(default=24, ge=1)
    max_filesize_mb: int = Field(default=2048, ge=1)
    max_job_minutes: int = Field(default=120, ge=1)
    info_cache_ttl_seconds: int = Field(default=600, ge=0)
    info_concurrency: int = Field(default=2, ge=1)
    cookies_file: Path | None = None
    proxy: str | None = None
    impersonate: str | None = None
    api_token: str | None = None
    log_level: str = "INFO"

    @field_validator("cookies_file", "proxy", "impersonate", "api_token", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.db"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def max_filesize_bytes(self) -> int:
        return self.max_filesize_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
