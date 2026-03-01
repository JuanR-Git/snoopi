import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402

transport = ASGITransport(app=app)


@pytest.mark.anyio
async def test_login_success():
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/auth/login", json={"username": "john", "password": "snoopi-john-2026"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["user"]["username"] == "john"


@pytest.mark.anyio
async def test_login_wrong_password():
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/auth/login", json={"username": "john", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.anyio
async def test_login_unknown_user():
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/auth/login", json={"username": "nobody", "password": "whatever"})
    assert r.status_code == 401


@pytest.mark.anyio
async def test_me_with_valid_token():
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        login = await c.post("/auth/login", json={"username": "john", "password": "snoopi-john-2026"})
        token = login.json()["token"]
        r = await c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "john"


@pytest.mark.anyio
async def test_me_without_token():
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_me_with_bad_token():
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/auth/me", headers={"Authorization": "Bearer invalidtoken123"})
    assert r.status_code == 401
