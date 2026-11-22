import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getAuth, setAuth, type StoredAuth } from "../services/authStorage";
import { UNAUTHORIZED_EVENT } from "../services/http";
import type { JoinResponse, Role } from "../types/api";

interface AuthContextValue {
  /** The signed-in facilitator or player, or null. */
  auth: StoredAuth | null;
  signIn: (token: string, role: string) => void;
  joinGame: (join: JoinResponse) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function toRole(role: string): Role {
  return role === "facilitator" ? "facilitator" : "participant";
}

/** Global state: who is signed in. Everything else lives in the page that needs it. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuthState] = useState<StoredAuth | null>(() => getAuth());

  const update = useCallback((next: StoredAuth | null) => {
    setAuth(next);
    setAuthState(next);
  }, []);

  const signIn = useCallback(
    (token: string, role: string) => {
      update({ token, role: toRole(role), participant: null, rejoinToken: null });
    },
    [update],
  );

  const joinGame = useCallback(
    (join: JoinResponse) => {
      update({
        token: join.access_token,
        role: "participant",
        participant: join.participant,
        rejoinToken: join.rejoin_token,
      });
    },
    [update],
  );

  const signOut = useCallback(() => update(null), [update]);

  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, signOut);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, signOut);
  }, [signOut]);

  const value = useMemo(
    () => ({ auth, signIn, joinGame, signOut }),
    [auth, signIn, joinGame, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return context;
}
