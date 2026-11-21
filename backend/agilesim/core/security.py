"""Password hashing, access tokens and join tokens.

Nothing here is home-made cryptography: Argon2id (``argon2-cffi``) for passwords, JWT through
``PyJWT`` for access tokens and ``secrets`` plus SHA-256 for random join tokens.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from agilesim.core.errors import UnauthorizedError

_hasher = PasswordHasher()
JWT_ALGORITHM = "HS256"
JOIN_TOKEN_BYTES = 32  # 256 bits of entropy, far above the 128 bits the schema documents


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_join_token() -> tuple[str, str]:
    """Return ``(token, sha256_hex)``: the token goes to the player, only the hash is stored."""
    token = secrets.token_urlsafe(JOIN_TOKEN_BYTES)
    return token, hash_join_token(token)


def hash_join_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(
    subject: uuid.UUID, role: str, *, secret: str, ttl: timedelta, now: datetime | None = None
) -> str:
    issued = now or datetime.now(UTC)
    claims = {"sub": str(subject), "role": role, "iat": issued, "exp": issued + ttl}
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> tuple[uuid.UUID, str]:
    """Return ``(subject id, role)`` or raise ``UnauthorizedError``."""
    try:
        claims = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return uuid.UUID(claims["sub"]), str(claims["role"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
