import type { Participant, Role } from "../types/api";

/** What is remembered about the signed-in person between page loads. */
export interface StoredAuth {
  token: string;
  role: Role;
  participant: Participant | null;
  rejoinToken: string | null;
}

const STORAGE_KEY = "agilesim.auth";

function isStoredAuth(value: unknown): value is StoredAuth {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Partial<StoredAuth>;
  return (
    typeof candidate.token === "string" &&
    (candidate.role === "facilitator" || candidate.role === "participant")
  );
}

function readFromStorage(): StoredAuth | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    return isStoredAuth(parsed) ? parsed : null;
  } catch {
    // Storage can be blocked or hold garbage: behave as signed out.
    return null;
  }
}

let current: StoredAuth | null = readFromStorage();

export function getAuth(): StoredAuth | null {
  return current;
}

export function setAuth(auth: StoredAuth | null): void {
  current = auth;
  try {
    if (auth === null) {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
    }
  } catch {
    // The session still works in memory when storage is unavailable.
  }
}
