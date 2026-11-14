"""Migrations: the models match the schema, and every step can be undone."""

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine

from agilesim.db import migrate
from agilesim.db.base import Base
from tests.db.test_metadata_and_url import EXPECTED_TABLES

pytestmark = pytest.mark.db


def test_models_match_the_migrated_schema(engine: Engine) -> None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_migrations_create_exactly_the_modelled_tables(engine: Engine) -> None:
    tables = set(sa.inspect(engine).get_table_names()) - {"alembic_version"}

    assert tables == EXPECTED_TABLES


def test_downgrade_to_base_and_upgrade_again(engine: Engine, database_url: str) -> None:
    migrate.downgrade("base", url=database_url)

    assert sa.inspect(engine).get_table_names() == ["alembic_version"]
    with engine.connect() as connection:
        functions = connection.scalars(
            sa.text(
                "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public'"
            )
        ).all()
    assert functions == []

    migrate.upgrade("head", url=database_url)

    assert set(sa.inspect(engine).get_table_names()) - {"alembic_version"} == EXPECTED_TABLES
