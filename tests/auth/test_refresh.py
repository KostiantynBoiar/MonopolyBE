from __future__ import annotations

from uuid import uuid4

from starlette.testclient import TestClient


def _register(client: TestClient) -> dict:
    suffix = uuid4().hex[:8]
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"rt_{suffix}@example.com",
            "password": "password123",
            "display_name": "RT User",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_register_returns_access_and_refresh(client: TestClient) -> None:
    token = _register(client)["token"]
    assert token["access_token"]
    assert token["refresh_token"]
    assert token["expires_in"] > 0
    assert token["refresh_expires_in"] > 0


def test_refresh_rotates_and_old_token_rejected(client: TestClient) -> None:
    old_refresh = _register(client)["token"]["refresh_token"]

    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200, r1.text
    new_token = r1.json()["token"]
    assert new_token["refresh_token"] != old_refresh

    # The new access token works.
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_token['access_token']}"},
    )
    assert me.status_code == 200

    # The old refresh token is single-use → rejected after rotation.
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401


def test_refresh_invalid_token_rejected(client: TestClient) -> None:
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    refresh = _register(client)["token"]["refresh_token"]

    out = client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert out.status_code == 204

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
