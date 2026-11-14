"""Mask names for read-only users, index the participant columns of the logs, check hash format.

* ``mask_name`` and the view ``participants_masked``: ``app_read`` no longer reads participant
  names or join-token hashes; ``facilitators_masked`` now masks the facilitator's name as well.
  ``app_write`` (the application) keeps full access to both tables.
* Indexes on the participant columns of the three logs: removing a participant sets them to NULL
  (anonymisation), which would otherwise scan the whole log.
* ``ck_facilitators_password_hashed`` checks the whole Argon2 (PHC string) or bcrypt format, not
  only the prefix.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MASK_NAME = """
CREATE FUNCTION mask_name(full_name text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT left(btrim(full_name), 1) || '***'
$$
"""

FACILITATORS_MASKED = """
CREATE VIEW facilitators_masked AS
SELECT id,
       mask_name(display_name) AS display_name_masked,
       mask_email(email) AS email_masked,
       is_active,
       created_at
  FROM facilitators
"""

# Definition of revision 0002, restored on downgrade.
FACILITATORS_MASKED_0002 = """
CREATE VIEW facilitators_masked AS
SELECT id, display_name, mask_email(email) AS email_masked, is_active, created_at
  FROM facilitators
"""

PARTICIPANTS_MASKED = """
CREATE VIEW participants_masked AS
SELECT id,
       session_id,
       team_id,
       mask_name(display_name) AS display_name_masked,
       role,
       consent_given_at,
       joined_at
  FROM participants
"""

PARTICIPANT_PUBLIC_COLUMNS = "id, session_id, team_id, role, consent_given_at, joined_at"

ACTOR_INDEXES = (
    ("ix_card_movements_actor_participant_id", "card_movements", "actor_participant_id"),
    ("ix_dice_rolls_rolled_by", "dice_rolls", "rolled_by"),
    ("ix_point_spends_actor_participant_id", "point_spends", "actor_participant_id"),
)

# Argon2 in the PHC string format ($argon2id$v=19$m=65536,t=3,p=4$salt$hash) or bcrypt
# ($2b$12$ + 22 characters of salt + 31 characters of hash).
HASH_FORMAT = (
    r"^(\$argon2(id|i|d)\$v=[0-9]+\$m=[0-9]+,t=[0-9]+,p=[0-9]+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+"
    r"|\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53})$"
)
HASH_PREFIX_0001 = r"^\$(argon2(id|i|d)|2[aby])\$"


def _replace_password_check(regex: str) -> None:
    op.execute("ALTER TABLE facilitators DROP CONSTRAINT ck_facilitators_password_hashed")
    op.execute(
        "ALTER TABLE facilitators ADD CONSTRAINT ck_facilitators_password_hashed "
        f"CHECK (password_hash ~ '{regex}')"
    )


def upgrade() -> None:
    op.execute(MASK_NAME)

    op.execute("DROP VIEW facilitators_masked")
    op.execute(FACILITATORS_MASKED)
    op.execute(PARTICIPANTS_MASKED)
    op.execute("GRANT SELECT ON facilitators_masked, participants_masked TO app_read")
    op.execute("GRANT ALL PRIVILEGES ON facilitators_masked, participants_masked TO app_admin")

    # app_read: names only through the masked views, never the join-token hash.
    op.execute("REVOKE SELECT (display_name) ON facilitators FROM app_read")
    op.execute("REVOKE SELECT ON participants FROM app_read")
    op.execute(f"GRANT SELECT ({PARTICIPANT_PUBLIC_COLUMNS}) ON participants TO app_read")
    # The application needs the names and checks join tokens.
    op.execute("GRANT SELECT ON participants TO app_write")

    for name, table, column in ACTOR_INDEXES:
        op.create_index(name, table, [column])

    _replace_password_check(HASH_FORMAT)


def downgrade() -> None:
    _replace_password_check(HASH_PREFIX_0001)

    for name, table, _ in ACTOR_INDEXES:
        op.drop_index(name, table_name=table)

    op.execute("REVOKE SELECT ON participants FROM app_write")
    op.execute("REVOKE SELECT ON participants FROM app_read")
    op.execute("GRANT SELECT ON participants TO app_read")
    op.execute("GRANT SELECT (display_name) ON facilitators TO app_read")

    op.execute("DROP VIEW participants_masked")
    op.execute("DROP VIEW facilitators_masked")
    op.execute(FACILITATORS_MASKED_0002)
    op.execute("GRANT SELECT ON facilitators_masked TO app_read")
    op.execute("GRANT ALL PRIVILEGES ON facilitators_masked TO app_admin")

    op.execute("DROP FUNCTION mask_name(text)")
