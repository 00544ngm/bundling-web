from __future__ import annotations

from typing import Any

import pytest

from backend.application import job_recovery
from backend.config import get_backend_settings
from backend.db.base import Base
from backend.db.engine import create_database_engine
from backend.db.models import AnalysisJob
from backend.db.session import create_session_factory
from backend.workers import settings as worker_settings


class _FakeRedis:
    """只记录调用，够 refresh_worker_identity 用。"""

    def __init__(self) -> None:
        self.set_calls: list[tuple[Any, ...]] = []

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.set_calls.append((key, value, ex))


async def _sqlite_factory(tmp_path, name: str):
    url = f"sqlite+aiosqlite:///{(tmp_path / name).as_posix()}"
    engine = create_database_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


@pytest.fixture
def ctx() -> dict[str, Any]:
    return {"redis": _FakeRedis()}


@pytest.mark.asyncio
async def test_worker_startup_recovers_jobs_left_running_by_the_previous_process(
    tmp_path, ctx, monkeypatch
) -> None:
    """worker 启动时必须回收孤儿任务 —— 否则它们永远卡在 running。

    on_worker_startup 内部才 import SessionFactory，所以替换模块属性即可注入
    测试库（这里用的仍是与迁移同源的 ORM metadata 建表）。
    """
    engine, factory = await _sqlite_factory(tmp_path, "worker-startup.db")
    try:
        async with factory() as session:
            stale = AnalysisJob(mode="hypothesis", status="running", request_payload={})
            done = AnalysisJob(mode="hypothesis", status="completed", request_payload={})
            session.add_all((stale, done))
            await session.commit()
            stale_id, done_id = stale.id, done.id

        monkeypatch.setattr("backend.db.session.SessionFactory", factory)

        await worker_settings.on_worker_startup(ctx)

        async with factory() as session:
            recovered = await session.get(AnalysisJob, stale_id)
            untouched = await session.get(AnalysisJob, done_id)
        assert recovered is not None
        assert recovered.status == "interrupted"
        assert recovered.error_code == "APP_INTERRUPTED"
        assert untouched is not None
        assert untouched.status == "completed"
        # 原有行为不能被顶掉：身份登记仍要发生（health 的 contract_match 依赖它）
        assert ctx["redis"].set_calls
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_startup_skips_recovery_when_disabled(
    tmp_path, ctx, monkeypatch
) -> None:
    """多副本部署时会把该开关关掉，此时绝不能碰任何 running 任务。"""
    engine, factory = await _sqlite_factory(tmp_path, "worker-startup-off.db")
    try:
        async with factory() as session:
            stale = AnalysisJob(mode="hypothesis", status="running", request_payload={})
            session.add(stale)
            await session.commit()
            stale_id = stale.id

        monkeypatch.setattr("backend.db.session.SessionFactory", factory)
        monkeypatch.setattr(
            get_backend_settings(), "recover_interrupted_jobs_on_startup", False
        )

        await worker_settings.on_worker_startup(ctx)

        async with factory() as session:
            untouched = await session.get(AnalysisJob, stale_id)
        assert untouched is not None
        assert untouched.status == "running"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_startup_survives_a_recovery_failure(ctx, monkeypatch) -> None:
    """回收失败不能让 worker 起不来 —— 起不来比留下一个孤儿任务更糟。"""

    async def _boom(_factory):
        raise RuntimeError("database is down")

    monkeypatch.setattr(job_recovery, "recover_interrupted_jobs", _boom)

    await worker_settings.on_worker_startup(ctx)  # 不应抛出

    assert ctx["redis"].set_calls
