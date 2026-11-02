"""Password hashes and the session cookie."""

from __future__ import annotations

import hashlib
import secrets

COOKIE = "omensite_session"
ANON = "omensite_csrf"
ITERATIONS = 200_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    _, digest = hash_password(password, salt)
    return secrets.compare_digest(digest, hash_hex)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def same_text(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)
