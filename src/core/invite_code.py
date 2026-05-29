import re
import secrets

INVITE_CODE_PATTERN = re.compile(r"^TYC-[A-Z0-9]{4}$")
_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def generate_invite_code() -> str:
    suffix = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
    return f"TYC-{suffix}"


def normalize_invite_code(code: str) -> str:
    return code.strip().upper()
