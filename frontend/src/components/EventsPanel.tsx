import { useCallback, useState, type FormEvent } from "react";

import { useAction } from "../hooks/useAction";
import { useAsync } from "../hooks/useAsync";
import { api } from "../services/api";
import type { GameEvent } from "../types/api";
import { ErrorBanner } from "./ErrorBanner";
import { FormField } from "./FormField";
import { LoadingState } from "./LoadingState";

const EFFECT_TEXT: Record<string, string> = {
  pull_cards: "Every team pulls more cards",
  block_top_card: "Blocks the best card in Development",
  emergency_card: "Adds the emergency card",
  dev_roll_bonus: "Development bonus: handled at the table",
};

function EventItem({
  event,
  canAct,
  busy,
  onApply,
  onDismiss,
}: {
  event: GameEvent;
  canAct: boolean;
  busy: boolean;
  onApply: (event: GameEvent) => void;
  onDismiss: (event: GameEvent) => void;
}) {
  const waiting = event.status === "proposed" || event.status === "confirmed";
  return (
    <li className="event">
      <div className="event-head">
        <strong>
          Day {event.day}: {event.title}
        </strong>
        <span className={`badge badge-${event.status}`}>{event.status}</span>
      </div>
      <p>{event.description}</p>
      {event.effect !== null && EFFECT_TEXT[event.effect] !== undefined ? (
        <p className="card-meta">{EFFECT_TEXT[event.effect]}</p>
      ) : null}
      {canAct && waiting ? (
        <div className="card-actions">
          <button type="button" disabled={busy} onClick={() => onApply(event)}>
            Apply
          </button>
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => onDismiss(event)}
          >
            Dismiss
          </button>
        </div>
      ) : null}
    </li>
  );
}

export function EventsPanel({ sessionId, running }: { sessionId: string; running: boolean }) {
  const load = useCallback((signal: AbortSignal) => api.listEvents(sessionId, signal), [sessionId]);
  const events = useAsync(load, { pollMs: 4000 });
  const action = useAction();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const act = async (work: () => Promise<unknown>) => {
    await action.run(work);
    events.reload();
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (title.trim() === "" || description.trim() === "") {
      return;
    }
    await act(() =>
      api.createEvent(sessionId, { title: title.trim(), description: description.trim() }),
    );
    setTitle("");
    setDescription("");
  };

  return (
    <section className="panel">
      <h2>Events</h2>
      {events.loading && events.data === null ? <LoadingState label="Loading events…" /> : null}
      <ErrorBanner error={events.error} />
      {events.data !== null && events.data.length === 0 ? (
        <p>Events appear here on their day.</p>
      ) : null}
      <ul className="plain-list">
        {(events.data ?? []).map((event) => (
          <EventItem
            key={event.id}
            event={event}
            canAct={running}
            busy={action.busy}
            onApply={(item) => void act(() => api.applyEvent(sessionId, item.id))}
            onDismiss={(item) => void act(() => api.dismissEvent(sessionId, item.id))}
          />
        ))}
      </ul>
      <ErrorBanner error={action.error} />
      {running ? (
        <form onSubmit={handleCreate} className="stack" noValidate>
          <h3>Add your own event</h3>
          <FormField label="Event title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <FormField
            label="What happens"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button type="submit" disabled={action.busy}>
            Add event
          </button>
        </form>
      ) : null}
    </section>
  );
}
