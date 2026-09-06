import "server-only";

const apiBaseUrl = () => process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function proxyHealth() {
  try {
    const upstream = await fetch(new URL("/health/status", apiBaseUrl()), {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
      headers: { Accept: "application/json" },
    });
    if (!upstream.ok) {
      return Response.json({ detail: "État système indisponible." }, { status: 502 });
    }
    const body: unknown = await upstream.json();
    return Response.json(body, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "API indisponible." }, { status: 503 });
  }
}

export async function proxyApi(request: Request, path: "/api/dashboard" | "/api/sync" | `/api/items/${string}`) {
  const input = new URL(request.url);
  const mode = input.searchParams.get("mode") ?? "live";
  if (mode !== "live" && mode !== "demo") return Response.json({ detail: "Mode invalide." }, { status: 400 });
  const query = input.searchParams.get("query")?.trim();
  if (query && (query.length > 200 || /[\u0000-\u001f]/.test(query))) return Response.json({ detail: "Le nom de l’objet est invalide (200 caractères maximum)." }, { status: 400 });
  if (request.method === "POST") {
    const origin = request.headers.get("origin");
    const requestHost = request.headers.get("host");
    if (origin) {
      let originHost: string | null = null;
      try { originHost = new URL(origin).host; } catch { /* rejet ci-dessous */ }
      if (!requestHost || originHost !== requestHost) {
        return Response.json({ detail: "Origine non autorisée." }, { status: 403 });
      }
    }
  }
  try {
    const target = new URL(path, apiBaseUrl());
    target.searchParams.set("mode", mode);
    if (query && path === "/api/sync") target.searchParams.set("query", query);
    const upstream = await fetch(target, { method: request.method, cache: "no-store", signal: AbortSignal.timeout(90_000), headers: { Accept: "application/json" } });
    if (!upstream.ok) {
      const messages: Record<number, string> = { 404: "Cet exemplaire est introuvable dans le mode sélectionné.", 422: "Vérifiez le nom exact du skin et réessayez.", 429: "Limite de requêtes atteinte. Réessayez plus tard.", 409: "Une synchronisation est déjà en cours." };
      return Response.json({ detail: messages[upstream.status] ?? "La requête a échoué côté API. Consultez les journaux du backend." }, { status: upstream.status >= 500 ? 502 : upstream.status });
    }
    const body: unknown = await upstream.json();
    return Response.json(body, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "API indisponible. Vérifiez que le backend est démarré, puis réessayez." }, { status: 503 });
  }
}
