from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from core.config import get_settings
from core.security import create_access_token
from tests.conftest import create_session, register_user


@pytest.fixture
def make_token():
    settings = get_settings()

    def _make(user_id: str) -> str:
        return create_access_token(user_id, settings).access_token

    return _make


@pytest.fixture
def registered_user(client: TestClient):
    """User + session for WebSocket tests: (user_id, token, session_id)."""
    user_id, token = register_user(client, "ws")
    session_id = create_session(client, token)
    yield user_id, token, session_id
