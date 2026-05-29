import re
import secrets

from core.constants import (
    INVITE_CODE_ALPHABET,
    INVITE_CODE_PATTERN,
    INVITE_CODE_PREFIX,
    INVITE_CODE_SUFFIX_LENGTH,
)

_INVITE_CODE_RE = re.compile(INVITE_CODE_PATTERN)


def generate_invite_code() -> str:
    suffix = "".join(
        secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_SUFFIX_LENGTH)
    )
    return f"{INVITE_CODE_PREFIX}{suffix}"


def normalize_invite_code(code: str) -> str:
    return code.strip().upper()


def is_valid_invite_code(code: str) -> bool:
    return _INVITE_CODE_RE.match(code) is not None
