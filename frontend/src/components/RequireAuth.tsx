import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../state/AuthContext";
import type { Role } from "../types/api";

/** Routes below this need a signed-in person of the given role. */
export function RequireAuth({ role }: { role: Role }) {
  const { auth } = useAuth();
  const location = useLocation();

  if (auth === null) {
    const target = role === "facilitator" ? "/login" : "/join";
    return <Navigate to={target} replace state={{ from: location.pathname }} />;
  }
  if (auth.role !== role) {
    return (
      <div className="banner banner-error" role="alert">
        You do not have access to this page.
      </div>
    );
  }
  return <Outlet />;
}
