from typing import Literal

WsErrorCode = Literal[
    "unauthorized",
    "not_member",
    "malformed",
    "unsupported_version",
    "unknown_type",
    "rate_limited",
    "internal",
]
