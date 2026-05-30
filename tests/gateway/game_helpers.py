from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from starlette.testclient import TestClient

from domain.game.schemas.state import GameState
from infra.mongo.games.repository import GameRepository
from tests.conftest import create_session, register_user


def ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


def envelope(msg_type: str, payload: dict | None = None) -> str:
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    })


def start_session(client: TestClient, session_id: str, host_token: str) -> None:
    resp = client.post(
        f"/api/v1/sessions/{session_id}/start",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert resp.status_code == 200, resp.text


def recv_game_state(ws) -> dict:
    while True:
        msg = ws.receive_json()
        if msg["type"] == "connection.ping":
            continue
        assert msg["type"] == "game.state", msg
        return msg


def recv_error(ws) -> dict:
    while True:
        msg = ws.receive_json()
        if msg["type"] == "connection.ping":
            continue
        assert msg["type"] == "system.error", msg
        return msg


@dataclass
class GameSetup:
    session_id: str
    host_id: str
    guest_id: str
    host_token: str
    guest_token: str

    @property
    def tokens_by_user(self) -> dict[str, str]:
        return {self.host_id: self.host_token, self.guest_id: self.guest_token}


def setup_two_player_game(client: TestClient) -> GameSetup:
    host_id, host_token = register_user(client, "host")
    guest_id, guest_token = register_user(client, "guest")
    session_id = create_session(client, host_token)
    client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    return GameSetup(
        session_id=session_id,
        host_id=host_id,
        guest_id=guest_id,
        host_token=host_token,
        guest_token=guest_token,
    )


def discover_current_token(client: TestClient, setup: GameSetup) -> str:
    start_session(client, setup.session_id, setup.host_token)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(setup.host_token),
    ) as probe:
        probe.receive_json()
        snapshot = recv_game_state(probe)["payload"]
    current_player_id = snapshot["turn"]["current_player_id"]
    user_by_player = {p["id"]: p["user_id"] for p in snapshot["players"]}
    return setup.tokens_by_user[user_by_player[current_player_id]]


def seed_game_state(client: TestClient, session_id: str, state: GameState) -> None:
    import anyio

    async def _update() -> None:
        db = client.app.state.mongo.db  # type: ignore[attr-defined]
        repo = GameRepository(db)
        stored = await repo.find_by_session_id(session_id)
        assert stored is not None
        result = await repo.update_with_version(
            stored.game_id,
            state,
            stored.version,
            stored.rng_state,
        )
        assert result is not None

    anyio.run(_update)


def load_game_state(client: TestClient, session_id: str) -> GameState:
    import anyio

    async def _load() -> GameState:
        db = client.app.state.mongo.db  # type: ignore[attr-defined]
        repo = GameRepository(db)
        stored = await repo.find_by_session_id(session_id)
        assert stored is not None
        return stored.state

    return anyio.run(_load)


def mutate_game_state(
    client: TestClient,
    session_id: str,
    mutator: Callable[[GameState], GameState],
) -> GameState:
    state = load_game_state(client, session_id)
    updated = mutator(state)
    seed_game_state(client, session_id, updated)
    return updated


def connect_and_sync(client: TestClient, session_id: str, token: str):
    ws = client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=ws_headers(token),
    )
    return ws


def player_token_for_current(setup: GameSetup, snapshot: dict) -> str:
    current_player_id = snapshot["turn"]["current_player_id"]
    user_by_player = {p["id"]: p["user_id"] for p in snapshot["players"]}
    return setup.tokens_by_user[user_by_player[current_player_id]]


def other_token_for_current(setup: GameSetup, snapshot: dict) -> str:
    current_player_id = snapshot["turn"]["current_player_id"]
    user_by_player = {p["id"]: p["user_id"] for p in snapshot["players"]}
    current_user = user_by_player[current_player_id]
    other_user = next(uid for uid in setup.tokens_by_user if uid != current_user)
    return setup.tokens_by_user[other_user]


def assert_dual_broadcast(
    client: TestClient,
    setup: GameSetup,
    action: Callable[[Any, Any], None],
) -> dict:
    """Run action on host_ws; both host and guest must receive the same seq."""
    with (
        client.websocket_connect(
            f"/ws/sessions/{setup.session_id}",
            headers=ws_headers(setup.host_token),
        ) as host_ws,
        client.websocket_connect(
            f"/ws/sessions/{setup.session_id}",
            headers=ws_headers(setup.guest_token),
        ) as guest_ws,
    ):
        host_ws.receive_json()
        guest_ws.receive_json()
        recv_game_state(host_ws)
        recv_game_state(guest_ws)
        action(host_ws, guest_ws)
        host_msg = recv_game_state(host_ws)
        guest_msg = recv_game_state(guest_ws)
        assert host_msg["seq"] == guest_msg["seq"]
        return host_msg
