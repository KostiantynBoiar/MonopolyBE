from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.conftest import create_session


def test_create_and_list_public_lobby(
    client: TestClient,
    user_pair: tuple,
    auth_header,
) -> None:
    (host_id, host_token), _ = user_pair

    create_resp = client.post(
        "/api/v1/sessions",
        json={"visibility": "public"},
        headers=auth_header(host_token),
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    session_id = body["session"]["id"]
    assert body["session"]["invite_code"].startswith("TYC-")
    assert body["session"]["your_role"] == "host"
    assert body["session"]["member_count"] == 1

    list_resp = client.get(
        "/api/v1/sessions",
        headers=auth_header(host_token),
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(item["id"] == session_id for item in items)


def test_private_not_in_lobby_list(
    client: TestClient,
    user_pair: tuple,
    auth_header,
) -> None:
    (_, host_token), _ = user_pair

    create_resp = client.post(
        "/api/v1/sessions",
        json={"visibility": "private"},
        headers=auth_header(host_token),
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session"]["id"]

    list_resp = client.get(
        "/api/v1/sessions",
        headers=auth_header(host_token),
    )
    ids = {item["id"] for item in list_resp.json()["items"]}
    assert session_id not in ids


def test_join_by_code(
    client: TestClient,
    user_pair: tuple,
    auth_header,
) -> None:
    (_, host_token), (guest_id, guest_token) = user_pair

    create_resp = client.post(
        "/api/v1/sessions",
        json={"visibility": "private"},
        headers=auth_header(host_token),
    )
    assert create_resp.status_code == 201
    invite_code = create_resp.json()["session"]["invite_code"]

    join_resp = client.post(
        "/api/v1/sessions/join-by-code",
        json={"invite_code": invite_code},
        headers=auth_header(guest_token),
    )
    assert join_resp.status_code == 200
    members = join_resp.json()["session"]["members"]
    assert any(m["user_id"] == guest_id for m in members)


def test_join_public_by_id(
    client: TestClient,
    user_pair: tuple,
    auth_header,
) -> None:
    (_, host_token), (guest_id, guest_token) = user_pair

    create_resp = client.post(
        "/api/v1/sessions",
        json={"visibility": "public"},
        headers=auth_header(host_token),
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session"]["id"]

    join_resp = client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers=auth_header(guest_token),
    )
    assert join_resp.status_code == 200
    assert join_resp.json()["session"]["member_count"] == 2
    assert any(m["user_id"] == guest_id for m in join_resp.json()["session"]["members"])


def test_kick_forbidden_for_non_host(
    client: TestClient,
    user_pair: tuple,
    auth_header,
) -> None:
    (host_id, host_token), (_, guest_token) = user_pair

    session_id = create_session(client, host_token)

    client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers=auth_header(guest_token),
    )

    kick_resp = client.delete(
        f"/api/v1/sessions/{session_id}/members/{host_id}",
        headers=auth_header(guest_token),
    )
    assert kick_resp.status_code == 403


def test_start_session(
    client: TestClient,
    user_pair: tuple,
    auth_header,
) -> None:
    (_, host_token), (_, guest_token) = user_pair

    session_id = create_session(client, host_token)

    start_resp = client.post(
        f"/api/v1/sessions/{session_id}/start",
        headers=auth_header(host_token),
    )
    assert start_resp.status_code == 200
    assert start_resp.json()["session"]["status"] == "in_progress"

    join_resp = client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers=auth_header(guest_token),
    )
    assert join_resp.status_code == 409
