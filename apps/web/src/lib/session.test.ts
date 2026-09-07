import { describe, expect, it } from "vitest";
import { createSessionToken, verifySessionToken } from "./session";

const secret = "a".repeat(32);

describe("signed sessions", () => {
  it("round-trips a valid payload", async () => {
    const payload = { username: "admin", expiresAt: 2_000, nonce: "nonce" };
    const token = await createSessionToken(payload, secret);
    await expect(verifySessionToken(token, secret, 1_000)).resolves.toEqual(payload);
  });

  it("rejects expired and modified tokens", async () => {
    const token = await createSessionToken({ username: "admin", expiresAt: 2_000, nonce: "n" }, secret);
    await expect(verifySessionToken(token, secret, 2_000)).resolves.toBeNull();
    await expect(verifySessionToken(`${token}x`, secret, 1_000)).resolves.toBeNull();
  });
});
