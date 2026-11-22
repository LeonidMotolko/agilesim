import { useCallback, useState, type FormEvent } from "react";

import { BoardView } from "../components/BoardView";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { POLL_MS, WORK_STAGES, stageLabel } from "../constants";
import { useAction } from "../hooks/useAction";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import { useAuth } from "../state/AuthContext";
import type { Board, Card, StageCode, WorkStage } from "../types/api";
import { newRequestId } from "../utils/errors";

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
  const board = useAsync(loadBoard, { pollMs: POLL_MS });
  const events = useAsync(loadEvents, { pollMs: 5000 });
  const action = useAction();
  const [notice, setNotice] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const act = async (work: () => Promise<string | void>) => {
    setNotice("");
    const message = await action.run(work);
    if (typeof message === "string") {
      setNotice(message);
    }
    board.reload();
  };

  const data = board.data;
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
    void act(async () => {
      await api.moveCard(teamId, card.id, {
        to_stage: target as StageCode,
        request_id: newRequestId(),
      });
      return `ID-${card.number} moved to ${stageLabel(target)}`;
    });
  };

  const handleRoll = (stage: WorkStage) => {
    void act(async () => {
      const roll = await api.rollDie(teamId, stage);
      return `${stageLabel(stage)} die: ${roll.value}`;
    });
  };

  return (
    <section>
      <h1>Your board</h1>
      <p className="card-meta">
        {playerName} · {data.day === 0 ? "Waiting for the facilitator to start" : `Day ${data.day}`}
        {data.wip_limits_enabled ? " · WIP limits on" : ""}
      </p>
      {rejoinToken !== null ? (
        <details>
          <summary>My rejoin code</summary>
          <p>
            Keep this code to return after closing the page: <code>{rejoinToken}</code>
          </p>
        </details>
      ) : null}

      {todaysEvents.map((event) => (
        <div key={event.id} className="banner banner-info" role="status">
          <strong>{event.title}.</strong> {event.description}
        </div>
      ))}
      <ErrorBanner error={action.error} />
      {notice !== "" ? (
        <div className="banner banner-info" role="status">
          {notice}
        </div>
      ) : null}

      <DicePanel board={data} busy={action.busy} onRoll={handleRoll} />
      <SpendPanel
        board={data}
        selectedId={selectedId}
        busy={action.busy}
        onSpend={(card, source, points) =>
          void act(async () => {
            const result = await api.spend(teamId, {
              card_id: card.id,
              source_stage: source,
              points,
              request_id: newRequestId(),
            });
            return result.squares_crossed > 0
              ? `Crossed out ${result.squares_crossed} square(s); ${result.points_left} points left`
              : `Points used; ${result.points_left} left`;
          })
        }
      />
      <BoardView
        board={data}
        onMove={handleMove}
        onSelect={(card) => setSelectedId(card.id)}
        selectedCardId={selectedId}
        busy={action.busy}
      />
    </section>
  );
}

function DicePanel({
  board,
  busy,
  onRoll,
}: {
  board: Board;
  busy: boolean;
  onRoll: (stage: WorkStage) => void;
}) {
  return (
    <section className="panel" aria-label="Dice">
      <h2>Dice</h2>
      <ul className="dice">
        {WORK_STAGES.map((stage) => {
          const die = board.dice.find((item) => item.stage === stage);
          return (
            <li key={stage}>
              <strong>{stageLabel(stage)}</strong>
              {die !== undefined ? (
                <span>
                  {" "}
                  rolled {die.value} · {die.points_left} left
                </span>
              ) : (
                <button
                  type="button"
                  disabled={busy || board.day === 0}
                  onClick={() => onRoll(stage)}
                >
                  Roll
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function SpendPanel({
  board,
  selectedId,
  busy,
  onSpend,
}: {
  board: Board;
  selectedId: string | null;
  busy: boolean;
  onSpend: (card: Card, source: WorkStage, points: number) => void;
}) {
  const [source, setSource] = useState<WorkStage | "">("");
  const [points, setPoints] = useState(1);
  const card = board.cards.find((item) => item.id === selectedId);
  const sources = board.dice.filter((die) => die.points_left > 0);
  const chosen = sources.find((die) => die.stage === source) ?? sources[0];

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (card !== undefined && chosen !== undefined) {
      onSpend(card, chosen.stage as WorkStage, Math.min(points, chosen.points_left));
    }
  };

  if (card === undefined) {
    return (
      <section className="panel">
        <h2>Spend points</h2>
        <p>Choose “Work on it” on a card to spend dice points on it.</p>
      </section>
    );
  }
  return (
    <section className="panel">
      <h2>Spend points on ID-{card.number}</h2>
      {sources.length === 0 ? (
        <p>Roll a die first, or all today’s points are used.</p>
      ) : (
        <form className="inline-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="spend-source">From die</label>
            <select
              id="spend-source"
              value={chosen?.stage ?? ""}
              onChange={(event) => setSource(event.target.value as WorkStage)}
            >
              {sources.map((die) => (
                <option key={die.stage} value={die.stage}>
                  {stageLabel(die.stage)} ({die.points_left} left)
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="spend-points">Points</label>
            <input
              id="spend-points"
              type="number"
              min={1}
              max={chosen?.points_left ?? 1}
              value={points}
              onChange={(event) => setPoints(Number(event.target.value) || 1)}
            />
          </div>
          <button type="submit" disabled={busy}>
            Spend
          </button>
        </form>
      )}
      {card.stage !== chosen?.stage && chosen !== undefined ? (
        <p className="card-meta">Help from another stage counts half, rounded down.</p>
      ) : null}
    </section>
  );
}
