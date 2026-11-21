import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ErrorBanner } from "../components/ErrorBanner";
import { FormField } from "../components/FormField";
import { api } from "../services/api";
import { useAuth } from "../state/AuthContext";
import { fieldErrors } from "../utils/errors";
import { validateLogin, type FormErrors } from "../utils/validation";

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [failure, setFailure] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const problems = validateLogin({ email, password });
    setErrors(problems);
    setFailure(null);
    if (Object.keys(problems).length > 0) {
      return;
    }
    setBusy(true);
    try {
      const token = await api.login({ email, password });
      signIn(token.access_token, token.role);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? "/sessions", { replace: true });
    } catch (error) {
      setErrors(fieldErrors(error));
      setFailure(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-form">
      <h1>Facilitator sign in</h1>
      <ErrorBanner error={failure} />
      <form onSubmit={handleSubmit} noValidate>
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          error={errors.email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <FormField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          error={errors.password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p>
        No account yet? <Link to="/register">Create one</Link>
      </p>
    </section>
  );
}
