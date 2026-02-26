import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    from main import app
    return app


@pytest.mark.asyncio
async def test_health_returns_ok(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "rosbridge" in response.json()


@pytest.mark.asyncio
async def test_create_walk_task(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": 100})
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "walk"
    assert data["distance_m"] == 100
    assert "id" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_invalid_task_type(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "fly", "distance_m": 100})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_negative_distance_rejected(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": -5})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_task_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/tasks/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_after_create(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post("/tasks", json={"type": "walk", "distance_m": 50})
        task_id = create.json()["id"]
        get = await client.get(f"/tasks/{task_id}")
    assert get.status_code == 200
    assert get.json()["id"] == task_id


@pytest.mark.asyncio
async def test_estop_returns_status(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/estop")
    assert response.status_code == 200
    assert "status" in response.json()
