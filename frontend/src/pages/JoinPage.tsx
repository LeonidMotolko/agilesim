import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorBanner } from "../components/ErrorBanner";
import { FormField } from "../components/FormField";
import { useAction } from "../hooks/useAction";
import { api } from "../services/api";
import { useAuth } from "../state/AuthContext";
import type { Team } from "../types/api";
import { fieldErrors } from "../utils/errors";
import { validateJoinCode, validateName, type FormErrors } from "../utils/validation";

export function JoinPage() {
  const { auth, joinGame } = useAuth();
  const navigate = useNavigate();
  const lookup = useAction();
  const join = useAction();
  const rejoin = useAction();

  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | undefined>();
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [teamId, setTeamId] = useState("");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [token, setToken] = useState("");

  const handleLookup = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validateJoinCode(code);
    setCodeError(problem);
    if (problem !== undefined) {
      return;
    }
    const found = await lookup.run(() => api.teamsByJoinCode(code.trim().toUpperCase()));
    if (found !== undefined) {
      setTeams(found);
      setTeamId(found[0]?.id ?? "");
    }
  };

  const handleJoin = async (event: FormEvent) => {
    event.preventDefault();
    const problems: FormErrors = {};
    const nameProblem = validateName(name, "name");
    if (nameProblem !== undefined) {
      problems.display_name = nameProblem;
    }
    if (teamId === "") {
      problems.team = "Choose your team";
    }
    if (!consent) {
      problems.consent = "Agree to the processing of the game data to play";
    }
    setErrors(problems);
    if (Object.keys(problems).length > 0) {
      return;
    }
    const joined = await join.run(() =>
      api.join({
        join_code: code.trim().toUpperCase(),
        display_name: name.trim(),
        team_id: teamId,
        consent,
      }),
    );
    if (joined !== undefined) {
      joinGame(joined);
      navigate("/play", { replace: true });
    }
  };

  const handleRejoin = async (event: FormEvent) => {
    event.preventDefault();
    if (token.trim() === "") {
      return;
    }
    const joined = await rejoin.run(() => api.rejoin(token.trim()));
    if (joined !== undefined) {
      joinGame(joined);
      navigate("/play", { replace: true });
    }
  };

  return (
    <section className="card-form">
      <h1>Join a game</h1>
      {auth?.role === "participant" ? (
        <p>
          You are already in a game. <Link to="/play">Go to your board</Link>
        </p>
      ) : null}

      {teams === null ? (
        <form onSubmit={handleLookup} noValidate>
          <FormField
            label="Join code"
            value={code}
            error={codeError}
            maxLength={6}
            autoCapitalize="characters"
            onChange={(event) => setCode(event.target.value)}
          />
          <button type="submit" disabled={lookup.busy}>
            Find my game
          </button>
          <ErrorBanner error={lookup.error} />
        </form>
      ) : (
        <form onSubmit={handleJoin} noValidate>
          {teams.length === 0 ? (
            <p className="banner banner-error" role="alert">
              This game has no teams yet. Ask your facilitator to add them.
            </p>
          ) : (
            <fieldset>
              <legend>Your team</legend>
              {teams.map((team) => (
                <label key={team.id} className="choice">
                  <input
                    type="radio"
                    name="team"
                    value={team.id}
                    checked={teamId === team.id}
                    onChange={() => setTeamId(team.id)}
                  />
                  {team.name}
                </label>
              ))}
              {errors.team ? <p className="field-error">{errors.team}</p> : null}
            </fieldset>
          )}
          <FormField
            label="Your name"
            value={name}
            error={errors.display_name}
            onChange={(event) => setName(event.target.value)}
          />
          <label className="choice">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            I agree that my game actions are recorded for the course research
          </label>
          {errors.consent ? <p className="field-error">{errors.consent}</p> : null}
          <button type="submit" disabled={join.busy || teams.length === 0}>
            Join
          </button>
          <button type="button" className="secondary" onClick={() => setTeams(null)}>
            Use another code
          </button>
          <ErrorBanner error={join.error} />
          {join.error !== null ? <ErrorFields error={join.error} /> : null}
        </form>
      )}

      <details>
        <summary>I left the game and want to come back</summary>
        <form onSubmit={handleRejoin} noValidate>
          <FormField
            label="Rejoin code"
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
          <button type="submit" disabled={rejoin.busy}>
            Rejoin
          </button>
          <ErrorBanner error={rejoin.error} />
        </form>
      </details>
    </section>
  );
}

/** Server-side field problems (rare: the form checks first) listed under the form. */
function ErrorFields({ error }: { error: unknown }) {
  const problems = Object.entries(fieldErrors(error));
  if (problems.length === 0) {
    return null;
  }
  return (
    <ul className="field-error">
      {problems.map(([field, message]) => (
        <li key={field}>
          {field}: {message}
        </li>
      ))}
    </ul>
  );
}
