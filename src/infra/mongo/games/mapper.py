from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from domain.game.schemas.state import GameState
from infra.mongo.games.document import GameDocument


def state_to_dict(state: GameState) -> dict[str, Any]:
    return state.model_dump(mode="json")


def dict_to_state(data: dict[str, Any]) -> GameState:
    return GameState.model_validate(data)


def to_domain(doc: GameDocument) -> tuple[GameState, int, int, list[int | tuple[int, ...]]]:
    """Return (state, seed, version, rng_state)."""
    return dict_to_state(doc.state), doc.seed, doc.version, doc.rng_state


def to_document(
    *,
    game_id: str,
    session_id: str,
    seed: int,
    rng_state: list[int | tuple[int, ...]],
    state: GameState,
    version: int = 0,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> GameDocument:
    now = datetime.now(UTC)
    return GameDocument(
        id=game_id,
        session_id=session_id,
        seed=seed,
        rng_state=rng_state,
        version=version,
        state=state_to_dict(state),
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def document_to_mongo(doc: GameDocument) -> dict[str, object]:
    payload = doc.model_dump()
    payload["_id"] = payload.pop("id")
    return payload


def document_from_mongo(raw: dict[str, object]) -> GameDocument:
    return GameDocument(
        id=str(raw["_id"]),
        session_id=str(raw["session_id"]),
        seed=int(cast(Any, raw["seed"])),
        rng_state=list(cast(list[Any], raw["rng_state"])),
        version=int(cast(Any, raw["version"])),
        state=dict(cast(dict[str, Any], raw["state"])),
        created_at=cast(datetime, raw["created_at"]),
        updated_at=cast(datetime, raw["updated_at"]),
    )
