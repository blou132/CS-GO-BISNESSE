import { NextRequest, NextResponse } from "next/server";
import { hasSessionSecret } from "@/lib/auth-config";
import { safeNextPath } from "@/lib/request-security";
import { SESSION_COOKIE_NAME, verifySessionToken } from "@/lib/session";

const PUBLIC_PATHS = new Set(["/login", "/api/login", "/api/health"]);

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const secret = hasSessionSecret();
  const expectedUsername = process.env.ADMIN_USERNAME?.trim();
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const session = secret ? await verifySessionToken(token, secret) : null;
  const authenticated = Boolean(session && expectedUsername && session.username === expectedUsername);

  if (pathname === "/login") {
    if (!authenticated) return NextResponse.next();
    const nextPath = safeNextPath(request.nextUrl.searchParams.get("next"));
    return NextResponse.redirect(new URL(nextPath, request.url));
  }
  if (PUBLIC_PATHS.has(pathname)) return NextResponse.next();
  if (authenticated) return NextResponse.next();

  if (pathname.startsWith("/api/")) {
    return NextResponse.json(
      { detail: "Authentification requise." },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)"],
};
