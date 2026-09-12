from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://bundling:bundling@127.0.0.1:5432/bundling"
    )
    redis_url: str = "redis://127.0.0.1:6379/0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    artifact_dir: Path = Path("output/bundling")
    api_prefix: str = "/api/v1"
    provider_encryption_key: str | None = None
    provider_key_file: Path = Path("backend/.api-config.key")
    # Web 版登录鉴权。
    auth_secret: str | None = None
    auth_token_ttl_seconds: int = 60 * 60 * 24 * 30
    admin_initial_password: str | None = None
    # Allow the provider/API settings endpoints to be reached from remote
    # clients (e.g. managing a server deployment from another machine).
    # Default False keeps the original "localhost only" security posture.
    allow_remote_settings: bool = False
    # ARQ worker 启动时把上一个进程残留的 running 任务标记为 interrupted。
    # 本项目按单 worker 部署（systemd bundling-worker 单实例 + max_jobs=1），
    # 此时启动即意味着那些任务已无人在跑。**若改为多副本 worker，必须置为 false**，
    # 否则滚动重启会把兄弟副本正在执行的任务误判为中断。
    recover_interrupted_jobs_on_startup: bool = True


@lru_cache
def get_backend_settings() -> BackendSettings:
    return BackendSettings()


def database_connection_url(settings: BackendSettings | None = None) -> URL:
    """Resolve the SQLAlchemy URL for the configured PostgreSQL database."""
    current = settings or get_backend_settings()
    return make_url(current.database_url)


__all__ = ["BackendSettings", "database_connection_url", "get_backend_settings"]
