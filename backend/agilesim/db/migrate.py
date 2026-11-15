"""Run migrations from code or the command line: ``python -m agilesim.db.migrate [revision]``."""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

_MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config(url: str | None = None) -> Config:
    """Alembic configuration pointing at the packaged migrations (no alembic.ini needed)."""
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS))
    if url:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade(revision: str = "head", url: str | None = None) -> None:
    command.upgrade(alembic_config(url), revision)


def downgrade(revision: str, url: str | None = None) -> None:
    command.downgrade(alembic_config(url), revision)


if __name__ == "__main__":
    upgrade(sys.argv[1] if len(sys.argv) > 1 else "head")
