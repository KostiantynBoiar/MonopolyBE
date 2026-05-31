from __future__ import annotations

from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from starlette.testclient import TestClient

from application.services.session_service import SessionService
from core.config import get_settings
from core.security import create_access_token, hash_password
from infra.mongo.users.repository import UserRepository
from main import create_app
from tests.conftest import register_user


@pytest.fixture
def auth_header():
    def _header(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _header


@pytest.fixture
def user_pair(client: TestClient):
    """Two registered users via REST: (host_id, host_token), (guest_id, guest_token)."""
    yield register_user(client, "host"), register_user(client, "guest")


@pytest.fixture
async def mongo_app() -> FastAPI:
    """App with lifespan on pytest's event loop (for async Motor tests)."""
    application = create_app()
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def session_service(mongo_app: FastAPI) -> SessionService:
    return SessionService.from_db(mongo_app.state.mongo.db)


@pytest.fixture
async def mongo_user_pair(mongo_app: FastAPI):
    """Two users in Mongo for async SessionService tests."""
    settings = get_settings()
    suffix = uuid4().hex[:8]
    repo = UserRepository(mongo_app.state.mongo.db)

    host = await repo.create(
        email=f"host_{suffix}@example.com",
        display_name="Host User",
        password_hash=hash_password("password123"),
    )
    guest = await repo.create(
        email=f"guest_{suffix}@example.com",
        display_name="Guest User",
        password_hash=hash_password("password123"),
    )
    host_token = create_access_token(host.id, settings)
    guest_token = create_access_token(guest.id, settings)

    yield (host.id, host_token), (guest.id, guest_token)
