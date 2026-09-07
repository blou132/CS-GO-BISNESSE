import { requireApiSession } from "@/lib/auth-server";
import { proxyApi } from "@/lib/proxy";
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const unauthorized = await requireApiSession(request);
  if (unauthorized) return unauthorized;
  const { id } = await params;
  if (!/^[a-zA-Z0-9_-]{1,200}$/.test(id)) return Response.json({ detail: "Identifiant invalide." }, { status: 400 });
  return proxyApi(request, `/api/items/${encodeURIComponent(id)}`);
}
