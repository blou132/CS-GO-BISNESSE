import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { createSessionToken, SESSION_COOKIE_NAME } from "@/lib/session";
import { proxy } from "./proxy";

const secret = "p".repeat(32);

afterEach(() => vi.unstubAllEnvs());

describe("authentication proxy", () => {
  it("redirects an anonymous page request to login", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("SESSION_SECRET", secret);
    const response = await proxy(new NextRequest("http://127.0.0.1:3000/markets?mode=live"));
    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("location") ?? "http://invalid");
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/markets?mode=live");
  });

  it("returns 401 for an anonymous private API request", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("SESSION_SECRET", secret);
    const response = await proxy(new NextRequest("http://127.0.0.1:3000/api/dashboard"));
    expect(response.status).toBe(401);
  });

  it("allows a valid signed admin session", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("SESSION_SECRET", secret);
    const token = await createSessionToken(
      { username: "admin", expiresAt: Date.now() + 60_000, nonce: "nonce" },
      secret,
    );
    const response = await proxy(
      new NextRequest("http://127.0.0.1:3000/markets", {
        headers: { cookie: `${SESSION_COOKIE_NAME}=${token}` },
      }),
    );
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });
});
