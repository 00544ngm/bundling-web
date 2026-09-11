from __future__ import annotations

from typing import Protocol

from arq.connections import ArqRedis


class JobQueue(Protocol):
    async def enqueue(self, function: str, *args: str) -> None: ...


class ArqJobQueue:
    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(self, function: str, *args: str) -> None:
        job = await self._redis.enqueue_job(function, *args)
        if job is None:
            raise RuntimeError("ARQ rejected the job")


__all__ = ["ArqJobQueue", "JobQueue"]
