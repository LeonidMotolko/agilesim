BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE scenarios (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    version SMALLINT DEFAULT '1' NOT NULL, 
    kind VARCHAR(6) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_scenarios PRIMARY KEY (id), 
    CONSTRAINT uq_scenarios_code_version UNIQUE (code, version), 
    CONSTRAINT ck_scenarios_kind_valid CHECK (kind IN ('kanban', 'scrum')), 
    CONSTRAINT ck_scenarios_version_positive CHECK (version >= 1)
);

CREATE TABLE scenario_stages (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    scenario_id UUID NOT NULL, 
    code VARCHAR(32) NOT NULL, 
    name VARCHAR(60) NOT NULL, 
    kind VARCHAR(7) NOT NULL, 
    position SMALLINT NOT NULL, 
    default_wip_limit SMALLINT, 
    CONSTRAINT pk_scenario_stages PRIMARY KEY (id), 
    CONSTRAINT fk_scenario_stages_scenario_id_scenarios FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE, 
    CONSTRAINT uq_scenario_stages_code UNIQUE (scenario_id, code), 
    CONSTRAINT uq_scenario_stages_position UNIQUE (scenario_id, position), 
    CONSTRAINT uq_scenario_stages_id_scenario UNIQUE (id, scenario_id), 
    CONSTRAINT ck_scenario_stages_kind_valid CHECK (kind IN ('backlog', 'work', 'done')), 
    CONSTRAINT ck_scenario_stages_position_non_negative CHECK (position >= 0), 
    CONSTRAINT ck_scenario_stages_wip_limit_positive CHECK (default_wip_limit IS NULL OR default_wip_limit >= 1), 
    CONSTRAINT ck_scenario_stages_wip_limit_only_for_work CHECK (kind = 'work' OR default_wip_limit IS NULL)
);

CREATE TABLE scenario_cards (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    scenario_id UUID NOT NULL, 
    number SMALLINT NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    value NUMERIC(10, 2) NOT NULL, 
    is_emergency BOOLEAN DEFAULT false NOT NULL, 
    CONSTRAINT pk_scenario_cards PRIMARY KEY (id), 
    CONSTRAINT fk_scenario_cards_scenario_id_scenarios FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE, 
    CONSTRAINT uq_scenario_cards_number UNIQUE (scenario_id, number), 
    CONSTRAINT uq_scenario_cards_id_scenario UNIQUE (id, scenario_id), 
    CONSTRAINT ck_scenario_cards_number_non_negative CHECK (number >= 0), 
    CONSTRAINT ck_scenario_cards_value_non_negative CHECK (value >= 0)
);

CREATE TABLE scenario_card_work (
    scenario_card_id UUID NOT NULL, 
    stage_id UUID NOT NULL, 
    scenario_id UUID NOT NULL, 
    squares SMALLINT NOT NULL, 
    CONSTRAINT pk_scenario_card_work PRIMARY KEY (scenario_card_id, stage_id), 
    CONSTRAINT fk_scenario_card_work_card FOREIGN KEY(scenario_card_id, scenario_id) REFERENCES scenario_cards (id, scenario_id) ON DELETE CASCADE, 
    CONSTRAINT fk_scenario_card_work_stage FOREIGN KEY(stage_id, scenario_id) REFERENCES scenario_stages (id, scenario_id) ON DELETE CASCADE, 
    CONSTRAINT ck_scenario_card_work_squares_positive CHECK (squares >= 1)
);

CREATE TABLE scenario_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    scenario_id UUID NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    day SMALLINT NOT NULL, 
    title VARCHAR(120) NOT NULL, 
    description TEXT NOT NULL, 
    effect VARCHAR(14) NOT NULL, 
    effect_amount SMALLINT, 
    CONSTRAINT pk_scenario_events PRIMARY KEY (id), 
    CONSTRAINT fk_scenario_events_scenario_id_scenarios FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE CASCADE, 
    CONSTRAINT uq_scenario_events_code UNIQUE (scenario_id, code), 
    CONSTRAINT uq_scenario_events_id_scenario UNIQUE (id, scenario_id), 
    CONSTRAINT ck_scenario_events_effect_valid CHECK (effect IN ('none', 'pull_cards', 'block_top_card', 'dev_roll_bonus', 'emergency_card')), 
    CONSTRAINT ck_scenario_events_day_positive CHECK (day >= 1), 
    CONSTRAINT ck_scenario_events_amount_valid CHECK (effect_amount IS NULL OR effect_amount >= 0)
);

CREATE INDEX ix_scenario_events_scenario_id_day ON scenario_events (scenario_id, day);

CREATE TABLE facilitators (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    display_name VARCHAR(80) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_facilitators PRIMARY KEY (id), 
    CONSTRAINT uq_facilitators_email UNIQUE (email), 
    CONSTRAINT ck_facilitators_email_lowercase CHECK (email = lower(email)), 
    CONSTRAINT ck_facilitators_email_has_at CHECK (position('@' IN email) > 1), 
    CONSTRAINT ck_facilitators_password_hashed CHECK (password_hash ~ '^\$(argon2(id|i|d)|2[aby])\$')
);

CREATE TABLE game_sessions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    facilitator_id UUID NOT NULL, 
    scenario_id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    join_code VARCHAR(6) NOT NULL, 
    status VARCHAR(8) DEFAULT 'lobby' NOT NULL, 
    current_day SMALLINT DEFAULT '0' NOT NULL, 
    wip_limits_enabled BOOLEAN DEFAULT false NOT NULL, 
    lead_time_convention VARCHAR(10) DEFAULT 'inclusive' NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_game_sessions PRIMARY KEY (id), 
    CONSTRAINT fk_game_sessions_facilitator_id_facilitators FOREIGN KEY(facilitator_id) REFERENCES facilitators (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_game_sessions_scenario_id_scenarios FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_game_sessions_join_code UNIQUE (join_code), 
    CONSTRAINT ck_game_sessions_status_valid CHECK (status IN ('lobby', 'running', 'paused', 'finished')), 
    CONSTRAINT ck_game_sessions_lead_time_convention_valid CHECK (lead_time_convention IN ('inclusive', 'difference')), 
    CONSTRAINT ck_game_sessions_join_code_format CHECK (join_code ~ '^[A-Z0-9]{6}$'), 
    CONSTRAINT ck_game_sessions_current_day_non_negative CHECK (current_day >= 0), 
    CONSTRAINT ck_game_sessions_finished_after_started CHECK (finished_at IS NULL OR started_at IS NOT NULL)
);

CREATE INDEX ix_game_sessions_facilitator_id ON game_sessions (facilitator_id);

CREATE TABLE session_stage_limits (
    session_id UUID NOT NULL, 
    stage_id UUID NOT NULL, 
    wip_limit SMALLINT NOT NULL, 
    CONSTRAINT pk_session_stage_limits PRIMARY KEY (session_id, stage_id), 
    CONSTRAINT fk_session_stage_limits_session_id_game_sessions FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_session_stage_limits_stage_id_scenario_stages FOREIGN KEY(stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_session_stage_limits_wip_limit_positive CHECK (wip_limit >= 1)
);

CREATE TABLE teams (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    session_id UUID NOT NULL, 
    name VARCHAR(60) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_teams PRIMARY KEY (id), 
    CONSTRAINT fk_teams_session_id_game_sessions FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT uq_teams_session_name UNIQUE (session_id, name), 
    CONSTRAINT uq_teams_id_session UNIQUE (id, session_id)
);

CREATE TABLE participants (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    session_id UUID NOT NULL, 
    team_id UUID, 
    display_name VARCHAR(60) NOT NULL, 
    role VARCHAR(12) DEFAULT 'player' NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    consent_given_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_participants PRIMARY KEY (id), 
    CONSTRAINT fk_participants_session_id_game_sessions FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_participants_team_id_teams FOREIGN KEY(team_id, session_id) REFERENCES teams (id, session_id), 
    CONSTRAINT uq_participants_session_name UNIQUE (session_id, display_name), 
    CONSTRAINT uq_participants_token_hash UNIQUE (token_hash), 
    CONSTRAINT ck_participants_role_valid CHECK (role IN ('player', 'scrum_master')), 
    CONSTRAINT ck_participants_token_hash_sha256 CHECK (token_hash ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_participants_display_name_not_blank CHECK (length(trim(display_name)) >= 1)
);

CREATE INDEX ix_participants_team_id ON participants (team_id);

CREATE TABLE cards (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    team_id UUID NOT NULL, 
    scenario_card_id UUID NOT NULL, 
    stage_id UUID NOT NULL, 
    stage_state VARCHAR(11), 
    is_blocked BOOLEAN DEFAULT false NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_cards PRIMARY KEY (id), 
    CONSTRAINT fk_cards_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE, 
    CONSTRAINT fk_cards_scenario_card_id_scenario_cards FOREIGN KEY(scenario_card_id) REFERENCES scenario_cards (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_cards_stage_id_scenario_stages FOREIGN KEY(stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_cards_team_scenario_card UNIQUE (team_id, scenario_card_id), 
    CONSTRAINT uq_cards_id_team UNIQUE (id, team_id), 
    CONSTRAINT ck_cards_stage_state_valid CHECK (stage_state IN ('in_progress', 'ready'))
);

CREATE INDEX ix_cards_team_id_stage_id ON cards (team_id, stage_id);

CREATE INDEX ix_cards_scenario_card_id ON cards (scenario_card_id);

CREATE TABLE card_work (
    card_id UUID NOT NULL, 
    stage_id UUID NOT NULL, 
    squares_left SMALLINT NOT NULL, 
    CONSTRAINT pk_card_work PRIMARY KEY (card_id, stage_id), 
    CONSTRAINT fk_card_work_card_id_cards FOREIGN KEY(card_id) REFERENCES cards (id) ON DELETE CASCADE, 
    CONSTRAINT fk_card_work_stage_id_scenario_stages FOREIGN KEY(stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_card_work_squares_left_non_negative CHECK (squares_left >= 0)
);

CREATE TABLE game_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    session_id UUID NOT NULL, 
    scenario_event_id UUID, 
    day SMALLINT NOT NULL, 
    title VARCHAR(120) NOT NULL, 
    description TEXT NOT NULL, 
    source VARCHAR(8) NOT NULL, 
    status VARCHAR(9) DEFAULT 'proposed' NOT NULL, 
    confirmed_by UUID, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    applied_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_game_events PRIMARY KEY (id), 
    CONSTRAINT fk_game_events_session_id_game_sessions FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_game_events_scenario_event_id_scenario_events FOREIGN KEY(scenario_event_id) REFERENCES scenario_events (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_game_events_confirmed_by_facilitators FOREIGN KEY(confirmed_by) REFERENCES facilitators (id) ON DELETE SET NULL, 
    CONSTRAINT uq_game_events_session_scenario_event UNIQUE (session_id, scenario_event_id), 
    CONSTRAINT ck_game_events_source_valid CHECK (source IN ('template', 'ai', 'manual')), 
    CONSTRAINT ck_game_events_status_valid CHECK (status IN ('proposed', 'confirmed', 'applied', 'dismissed')), 
    CONSTRAINT ck_game_events_day_positive CHECK (day >= 1), 
    CONSTRAINT ck_game_events_confirmed_has_timestamp CHECK (status NOT IN ('confirmed', 'applied') OR confirmed_at IS NOT NULL), 
    CONSTRAINT ck_game_events_applied_has_timestamp CHECK (status <> 'applied' OR applied_at IS NOT NULL), 
    CONSTRAINT ck_game_events_template_event_has_origin CHECK (source <> 'template' OR scenario_event_id IS NOT NULL)
);

CREATE INDEX ix_game_events_session_id_day ON game_events (session_id, day);

CREATE TABLE survey_responses (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    participant_id UUID NOT NULL, 
    phase VARCHAR(4) NOT NULL, 
    confidence SMALLINT NOT NULL, 
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_survey_responses PRIMARY KEY (id), 
    CONSTRAINT fk_survey_responses_participant_id_participants FOREIGN KEY(participant_id) REFERENCES participants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_survey_responses_phase UNIQUE (participant_id, phase), 
    CONSTRAINT ck_survey_responses_phase_valid CHECK (phase IN ('pre', 'post')), 
    CONSTRAINT ck_survey_responses_confidence_range CHECK (confidence BETWEEN 1 AND 5)
);

CREATE TABLE ai_drafts (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    session_id UUID NOT NULL, 
    team_id UUID, 
    kind VARCHAR(14) NOT NULL, 
    prompt TEXT NOT NULL, 
    content TEXT NOT NULL, 
    model VARCHAR(64) NOT NULL, 
    status VARCHAR(8) DEFAULT 'draft' NOT NULL, 
    reviewed_by UUID, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_ai_drafts PRIMARY KEY (id), 
    CONSTRAINT fk_ai_drafts_session_id_game_sessions FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_ai_drafts_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE SET NULL, 
    CONSTRAINT fk_ai_drafts_reviewed_by_facilitators FOREIGN KEY(reviewed_by) REFERENCES facilitators (id) ON DELETE SET NULL, 
    CONSTRAINT ck_ai_drafts_kind_valid CHECK (kind IN ('event', 'retro_feedback')), 
    CONSTRAINT ck_ai_drafts_status_valid CHECK (status IN ('draft', 'approved', 'rejected')), 
    CONSTRAINT ck_ai_drafts_reviewed_has_reviewer CHECK (status = 'draft' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE INDEX ix_ai_drafts_session_id_kind ON ai_drafts (session_id, kind);

CREATE TABLE card_movements (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    team_id UUID NOT NULL, 
    card_id UUID NOT NULL, 
    day SMALLINT NOT NULL, 
    from_stage_id UUID, 
    from_state VARCHAR(11), 
    to_stage_id UUID NOT NULL, 
    to_state VARCHAR(11), 
    actor_participant_id UUID, 
    actor_facilitator_id UUID, 
    request_id UUID NOT NULL, 
    is_manual BOOLEAN DEFAULT false NOT NULL, 
    comment TEXT, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_card_movements PRIMARY KEY (id), 
    CONSTRAINT fk_card_movements_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE, 
    CONSTRAINT fk_card_movements_card_id_cards FOREIGN KEY(card_id, team_id) REFERENCES cards (id, team_id) ON DELETE CASCADE, 
    CONSTRAINT fk_card_movements_from_stage_id_scenario_stages FOREIGN KEY(from_stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_card_movements_to_stage_id_scenario_stages FOREIGN KEY(to_stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_card_movements_actor_participant_id_participants FOREIGN KEY(actor_participant_id) REFERENCES participants (id) ON DELETE SET NULL, 
    CONSTRAINT fk_card_movements_actor_facilitator_id_facilitators FOREIGN KEY(actor_facilitator_id) REFERENCES facilitators (id) ON DELETE SET NULL, 
    CONSTRAINT uq_card_movements_request UNIQUE (team_id, request_id), 
    CONSTRAINT ck_card_movements_from_state_valid CHECK (from_state IN ('in_progress', 'ready')), 
    CONSTRAINT ck_card_movements_to_state_valid CHECK (to_state IN ('in_progress', 'ready')), 
    CONSTRAINT ck_card_movements_day_positive CHECK (day >= 1), 
    CONSTRAINT ck_card_movements_single_actor CHECK (num_nonnulls(actor_participant_id, actor_facilitator_id) <= 1), 
    CONSTRAINT ck_card_movements_manual_needs_comment_and_facilitator CHECK (NOT is_manual OR (comment IS NOT NULL AND actor_facilitator_id IS NOT NULL))
);

CREATE INDEX ix_card_movements_card_id_day ON card_movements (card_id, day);

CREATE INDEX ix_card_movements_team_id_day ON card_movements (team_id, day);

CREATE TABLE dice_rolls (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    team_id UUID NOT NULL, 
    stage_id UUID NOT NULL, 
    day SMALLINT NOT NULL, 
    value SMALLINT NOT NULL, 
    rolled_by UUID, 
    request_id UUID NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_dice_rolls PRIMARY KEY (id), 
    CONSTRAINT fk_dice_rolls_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE, 
    CONSTRAINT fk_dice_rolls_stage_id_scenario_stages FOREIGN KEY(stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_dice_rolls_rolled_by_participants FOREIGN KEY(rolled_by) REFERENCES participants (id) ON DELETE SET NULL, 
    CONSTRAINT uq_dice_rolls_team_stage_day UNIQUE (team_id, stage_id, day), 
    CONSTRAINT uq_dice_rolls_request UNIQUE (team_id, request_id), 
    CONSTRAINT ck_dice_rolls_value_range CHECK (value BETWEEN 1 AND 6), 
    CONSTRAINT ck_dice_rolls_day_positive CHECK (day >= 1)
);

CREATE TABLE point_spends (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    team_id UUID NOT NULL, 
    card_id UUID NOT NULL, 
    day SMALLINT NOT NULL, 
    source_stage_id UUID NOT NULL, 
    target_stage_id UUID NOT NULL, 
    points_spent SMALLINT NOT NULL, 
    squares_crossed SMALLINT NOT NULL, 
    actor_participant_id UUID, 
    request_id UUID NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_point_spends PRIMARY KEY (id), 
    CONSTRAINT fk_point_spends_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE, 
    CONSTRAINT fk_point_spends_card_id_cards FOREIGN KEY(card_id, team_id) REFERENCES cards (id, team_id) ON DELETE CASCADE, 
    CONSTRAINT fk_point_spends_source_stage_id_scenario_stages FOREIGN KEY(source_stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_point_spends_target_stage_id_scenario_stages FOREIGN KEY(target_stage_id) REFERENCES scenario_stages (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_point_spends_actor_participant_id_participants FOREIGN KEY(actor_participant_id) REFERENCES participants (id) ON DELETE SET NULL, 
    CONSTRAINT uq_point_spends_request UNIQUE (team_id, request_id), 
    CONSTRAINT ck_point_spends_day_positive CHECK (day >= 1), 
    CONSTRAINT ck_point_spends_points_positive CHECK (points_spent >= 1), 
    CONSTRAINT ck_point_spends_half_value_rule CHECK (squares_crossed = CASE WHEN source_stage_id = target_stage_id THEN points_spent ELSE points_spent / 2 END)
);

CREATE INDEX ix_point_spends_card_id ON point_spends (card_id);

CREATE INDEX ix_point_spends_team_id_day ON point_spends (team_id, day);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

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
$$;

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END
$$;

CREATE FUNCTION apply_card_movement() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.from_stage_id IS NULL THEN
        -- A card entering the board directly (for example the emergency card). That can only be
        -- its first movement. The card is locked first, so a concurrent first movement is visible
        -- to the check below (each statement takes a fresh snapshot) once its lock is released.
        PERFORM FROM cards WHERE id = NEW.card_id FOR NO KEY UPDATE;
        IF EXISTS (SELECT FROM card_movements WHERE card_id = NEW.card_id AND id <> NEW.id) THEN
            RAISE EXCEPTION 'card % is already on the board: the movement must say where it starts',
                NEW.card_id
                USING ERRCODE = 'check_violation';
        END IF;
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
$$;

CREATE FUNCTION mask_email(address text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT left(split_part(address, '@', 1), 1) || '***@' || split_part(address, '@', 2)
$$;

CREATE TRIGGER card_movements_append_only BEFORE UPDATE OR DELETE ON card_movements FOR EACH ROW EXECUTE FUNCTION forbid_modification();

CREATE TRIGGER dice_rolls_append_only BEFORE UPDATE OR DELETE ON dice_rolls FOR EACH ROW EXECUTE FUNCTION forbid_modification();

CREATE TRIGGER point_spends_append_only BEFORE UPDATE OR DELETE ON point_spends FOR EACH ROW EXECUTE FUNCTION forbid_modification();

CREATE TRIGGER facilitators_set_updated_at BEFORE UPDATE ON facilitators FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER game_sessions_set_updated_at BEFORE UPDATE ON game_sessions FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER cards_set_updated_at BEFORE UPDATE ON cards FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER card_movements_apply AFTER INSERT ON card_movements FOR EACH ROW EXECUTE FUNCTION apply_card_movement();

CREATE VIEW facilitators_masked AS
SELECT id, display_name, mask_email(email) AS email_masked, is_active, created_at
  FROM facilitators;

CREATE VIEW card_flow AS
WITH moves AS (
    SELECT m.card_id,
           (array_agg(m.day ORDER BY m.id DESC) FILTER (
               WHERE (m.from_stage_id IS NULL OR fs.kind = 'backlog') AND ts.kind <> 'backlog'
           ))[1] AS last_pull_day,
           (array_agg(m.day ORDER BY m.id DESC) FILTER (
               WHERE ts.kind = 'done' AND fs.kind IS DISTINCT FROM 'done'
           ))[1] AS last_done_day
      FROM card_movements m
      LEFT JOIN scenario_stages fs ON fs.id = m.from_stage_id
      JOIN scenario_stages ts ON ts.id = m.to_stage_id
     GROUP BY m.card_id
),
flow AS (
    SELECT c.id AS card_id,
           c.team_id,
           c.scenario_card_id,
           CASE WHEN cs.kind <> 'backlog' THEN mv.last_pull_day END AS pulled_day,
           CASE WHEN cs.kind = 'done' THEN mv.last_done_day END AS done_day
      FROM cards c
      JOIN scenario_stages cs ON cs.id = c.stage_id
      LEFT JOIN moves mv ON mv.card_id = c.id
)
SELECT f.card_id,
       f.team_id,
       t.session_id,
       sc.number AS card_number,
       sc.title,
       sc.value,
       sc.is_emergency,
       f.pulled_day,
       f.done_day,
       CASE
           WHEN f.pulled_day IS NOT NULL AND f.done_day IS NOT NULL
           THEN f.done_day - f.pulled_day
                + CASE gs.lead_time_convention WHEN 'inclusive' THEN 1 ELSE 0 END
       END AS lead_time_days
  FROM flow f
  JOIN teams t ON t.id = f.team_id
  JOIN game_sessions gs ON gs.id = t.session_id
  JOIN scenario_cards sc ON sc.id = f.scenario_card_id;

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
  JOIN scenario_stages st ON st.id = latest.to_stage_id;

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
 GROUP BY t.id, t.session_id, t.name;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

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
$$;

GRANT app_read TO app_write;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agilesim_app') THEN
        GRANT app_write TO agilesim_app;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO app_read, app_write;

GRANT USAGE, CREATE ON SCHEMA public TO app_admin;

GRANT SELECT ON scenarios, scenario_stages, scenario_cards, scenario_card_work, scenario_events, game_sessions, session_stage_limits, teams, participants, cards, card_work, game_events, survey_responses, ai_drafts, card_movements, dice_rolls, point_spends, facilitators_masked, card_flow, card_daily_state, team_results TO app_read;

GRANT SELECT (id, display_name, is_active, created_at, updated_at) ON facilitators TO app_read;

GRANT INSERT, UPDATE, DELETE ON game_sessions, session_stage_limits, teams, participants, cards, card_work, game_events, survey_responses, ai_drafts TO app_write;

GRANT INSERT ON card_movements, dice_rolls, point_spends TO app_write;

GRANT SELECT, INSERT, UPDATE ON facilitators TO app_write;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_admin;

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

INSERT INTO scenarios (code, version, kind, name)
VALUES ('startup-flow', 1, 'kanban', 'Startup Flow (Kanban)');

INSERT INTO scenario_stages (scenario_id, code, name, kind, position, default_wip_limit)
SELECT s.id, v.code, v.name, v.kind, v.position, v.wip_limit
  FROM scenarios s,
       (VALUES ('backlog', 'Backlog', 'backlog', 0, NULL),
               ('analysis', 'Analysis', 'work', 1, 2),
               ('development', 'Development', 'work', 2, 3),
               ('testing', 'Testing', 'work', 3, 2),
               ('done', 'Done', 'done', 4, NULL)) AS v(code, name, kind, position, wip_limit)
 WHERE s.code = 'startup-flow' AND s.version = 1;

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
 WHERE s.code = 'startup-flow' AND s.version = 1;

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

COMMIT;

