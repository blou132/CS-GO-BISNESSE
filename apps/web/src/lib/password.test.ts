import { describe, expect, it } from "vitest";
import { hashPassword, verifyPassword } from "./password";

describe("password hashing", () => {
  it("verifies only the original password", () => {
    const hash = hashPassword("correct-password", Buffer.alloc(16, 7));
    expect(hash).toMatch(/^scrypt\$16384\$8\$1\$/);
    expect(verifyPassword("correct-password", hash)).toBe(true);
    expect(verifyPassword("wrong-password", hash)).toBe(false);
  });

  it("rejects malformed or excessive Scrypt parameters", () => {
    expect(verifyPassword("password", "not-a-hash")).toBe(false);
    expect(verifyPassword("password", "scrypt$999999$8$1$c2FsdA$aGFzaA")).toBe(false);
  });
});
