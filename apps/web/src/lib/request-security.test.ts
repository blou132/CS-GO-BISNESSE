import { describe, expect, it } from "vitest";
import { isSameOrigin, safeNextPath } from "./request-security";

describe("request security", () => {
  it("rejects cross-origin requests", () => {
    const request = new Request("http://127.0.0.1:3000/api/login", {
      headers: { host: "127.0.0.1:3000", origin: "https://example.test" },
    });
    expect(isSameOrigin(request)).toBe(false);
  });

  it("accepts an opaque origin only for a browser-confirmed same-origin form", () => {
    const sameOrigin = new Request("http://127.0.0.1:3000/logout", {
      headers: { origin: "null", "sec-fetch-site": "same-origin" },
    });
    const untrusted = new Request("http://127.0.0.1:3000/logout", {
      headers: { origin: "null", "sec-fetch-site": "cross-site" },
    });
    expect(isSameOrigin(sameOrigin)).toBe(true);
    expect(isSameOrigin(untrusted)).toBe(false);
  });

  it("allows only local redirect paths", () => {
    expect(safeNextPath("/markets?mode=live")).toBe("/markets?mode=live");
    expect(safeNextPath("https://example.test")).toBe("/");
    expect(safeNextPath("//example.test")).toBe("/");
    expect(safeNextPath("/\\example.test")).toBe("/");
  });
});
