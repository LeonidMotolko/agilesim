import { useCallback, useState, type FormEvent } from "react";

import { BoardView } from "../components/BoardView";
import { DayStrip } from "../components/DayStrip";
import { DieTray } from "../components/Dice";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { useToast } from "../components/Toasts";
import { POLL_MS, WORK_STAGES, stageLabel } from "../constants";
import { useAction } from "../hooks/useAction";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import { useAuth } from "../state/AuthContext";
import type { Board, Card, SpendResult, StageCode, WorkStage } from "../types/api";
import { describeError, newRequestId } from "../utils/errors";

export function PlayPage() {
  const { auth } = useAuth();
  const participant = auth?.participant ?? null;
  if (participant === null || participant.team_id === null) {
    return (
      <p className="banner banner-error" role="alert">
        You are not in a team yet. Join a game and pick a team first.
      </p>
    );
  }
  return (
    <TeamPlay
      teamId={participant.team_id}
      sessionId={participant.session_id}
      playerName={participant.display_name}
      rejoinToken={auth?.rejoinToken ?? null}
    />
  );
}

interface TeamPlayProps {
  teamId: string;
  sessionId: string;
  playerName: string;
  rejoinToken: string | null;
}

function TeamPlay({ teamId, sessionId, playerName, rejoinToken }: TeamPlayProps) {
  const loadBoard = useCallback((signal: AbortSignal) => api.board(teamId, signal), [teamId]);
  const loadEvents = useCallback(
    (signal: AbortSignal) => api.listEvents(sessionId, signal),
    [sessionId],
  );
  const { notify } = useToast();
  const board = useAsync(loadBoard, { pollMs: POLL_MS });
  const events = useAsync(loadEvents, { pollMs: 5000 });
  const loadSession = useCallback(
    (signal: AbortSignal) => api.getSession(sessionId, signal),
    [sessionId],
  );
  const session = useAsync(loadSession, { pollMs: 5000 });
  const action = useAction((caught) => notify(describeError(caught), "error"));
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Runs one action and refetches the board before the buttons come back, so nobody can press
  // "Move" again on a card that has already moved. Resolves to false when the action failed.
  const act = async (work: () => Promise<string>): Promise<boolean> => {
    const message = await action.run(async () => {
      try {
        return await work();
      } finally {
        await board.reload();
      }
    });
    if (message === undefined) {
      return false;
    }
    notify(message);
    return true;
  };

  const data = board.data;
  const finished = session.data?.status === "finished";
  if (data === null) {
    return board.error !== null ? (
      <ErrorBanner error={board.error} />
    ) : (
      <LoadingState label="Loading your board…" />
    );
  }

  const todaysEvents = (events.data ?? []).filter(
    (event) => event.status === "applied" && event.day === data.day,
  );

  const handleMove = (card: Card, target: string) => {
    if (finished) {
      return;
    }
    void act(async () => {
      await api.moveCard(teamId, card.id, {
        to_stage: target as StageCode,
        request_id: newRequestId(),
      });
      return `ID-${card.number} moved to ${stageLabel(target)}`;
    });
  };

  const handleRoll = (stage: WorkStage): Promise<boolean> =>
    act(async () => {
      const roll = await api.rollDie(teamId, stage);
      return `${stageLabel(stage)} die: ${roll.value}`;
    });

  return (
    <div className="play">
      <aside className="desk" aria-label="Your desk">
        <header>
          <h1>Your board</h1>
          <p className="muted">Playing as {playerName}</p>
        </header>
        <DayStrip day={data.day} note={data.wip_limits_enabled ? "WIP limits on" : undefined} />

        {finished ? (
          <p className="today-event" role="status">
            <strong>The game is over.</strong> Your facilitator will show the results.
          </p>
        ) : null}

        {todaysEvents.map((event) => (
          <p key={event.id} className="today-event" role="status">
            <strong>{event.title}.</strong> {event.description}
          </p>
        ))}

        <section className="panel" aria-label="Dice">
          <h2>Dice</h2>
          <ul className="dice-row">
            {WORK_STAGES.map((stage) => (
              <DieTray
                key={stage}
                stage={stage}
                die={data.dice.find((item) => item.stage === stage)}
                disabled={action.busy || data.day === 0 || finished}
                onRoll={handleRoll}
              />
            ))}
          </ul>
        </section>

        <SpendPanel
          board={data}
          selectedId={selectedId}
          busy={action.busy}
          finished={finished}
          onSpend={(card, source, points) =>
            void act(async () => {
              const result = await api.spend(teamId, {
                card_id: card.id,
                source_stage: source,
                points,
                request_id: newRequestId(),
              });
              return describeSpend(card, result);
            })
          }
        />

        {rejoinToken !== null ? (
          <details className="rejoin">
            <summary>My rejoin code</summary>
            <p>
              Keep this code to return after closing the page: <code>{rejoinToken}</code>
            </p>
          </details>
        ) : null}
      </aside>

      <section className="board-area" aria-label="Team board">
        <BoardView
          board={data}
          onMove={finished ? undefined : handleMove}
          onSelect={finished ? undefined : (card) => setSelectedId(card.id)}
          selectedCardId={selectedId}
          busy={action.busy}
        />
      </section>
    </div>
  );
}

function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** What the toast says after points were spent; it names the unblocking, which has no squares. */
export function describeSpend(card: Card, result: SpendResult): string {
  const left = `${pluralize(result.points_left, "point")} left`;
  if (card.is_blocked && !result.card.is_blocked) {
    return `ID-${card.number} is unblocked; ${left}`;
  }
  if (card.is_blocked) {
    return `Points went to unblocking ID-${card.number}; ${left}`;
  }
  if (result.squares_crossed > 0) {
    return `Crossed out ${pluralize(result.squares_crossed, "square")}; ${left}`;
  }
  return `Points used; ${left}`;
}

export function SpendPanel({
  board,
  selectedId,
  busy,
  finished = false,
  onSpend,
}: {
  board: Board;
  selectedId: string | null;
  busy: boolean;
  finished?: boolean;
  onSpend: (card: Card, source: WorkStage, points: number) => void;
}) {
  const [source, setSource] = useState<WorkStage | "">("");
  const [points, setPoints] = useState(1);
  const card = board.cards.find((item) => item.id === selectedId);
  const withPoints = board.dice.filter((die) => die.points_left > 0);
  const chosen = withPoints.find((die) => die.stage === source) ?? withPoints[0];
  const available = chosen?.points_left ?? 1;
  const amount = Math.min(Math.max(points, 1), available);
  const workable =
    !finished &&
    card !== undefined &&
    WORK_STAGES.some((stage) => stage === card.stage) &&
    chosen !== undefined;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (card !== undefined && chosen !== undefined && workable) {
      onSpend(card, chosen.stage as WorkStage, amount);
    }
  };

  let hint = "";
  if (finished) {
    hint = "The game is over, so points can no longer be spent.";
  } else if (card === undefined) {
    hint = "Press “Work on it” on a card in Analysis, Development or Testing.";
  } else if (!WORK_STAGES.some((stage) => stage === card.stage)) {
    hint = "This card is not in a work stage. Pick another one.";
  } else if (withPoints.length === 0) {
    hint = "Roll a die first, or all of today’s points are used.";
  } else if (chosen !== undefined && card.stage !== chosen.stage) {
    hint = "Help from another stage counts half, rounded down.";
  }

  return (
    <section className="panel spend" aria-label="Spend points">
      <h2>Spend points</h2>
      <p className="spend-target">
        {card !== undefined ? (
          <>
            <strong>ID-{card.number}</strong> {card.title}
          </>
        ) : (
          <span className="muted">No card chosen</span>
        )}
      </p>
      <form onSubmit={handleSubmit}>
        <div className="source-group" role="radiogroup" aria-label="Spend from die">
          {WORK_STAGES.map((stage) => {
            const left = board.dice.find((die) => die.stage === stage)?.points_left ?? 0;
            const active = chosen?.stage === stage;
            return (
              <button
                key={stage}
                type="button"
                role="radio"
                aria-checked={active}
                aria-label={`${stageLabel(stage)}, ${left} points left`}
                disabled={left === 0}
                className={`source stage-${stage}${active ? " active" : ""}`}
                onClick={() => setSource(stage)}
              >
                <span>{stageLabel(stage)}</span>
                <strong>{left}</strong>
              </button>
            );
          })}
        </div>
        <div className="stepper">
          <button
            type="button"
            className="secondary step"
            aria-label="Fewer points"
            disabled={amount <= 1}
            onClick={() => setPoints(amount - 1)}
          >
            −
          </button>
          <output aria-label="Points to spend" aria-live="polite">
            {amount}
          </output>
          <button
            type="button"
            className="secondary step"
            aria-label="More points"
            disabled={amount >= available}
            onClick={() => setPoints(amount + 1)}
          >
            +
          </button>
          <button type="submit" className="spend-go" disabled={busy || !workable}>
            Spend
          </button>
        </div>
      </form>
      <p className="hint">{hint}</p>
    </section>
  );
}
