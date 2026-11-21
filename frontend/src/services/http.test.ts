import { afterEach, describe, expect, it, vi } from "vitest";

import { setAuth } from "./authStorage";
import { ApiError, UNAUTHORIZED_EVENT, request } from "./http";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("request", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setAuth(null);
  });

  it("returns the parsed body and calls the versioned API path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await request<{ status: string }>("GET", "/sessions");

    expect(result).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/sessions",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("sends the access token and a JSON body", async () => {
    setAuth({ token: "secret", role: "facilitator", participant: null, rejoinToken: null });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await request("POST", "/sessions", { body: { name: "Group 1" } });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).toMatchObject({
      Authorization: "Bearer secret",
      "Content-Type": "application/json",
    });
    expect(init.body).toBe('{"name":"Group 1"}');
  });

  it("turns the uniform error body into an ApiError", async () => {
    const body = { error: { code: "rule_violation", message: "Card blocked" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(body, 422)));

    const failure = request("POST", "/teams/1/spend").catch((error: unknown) => error);

    await expect(failure).resolves.toMatchObject({
      status: 422,
      code: "rule_violation",
      message: "Card blocked",
    });
    expect(await failure).toBeInstanceOf(ApiError);
  });

  it("reports an unreachable server as status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(request("GET", "/sessions")).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("announces a rejected token so the app can sign out", async () => {
    setAuth({ token: "old", role: "facilitator", participant: null, rejoinToken: null });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse({ error: { code: "unauthorized", message: "x" } }, 401)),
    );
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);

    await expect(request("GET", "/sessions")).rejects.toMatchObject({ status: 401 });

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("does not announce a 401 of a request that sent no token (wrong password)", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse({ error: { code: "unauthorized", message: "Bad" } }, 401)),
    );
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);

    await expect(request("POST", "/auth/login", { auth: false })).rejects.toBeInstanceOf(ApiError);

    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });
});
