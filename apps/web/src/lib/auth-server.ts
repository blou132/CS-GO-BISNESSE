import "server-only";

import { hasSessionSecret } from "./auth-config";
import { SESSION_COOKIE_NAME, type SessionPayload, verifySessionToken } from "./session";

export async function requestSession(request: Request): Promise<SessionPayload | null> {
  const secret = hasSessionSecret();
  const expectedUsername = process.env.ADMIN_USERNAME?.trim();
  if (!secret || !expectedUsername) return null;

  const token = readCookie(request.headers.get("cookie"), SESSION_COOKIE_NAME);
  const session = await verifySessionToken(token, secret);
  return session?.username === expectedUsername ? session : null;
}

export async function requireApiSession(request: Request): Promise<Response | null> {
  if (await requestSession(request)) return null;
  return Response.json(
    { detail: "Authentification requise." },
    { status: 401, headers: { "Cache-Control": "no-store" } },
  );
}

function readCookie(header: string | null, name: string): string | undefined {
  if (!header) return undefined;
  for (const part of header.split(";")) {
    const [cookieName, ...valueParts] = part.trim().split("=");
    if (cookieName === name) return valueParts.join("=");
  }
  return undefined;
}
