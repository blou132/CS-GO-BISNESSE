import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { proxyScanner } from "./proxy";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("proxyScanner", () => {
  it("forwards only allowlisted scanner parameters", async () => {
    vi.stubEnv("API_BASE_URL", "http://api.internal:8000");
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ items: [], total: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await proxyScanner(
      new Request(
        "http://panel.local/api/scanner?mode=demo&page=2&skin=AK-47%20%7C%20Redline&ignored=secret",
      ),
    );

    expect(response.status).toBe(200);
    const target = new URL(fetchMock.mock.calls[0][0] as URL);
    expect(target.origin).toBe("http://api.internal:8000");
    expect(target.pathname).toBe("/api/scanner");
    expect(target.searchParams.get("mode")).toBe("demo");
    expect(target.searchParams.get("page")).toBe("2");
    expect(target.searchParams.get("skin")).toBe("AK-47 | Redline");
    expect(target.searchParams.has("ignored")).toBe(false);
  });

  it("does not expose backend details from server errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ detail: "internal traceback" }, { status: 500 })),
    );

    const response = await proxyScanner(new Request("http://panel.local/api/scanner"));

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({ detail: "API scanner indisponible." });
  });
});
