import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "./App";
import { setAuth } from "./services/authStorage";
import { AuthProvider } from "./state/AuthContext";

function renderAt(path: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("routes", () => {
  beforeEach(() => {
    setAuth(null);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setAuth(null);
  });

  it("shows the start page with both ways in", () => {
    renderAt("/");

    expect(screen.getByRole("heading", { name: "AgileSim" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Join a game" })).toHaveLength(2);
  });

  it("sends a signed-out visitor from a facilitator page to the sign-in form", () => {
    renderAt("/sessions");

    expect(screen.getByRole("heading", { name: "Facilitator sign in" })).toBeInTheDocument();
  });

  it("sends a signed-out visitor from the board to the join form", () => {
    renderAt("/play");

    expect(screen.getByRole("heading", { name: "Join a game" })).toBeInTheDocument();
  });

  it("keeps a player out of the facilitator pages", () => {
    setAuth({ token: "t", role: "participant", participant: null, rejoinToken: null });

    renderAt("/sessions");

    expect(screen.getByRole("alert")).toHaveTextContent("do not have access");
  });

  it("shows a not-found page for unknown addresses", () => {
    renderAt("/nowhere");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
