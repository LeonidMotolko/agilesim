import { useCallback, useState } from "react";

import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { TeamResult } from "../types/api";
import { filterRows } from "../utils/table";
import { ErrorBanner } from "./ErrorBanner";
import { FormField } from "./FormField";
import { LoadingState } from "./LoadingState";
import { SortableTable, type Column } from "./SortableTable";

export const RESULT_COLUMNS: Column<TeamResult>[] = [
  {
    key: "rank",
    header: "Rank",
    render: (row) => <span className={`rank rank-${row.money_rank}`}>{row.money_rank}</span>,
    sortValue: (row) => row.money_rank,
  },
  {
    key: "team",
    header: "Team",
    render: (row) => row.team_name,
    sortValue: (row) => row.team_name,
  },
  {
    key: "done",
    header: "Cards done",
    render: (row) => row.done_cards,
    sortValue: (row) => row.done_cards,
  },
  {
    key: "money",
    header: "Money earned",
    render: (row) => `$${row.money_earned}`,
    sortValue: (row) => row.money_earned,
  },
  {
    key: "lead",
    header: "Avg Lead Time (days)",
    render: (row) => row.avg_lead_time_days ?? "–",
    sortValue: (row) => row.avg_lead_time_days,
  },
];

export function ResultsPanel({ sessionId }: { sessionId: string }) {
  const load = useCallback((signal: AbortSignal) => api.results(sessionId, signal), [sessionId]);
  const results = useAsync(load, { pollMs: 5000 });
  const [query, setQuery] = useState("");

  const rows = filterRows(results.data ?? [], query, (row) => row.team_name);

  return (
    <section className="panel">
      <h2>Results</h2>
      <FormField
        label="Find a team"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {results.loading && results.data === null ? <LoadingState label="Loading results…" /> : null}
      <ErrorBanner error={results.error} />
      {results.data !== null ? (
        <SortableTable
          columns={RESULT_COLUMNS}
          rows={rows}
          rowKey={(row) => row.team_id}
          emptyText="No teams match."
          initialSort={{ key: "rank", direction: "asc" }}
        />
      ) : null}
    </section>
  );
}
