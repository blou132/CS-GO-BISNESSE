import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createSessionToken, SESSION_COOKIE_NAME } from "./session";

vi.mock("server-only", () => ({}));

import { proxyWatchlist } from "./watchlist-proxy";

const id = "10203040-1111-4222-8333-0123456789ab";
let cookie: string;
beforeEach(async () => {
  vi.stubEnv("ADMIN_USERNAME", "admin");
  vi.stubEnv("SESSION_SECRET", "t".repeat(32));
  const token = await createSessionToken({ username: "admin", expiresAt: Date.now() + 60_000, nonce: "test" }, "t".repeat(32));
  cookie = `${SESSION_COOKIE_NAME}=${token}`;
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

function request(method = "GET", body?: string, origin = "http://localhost") {
  return new Request("http://localhost/api/watchlist?mode=demo&ignored=value", {
    method, body,
    headers: { cookie, origin, host: "localhost", "content-type": "application/json" },
  });
}

describe("watchlist authorization and transport", () => {
  it("rejects anonymous writes without contacting the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await proxyWatchlist(new Request("http://localhost/api/watchlist", { method: "POST" }));
    expect(result.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects cross-origin authenticated mutations", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await proxyWatchlist(request("POST", "{}", "https://untrusted.example"))).status).toBe(403);
    expect((await proxyWatchlist(request("DELETE", undefined, "https://untrusted.example"), id)).status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves decimal strings and only forwards documented query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ id }, { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const body = JSON.stringify({ name: "TEST", filters: { max_price_eur: "25.12345678" } });
    expect((await proxyWatchlist(request("POST", body))).status).toBe(201);
    const target = fetchMock.mock.calls[0][0] as URL;
    expect(target.search).toBe("?mode=demo");
    expect(fetchMock.mock.calls[0][1].body).toBe(body);
    expect(fetchMock.mock.calls[0][1].headers.cookie).toBeUndefined();
  });

  it("rejects invalid paths and JSON without reaching the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await proxyWatchlist(request(), "../../health/status")).status).toBe(400);
    expect((await proxyWatchlist(request("POST", "{"))).status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("handles deletion without parsing a JSON body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    expect((await proxyWatchlist(request("DELETE"), id)).status).toBe(204);
  });

  it("keeps internal database errors out of the browser", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "private traceback" }, { status: 500 })));
    const result = await proxyWatchlist(request());
    expect(result.status).toBe(502);
    expect(await result.text()).not.toContain("private traceback");
  });
});
