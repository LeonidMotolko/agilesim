import { useState, type FormEvent } from "react";

import { useAction } from "../hooks/useAction";
import { api } from "../services/api";
import type { Team } from "../types/api";
import { validateName } from "../utils/validation";
import { ErrorBanner } from "./ErrorBanner";
import { FormField } from "./FormField";

interface TeamsPanelProps {
  sessionId: string;
  teams: Team[];
  canAdd: boolean;
  onChanged: () => void;
}

export function TeamsPanel({ sessionId, teams, canAdd, onChanged }: TeamsPanelProps) {
  const action = useAction();
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | undefined>();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validateName(name, "team name");
    setNameError(problem);
    if (problem !== undefined) {
      return;
    }
    const created = await action.run(() => api.createTeam(sessionId, name.trim()));
    if (created !== undefined) {
      setName("");
      onChanged();
    }
  };

  return (
    <section className="panel">
      <h2>Teams</h2>
      {teams.length === 0 ? (
        <p>No teams yet.</p>
      ) : (
        <ul className="plain-list">
          {teams.map((team) => (
            <li key={team.id}>{team.name}</li>
          ))}
        </ul>
      )}
      {canAdd ? (
        <form className="inline-form" onSubmit={handleSubmit} noValidate>
          <FormField
            label="Team name"
            value={name}
            error={nameError}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" disabled={action.busy}>
            Add team
          </button>
        </form>
      ) : null}
      <ErrorBanner error={action.error} />
    </section>
  );
}
