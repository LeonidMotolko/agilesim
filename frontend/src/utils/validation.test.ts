import { describe, expect, it } from "vitest";

import { validateJoinCode, validateLogin, validateName, validateRegistration } from "./validation";

describe("validateLogin", () => {
  it("asks for both fields", () => {
    expect(validateLogin({ email: "", password: "" })).toEqual({
      email: "Enter your email",
      password: "Enter your password",
    });
  });

  it("rejects an address without a domain", () => {
    expect(validateLogin({ email: "anna@x", password: "p" }).email).toBe(
      "Enter a valid email address",
    );
  });

  it("accepts a valid pair", () => {
    expect(validateLogin({ email: "anna@example.com", password: "p" })).toEqual({});
  });
});

describe("validateRegistration", () => {
  it("needs a password of at least 10 characters", () => {
    const errors = validateRegistration({
      email: "anna@example.com",
      display_name: "Anna",
      password: "short",
    });
    expect(errors).toEqual({ password: "Use at least 10 characters" });
  });
});

describe("validateName and validateJoinCode", () => {
  it("checks names and join codes", () => {
    expect(validateName("  ", "team name")).toBe("Enter the team name");
    expect(validateName("x".repeat(61), "team name")).toBe("Use at most 60 characters");
    expect(validateName("Alpha", "team name")).toBeUndefined();
    expect(validateJoinCode("AB12")).toBeDefined();
    expect(validateJoinCode("ab12cd")).toBeUndefined();
  });
});
