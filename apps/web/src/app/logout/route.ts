import { NextRequest, NextResponse } from "next/server";
import { readAuthConfig } from "@/lib/auth-config";
import { isSameOrigin } from "@/lib/request-security";
import { expiredSessionCookieOptions, SESSION_COOKIE_NAME } from "@/lib/session";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ detail: "Origine non autorisée." }, { status: 403 });
  }
  const auth = readAuthConfig();
  const secure = auth.ok ? auth.config.sessionCookieSecure : false;
  const response = new NextResponse(null, { status: 303, headers: { Location: "/login" } });
  response.cookies.set(SESSION_COOKIE_NAME, "", expiredSessionCookieOptions(secure));
  console.info(JSON.stringify({ component: "auth", event: "logout" }));
  return response;
}
