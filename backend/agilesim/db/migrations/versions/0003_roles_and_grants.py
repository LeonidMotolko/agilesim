"""Database roles and least-privilege grants.

Group roles (no login; cluster-wide, so they are created only if missing and kept on downgrade):

* ``app_read``  - read-only; sees personal data only through ``facilitators_masked``.
* ``app_write`` - what the application needs: DML on game tables, INSERT-only on the logs, no
  writes to the scenario catalogue. Inherits ``app_read``.
* ``app_admin`` - full rights on the schema objects, for maintenance and catalogue changes.

The application connects as a login role that is a member of ``app_write`` (``agilesim_app``,
created by ``db/init/``), never as a superuser or as the schema owner.

New tables get no automatic grants: add them here (or in a later migration). A test fails when
a table has no ``app_read`` privilege.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("app_read", "app_write", "app_admin")

# Reference data: changed by administrators only.
CATALOGUE_TABLES = (
    "scenarios",
    "scenario_stages",
    "scenario_cards",
    "scenario_card_work",
    "scenario_events",
)
# Mutable game state.
STATE_TABLES = (
    "game_sessions",
    "session_stage_limits",
    "teams",
    "participants",
    "cards",
    "card_work",
    "game_events",
    "survey_responses",
    "ai_drafts",
)
APPEND_ONLY_TABLES = ("card_movements", "dice_rolls", "point_spends")
VIEWS = ("facilitators_masked", "card_flow", "card_daily_state", "team_results")
FACILITATOR_PUBLIC_COLUMNS = "id, display_name, is_active, created_at, updated_at"

CREATE_ROLES = """
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['app_read', 'app_write', 'app_admin'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE', role_name
            );
        END IF;
    END LOOP;
END
$$
"""

JOIN_APPLICATION_ROLE = """
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agilesim_app') THEN
        GRANT app_write TO agilesim_app;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(CREATE_ROLES)
    op.execute("GRANT app_read TO app_write")
    op.execute(JOIN_APPLICATION_ROLE)

    op.execute("GRANT USAGE ON SCHEMA public TO app_read, app_write")
    op.execute("GRANT USAGE, CREATE ON SCHEMA public TO app_admin")

    read_tables = (*CATALOGUE_TABLES, *STATE_TABLES, *APPEND_ONLY_TABLES, *VIEWS)
    op.execute(f"GRANT SELECT ON {', '.join(read_tables)} TO app_read")
    op.execute(f"GRANT SELECT ({FACILITATOR_PUBLIC_COLUMNS}) ON facilitators TO app_read")

    op.execute(f"GRANT INSERT, UPDATE, DELETE ON {', '.join(STATE_TABLES)} TO app_write")
    op.execute(f"GRANT INSERT ON {', '.join(APPEND_ONLY_TABLES)} TO app_write")
    # Accounts are created and updated by the application, never deleted (sessions keep a
    # RESTRICT reference to their facilitator).
    op.execute("GRANT SELECT, INSERT, UPDATE ON facilitators TO app_write")

    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_admin")


def downgrade() -> None:
    op.execute(
        "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM app_read, app_write, app_admin"
    )
    op.execute("REVOKE ALL PRIVILEGES ON SCHEMA public FROM app_read, app_write, app_admin")
    op.execute("REVOKE app_read FROM app_write")
