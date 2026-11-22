import { describe, expect, it } from "vitest";

import { ApiError } from "../services/http";
import { describeError, fieldErrors, newRequestId } from "./errors";

describe("describeError", () => {
  const cases: [ApiError, RegExp][] = [
    [new ApiError(0, "network_error", "x"), /Cannot reach the server/],
    [new ApiError(401, "unauthorized", "x"), /sign in again/],
    [new ApiError(403, "forbidden", "x"), /do not have access/],
    [new ApiError(404, "not_found", "x"), /Not found/],
    [new ApiError(500, "internal_error", "x"), /went wrong on the server/],
  ];

  it.each(cases)("explains %s in plain words", (error, expected) => {
    expect(describeError(error)).toMatch(expected);
  });

  it("shows the server's own message for rule violations and conflicts", () => {
    expect(describeError(new ApiError(422, "rule_violation", "Card blocked"))).toBe("Card blocked");
    expect(describeError(new ApiError(409, "conflict", "The game has already started"))).toBe(
      "The game has already started",
    );
  });

  it("handles errors that did not come from the API", () => {
    expect(describeError(new Error("boom"))).toBe("boom");
  });
});

describe("fieldErrors", () => {
  it("maps validation details to fields", () => {
    const error = new ApiError(422, "validation_error", "Invalid request", [
      { field: "email", message: "Enter a valid email" },
      { field: "password", message: "Too short" },
    ]);
    expect(fieldErrors(error)).toEqual({ email: "Enter a valid email", password: "Too short" });
  });

  it("is empty for other errors", () => {
    expect(fieldErrors(new ApiError(409, "conflict", "x"))).toEqual({});
  });
});

describe("newRequestId", () => {
  it("makes distinct UUID-shaped ids", () => {
    const first = newRequestId();
    expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(newRequestId()).not.toBe(first);
  });
});
