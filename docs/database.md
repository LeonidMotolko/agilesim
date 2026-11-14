# AgileSim database

PostgreSQL 17, schema `public`, managed only through Alembic migrations
(`backend/agilesim/db/migrations/versions/`). Models: `backend/agilesim/db/models.py`.

| File | Purpose |
| --- | --- |
| [er-diagram.svg](er-diagram.svg) / [er-diagram.mmd](er-diagram.mmd) | Logical schema (Mermaid source and rendered image) |
| [schema.sql](schema.sql) | DDL script: the SQL that the migrations run (`alembic upgrade head --sql`) |
| this file | Data dictionary, integrity rules, roles, indexes, versioning |

![Logical schema](er-diagram.svg)

The tables fall into four blocks:

* **Scenario catalogue** (reference data): `scenarios`, `scenario_stages`, `scenario_cards`,
  `scenario_card_work`, `scenario_events`. Changed by administrators only.
* **Accounts and sessions**: `facilitators`, `game_sessions`, `session_stage_limits`, `teams`,
  `participants`.
* **Game state**: `cards`, `card_work`, `game_events`, `survey_responses`, `ai_drafts`.
* **Append-only logs**: `card_movements`, `dice_rolls`, `point_spends`. The metrics (Lead Time,
  money, daily states) are computed from `card_movements` by views.

## Design decisions

**Third normal form.** Facts are stored once. A team's `cards` row holds only the team's own
state (current column, blocked flag); title, value and the work each stage needs are read from
the scenario card. The work still open per stage is one row per stage in `card_work`
(no repeating columns such as `analysis_left`, `development_left`). The scenario's stages are rows of
`scenario_stages`, not columns or an enum, so another scenario can have other columns.
`scenario_card_work.scenario_id` repeats the scenario on purpose: two composite foreign keys use it
to guarantee that a card and a stage belong to the same scenario without a trigger.

**Where the schema is deliberately not minimal.**
`cards.stage_id/stage_state` is the *current* position and could be derived from the log; it is
kept (and synchronised by a trigger) because the board reads it on every request.
`card_movements` stores stage ids of the moment, which are immutable because a scenario version
is never edited after it is used (a change is a new `version` row).

**No JSON.** No column stores JSON or JSONB. Scenario rules that are not tabular (event effects)
are a closed list in `scenario_events.effect`, applied by the rule engine.

**Enumerations** are `varchar` columns with a CHECK constraint listing the values (`*_valid`
constraints), not native PostgreSQL enums, so a new value is a one-line migration.

**Money** is `numeric(10,2)`; all points in time are `timestamptz`; days of the game are
`smallint` (the game has 8 days).

**Passwords** are never stored in plain text. `facilitators.password_hash` must match the shape of
an Argon2 or bcrypt hash (`ck_facilitators_password_hashed`), so plain text, MD5 and SHA-1 are
rejected by the database itself. Participants have no password: they hold a random join token of
which only the SHA-256 hash is stored (`participants.token_hash`).

## Integrity and transactions

* Every table has a primary key; every relationship is a foreign key with an explicit
  `ON DELETE` rule: `CASCADE` for owned data (a session owns its teams, cards, logs), `RESTRICT`
  for catalogue data and for the facilitator of a session, `SET NULL` for optional actors, so removing a
  participant anonymises the log instead of deleting history.
* Business rules that fit in one row are CHECK constraints: dice value 1 to 6, join code format
  (`^[A-Z0-9]{6}$`), manual log rows need a comment and a facilitator, an applied event needs its
  timestamps, help points count half rounded down (`ck_point_spends_half_value_rule`), and more.
* Rules that span rows are UNIQUE constraints: one roll per team, stage and day; one log row per
  `(team, request_id)` (this makes retried requests idempotent); one instance of a scenario event
  per session; one answer per participant and survey phase.
* Composite foreign keys keep related rows inside one team or session: a log row's card must
  belong to the log row's team; a participant's team must belong to the participant's session.
* Each game action is one transaction in the application: the log row, the card update (done by
  trigger) and the work squares change commit or roll back together. Isolation is the PostgreSQL
  default (read committed); two concurrent moves of one card cannot both succeed because the
  `apply_card_movement` trigger updates the card only if it is still where the move says (a move
  without a source stage locks the card and is accepted only as its first movement).

## Functions, triggers and views (migration 0002)

| Object | What it does |
| --- | --- |
| `forbid_modification()` + triggers `*_append_only` | `card_movements`, `dice_rolls` and `point_spends` reject direct UPDATE and DELETE. Cascades (deleting a session) and the anonymising `SET NULL` still work because they arrive from a foreign-key trigger one level deeper (`pg_trigger_depth()`). |
| `apply_card_movement()` + trigger `card_movements_apply` | After a log row is inserted, moves the card to the logged position; refuses a move whose source position is stale. A row without a source stage (a card entering the board directly, such as the emergency card) is accepted only as the card's first movement. |
| `set_updated_at()` + triggers `*_set_updated_at` | Maintains `updated_at` on `facilitators`, `game_sessions`, `cards`. |
| `mask_email(text)` | `anna.k@example.com` becomes `a***@example.com`. |
| view `facilitators_masked` | Facilitators without the password hash and with a masked e-mail; the only way `app_read` sees accounts. |
| view `card_flow` | Per card: pull day, Done day, Lead Time under the session's counting convention (default inclusive: Done minus pull plus 1). Cycle Time equals Lead Time in this scenario because work starts at the pull. Corrections are respected: the days are those of the latest pull (or direct entry) and the latest arrival in Done, and they count only while the card is out of the backlog or in Done, so a card moved back out of Done has no Done day and earns no money. |
| view `card_daily_state` | One row per card and day from the pull to Done (or the current day), carrying the last logged position forward. This is the layout of the supervisor's logging table. |
| view `team_results` | Cards done, money earned (only cards in Done), average Lead Time and the rank of the team in its session (window function). |

## Roles and access (migration 0003)

| Role | Login | Rights |
| --- | --- | --- |
| `app_read` | no | SELECT on all tables and views except the personal columns of `facilitators` (`email`, `password_hash`); sees accounts through `facilitators_masked`. |
| `app_write` | no | Inherits `app_read`. INSERT/UPDATE/DELETE on game state; INSERT only on the three logs (the triggers are a second lock); SELECT/INSERT/UPDATE on `facilitators`; no write access to the scenario catalogue. |
| `app_admin` | no | All privileges on the schema's tables, plus CREATE in the schema: catalogue changes and maintenance. |
| `agilesim_app` | yes | The role the API connects with (`AGILESIM_DATABASE_URL`). Member of `app_write`. Not a superuser, owns nothing. Created by `db/init/10-app-role.sh`. |
| schema owner (`POSTGRES_USER`) | yes | Runs the migrations only (`AGILESIM_MIGRATION_DATABASE_URL`). |

The application never runs under the superuser. New tables get **no** automatic grants: add the
grant in the migration that creates the table. The test `test_every_table_and_view_is_readable_by_app_read`
fails when a table was forgotten.

Game roles are a different layer: a *facilitator* owns sessions (`game_sessions.facilitator_id`) and
may act on all of its teams; a *participant* is bound to one team of one session
(`participants.team_id`) and acts only on that team. The API enforces that, using the database
keys above.

## Indexes (and why)

Primary keys and UNIQUE constraints already create indexes (join code, team name per session,
request ids, the roll rule). Additional indexes exist only for queries the game runs constantly:

| Index | Query it serves |
| --- | --- |
| `ix_cards_team_id_stage_id` | Board of a team: cards per column; WIP counters |
| `ix_cards_scenario_card_id` | Join to the scenario card; protects the `RESTRICT` check |
| `ix_card_movements_card_id_day` | Card history, `card_flow` and `card_daily_state` |
| `ix_card_movements_team_id_day` | Log of a team per day, CSV/XLSX export |
| `ix_point_spends_card_id`, `ix_point_spends_team_id_day` | Points spent on a card; points of a team per day |
| `ix_game_sessions_facilitator_id` | "My sessions" list of a facilitator |
| `ix_participants_team_id` | Members of a team |
| `ix_game_events_session_id_day` | The event of the current day |
| `ix_scenario_events_scenario_id_day` | Event cards of a scenario by day |
| `ix_ai_drafts_session_id_kind` | Pending drafts of a session |

## Versioning and deployment

The structure is created and changed only by Alembic migrations kept in Git; nothing is created by
hand. Each migration has `upgrade()` and `downgrade()`, and the tests run both.

| Revision | Content |
| --- | --- |
| `0001` | Tables, keys, constraints, indexes |
| `0002` | Functions, triggers, views |
| `0003` | Roles and grants |
| `0004` | Reference data: Startup Flow scenario, its five stages and its event cards |

```bash
cd backend
AGILESIM_MIGRATION_DATABASE_URL=postgresql://owner:***@localhost/agilesim uv run python -m agilesim.db.migrate        # to head
AGILESIM_MIGRATION_DATABASE_URL=... uv run alembic -c alembic.ini upgrade head --sql > ../docs/schema.sql             # DDL script
AGILESIM_MIGRATION_DATABASE_URL=... uv run alembic -c alembic.ini revision -m "describe the change"                   # new migration
```

With Docker Compose the backend container runs the migrations before the API starts.
A test compares the models with the migrated schema (`alembic` autogenerate diff must be empty), so
the models and the migrations cannot drift apart.

## Test data

* Reference data (`0004`): the scenario, the stages Backlog, Analysis, Development, Testing, Done
  (WIP defaults 2/3/2) and the five event cards of days 2, 3, 4, 6, 7. The 18 backlog cards
  belong to the course materials and are loaded as data, not as a migration.
* Tests build their own rows (`backend/tests/db/factories.py`) inside a transaction that is rolled
  back. They cover the reference set of the analysis (cards 104, 105, 115, 102: Lead Time 5, 3, 8, 2,
  money 330), unfinished cards, cards never pulled, two teams ranked by money, and every constraint
  with a valid and an invalid row.

## Data dictionary

`PK` primary key, `FK` foreign key, `UK` unique, `NN` not null. Constraint names are
`ck_<table>_<name>`, `uq_<table>_<name>`, `fk_<table>_<column>_<table>`, `ix_<table>_<columns>`.

### `scenarios`
A playable scenario in one version.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK, generated |
| `code` | varchar(40) | NN, stable key such as `startup-flow`; UK with `version` |
| `version` | smallint | NN, default 1, `>= 1`; a used version is never edited |
| `kind` | varchar(6) | NN, `kanban` or `scrum` |
| `name` | varchar(120) | NN |
| `created_at` | timestamptz | NN, default now |

### `scenario_stages`
A board column of a scenario.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `scenario_id` | uuid | FK `scenarios`, cascade; UK with `code`, with `position`, with `id` |
| `code` | varchar(32) | NN, `backlog`, `analysis`, `development`, `testing`, `done` |
| `name` | varchar(60) | NN, display name |
| `kind` | varchar(7) | NN, `backlog`, `work` or `done` |
| `position` | smallint | NN, `>= 0`, left to right |
| `default_wip_limit` | smallint | `>= 1`; only for `work` stages (null otherwise) |

### `scenario_cards`
A ticket of the scenario backlog.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `scenario_id` | uuid | FK `scenarios`, cascade; UK with `number` |
| `number` | smallint | NN, card id shown to players (for example 104), `>= 0` |
| `title` | varchar(200) | NN |
| `value` | numeric(10,2) | NN, business value in dollars, `>= 0` |
| `is_emergency` | boolean | NN, default false; the emergency card of day 7 (outside the WIP limits) |

### `scenario_card_work`
Work squares a scenario card needs on a stage.

| Column | Type | Notes |
| --- | --- | --- |
| `scenario_card_id` | uuid | PK part; composite FK to `scenario_cards (id, scenario_id)` |
| `stage_id` | uuid | PK part; composite FK to `scenario_stages (id, scenario_id)` |
| `scenario_id` | uuid | NN, makes both composite keys check the same scenario |
| `squares` | smallint | NN, `>= 1` |

### `scenario_events`
An event card of a scenario.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `scenario_id` | uuid | FK `scenarios`, cascade; UK with `code` |
| `code` | varchar(40) | NN, for example `marketing_push` |
| `day` | smallint | NN, `>= 1` |
| `title` | varchar(120) | NN |
| `description` | text | NN, text shown to the facilitator |
| `effect` | varchar(14) | NN, `none`, `pull_cards`, `block_top_card`, `dev_roll_bonus`, `emergency_card` |
| `effect_amount` | smallint | `>= 0`, size of the effect (cards to pull, points to unblock, bonus) |

### `facilitators`
Accounts of facilitators (Product Owners).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `email` | varchar(254) | NN, UK, lower case, contains `@`; personal data (masked for `app_read`) |
| `display_name` | varchar(80) | NN |
| `password_hash` | varchar(255) | NN, must look like an Argon2 or bcrypt hash; hidden from `app_read` |
| `is_active` | boolean | NN, default true |
| `created_at` | timestamptz | NN, default now |
| `updated_at` | timestamptz | NN, set by trigger |

### `game_sessions`
One game run by a facilitator for several teams.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `facilitator_id` | uuid | FK `facilitators`, restrict, indexed |
| `scenario_id` | uuid | FK `scenarios`, restrict |
| `name` | varchar(120) | NN |
| `join_code` | varchar(6) | NN, UK, `^[A-Z0-9]{6}$` |
| `status` | varchar(8) | NN, default `lobby`; `lobby`, `running`, `paused`, `finished` |
| `current_day` | smallint | NN, default 0, `>= 0` |
| `wip_limits_enabled` | boolean | NN, default false; switched on after Retrospective 1 |
| `lead_time_convention` | varchar(10) | NN, default `inclusive`; or `difference` |
| `started_at`, `finished_at` | timestamptz | `finished_at` needs `started_at` |
| `created_at`, `updated_at` | timestamptz | NN; `updated_at` set by trigger |

### `session_stage_limits`
WIP limit of one stage in one session (overrides the scenario default).

| Column | Type | Notes |
| --- | --- | --- |
| `session_id` | uuid | PK part; FK `game_sessions`, cascade |
| `stage_id` | uuid | PK part; FK `scenario_stages`, restrict |
| `wip_limit` | smallint | NN, `>= 1` |

### `teams`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `session_id` | uuid | FK `game_sessions`, cascade; UK with `name` and with `id` |
| `name` | varchar(60) | NN |
| `created_at` | timestamptz | NN, default now |

### `participants`
A player without an account.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `session_id` | uuid | FK `game_sessions`, cascade; UK with `display_name` |
| `team_id` | uuid | Optional; composite FK to `teams (id, session_id)`, so the team is in the same session; indexed |
| `display_name` | varchar(60) | NN, not blank; the only personal data |
| `role` | varchar(12) | NN, default `player`; or `scrum_master` |
| `token_hash` | varchar(64) | NN, UK, SHA-256 hex of the join token |
| `consent_given_at` | timestamptz | NN, moment of consent to take part |
| `joined_at` | timestamptz | NN, default now |

### `cards`
A team's copy of a scenario card and its current position.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK; UK with `team_id` (target of the log's composite keys) |
| `team_id` | uuid | FK `teams`, cascade; UK with `scenario_card_id` |
| `scenario_card_id` | uuid | FK `scenario_cards`, restrict |
| `stage_id` | uuid | FK `scenario_stages`, restrict; current column |
| `stage_state` | varchar(11) | `in_progress` or `ready`; null in Backlog and Done |
| `is_blocked` | boolean | NN, default false |
| `updated_at` | timestamptz | NN, set by trigger |

### `card_work`
| Column | Type | Notes |
| --- | --- | --- |
| `card_id` | uuid | PK part; FK `cards`, cascade |
| `stage_id` | uuid | PK part; FK `scenario_stages`, restrict |
| `squares_left` | smallint | NN, `>= 0` |

### `game_events`
An event in one session: from the scenario, drafted by the AI, or entered by hand.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `session_id` | uuid | FK `game_sessions`, cascade |
| `scenario_event_id` | uuid | FK `scenario_events`, restrict; required when `source = template`; UK with `session_id` (applied once) |
| `day` | smallint | NN, `>= 1` |
| `title` | varchar(120) | NN |
| `description` | text | NN |
| `source` | varchar(8) | NN, `template`, `ai`, `manual` |
| `status` | varchar(9) | NN, default `proposed`; `confirmed`, `applied`, `dismissed`; confirmed or applied needs `confirmed_at`, applied needs `applied_at` |
| `confirmed_by` | uuid | FK `facilitators`, set null |
| `confirmed_at`, `applied_at` | timestamptz | See `status` |
| `created_at` | timestamptz | NN, default now |

### `survey_responses`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `participant_id` | uuid | FK `participants`, cascade; UK with `phase` |
| `phase` | varchar(4) | NN, `pre` or `post` |
| `confidence` | smallint | NN, 1 to 5 |
| `submitted_at` | timestamptz | NN, default now |

### `ai_drafts`
Text drafted by the AI assistant; shown to players only after approval.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid | PK |
| `session_id` | uuid | FK `game_sessions`, cascade |
| `team_id` | uuid | FK `teams`, set null |
| `kind` | varchar(14) | NN, `event` or `retro_feedback` |
| `prompt` | text | NN, the prompt sent (kept for quality evaluation) |
| `content` | text | NN, the generated text |
| `model` | varchar(64) | NN, model identifier |
| `status` | varchar(8) | NN, default `draft`; `approved`, `rejected` need `reviewed_by` and `reviewed_at` |
| `reviewed_by` | uuid | FK `facilitators`, set null |
| `reviewed_at` | timestamptz | See `status` |
| `created_at` | timestamptz | NN, default now |

### `card_movements` (append-only)
| Column | Type | Notes |
| --- | --- | --- |
| `id` | bigint | PK, identity (log order) |
| `team_id` | uuid | FK `teams`, cascade; UK with `request_id` |
| `card_id` | uuid | Composite FK to `cards (id, team_id)`, cascade |
| `day` | smallint | NN, `>= 1` |
| `from_stage_id` | uuid | FK `scenario_stages`, restrict; null when a card enters the board directly |
| `from_state` | varchar(11) | `in_progress` or `ready` |
| `to_stage_id` | uuid | NN, FK `scenario_stages`, restrict |
| `to_state` | varchar(11) | `in_progress` or `ready` |
| `actor_participant_id` | uuid | FK `participants`, set null |
| `actor_facilitator_id` | uuid | FK `facilitators`, set null; at most one actor |
| `request_id` | uuid | NN, idempotency key of the API request |
| `is_manual` | boolean | NN, default false; a manual row needs a comment and a facilitator |
| `comment` | text | Reason of a manual correction |
| `occurred_at` | timestamptz | NN, default now |

### `dice_rolls` (append-only)
| Column | Type | Notes |
| --- | --- | --- |
| `id` | bigint | PK, identity |
| `team_id` | uuid | FK `teams`, cascade; UK with `stage_id` and `day` (one roll per stage and day) and with `request_id` |
| `stage_id` | uuid | NN, FK `scenario_stages`, restrict |
| `day` | smallint | NN, `>= 1` |
| `value` | smallint | NN, 1 to 6 |
| `rolled_by` | uuid | FK `participants`, set null |
| `request_id` | uuid | NN |
| `occurred_at` | timestamptz | NN, default now |

### `point_spends` (append-only)
| Column | Type | Notes |
| --- | --- | --- |
| `id` | bigint | PK, identity |
| `team_id` | uuid | FK `teams`, cascade; UK with `request_id` |
| `card_id` | uuid | Composite FK to `cards (id, team_id)`, cascade |
| `day` | smallint | NN, `>= 1` |
| `source_stage_id` | uuid | NN, FK `scenario_stages`, restrict; stage of the die |
| `target_stage_id` | uuid | NN, FK `scenario_stages`, restrict; stage of the card |
| `points_spent` | smallint | NN, `>= 1` |
| `squares_crossed` | smallint | NN; equals the points for the same stage, half rounded down for help |
| `actor_participant_id` | uuid | FK `participants`, set null |
| `request_id` | uuid | NN |
| `occurred_at` | timestamptz | NN, default now |
