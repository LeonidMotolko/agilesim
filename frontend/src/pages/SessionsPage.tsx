import { useCallback, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ErrorBanner } from "../components/ErrorBanner";
import { FormField } from "../components/FormField";
import { LoadingState } from "../components/LoadingState";
import { SortableTable, type Column } from "../components/SortableTable";
import { useAction } from "../hooks/useAction";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { GameSession } from "../types/api";
import { filterRows } from "../utils/table";
import { validateName } from "../utils/validation";

const COLUMNS: Column<GameSession>[] = [
  {
    key: "name",
    header: "Session",
    render: (row) => <Link to={`/sessions/${row.id}`}>{row.name}</Link>,
    sortValue: (row) => row.name,
  },
  { key: "code", header: "Join code", render: (row) => <code>{row.join_code}</code> },
  {
    key: "status",
    header: "Status",
    render: (row) => row.status,
    sortValue: (row) => row.status,
  },
  {
    key: "day",
    header: "Day",
    render: (row) => row.current_day,
    sortValue: (row) => row.current_day,
  },
];

export function SessionsPage() {
  const load = useCallback((signal: AbortSignal) => api.listSessions(signal), []);
  const sessions = useAsync(load);
  const action = useAction();
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | undefined>();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validateName(name, "session name");
    setNameError(problem);
    if (problem !== undefined) {
      return;
    }
    const created = await action.run(() => api.createSession(name.trim()));
    if (created !== undefined) {
      setName("");
      sessions.reload();
    }
  };

  const rows = filterRows(
    (sessions.data ?? []).filter((row) => status === "all" || row.status === status),
    query,
    (row) => `${row.name} ${row.join_code}`,
  );

  return (
    <section>
      <h1>Your sessions</h1>
      <form className="inline-form" onSubmit={handleCreate} noValidate>
        <FormField
          label="New session name"
          value={name}
          error={nameError}
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" disabled={action.busy}>
          Create session
        </button>
      </form>
      <ErrorBanner error={action.error} />

      <div className="filters">
        <FormField
          label="Search"
          value={query}
          placeholder="Name or join code"
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="field">
          <label htmlFor="status-filter">Status</label>
          <select
            id="status-filter"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">All</option>
            <option value="lobby">Lobby</option>
            <option value="running">Running</option>
            <option value="finished">Finished</option>
          </select>
        </div>
      </div>

      {sessions.loading && sessions.data === null ? (
        <LoadingState label="Loading sessions…" />
      ) : null}
      <ErrorBanner error={sessions.error} />
      {sessions.data !== null ? (
        <SortableTable
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => row.id}
          emptyText="No sessions yet. Create the first one above."
        />
      ) : null}
    </section>
  );
}
