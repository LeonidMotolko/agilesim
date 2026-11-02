import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the API as online when the health check succeeds", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

    render(<App />);

    expect(screen.getByRole("heading", { name: "AgileSim" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("api-status")).toHaveTextContent("online"));
  });

  it("shows the API as offline when the health check fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    render(<App />);

    await waitFor(() => expect(screen.getByTestId("api-status")).toHaveTextContent("offline"));
  });
});
