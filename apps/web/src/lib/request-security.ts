export function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  if (origin === "null") return request.headers.get("sec-fetch-site") === "same-origin";
  const host = request.headers.get("host");
  try {
    return Boolean(host && new URL(origin).host === host);
  } catch {
    return false;
  }
}

export function clientKey(request: Request, username: string): string {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const address = forwarded || request.headers.get("x-real-ip") || "local";
  return `${address}:${username || "unknown"}`;
}

export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  if (value.includes("\\") || /[\u0000-\u001f]/.test(value)) return "/";
  return value;
}
