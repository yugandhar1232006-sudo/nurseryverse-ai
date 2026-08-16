import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/error";
import { classifyLoginError } from "@/lib/auth/login-error";

describe("classifyLoginError", () => {
  it("classifies a network failure (status 0)", () => {
    const error = new ApiError({ status: 0, code: "network_error", message: "Unable to reach the server." });
    expect(classifyLoginError(error)).toEqual({ kind: "network", message: "Unable to reach the server." });
  });

  it("classifies a 429 as rate_limited", () => {
    const error = new ApiError({ status: 429, code: "rate_limit_exceeded", message: "Too many attempts." });
    expect(classifyLoginError(error)).toEqual({ kind: "rate_limited", message: "Too many attempts." });
  });

  it("classifies a locked-account 401 by message substring", () => {
    const error = new ApiError({
      status: 401,
      code: "authentication_error",
      message: "Account is temporarily locked due to too many failed attempts.",
    });
    expect(classifyLoginError(error)).toEqual({
      kind: "account_locked",
      message: "Account is temporarily locked due to too many failed attempts.",
    });
  });

  it("classifies a wrong-password/unknown-email 401 as invalid_credentials (identical to locked except message)", () => {
    const error = new ApiError({ status: 401, code: "authentication_error", message: "Incorrect email or password." });
    expect(classifyLoginError(error)).toEqual({ kind: "invalid_credentials", message: "Incorrect email or password." });
  });

  it("classifies a 5xx as server", () => {
    const error = new ApiError({ status: 503, code: "unknown_error", message: "The service is temporarily unavailable." });
    expect(classifyLoginError(error).kind).toBe("server");
  });

  it("classifies any other status as unknown", () => {
    const error = new ApiError({ status: 418, code: "unknown_error", message: "I'm a teapot." });
    expect(classifyLoginError(error).kind).toBe("unknown");
  });

  it("classifies a non-ApiError (e.g. a thrown string) as unknown with generic copy", () => {
    expect(classifyLoginError("boom")).toEqual({
      kind: "unknown",
      message: "Something went wrong. Please try again.",
    });
  });
});
