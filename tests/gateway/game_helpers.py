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


_SKIP_TYPES = frozenset({"connection.ping", "session.updated"})


def recv_game_state(ws) -> dict:
    """Return the next game.state frame, skipping pings and session.updated."""
    while True:
        msg = ws.receive_json()
        if msg["type"] in _SKIP_TYPES:
            continue
        assert msg["type"] == "game.state", msg
        return msg


def recv_error(ws) -> dict:
    """Return the next system.error frame, skipping pings and session.updated."""
    while True:
        msg = ws.receive_json()
        if msg["type"] in _SKIP_TYPES:
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


def _run_with_fresh_motor(coro_fn: Callable, *args: Any) -> Any:
    """Run an async function with a fresh Motor client (avoids event-loop conflicts
    with the Motor client that the TestClient's ASGI runner owns)."""
    import asyncio
    from core.config import get_settings
    from motor.motor_asyncio import AsyncIOMotorClient

    settings = get_settings()

    async def _wrapper():
        mc = AsyncIOMotorClient(settings.mongodb_uri)
        try:
            db = mc[settings.mongodb_db]
            return await coro_fn(db, *args)
        finally:
            mc.close()

    return asyncio.run(_wrapper())


def seed_game_state(client: TestClient, session_id: str, state: GameState) -> None:
    async def _update(db, sid: str, new_state: GameState) -> None:
        repo = GameRepository(db)
        stored = await repo.find_by_session_id(sid)
        assert stored is not None
        result = await repo.update_with_version(
            stored.game_id,
            new_state,
            stored.version,
            stored.rng_state,
        )
        assert result is not None

    _run_with_fresh_motor(_update, session_id, state)


def load_game_state(client: TestClient, session_id: str) -> GameState:
    async def _load(db, sid: str) -> GameState:
        repo = GameRepository(db)
        stored = await repo.find_by_session_id(sid)
        assert stored is not None
        return stored.state

    return _run_with_fresh_motor(_load, session_id)


def mutate_game_state(
    client: TestClient,
    session_id: str,
    mutator: Callable[[GameState], GameState],
) -> GameState:
    state = load_game_state(client, session_id)
    updated = mutator(state)
    seed_game_state(client, session_id, updated)
    return updated


def seed_post_roll_buyable(
    client: TestClient, session_id: str, position: int = 1
) -> GameState:
    """Deterministically put the current player in POST_ROLL standing on an unowned,
    purchasable property (default Mediterranean Ave, pos 1) with can_buy available —
    avoids the flakiness of rolling until a random buyable tile is reached."""
    from domain.game.enums import TurnPhase

    def _mutate(state: GameState) -> GameState:
        cur = state.turn.current_player_id
        spaces = list(state.spaces)
        spaces[position] = spaces[position].model_copy(
            update={"owner_id": None, "houses": 0, "has_hotel": False, "is_mortgaged": False}
        )
        players = list(state.players)
        idx = next(i for i, p in enumerate(players) if p.id == cur)
        players[idx] = players[idx].model_copy(update={"position": position})
        turn = state.turn.model_copy(
            update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": position}
        )
        return state.model_copy(
            update={"spaces": tuple(spaces), "players": tuple(players), "turn": turn}
        )

    return mutate_game_state(client, session_id, _mutate)


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
    """Run action on the CURRENT player's socket; both connected players must receive
    the same broadcast seq. Returns the current player's frame."""
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
        # Drain welcome + session.updated + initial game.state from both sockets.
        host_ws.receive_json()   # system.welcome
        guest_ws.receive_json()  # system.welcome
        host_snap = recv_game_state(host_ws)
        recv_game_state(guest_ws)

        # The action must come from whoever's turn it is.
        current_player_id = host_snap["payload"]["turn"]["current_player_id"]
        user_by_player = {p["id"]: p["user_id"] for p in host_snap["payload"]["players"]}
        current_user = user_by_player[current_player_id]
        if current_user == setup.host_id:
            current_ws, other_ws = host_ws, guest_ws
        else:
            current_ws, other_ws = guest_ws, host_ws

        action(current_ws, other_ws)
        current_msg = recv_game_state(current_ws)
        other_msg = recv_game_state(other_ws)
        assert current_msg["seq"] == other_msg["seq"]
        return current_msg
