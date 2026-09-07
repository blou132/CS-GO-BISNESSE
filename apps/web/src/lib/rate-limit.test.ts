import { describe, expect, it } from "vitest";
import { LoginRateLimiter } from "./rate-limit";

describe("LoginRateLimiter", () => {
  it("blocks after the configured number of failures and expires the bucket", () => {
    const limiter = new LoginRateLimiter();
    const settings = { maxAttempts: 2, windowSeconds: 60 };
    limiter.recordFailure("admin", settings, 1_000);
    expect(limiter.check("admin", settings, 1_001).allowed).toBe(true);
    limiter.recordFailure("admin", settings, 1_002);
    expect(limiter.check("admin", settings, 1_003)).toEqual({
      allowed: false,
      retryAfterSeconds: 60,
    });
    expect(limiter.check("admin", settings, 61_003).allowed).toBe(true);
  });
});
