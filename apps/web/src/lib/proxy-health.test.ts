import { afterEach, describe, expect, it, vi } from "vitest";
import { hashPassword } from "./password";

vi.mock("server-only", () => ({}));

import { proxyHealth } from "./proxy";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("proxyHealth", () => {
  it("fails closed before contacting the backend when auth is invalid", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await proxyHealth();
    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({ authentication: "unhealthy" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("adds a healthy auth state to a healthy backend response", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("ADMIN_PASSWORD_HASH", hashPassword("correct-password", Buffer.alloc(16, 5)));
    vi.stubEnv("SESSION_SECRET", "s".repeat(32));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({ api: "healthy", database: "healthy", markets: {} }),
      ),
    );
    const response = await proxyHealth();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ authentication: "healthy" });
  });
});
