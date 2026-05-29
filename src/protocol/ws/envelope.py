from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RawEnvelope(BaseModel):
    v: int
    type: str
    seq: int | None = None
    ts: datetime
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def make_outbound(
    msg_type: str,
    payload: BaseModel | dict[str, Any],
) -> dict[str, Any]:
    payload_dict = (
        payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    )
    return {
        "v": 1,
        "type": msg_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload_dict,
    }
