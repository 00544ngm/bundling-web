"""Login gate on job/search routes.

/jobs* and /search are data + task-authoring surface, so they must require a
valid login. Requests without a usable Bearer token are rejected before any
repository work happens.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app


@pytest.mark.asyncio
async def test_jobs_list_requires_login_in_server_mode() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/jobs")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_job_submit_requires_login_in_server_mode() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/jobs/hypothesis",
            json={"url": "https://www.walmart.com/ip/whatever"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_search_requires_login_in_server_mode() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/search", json={"keyword": "cast iron"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_artifact_download_requires_login_in_server_mode() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000/artifacts/json")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"
