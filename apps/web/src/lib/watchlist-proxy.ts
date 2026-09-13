import "server-only";

import { requireApiSession } from "./auth-server";
import { isSameOrigin } from "./request-security";

const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const headers = { "Cache-Control": "no-store" };

export async function proxyWatchlist(request: Request, id?: string, matches = false) {
  const unauthorized = await requireApiSession(request);
  if (unauthorized) return unauthorized;
  const mutation = request.method !== "GET";
  if (mutation && !isSameOrigin(request)) {
    return Response.json({ detail: "Origine non autorisée." }, { status: 403, headers });
  }
  if (id !== undefined && !uuid.test(id)) {
    return Response.json({ detail: "Identifiant de règle invalide." }, { status: 400, headers });
  }
  const input = new URL(request.url);
  const mode = input.searchParams.get("mode") ?? "live";
  if (mode !== "live" && mode !== "demo") {
    return Response.json({ detail: "Mode invalide." }, { status: 400, headers });
  }
  const path = `/api/watchlist${id ? `/${id}${matches ? "/matches" : ""}` : ""}`;
  const target = new URL(path, process.env.API_BASE_URL ?? "http://127.0.0.1:8000");
  target.searchParams.set("mode", mode);
  for (const key of ["page", "page_size", "sort"]) {
    const value = input.searchParams.get(key);
    if (value !== null) target.searchParams.set(key, value);
  }
  let body: string | undefined;
  if (request.method === "POST" || request.method === "PUT") {
    if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") {
      return Response.json({ detail: "Un objet JSON est requis." }, { status: 415, headers });
    }
    try {
      body = await request.text();
      if (body.length > 8192) return Response.json({ detail: "Règle trop volumineuse." }, { status: 413, headers });
      JSON.parse(body);
    } catch {
      return Response.json({ detail: "Règle JSON invalide." }, { status: 400, headers });
    }
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      body,
      headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    if (upstream.status === 204) return new Response(null, { status: 204, headers });
    if (!upstream.ok) {
      const detail = upstream.status === 404 ? "Règle introuvable dans ce mode."
        : upstream.status === 409 ? "Cette règle est en pause."
        : upstream.status === 422 ? "Vérifiez le nom exact, les montants, le float, la phase et les seeds (0 à 1000)."
        : "Watchlist temporairement indisponible.";
      return Response.json({ detail }, { status: upstream.status >= 500 ? 502 : upstream.status, headers });
    }
    return Response.json(await upstream.json(), { status: upstream.status, headers });
  } catch {
    return Response.json({ detail: "API watchlist indisponible." }, { status: 503, headers });
  }
}
