import { useCallback, useState } from "react";

import { POLL_MS } from "../constants";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { Team } from "../types/api";
import { BoardView } from "./BoardView";
import { ErrorBanner } from "./ErrorBanner";
import { LoadingState } from "./LoadingState";

function SelectedBoard({ teamId }: { teamId: string }) {
  const load = useCallback((signal: AbortSignal) => api.board(teamId, signal), [teamId]);
  const board = useAsync(load, { pollMs: POLL_MS });
  return (
    <>
      {board.loading && board.data === null ? <LoadingState label="Loading board…" /> : null}
      <ErrorBanner error={board.error} />
      {board.data !== null ? <BoardView board={board.data} /> : null}
    </>
  );
}

/** The facilitator watches any team's board (read only). */
export function TeamBoardViewer({ teams }: { teams: Team[] }) {
  const [selected, setSelected] = useState("");
  const teamId = selected !== "" ? selected : (teams[0]?.id ?? "");

  if (teams.length === 0) {
    return null;
  }
  return (
    <section className="panel">
      <h2>Team boards</h2>
      <div className="field">
        <label htmlFor="team-select">Team</label>
        <select
          id="team-select"
          value={teamId}
          onChange={(event) => setSelected(event.target.value)}
        >
          {teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
      </div>
      <SelectedBoard teamId={teamId} />
    </section>
  );
}
