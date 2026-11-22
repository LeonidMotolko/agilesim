import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorBanner } from "../components/ErrorBanner";
import { FormField } from "../components/FormField";
import { api } from "../services/api";
import { useAuth } from "../state/AuthContext";
import { fieldErrors } from "../utils/errors";
import { validateRegistration, type FormErrors } from "../utils/validation";

export function RegisterPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [failure, setFailure] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const values = { email, display_name: displayName, password };
    const problems = validateRegistration(values);
    setErrors(problems);
    setFailure(null);
    if (Object.keys(problems).length > 0) {
      return;
    }
    setBusy(true);
    try {
      const token = await api.register(values);
      signIn(token.access_token, token.role);
      navigate("/sessions", { replace: true });
    } catch (error) {
      setErrors(fieldErrors(error));
      setFailure(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-form">
      <h1>Create a facilitator account</h1>
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
          label="Your name"
          autoComplete="name"
          value={displayName}
          error={errors.display_name}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <FormField
          label="Password"
          type="password"
          autoComplete="new-password"
          value={password}
          error={errors.password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <button type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p>
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </section>
  );
}
