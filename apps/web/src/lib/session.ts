export const SESSION_COOKIE_NAME = "cs2_admin_session";

export interface SessionPayload {
  username: string;
  expiresAt: number;
  nonce: string;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

export function sessionCookieOptions(maxAge: number, secure: boolean) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure,
    maxAge,
    path: "/",
  };
}

export function expiredSessionCookieOptions(secure: boolean) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure,
    maxAge: 0,
    path: "/",
  };
}

export async function createSessionToken(payload: SessionPayload, secret: string): Promise<string> {
  const encodedPayload = base64UrlEncode(encoder.encode(JSON.stringify(payload)));
  const signature = await sign(encodedPayload, secret);
  return `${encodedPayload}.${signature}`;
}

export async function verifySessionToken(
  token: string | undefined,
  secret: string,
  now = Date.now(),
): Promise<SessionPayload | null> {
  if (!token || !secret) return null;
  const [encodedPayload, signature, extra] = token.split(".");
  if (!encodedPayload || !signature || extra !== undefined) return null;
  if (!(await verify(encodedPayload, signature, secret))) return null;
  try {
    const payload = JSON.parse(decoder.decode(base64UrlDecode(encodedPayload))) as Partial<SessionPayload>;
    if (
      typeof payload.username !== "string" ||
      typeof payload.expiresAt !== "number" ||
      typeof payload.nonce !== "string" ||
      payload.expiresAt <= now
    ) {
      return null;
    }
    return { username: payload.username, expiresAt: payload.expiresAt, nonce: payload.nonce };
  } catch {
    return null;
  }
}

export function randomNonce(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

async function sign(payload: string, secret: string): Promise<string> {
  const key = await importKey(secret);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return base64UrlEncode(new Uint8Array(signature));
}

async function verify(payload: string, signature: string, secret: string): Promise<boolean> {
  try {
    const key = await importKey(secret);
    return await crypto.subtle.verify(
      "HMAC",
      key,
      base64UrlDecode(signature),
      encoder.encode(payload),
    );
  } catch {
    return false;
  }
}

async function importKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function base64UrlDecode(value: string): ArrayBuffer {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0)).buffer;
}
