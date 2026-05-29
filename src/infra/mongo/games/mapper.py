from __future__ import annotations

from datetime import UTC, datetime

from domain.game.schemas.state import GameState
from infra.mongo.games.document import GameDocument


def state_to_dict(state: GameState) -> dict:
    return state.model_dump(mode="json")


def dict_to_state(data: dict) -> GameState:
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
        seed=int(raw["seed"]),  # type: ignore[arg-type]
        rng_state=list(raw["rng_state"]),  # type: ignore[arg-type]
        version=int(raw["version"]),  # type: ignore[arg-type]
        state=dict(raw["state"]),  # type: ignore[arg-type]
        created_at=raw["created_at"],  # type: ignore[arg-type]
        updated_at=raw["updated_at"],  # type: ignore[arg-type]
    )
