import uuid
from datetime import UTC, datetime, timedelta

import pytest

from agilesim.core import security
from agilesim.core.errors import UnauthorizedError

SECRET = "unit-test-secret-with-enough-length-0123456789"
SUBJECT = uuid.UUID("11111111-1111-1111-1111-111111111111")


def test_password_hash_is_argon2_and_verifies() -> None:
    hashed = security.hash_password("correct horse battery")

    assert hashed.startswith("$argon2id$")
    assert security.verify_password("correct horse battery", hashed)


def test_wrong_password_and_garbage_hash_do_not_verify() -> None:
    hashed = security.hash_password("correct horse battery")

    assert not security.verify_password("wrong password", hashed)
    assert not security.verify_password("anything", "not-a-hash")


def test_same_password_gets_different_salts() -> None:
    assert security.hash_password("same password!") != security.hash_password("same password!")


def test_join_token_is_random_and_only_its_hash_matches() -> None:
    token, token_hash = security.new_join_token()
    other, other_hash = security.new_join_token()

    assert token != other
    assert len(token_hash) == 64
    assert security.hash_join_token(token) == token_hash
    assert token_hash != other_hash


def test_access_token_round_trip() -> None:
    token = security.create_access_token(
        SUBJECT, "facilitator", secret=SECRET, ttl=timedelta(minutes=5)
    )

    assert security.decode_access_token(token, secret=SECRET) == (SUBJECT, "facilitator")


def test_expired_token_is_rejected() -> None:
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    token = security.create_access_token(
        SUBJECT, "participant", secret=SECRET, ttl=timedelta(minutes=5), now=long_ago
    )

    with pytest.raises(UnauthorizedError):
        security.decode_access_token(token, secret=SECRET)


def test_token_signed_with_another_key_is_rejected() -> None:
    token = security.create_access_token(
        SUBJECT,
        "participant",
        secret="another-secret-with-enough-length-0123456789",
        ttl=timedelta(minutes=5),
    )

    with pytest.raises(UnauthorizedError):
        security.decode_access_token(token, secret=SECRET)


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        security.decode_access_token("not.a.token", secret=SECRET)
