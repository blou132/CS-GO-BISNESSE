import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { hashPassword } from "@/lib/password";
import { loginRateLimiter } from "@/lib/rate-limit";
import { POST } from "./route";

function request(username: string, password: string, origin = "http://127.0.0.1:3000") {
  return new NextRequest("http://127.0.0.1:3000/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", host: "127.0.0.1:3000", origin },
    body: JSON.stringify({ username, password }),
  });
}

describe("POST /api/login", () => {
  beforeEach(() => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("ADMIN_PASSWORD_HASH", hashPassword("correct-password", Buffer.alloc(16, 3)));
    vi.stubEnv("SESSION_SECRET", "s".repeat(32));
    vi.stubEnv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "1");
    loginRateLimiter.reset();
  });

  afterEach(() => {
    loginRateLimiter.reset();
    vi.unstubAllEnvs();
  });

  it("sets a signed HttpOnly session cookie after valid credentials", async () => {
    const response = await POST(request("admin", "correct-password"));
    expect(response.status).toBe(200);
    const cookie = response.headers.get("set-cookie");
    expect(cookie).toContain("cs2_admin_session=");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=lax");
  });

  it("adds the Secure flag when configured", async () => {
    vi.stubEnv("SESSION_COOKIE_SECURE", "true");
    const response = await POST(request("admin", "correct-password"));
    expect(response.headers.get("set-cookie")).toContain("Secure");
  });

  it("uses a generic error and rate-limits repeated failures", async () => {
    const first = await POST(request("admin", "wrong-password"));
    expect(first.status).toBe(401);
    await expect(first.json()).resolves.toEqual({ detail: "Identifiant ou mot de passe invalide." });

    const second = await POST(request("admin", "wrong-password"));
    expect(second.status).toBe(429);
    expect(second.headers.get("retry-after")).toBeTruthy();
  });

  it("does not allow username rotation to bypass the failure limit", async () => {
    expect((await POST(request("intruder-one", "wrong-password"))).status).toBe(401);
    expect((await POST(request("intruder-two", "wrong-password"))).status).toBe(429);
  });

  it("rejects a cross-origin login", async () => {
    const response = await POST(request("admin", "correct-password", "https://example.test"));
    expect(response.status).toBe(403);
  });

  it("fails closed when the authentication configuration is invalid", async () => {
    vi.stubEnv("ADMIN_PASSWORD_HASH", "");
    const response = await POST(request("admin", "correct-password"));
    expect(response.status).toBe(503);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
