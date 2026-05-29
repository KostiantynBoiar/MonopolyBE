from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class GameDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    session_id: str
    seed: int
    # Opaque random.getstate() = (version, 625-int tuple, gauss_next: float | None).
    # Stored and restored verbatim; the third element is usually None, so keep this permissive.
    rng_state: list[Any]
    version: int
    state: dict[str, Any]
    created_at: datetime
    updated_at: datetime
