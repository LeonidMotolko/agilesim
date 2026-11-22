import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../state/AuthContext";
import { ApiStatus } from "./ApiStatus";

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="3" y="4" width="26" height="7" rx="2" fill="var(--analysis)" />
      <rect x="3" y="13" width="20" height="7" rx="2" fill="var(--development)" />
      <rect x="3" y="22" width="14" height="7" rx="2" fill="var(--done)" />
    </svg>
  );
}

export function Layout() {
  const { auth, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = () => {
    signOut();
    navigate("/");
  };

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <BrandMark />
          AgileSim
        </Link>
        <nav aria-label="Main">
          {auth?.role === "facilitator" ? <NavLink to="/sessions">Sessions</NavLink> : null}
          {auth?.role === "participant" ? <NavLink to="/play">My board</NavLink> : null}
          {auth === null ? (
            <>
              <NavLink to="/login">Facilitator sign in</NavLink>
              <NavLink to="/join">Join a game</NavLink>
            </>
          ) : (
            <button type="button" className="link-button" onClick={handleSignOut}>
              Sign out
            </button>
          )}
        </nav>
      </header>
      <main className="page">
        <Outlet />
      </main>
      <footer className="footer">
        <ApiStatus />
      </footer>
    </div>
  );
}
