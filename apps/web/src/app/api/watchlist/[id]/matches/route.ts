import { proxyWatchlist } from "@/lib/watchlist-proxy";

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  return proxyWatchlist(request, (await context.params).id, true);
}
