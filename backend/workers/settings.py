from __future__ import annotations

from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.logger import logger
from backend.config import get_backend_settings
from backend.workers.jobs import run_analysis_job, run_cross_review
from backend.workers.runtime_identity import refresh_worker_identity


def redis_settings() -> RedisSettings:
    settings = get_backend_settings()
    return RedisSettings.from_dsn(settings.redis_url)


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    """ARQ worker 启动钩子：先登记身份，再回收上次残留的中断任务。

    为什么这里可以无条件回收：本项目按**单 worker** 部署（systemd 的
    `bundling-worker` 单实例，且 `max_jobs=1`）。本进程刚启动，不存在任何属于
    它的在跑任务，所以此刻仍是 `running` 的任务必然是上一个进程崩溃留下的孤儿。
    不处理的话它们会永远卡在 running，前端一直显示"执行中"，用户只能手工重提。
    之前这段逻辑挂在 API 启动上是不对的（server 模式下 API 与 worker 是独立进程，
    API 重启会误标 worker 正在跑的任务），挂在 worker 启动上才是正确位置。

    **若将来改成多副本 worker，必须先把
    `recover_interrupted_jobs_on_startup` 置为 false**，否则滚动重启会把兄弟副本
    正在执行的任务误判为中断。见 BackendSettings 中的同名字段。
    """
    await refresh_worker_identity(ctx)

    if not get_backend_settings().recover_interrupted_jobs_on_startup:
        return

    # 延迟导入：与 backend/main.py 一样，避免在模块导入期就拉起数据库栈。
    from backend.application.job_recovery import recover_interrupted_jobs
    from backend.db.session import SessionFactory

    try:
        recovered = await recover_interrupted_jobs(SessionFactory)
    except Exception:  # noqa: BLE001 - 启动钩子抛异常会让 worker 起不来
        logger.exception("启动时回收中断任务失败，worker 继续启动")
        return
    if recovered:
        logger.warning("启动时把 %d 个上次残留的 running 任务标记为 interrupted", recovered)


class WorkerSettings:
    functions: ClassVar = [run_analysis_job, run_cross_review]
    on_startup = on_worker_startup
    cron_jobs: ClassVar = [
        cron(
            refresh_worker_identity,
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=False,
        )
    ]
    redis_settings = redis_settings()
    max_jobs: int = 1
    # 外层兜底上限 1200s；具体任务的实际执行上限由 jobs._resolve_job_deadline
    # 按 provider/model 施加（普通通道 600s、Maike 中转 gpt 通道 1000s），
    # 因此该值需大于内层上限以免 ARQ 提前掐断慢速但受控的任务。
    job_timeout: int = 1200


__all__ = ["WorkerSettings"]
