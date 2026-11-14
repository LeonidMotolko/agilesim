"""The data dictionary in docs/database.md covers every table and column of the models."""

import re
from pathlib import Path

from agilesim.db.base import Base

DOC = Path(__file__).parents[3] / "docs" / "database.md"


def sections() -> dict[str, str]:
    text = DOC.read_text(encoding="utf-8")
    parts = re.split(r"^### `(\w+)`", text, flags=re.MULTILINE)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def test_every_table_has_a_section() -> None:
    assert set(Base.metadata.tables) <= set(sections())


def test_every_column_is_described() -> None:
    documented = sections()
    missing = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if f"`{column.name}`" not in documented[table.name]
    ]

    assert missing == []
