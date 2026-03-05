import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import create_token  # noqa: E402
from main import app  # noqa: E402

transport = ASGITransport(app=app)


def _auth_header() -> dict:
    """Create a valid auth header for test requests."""
    token = create_token("john", "John")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_returns_ok():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "rosbridge" in response.json()


@pytest.mark.asyncio
async def test_create_walk_task():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": 100}, headers=_auth_header())
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "walk"
    assert data["distance_m"] == 100
    assert "id" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_create_task_requires_auth():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": 100})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_task_type():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "fly", "distance_m": 100}, headers=_auth_header())
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_negative_distance_rejected():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": -5}, headers=_auth_header())
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_task_not_found():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tasks/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_after_create():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post("/tasks", json={"type": "walk", "distance_m": 50}, headers=_auth_header())
        task_id = create.json()["id"]
        get = await client.get(f"/tasks/{task_id}")
    assert get.status_code == 200
    assert get.json()["id"] == task_id


@pytest.mark.asyncio
async def test_estop_returns_status():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/estop", headers=_auth_header())
    assert response.status_code == 200
    assert "status" in response.json()


@pytest.mark.asyncio
async def test_estop_requires_auth():
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/estop")
    assert response.status_code == 401
