import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { hashPassword } from "@/lib/password";
import { POST } from "./route";

afterEach(() => vi.unstubAllEnvs());

describe("POST /logout", () => {
  it("expires the session cookie and redirects to login", async () => {
    vi.stubEnv("ADMIN_USERNAME", "admin");
    vi.stubEnv("ADMIN_PASSWORD_HASH", hashPassword("correct-password", Buffer.alloc(16, 4)));
    vi.stubEnv("SESSION_SECRET", "s".repeat(32));
    const request = new NextRequest("http://127.0.0.1:3000/logout", {
      method: "POST",
      headers: { host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000" },
    });

    const response = await POST(request);
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/login");
    expect(response.headers.get("set-cookie")).toContain("cs2_admin_session=;");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });

  it("rejects cross-origin logout", async () => {
    const request = new NextRequest("http://127.0.0.1:3000/logout", {
      method: "POST",
      headers: { host: "127.0.0.1:3000", origin: "https://example.test" },
    });
    expect((await POST(request)).status).toBe(403);
  });
});
