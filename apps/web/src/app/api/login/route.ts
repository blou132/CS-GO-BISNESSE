import { NextRequest, NextResponse } from "next/server";
import { readAuthConfig } from "@/lib/auth-config";
import { verifyPassword } from "@/lib/password";
import { clientKey, isSameOrigin } from "@/lib/request-security";
import { loginRateLimiter } from "@/lib/rate-limit";
import {
  createSessionToken,
  randomNonce,
  SESSION_COOKIE_NAME,
  sessionCookieOptions,
} from "@/lib/session";

export const runtime = "nodejs";

const invalidLogin = () =>
  NextResponse.json(
    { detail: "Identifiant ou mot de passe invalide." },
    { status: 401, headers: { "Cache-Control": "no-store" } },
  );

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json(
      { detail: "Origine non autorisée." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  const auth = readAuthConfig();
  if (!auth.ok) {
    console.error(JSON.stringify({ component: "auth", event: "configuration_invalid", errors: auth.errors }));
    return NextResponse.json(
      { detail: "Authentification temporairement indisponible." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }

  const credentials = await readCredentials(request);
  if (!credentials) return invalidLogin();

  const { config } = auth;
  const normalizedUsername = credentials.username.trim();
  const accountKey = `account:${normalizedUsername === config.adminUsername ? "admin" : "invalid"}`;
  const sourceKey = clientKey(request, normalizedUsername.toLocaleLowerCase("en-US"));
  const settings = {
    maxAttempts: config.loginRateLimitMaxAttempts,
    windowSeconds: config.loginRateLimitWindowSeconds,
  };
  const limits = [loginRateLimiter.check(accountKey, settings), loginRateLimiter.check(sourceKey, settings)];
  const blocked = limits.find((limit) => !limit.allowed);
  if (blocked) {
    console.warn(JSON.stringify({ component: "auth", event: "login_rate_limited" }));
    return NextResponse.json(
      { detail: "Trop de tentatives. Réessayez plus tard." },
      {
        status: 429,
        headers: {
          "Cache-Control": "no-store",
          "Retry-After": String(blocked.retryAfterSeconds),
        },
      },
    );
  }

  const passwordMatches = verifyPassword(credentials.password, config.adminPasswordHash);
  const usernameMatches = normalizedUsername === config.adminUsername;
  if (!passwordMatches || !usernameMatches) {
    loginRateLimiter.recordFailure(accountKey, settings);
    loginRateLimiter.recordFailure(sourceKey, settings);
    console.warn(JSON.stringify({ component: "auth", event: "login_failed" }));
    return invalidLogin();
  }

  loginRateLimiter.clear(accountKey);
  loginRateLimiter.clear(sourceKey);
  const token = await createSessionToken(
    {
      username: config.adminUsername,
      expiresAt: Date.now() + config.sessionTtlSeconds * 1000,
      nonce: randomNonce(),
    },
    config.sessionSecret,
  );
  const response = NextResponse.json(
    { ok: true },
    { status: 200, headers: { "Cache-Control": "no-store" } },
  );
  response.cookies.set(
    SESSION_COOKIE_NAME,
    token,
    sessionCookieOptions(config.sessionTtlSeconds, config.sessionCookieSecure),
  );
  console.info(JSON.stringify({ component: "auth", event: "login_success" }));
  return response;
}

async function readCredentials(
  request: NextRequest,
): Promise<{ username: string; password: string } | null> {
  try {
    const body = (await request.json()) as Record<string, unknown>;
    if (typeof body.username !== "string" || typeof body.password !== "string") return null;
    if (body.username.length > 64 || body.password.length < 1 || body.password.length > 1024) return null;
    return { username: body.username, password: body.password };
  } catch {
    return null;
  }
}
