"""Generate ``demo_data.sql``: a played Startup Flow session for demonstrations.

The script plays the eight days of the scenario for two teams with a seeded random number
generator and writes plain SQL, so the result is the same on every run and can be reviewed in
Git. It needs only the Python standard library:

    python backend/scripts/generate_demo_data.py > db/demo/demo_data.sql

Rules it follows (scenario "Startup Flow"):

* day 1 pulls the five most valuable cards, day 2 the cards of the marketing push;
* three dice per day (Analysis, Development, Testing); points go to the cards of the stage,
  left-over points help another stage at half value, rounded down;
* days 1-4 have no WIP limits, days 5-8 use Analysis 2, Development 3, Testing 2;
* day 3 blocks the most valuable Development card, 3 full Development points remove the block;
* day 6: team Beta spends its Development roll on refactoring and gets +1 on later rolls;
* day 7: the emergency card enters the board outside the limits and takes all dice first.

The backlog cards are illustrative: only the values of cards 102, 104, 105, 106, 115 and 116
come from the analysis document; the other values, all titles and all work squares are
placeholders until the course backlog is loaded.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

SEED = 2026
NAMESPACE = uuid.UUID("6f1d3c0a-5b7e-4c1a-9a57-a611e51dd000")
START = datetime(2026, 11, 10, 10, 15, tzinfo=UTC)
DAY_LENGTH = timedelta(minutes=7)
DAYS = 8
WORK_STAGES = ("analysis", "development", "testing")
NEXT_STAGE = {"analysis": "development", "development": "testing", "testing": "done"}
WIP_LIMITS = {"analysis": 2, "development": 3, "testing": 2}
EMERGENCY_NUMBER = 999
FACILITATOR_EMAIL = "demo.facilitator@example.com"
# Format-valid Argon2id string that is not the hash of any password: the demo account cannot
# sign in.
DEMO_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$ZGVtb3NhbHRkZW1v$ZGVtb2RlbW9kZW1vZGVtb2RlbW8"

# number: (title, value)
BACKLOG: dict[int, tuple[str, int]] = {
    101: ("Landing page copy", 30),
    102: ("Founder profile page", 40),
    103: ("E-mail confirmation", 50),
    104: ("Pitch deck upload", 100),
    105: ("Mentor search", 80),
    106: ("Investor dashboard", 90),
    107: ("Demo day schedule", 60),
    108: ("Application form", 70),
    109: ("FAQ page", 20),
    110: ("Team invitations", 45),
    111: ("Feedback form", 55),
    112: ("Newsletter sign-up", 35),
    113: ("Dark theme", 25),
    114: ("Calendar export", 65),
    115: ("Payment of the participation fee", 110),
    116: ("Mentor booking", 85),
    117: ("Progress report", 75),
    118: ("Footer links", 10),
}
EMERGENCY = ("Emergency: the registration form is down", 0)


def uid(*parts: object) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(str(part) for part in parts)))


def quote(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return "'" + value.strftime("%Y-%m-%d %H:%M:%S+00") + "'"
    return "'" + str(value).replace("'", "''") + "'"


def row(*values: object) -> str:
    return "(" + ", ".join(quote(value) for value in values) + ")"


@dataclass
class Card:
    number: int
    value: int
    work: dict[str, int]
    left: dict[str, int] = field(default_factory=dict)
    stage: str = "backlog"
    state: str | None = None
    blocked: bool = False
    on_board: bool = False

    @property
    def is_emergency(self) -> bool:
        return self.number == EMERGENCY_NUMBER


class Team:
    """Plays the game for one team and collects the rows of the three logs."""

    def __init__(self, name: str, members: list[str], work: dict[int, dict[str, int]]) -> None:
        self.name = name
        self.id = uid("team", name)
        self.members = members
        self.cards = {
            number: Card(number, value, dict(work[number]), dict(work[number]))
            for number, (_, value) in BACKLOG.items()
        }
        self.cards[EMERGENCY_NUMBER] = Card(
            EMERGENCY_NUMBER, 0, dict(work[EMERGENCY_NUMBER]), dict(work[EMERGENCY_NUMBER])
        )
        self.movements: list[list[str]] = [[]]  # batches of VALUES rows
        self.rolls: list[str] = []
        self.spends: list[str] = []
        self.refactored = False
        self.corrected = False
        self.day = 0
        self.tick = 0
        self.rng = random.Random(f"{SEED}/{name}")

    # ------------------------------------------------------------------ helpers

    def card_id(self, card: Card) -> str:
        return uid("card", self.name, card.number)

    def now(self) -> datetime:
        self.tick += 1
        return START + DAY_LENGTH * (self.day - 1) + timedelta(seconds=5 * self.tick)

    def member(self) -> str:
        return uid("participant", self.name, self.rng.choice(self.members))

    def in_stage(self, stage: str, state: str | None = "in_progress") -> list[Card]:
        found = [
            card
            for card in self.cards.values()
            if card.stage == stage and (state is None or card.state == state)
        ]
        return sorted(found, key=lambda card: (not card.is_emergency, -card.value, card.number))

    def has_room(self, stage: str) -> bool:
        if stage == "done" or self.day <= 4:
            return True
        used = sum(1 for card in self.in_stage(stage, None) if not card.is_emergency)
        return used < WIP_LIMITS[stage]

    def move(
        self,
        card: Card,
        stage: str,
        state: str | None,
        *,
        by_facilitator: bool = False,
        comment: str | None = None,
    ) -> None:
        entering = not card.on_board and card.is_emergency
        if entering:
            self.movements.append([])  # the first movement of a card must be alone (trigger)
        self.movements[-1].append(
            row(
                self.id,
                self.card_id(card),
                self.day,
                None if entering else card.stage,
                None if entering else card.state,
                stage,
                state,
                None if by_facilitator else self.member(),
                uid("facilitator") if by_facilitator else None,
                uid("move", self.name, len(self.spends), sum(map(len, self.movements))),
                comment is not None,
                comment,
                self.now(),
            )
        )
        if entering:
            self.movements.append([])
        card.stage, card.state, card.on_board = stage, state, True

    def advance(self, card: Card) -> None:
        """Move a finished card to the next column if that column has room."""
        target = NEXT_STAGE[card.stage]
        if self.has_room(target) or card.is_emergency:
            self.move(card, target, None if target == "done" else "in_progress")

    def spend(self, card: Card, source: str, points: int) -> int:
        """Spend ``points`` of the ``source`` roll on ``card``; return the points used."""
        target = card.stage
        if source == target:
            used = min(points, card.left[target])
            crossed = used
        else:
            used = min(points, 2 * card.left[target])
            crossed = used // 2
        if used < 1 or (crossed == 0 and source != target and used < 2):
            return 0
        card.left[target] -= crossed
        self.spends.append(
            row(
                self.id,
                self.card_id(card),
                self.day,
                source,
                target,
                used,
                crossed,
                self.member(),
                uid("spend", self.name, len(self.spends)),
                self.now(),
            )
        )
        if card.left[target] == 0:
            if target == "testing":
                self.advance(card)
            else:
                self.move(card, target, "ready")
                self.advance(card)
        return used

    # ------------------------------------------------------------------ one day

    def replenish(self) -> None:
        backlog = [card for card in self.in_stage("backlog", None) if not card.is_emergency]
        if self.day == 1:
            pulled = backlog[:5]
        elif self.day == 2:
            pulled = [card for card in backlog if card.number in (106, 107, 108)]
        elif self.day <= 4:
            pulled = backlog[:1]
        else:
            pulled = backlog[
                : max(0, WIP_LIMITS["analysis"] - len(self.in_stage("analysis", None)))
            ]
        for card in pulled:
            self.move(card, "analysis", "in_progress", by_facilitator=True)

    def play_day(self, day: int) -> None:
        self.day, self.tick = day, 0
        # Cards that waited in "ready" move on first (pull from the right side of the board).
        for stage in ("development", "analysis"):
            for card in self.in_stage(stage, "ready"):
                self.advance(card)
        self.replenish()

        pool: dict[str, int] = {}
        for stage in WORK_STAGES:
            value = self.rng.randint(1, 6)
            self.rolls.append(
                row(
                    self.id,
                    stage,
                    day,
                    value,
                    self.member(),
                    uid("roll", self.name, stage, day),
                    self.now(),
                )
            )
            pool[stage] = value
        if self.refactored:
            pool["development"] = min(6, pool["development"] + 1)

        if day == 6 and self.name == "Beta":
            # Technical debt: the whole Development roll goes to refactoring.
            pool["development"] = 0
            self.refactored = True

        if day == 7:
            self.move(
                self.cards[EMERGENCY_NUMBER], "development", "in_progress", by_facilitator=True
            )
        emergency = self.cards[EMERGENCY_NUMBER]
        for stage in ("analysis", "development", "testing"):
            # All dice go to the emergency card while it is open.
            if emergency.on_board and emergency.stage != "done" and pool[stage]:
                pool[stage] -= self.spend(emergency, stage, pool[stage])

        blocked = next((card for card in self.cards.values() if card.blocked), None)
        if blocked and pool["development"] >= 3:
            pool["development"] -= 3  # three full Development points remove the block
            blocked.blocked = False

        for stage in ("testing", "development", "analysis"):
            for card in self.in_stage(stage):
                if pool[stage] and not card.blocked:
                    pool[stage] -= self.spend(card, stage, pool[stage])
            if pool[stage] >= 2:  # help the bottleneck at half value
                target = "development" if stage == "testing" else "testing"
                for card in self.in_stage(target):
                    if pool[stage] >= 2 and not card.blocked:
                        pool[stage] -= self.spend(card, stage, pool[stage])

        if day == 3:
            top = next(iter(self.in_stage("development")), None)
            if top:
                top.blocked = True  # integration error

        if self.name == "Beta" and not self.corrected and day < DAYS:
            done_today = [
                card
                for card in self.in_stage("done", None)
                if not card.is_emergency and card.left["testing"] == 0
            ]
            if done_today:
                # A facilitator's correction (US-06): the card goes back and is finished later.
                card = done_today[0]
                card.left["testing"] = 1
                self.move(
                    card,
                    "testing",
                    "in_progress",
                    by_facilitator=True,
                    comment="Moved to Done by mistake: one Testing square was still open",
                )
                self.corrected = True


def build() -> str:
    rng = random.Random(SEED)
    work = {
        number: {
            "analysis": rng.randint(1, 3),
            "development": rng.randint(2, 5),
            "testing": rng.randint(1, 3),
        }
        for number in BACKLOG
    }
    work[EMERGENCY_NUMBER] = {"development": 3, "testing": 2}

    teams = [
        Team("Alpha", ["Anna", "Boris", "Clara"], work),
        Team("Beta", ["Dmitri", "Eva", "Felix"], work),
    ]
    for team in teams:
        for day in range(1, DAYS + 1):
            team.play_day(day)

    facilitator = uid("facilitator")
    played, lobby = uid("session", "DEMO01"), uid("session", "DEMO02")
    finished = START + DAY_LENGTH * DAYS
    out: list[str] = []
    emit = out.append

    emit("-- Demo data for AgileSim: a finished Startup Flow session with two teams and a")
    emit("-- second session that is still in the lobby.")
    emit("-- GENERATED by backend/scripts/generate_demo_data.py - do not edit by hand.")
    emit("-- Run as the schema owner after the migrations. Running it again replaces the demo")
    emit("-- sessions; it does not touch other sessions.")
    emit("BEGIN;")
    emit("")
    emit("DELETE FROM game_sessions WHERE join_code IN ('DEMO01', 'DEMO02');")
    emit(f"DELETE FROM facilitators WHERE email = {quote(FACILITATOR_EMAIL)};")
    emit("")
    emit("CREATE TEMPORARY TABLE demo_scenario ON COMMIT DROP AS")
    emit("SELECT id FROM scenarios WHERE code = 'startup-flow' AND version = 1;")
    emit("CREATE TEMPORARY TABLE demo_stage ON COMMIT DROP AS")
    emit("SELECT st.code, st.id")
    emit("  FROM scenario_stages st JOIN demo_scenario s ON s.id = st.scenario_id;")
    emit("")

    emit("-- Backlog cards (illustrative values, see the generator) and the emergency card.")
    emit("INSERT INTO scenario_cards (scenario_id, number, title, value, is_emergency)")
    emit("SELECT s.id, v.number, v.title, v.value, v.is_emergency")
    emit("  FROM demo_scenario s,")
    emit("       (VALUES")
    card_rows = [row(number, title, value, False) for number, (title, value) in BACKLOG.items()]
    card_rows.append(row(EMERGENCY_NUMBER, EMERGENCY[0], EMERGENCY[1], True))
    emit(",\n".join("          " + line for line in card_rows))
    emit("       ) AS v(number, title, value, is_emergency)")
    emit("ON CONFLICT ON CONSTRAINT uq_scenario_cards_number DO NOTHING;")
    emit("")
    emit("INSERT INTO scenario_card_work (scenario_card_id, stage_id, scenario_id, squares)")
    emit("SELECT sc.id, st.id, sc.scenario_id, v.squares")
    emit("  FROM (VALUES")
    emit(
        ",\n".join(
            "          " + row(number, stage, squares)
            for number, stages in work.items()
            for stage, squares in stages.items()
        )
    )
    emit("       ) AS v(number, stage, squares)")
    emit("  JOIN demo_scenario s ON true")
    emit("  JOIN scenario_cards sc ON sc.scenario_id = s.id AND sc.number = v.number")
    emit("  JOIN demo_stage st ON st.code = v.stage")
    emit("ON CONFLICT DO NOTHING;")
    emit("")

    emit("-- Accounts and sessions.")
    emit("INSERT INTO facilitators (id, email, display_name, password_hash) VALUES")
    emit("  " + row(facilitator, FACILITATOR_EMAIL, "Demo Facilitator", DEMO_PASSWORD_HASH) + ";")
    emit("")
    emit("INSERT INTO game_sessions (id, facilitator_id, scenario_id, name, join_code, status,")
    emit("                           current_day, wip_limits_enabled, started_at, finished_at)")
    emit("SELECT CAST(v.id AS uuid), CAST(v.facilitator AS uuid), s.id, v.name, v.join_code,")
    emit("       v.status, v.current_day, v.wip, CAST(v.started_at AS timestamptz),")
    emit("       CAST(v.finished_at AS timestamptz)")
    emit("  FROM demo_scenario s,")
    emit("       (VALUES")
    emit(
        "          "
        + row(
            played,
            facilitator,
            "Demo: group 1 (finished)",
            "DEMO01",
            "finished",
            DAYS,
            True,
            START,
            finished,
        )
        + ","
    )
    emit(
        "          "
        + row(lobby, facilitator, "Demo: group 2 (lobby)", "DEMO02", "lobby", 0, False, None, None)
    )
    emit("       ) AS v(id, facilitator, name, join_code, status, current_day, wip, started_at,")
    emit("              finished_at);")
    emit("")
    emit("INSERT INTO session_stage_limits (session_id, stage_id, wip_limit)")
    emit(f"SELECT CAST({quote(played)} AS uuid), st.id, v.wip_limit")
    emit(
        "  FROM (VALUES "
        + ", ".join(row(stage, limit) for stage, limit in WIP_LIMITS.items())
        + ") AS v(stage, wip_limit)"
    )
    emit("  JOIN demo_stage st ON st.code = v.stage;")
    emit("")
    emit("INSERT INTO teams (id, session_id, name) VALUES")
    team_rows = [row(team.id, played, team.name) for team in teams]
    team_rows.append(row(uid("team", "Gamma"), lobby, "Gamma"))
    emit(",\n".join("  " + line for line in team_rows) + ";")
    emit("")

    joined = START - timedelta(minutes=10)
    participants: list[tuple[str, str, str | None, str, str]] = [
        (
            uid("participant", team.name, name),
            played,
            team.id,
            name,
            "scrum_master" if index == 0 else "player",
        )
        for team in teams
        for index, name in enumerate(team.members)
    ]
    participants.append(
        (uid("participant", "Gamma", "Greta"), lobby, uid("team", "Gamma"), "Greta", "player")
    )
    # Two players of the lobby session have not chosen a team yet.
    participants.append((uid("participant", "-", "Hugo"), lobby, None, "Hugo", "player"))
    participants.append((uid("participant", "-", "Irina"), lobby, None, "Irina", "player"))
    emit("-- Participants: only the SHA-256 hash of the join token is stored.")
    emit("INSERT INTO participants (id, session_id, team_id, display_name, role, token_hash,")
    emit("                          consent_given_at, joined_at) VALUES")
    emit(
        ",\n".join(
            "  "
            + row(
                pid,
                session,
                team_id,
                name,
                role,
                hashlib.sha256(f"demo-token/{pid}".encode()).hexdigest(),
                joined,
                joined,
            )
            for pid, session, team_id, name, role in participants
        )
        + ";"
    )
    emit("")

    emit("-- Survey before and after the game (Felix did not answer the second one).")
    emit("INSERT INTO survey_responses (participant_id, phase, confidence, submitted_at) VALUES")
    survey_rng = random.Random(f"{SEED}/survey")
    survey_rows = []
    for pid, session, _team, name, _role in participants:
        before = survey_rng.randint(1, 3)
        if session == played:
            survey_rows.append(row(pid, "pre", before, joined + timedelta(minutes=3)))
            if name != "Felix":
                survey_rows.append(
                    row(
                        pid,
                        "post",
                        min(5, before + survey_rng.randint(1, 2)),
                        finished + timedelta(minutes=20),
                    )
                )
        elif name == "Greta":
            survey_rows.append(row(pid, "pre", before, joined + timedelta(minutes=3)))
    emit(",\n".join("  " + line for line in survey_rows) + ";")
    emit("")

    emit("-- Every team gets its own copy of every card; all start in the backlog.")
    emit("INSERT INTO cards (id, team_id, scenario_card_id, stage_id, is_blocked)")
    emit("SELECT CAST(v.id AS uuid), CAST(v.team AS uuid), sc.id, st.id, v.is_blocked")
    emit("  FROM (VALUES")
    emit(
        ",\n".join(
            "          " + row(team.card_id(card), team.id, card.number, card.blocked)
            for team in teams
            for card in team.cards.values()
        )
    )
    emit("       ) AS v(id, team, number, is_blocked)")
    emit("  JOIN demo_scenario s ON true")
    emit("  JOIN scenario_cards sc ON sc.scenario_id = s.id AND sc.number = v.number")
    emit("  JOIN demo_stage st ON st.code = 'backlog';")
    emit("")
    emit("-- Work squares still open at the end of the game.")
    emit("INSERT INTO card_work (card_id, stage_id, squares_left)")
    emit("SELECT CAST(v.card AS uuid), st.id, v.squares_left")
    emit("  FROM (VALUES")
    emit(
        ",\n".join(
            "          " + row(team.card_id(card), stage, left)
            for team in teams
            for card in team.cards.values()
            for stage, left in card.left.items()
        )
    )
    emit("       ) AS v(card, stage, squares_left)")
    emit("  JOIN demo_stage st ON st.code = v.stage;")
    emit("")

    emit("-- Dice rolls: one per team, stage and day.")
    emit(
        "INSERT INTO dice_rolls (team_id, stage_id, day, value, rolled_by, request_id, occurred_at)"
    )
    emit("SELECT CAST(v.team AS uuid), st.id, v.day, v.value, CAST(v.rolled_by AS uuid),")
    emit("       CAST(v.request AS uuid), CAST(v.at AS timestamptz)")
    emit("  FROM (VALUES")
    emit(",\n".join("          " + line for team in teams for line in team.rolls))
    emit("       ) AS v(team, stage, day, value, rolled_by, request, at)")
    emit("  JOIN demo_stage st ON st.code = v.stage")
    emit(" ORDER BY v.at;")
    emit("")

    emit("-- Card movements. The trigger apply_card_movement moves the cards, so the rows are")
    emit("-- inserted in the order of the game.")
    for team in teams:
        for batch in team.movements:
            if not batch:
                continue
            emit("INSERT INTO card_movements (team_id, card_id, day, from_stage_id, from_state,")
            emit("                            to_stage_id, to_state, actor_participant_id,")
            emit(
                "                            actor_facilitator_id, request_id, is_manual, comment,"
            )
            emit("                            occurred_at)")
            emit("SELECT CAST(v.team AS uuid), CAST(v.card AS uuid), v.day, fs.id,")
            emit("       CAST(v.from_state AS varchar), ts.id, CAST(v.to_state AS varchar),")
            emit("       CAST(v.participant AS uuid), CAST(v.facilitator AS uuid),")
            emit("       CAST(v.request AS uuid), v.is_manual, CAST(v.comment AS text),")
            emit("       CAST(v.at AS timestamptz)")
            emit("  FROM (VALUES")
            emit(",\n".join("          " + line for line in batch))
            emit("       ) AS v(team, card, day, from_stage, from_state, to_stage, to_state,")
            emit("              participant, facilitator, request, is_manual, comment, at)")
            emit("  LEFT JOIN demo_stage fs ON fs.code = v.from_stage")
            emit("  JOIN demo_stage ts ON ts.code = v.to_stage")
            emit(" ORDER BY v.at;")
            emit("")

    emit("-- Points spent on cards; help from another stage counts half, rounded down.")
    emit("INSERT INTO point_spends (team_id, card_id, day, source_stage_id, target_stage_id,")
    emit("                          points_spent, squares_crossed, actor_participant_id,")
    emit("                          request_id, occurred_at)")
    emit("SELECT CAST(v.team AS uuid), CAST(v.card AS uuid), v.day, ss.id, ts.id, v.points,")
    emit("       v.crossed, CAST(v.participant AS uuid), CAST(v.request AS uuid),")
    emit("       CAST(v.at AS timestamptz)")
    emit("  FROM (VALUES")
    emit(",\n".join("          " + line for team in teams for line in team.spends))
    emit(
        "       ) AS v(team, card, day, source, target, points, crossed, participant, request, at)"
    )
    emit("  JOIN demo_stage ss ON ss.code = v.source")
    emit("  JOIN demo_stage ts ON ts.code = v.target")
    emit(" ORDER BY v.at;")
    emit("")

    emit("-- Events of the played session: the five scenario events were applied, an AI proposal")
    emit("-- was dismissed by the facilitator.")
    emit("INSERT INTO game_events (session_id, scenario_event_id, day, title, description, source,")
    emit("                         status, confirmed_by, confirmed_at, applied_at)")
    emit(f"SELECT CAST({quote(played)} AS uuid), e.id, e.day, e.title, e.description, 'template',")
    emit(f"       'applied', CAST({quote(facilitator)} AS uuid),")
    emit(f"       CAST({quote(START)} AS timestamptz) + (e.day - 1) * interval '7 minutes',")
    emit(f"       CAST({quote(START)} AS timestamptz) + (e.day - 1) * interval '7 minutes'")
    emit("  FROM scenario_events e JOIN demo_scenario s ON s.id = e.scenario_id;")
    emit("INSERT INTO game_events (session_id, day, title, description, source, status) VALUES")
    emit(
        "  "
        + row(
            played,
            5,
            "Key tester is ill",
            "The Testing die counts half today. Proposed by the AI assistant, "
            "dismissed by the facilitator.",
            "ai",
            "dismissed",
        )
        + ";"
    )
    emit("")
    emit("-- AI drafts: nothing reaches the players before a facilitator approves it.")
    emit("INSERT INTO ai_drafts (session_id, team_id, kind, prompt, content, model, status,")
    emit("                       reviewed_by, reviewed_at) VALUES")
    review = finished + timedelta(minutes=5)
    emit(
        ",\n".join(
            "  " + line
            for line in (
                row(
                    played,
                    None,
                    "event",
                    "Propose an event for day 5 of Startup Flow.",
                    "Key tester is ill: the Testing die counts half today.",
                    "demo-model",
                    "rejected",
                    facilitator,
                    START + DAY_LENGTH * 4,
                ),
                row(
                    played,
                    teams[0].id,
                    "retro_feedback",
                    "Summarise the flow of team Alpha.",
                    "Cards waited longest before Testing. Limiting work in progress shortened the "
                    "queue in round 2.",
                    "demo-model",
                    "approved",
                    facilitator,
                    review,
                ),
                row(
                    played,
                    teams[1].id,
                    "retro_feedback",
                    "Summarise the flow of team Beta.",
                    "Refactoring on day 6 cost one Development roll and paid back on days 7 and 8.",
                    "demo-model",
                    "draft",
                    None,
                    None,
                ),
            )
        )
        + ";"
    )
    emit("")
    emit("COMMIT;")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(build(), end="")
