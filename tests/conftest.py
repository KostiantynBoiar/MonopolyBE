from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from main import create_app

_TEST_PASSWORD = "password123"


def register_user(client: TestClient, label: str) -> tuple[str, str]:
    """Register a user via REST; return (user_id, access_token)."""
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{label}_{suffix}@example.com",
            "display_name": label.replace("_", " ").title(),
            "password": _TEST_PASSWORD,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["user"]["id"], body["token"]["access_token"]


def create_session(
    client: TestClient,
    token: str,
    *,
    visibility: str = "public",
) -> str:
    """Create a waiting session; return session_id."""
    resp = client.post(
        "/api/v1/sessions",
        json={"visibility": visibility},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["session"]["id"]


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Sync test client with lifespan; supports HTTP and WebSocket."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def app(client: TestClient) -> FastAPI:
    return client.app  # type: ignore[return-value]
