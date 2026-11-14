"""Reference data: the Startup Flow (Kanban) scenario with its stages and event cards.

The 18 backlog cards are loaded separately (they belong to the course materials, not to the
platform); the stage and event definitions below follow the scenario description.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCENARIO = """
INSERT INTO scenarios (code, version, kind, name)
VALUES ('startup-flow', 1, 'kanban', 'Startup Flow (Kanban)')
"""

STAGES = """
INSERT INTO scenario_stages (scenario_id, code, name, kind, position, default_wip_limit)
SELECT s.id, v.code, v.name, v.kind, v.position, v.wip_limit
  FROM scenarios s,
       (VALUES ('backlog', 'Backlog', 'backlog', 0, NULL),
               ('analysis', 'Analysis', 'work', 1, 2),
               ('development', 'Development', 'work', 2, 3),
               ('testing', 'Testing', 'work', 3, 2),
               ('done', 'Done', 'done', 4, NULL)) AS v(code, name, kind, position, wip_limit)
 WHERE s.code = 'startup-flow' AND s.version = 1
"""

EVENTS = """
INSERT INTO scenario_events (scenario_id, code, day, title, description, effect, effect_amount)
SELECT s.id, v.code, v.day, v.title, v.description, v.effect, v.amount
  FROM scenarios s,
       (VALUES
          ('marketing_push', 2, 'Marketing push',
           'Pull three more cards (ID-106, ID-107, ID-108) into work regardless of the load.',
           'pull_cards', 3),
          ('integration_error', 3, 'Integration error',
           'The most valuable card in Development is BLOCKED until 3 full Development points '
           'are spent on it.',
           'block_top_card', 3),
          ('testing_pile_up', 4, 'Testing pile-up',
           'Many cards reach Testing, but the team has one die for Testing.',
           'none', NULL),
          ('technical_debt', 6, 'Technical debt',
           'The team may spend the whole Development roll on refactoring; later Development '
           'rolls get +1.',
           'dev_roll_bonus', 1),
          ('critical_bug', 7, 'Critical bug',
           'An emergency card worth $0 enters outside the WIP limits; all dice go to it.',
           'emergency_card', 0)
       ) AS v(code, day, title, description, effect, amount)
 WHERE s.code = 'startup-flow' AND s.version = 1
"""


def upgrade() -> None:
    for statement in (SCENARIO, STAGES, EVENTS):
        op.execute(statement)


def downgrade() -> None:
    # Stages and events are removed by the ON DELETE CASCADE of their scenario.
    op.execute("DELETE FROM scenarios WHERE code = 'startup-flow' AND version = 1")
