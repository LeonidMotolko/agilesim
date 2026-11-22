import { useCallback } from "react";
import { useParams } from "react-router-dom";

import { ErrorBanner } from "../components/ErrorBanner";
import { EventsPanel } from "../components/EventsPanel";
import { LoadingState } from "../components/LoadingState";
import { ResultsPanel } from "../components/ResultsPanel";
import { TeamBoardViewer } from "../components/TeamBoardViewer";
import { TeamsPanel } from "../components/TeamsPanel";
import { GAME_DAYS } from "../constants";
import { useAction } from "../hooks/useAction";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";

export function SessionPage() {
  const { sessionId = "" } = useParams();
  const loadSession = useCallback(
    (signal: AbortSignal) => api.getSession(sessionId, signal),
    [sessionId],
  );
  const loadTeams = useCallback(
    (signal: AbortSignal) => api.listTeams(sessionId, signal),
    [sessionId],
  );
  const session = useAsync(loadSession, { pollMs: 5000 });
  const teams = useAsync(loadTeams, { pollMs: 5000 });
  const action = useAction();

  const game = session.data;
  if (game === null) {
    return session.error !== null ? (
      <ErrorBanner error={session.error} />
    ) : (
      <LoadingState label="Loading session…" />
    );
  }

  const teamList = teams.data ?? [];
  const running = game.status === "running";

  const run = async (work: () => Promise<unknown>) => {
    await action.run(work);
    session.reload();
    teams.reload();
  };

  return (
    <section>
      <h1>{game.name}</h1>
      <div className="panel summary">
        <p>
          Join code <code className="join-code">{game.join_code}</code>
        </p>
        <p>
          Status: <strong>{game.status}</strong>
          {game.status !== "lobby" ? ` · Day ${game.current_day} of ${GAME_DAYS}` : ""}
          {game.wip_limits_enabled ? " · WIP limits on" : ""}
        </p>
        {game.status === "lobby" ? (
          <button
            type="button"
            disabled={action.busy || teamList.length === 0}
            onClick={() => void run(() => api.startGame(game.id))}
          >
            Start the game
          </button>
        ) : null}
        {running ? (
          <button
            type="button"
            disabled={action.busy}
            onClick={() => void run(() => api.nextDay(game.id))}
          >
            {game.current_day >= GAME_DAYS ? "Finish the game" : `Close day ${game.current_day}`}
          </button>
        ) : null}
        <ErrorBanner error={action.error} />
        {game.status === "lobby" && teamList.length === 0 ? (
          <p className="card-meta">Add at least one team to start.</p>
        ) : null}
      </div>

      <div className="grid-two">
        <TeamsPanel
          sessionId={game.id}
          teams={teamList}
          canAdd={game.status !== "finished"}
          onChanged={teams.reload}
        />
        <EventsPanel sessionId={game.id} running={running} />
      </div>

      {game.status !== "lobby" ? (
        <>
          <ResultsPanel sessionId={game.id} />
          <TeamBoardViewer teams={teamList} />
        </>
      ) : null}
    </section>
  );
}
