import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

const KEY_LENGTH = 64;
const SCRYPT_N = 16384;
const SCRYPT_R = 8;
const SCRYPT_P = 1;
const MAXMEM = 64 * 1024 * 1024;

export function hashPassword(password: string, salt = randomBytes(16)): string {
  if (!password) throw new Error("Password is required.");
  const hash = scryptSync(password, salt, KEY_LENGTH, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
    maxmem: MAXMEM,
  });
  return [
    "scrypt",
    SCRYPT_N,
    SCRYPT_R,
    SCRYPT_P,
    salt.toString("base64url"),
    hash.toString("base64url"),
  ].join("$");
}

export function verifyPassword(password: string, storedHash: string): boolean {
  const parts = storedHash.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") return false;
  const [, nValue, rValue, pValue, saltValue, hashValue] = parts;
  const n = Number(nValue);
  const r = Number(rValue);
  const p = Number(pValue);
  if (!Number.isInteger(n) || !Number.isInteger(r) || !Number.isInteger(p)) return false;
  if (n < 4096 || n > 32768 || r < 1 || r > 16 || p < 1 || p > 4) return false;
  try {
    const salt = Buffer.from(saltValue, "base64url");
    const expected = Buffer.from(hashValue, "base64url");
    if (salt.length < 16 || expected.length !== KEY_LENGTH) return false;
    const actual = scryptSync(password, salt, expected.length, { N: n, r, p, maxmem: MAXMEM });
    return actual.length === expected.length && timingSafeEqual(actual, expected);
  } catch {
    return false;
  }
}
