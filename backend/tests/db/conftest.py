"""Fixtures for tests that run against a real PostgreSQL database."""

from collections.abc import Generator, Iterator
from contextlib import contextmanager

import pytest
import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agilesim.db import migrate
from agilesim.db.session import make_engine
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture(scope="session")
def database_url() -> str:
    assert TEST_DATABASE_URL, "database tests need AGILESIM_TEST_DATABASE_URL"
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """A clean database migrated to the latest revision, shared by all tests of the session."""
    engine = make_engine(database_url)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    migrate.upgrade("head", url=database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back, so tests never see each other."""
    with engine.connect() as connection:
        outer = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


@contextmanager
def as_role(session: Session, role: str) -> Generator[None]:
    """Run the enclosed statements with the privileges of a database role."""
    session.flush()
    session.execute(sa.text(f"SET LOCAL ROLE {role}"))
    try:
        yield
    finally:
        session.execute(sa.text("RESET ROLE"))


@contextmanager
def failing(
    session: Session, error: type[Exception] = IntegrityError, match: str | None = None
) -> Generator[None]:
    """Expect ``error`` from the enclosed statements and roll back only to a savepoint.

    Opening a savepoint flushes the session, which would raise outside the block. Objects added
    before the block are therefore set aside and re-added inside it, so that the flush the test
    asks for happens within the savepoint and the session stays usable afterwards.
    """
    pending = list(session.new)
    for instance in pending:
        session.expunge(instance)
    with pytest.raises(error, match=match), session.begin_nested():  # noqa: PT012
        for instance in pending:
            session.add(instance)
        yield
