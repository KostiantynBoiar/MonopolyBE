from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.config import get_settings
from core.security import create_access_token
from infra.mongo.users.repository import UserRepository
from main import create_app


@pytest.fixture
async def app() -> FastAPI:
    async with LifespanManager(create_app()) as mgr:
        yield mgr.app  # type: ignore[misc]


@pytest.fixture
async def http_client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def make_token():
    settings = get_settings()

    def _make(user_id: str) -> str:
        return create_access_token(user_id, settings).access_token

    return _make


@pytest.fixture
async def registered_user(app: FastAPI):
    """Insert a real user into Mongo and return (user_id, token)."""
    settings = get_settings()
    from core.security import hash_password

    repo = UserRepository(app.state.mongo.db)
    user = await repo.create(
        email="test_ws@example.com",
        display_name="WS Tester",
        password_hash=hash_password("password123"),
    )
    token = create_access_token(user.id, settings).access_token
    yield user.id, token
    await app.state.mongo.db.users.delete_one({"_id": user.id})
