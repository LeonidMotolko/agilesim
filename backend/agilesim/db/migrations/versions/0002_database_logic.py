"""Business rules in the database: functions, triggers and views.

* ``forbid_modification`` keeps the three logs append-only.
* ``apply_card_movement`` keeps ``cards`` (current position) in step with ``card_movements``.
* ``set_updated_at`` maintains ``updated_at`` columns.
* ``mask_email`` and the view ``facilitators_masked`` hide personal data from read-only users.
* ``card_flow``, ``card_daily_state`` and ``team_results`` compute the game metrics from the log.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORBID_MODIFICATION = """
CREATE FUNCTION forbid_modification() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Deleting a whole session or team cascades into the logs (and anonymises actors when a
    -- participant is removed). Those changes arrive from a foreign-key trigger, one level deep.
    IF pg_trigger_depth() > 1 THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '% on % is not allowed: the table is append-only', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END
$$
"""

SET_UPDATED_AT = """
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END
$$
"""

APPLY_CARD_MOVEMENT = """
CREATE FUNCTION apply_card_movement() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.from_stage_id IS NULL THEN
        -- A card entering the board directly (for example the emergency card).
        UPDATE cards SET stage_id = NEW.to_stage_id, stage_state = NEW.to_state
         WHERE id = NEW.card_id;
        RETURN NEW;
    END IF;

    UPDATE cards SET stage_id = NEW.to_stage_id, stage_state = NEW.to_state
     WHERE id = NEW.card_id
       AND stage_id = NEW.from_stage_id
       AND stage_state IS NOT DISTINCT FROM NEW.from_state;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'card % is not where the movement says it starts', NEW.card_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

MASK_EMAIL = """
CREATE FUNCTION mask_email(address text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT left(split_part(address, '@', 1), 1) || '***@' || split_part(address, '@', 2)
$$
"""

FACILITATORS_MASKED = """
CREATE VIEW facilitators_masked AS
SELECT id, display_name, mask_email(email) AS email_masked, is_active, created_at
  FROM facilitators
"""

# Lead Time follows the session's counting convention (default "inclusive": Done day - pull day
# + 1). In this scenario work starts when a card is pulled, so Cycle Time equals Lead Time.
CARD_FLOW = """
CREATE VIEW card_flow AS
WITH moves AS (
    SELECT m.card_id,
           min(m.day) FILTER (WHERE fs.kind = 'backlog') AS pulled_day,
           min(m.day) FILTER (WHERE ts.kind = 'done') AS done_day
      FROM card_movements m
      LEFT JOIN scenario_stages fs ON fs.id = m.from_stage_id
      JOIN scenario_stages ts ON ts.id = m.to_stage_id
     GROUP BY m.card_id
)
SELECT c.id AS card_id,
       c.team_id,
       t.session_id,
       sc.number AS card_number,
       sc.title,
       sc.value,
       sc.is_emergency,
       mv.pulled_day,
       mv.done_day,
       CASE
           WHEN mv.pulled_day IS NOT NULL AND mv.done_day IS NOT NULL
           THEN mv.done_day - mv.pulled_day
                + CASE gs.lead_time_convention WHEN 'inclusive' THEN 1 ELSE 0 END
       END AS lead_time_days
  FROM cards c
  JOIN teams t ON t.id = c.team_id
  JOIN game_sessions gs ON gs.id = t.session_id
  JOIN scenario_cards sc ON sc.id = c.scenario_card_id
  LEFT JOIN moves mv ON mv.card_id = c.id
"""

# One row per card and day between the pull and Done (or the current day), carrying the last
# logged position forward; this is the layout of the supervisor's logging table.
CARD_DAILY_STATE = """
CREATE VIEW card_daily_state AS
SELECT f.card_id,
       f.team_id,
       d.day,
       st.code AS stage_code,
       latest.to_state AS stage_state
  FROM card_flow f
 CROSS JOIN LATERAL generate_series(
           CAST(f.pulled_day AS integer),
           CAST(COALESCE(f.done_day,
                         (SELECT gs.current_day FROM game_sessions gs
                           WHERE gs.id = f.session_id)) AS integer)
       ) AS d(day)
 CROSS JOIN LATERAL (
       SELECT m.to_stage_id, m.to_state
         FROM card_movements m
        WHERE m.card_id = f.card_id AND m.day <= d.day
        ORDER BY m.id DESC
        LIMIT 1
       ) AS latest
  JOIN scenario_stages st ON st.id = latest.to_stage_id
"""

TEAM_RESULTS = """
CREATE VIEW team_results AS
SELECT t.id AS team_id,
       t.session_id,
       t.name AS team_name,
       count(f.card_id) FILTER (WHERE f.done_day IS NOT NULL) AS done_cards,
       COALESCE(sum(f.value) FILTER (WHERE f.done_day IS NOT NULL), 0) AS money_earned,
       round(avg(f.lead_time_days) FILTER (WHERE f.done_day IS NOT NULL), 2) AS avg_lead_time_days,
       rank() OVER (
           PARTITION BY t.session_id
           ORDER BY COALESCE(sum(f.value) FILTER (WHERE f.done_day IS NOT NULL), 0) DESC
       ) AS money_rank
  FROM teams t
  LEFT JOIN card_flow f ON f.team_id = t.id
 GROUP BY t.id, t.session_id, t.name
"""

APPEND_ONLY_TABLES = ("card_movements", "dice_rolls", "point_spends")
UPDATED_AT_TABLES = ("facilitators", "game_sessions", "cards")


def upgrade() -> None:
    for statement in (FORBID_MODIFICATION, SET_UPDATED_AT, APPLY_CARD_MOVEMENT, MASK_EMAIL):
        op.execute(statement)

    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_modification()"
        )
    for table in UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_set_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )
    op.execute(
        "CREATE TRIGGER card_movements_apply AFTER INSERT ON card_movements "
        "FOR EACH ROW EXECUTE FUNCTION apply_card_movement()"
    )

    for statement in (FACILITATORS_MASKED, CARD_FLOW, CARD_DAILY_STATE, TEAM_RESULTS):
        op.execute(statement)


def downgrade() -> None:
    for view in ("team_results", "card_daily_state", "card_flow", "facilitators_masked"):
        op.execute(f"DROP VIEW {view}")

    op.execute("DROP TRIGGER card_movements_apply ON card_movements")
    for table in UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER {table}_set_updated_at ON {table}")
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")

    for function in (
        "mask_email(text)",
        "apply_card_movement()",
        "set_updated_at()",
        "forbid_modification()",
    ):
        op.execute(f"DROP FUNCTION {function}")
