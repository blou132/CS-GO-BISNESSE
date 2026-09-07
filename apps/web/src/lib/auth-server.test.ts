import { afterEach, describe, expect, it, vi } from "vitest";
import { createSessionToken, SESSION_COOKIE_NAME } from "./session";

vi.mock("server-only", () => ({}));

import { requireApiSession } from "./auth-server";

const secret = "q".repeat(32);

afterEach(() => vi.unstubAllEnvs());

describe("requireApiSession", () => {
  it("rejects a request without a session", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("SESSION_SECRET", secret);
    const response = await requireApiSession(new Request("http://localhost/api/dashboard"));
    expect(response?.status).toBe(401);
  });

  it("accepts a signed session for the configured administrator", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("SESSION_SECRET", secret);
    const token = await createSessionToken(
      { username: "admin", expiresAt: Date.now() + 60_000, nonce: "nonce" },
      secret,
    );
    const request = new Request("http://localhost/api/dashboard", {
      headers: { cookie: `${SESSION_COOKIE_NAME}=${token}` },
    });
    await expect(requireApiSession(request)).resolves.toBeNull();
  });
});
