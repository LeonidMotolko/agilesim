import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../services/api";
import { getAuth, setAuth } from "../services/authStorage";
import { ApiError } from "../services/http";
import { AuthProvider } from "../state/AuthContext";
import { LoginPage } from "./LoginPage";

vi.mock("../services/api", () => ({ api: { login: vi.fn() } }));

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/sessions" element={<p>Your sessions page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

function fill(email: string, password: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(api.login).mockReset();
    setAuth(null);
  });

  afterEach(() => {
    setAuth(null);
  });

  it("shows field errors and does not call the API for an empty form", async () => {
    renderLogin();

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter your email")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(api.login).not.toHaveBeenCalled();
  });

  it("signs in, remembers the token and opens the sessions page", async () => {
    vi.mocked(api.login).mockResolvedValue({
      access_token: "token-1",
      token_type: "bearer",
      role: "facilitator",
    });
    renderLogin();

    fill("anna@example.com", "a-long-password");

    expect(await screen.findByText("Your sessions page")).toBeInTheDocument();
    expect(api.login).toHaveBeenCalledWith({
      email: "anna@example.com",
      password: "a-long-password",
    });
    expect(getAuth()).toMatchObject({ token: "token-1", role: "facilitator" });
  });

  it("explains a rejected password without signing in", async () => {
    vi.mocked(api.login).mockRejectedValue(
      new ApiError(401, "unauthorized", "Wrong email or password"),
    );
    renderLogin();

    fill("anna@example.com", "wrong-password");

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(getAuth()).toBeNull();
  });
});
