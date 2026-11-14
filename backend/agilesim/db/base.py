"""Declarative base, constraint naming convention and column helpers."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names make Alembic migrations deterministic and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy declares this as a class attribute
        uuid.UUID: sa.Uuid(),
        datetime: sa.DateTime(timezone=True),
        dict[str, Any]: JSONB(),
    }


def uuid_pk() -> Mapped[uuid.UUID]:
    """Client-generated UUID primary key (the server default covers raw SQL inserts)."""
    return mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sa.text("gen_random_uuid()")
    )


def bigint_pk() -> Mapped[int]:
    """Monotonic identity key for append-only tables (insertion order = log order)."""
    return mapped_column(sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def created_at() -> Mapped[datetime]:
    return mapped_column(server_default=sa.func.now())


def enum_type(enum_cls: type[StrEnum]) -> sa.Enum:
    """Store an enum as VARCHAR holding the member *values* (no native PostgreSQL enum)."""
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=max(len(member.value) for member in enum_cls),
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


def enum_check(column: str, enum_cls: type[StrEnum]) -> sa.CheckConstraint:
    """CHECK constraint restricting ``column`` to the values of ``enum_cls``."""
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return sa.CheckConstraint(f"{column} IN ({values})", name=f"{column}_valid")
