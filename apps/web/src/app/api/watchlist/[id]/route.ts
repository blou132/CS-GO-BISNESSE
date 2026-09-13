import { proxyWatchlist } from "@/lib/watchlist-proxy";

type Context = { params: Promise<{ id: string }> };

export async function PUT(request: Request, context: Context) {
  return proxyWatchlist(request, (await context.params).id);
}

export async function DELETE(request: Request, context: Context) {
  return proxyWatchlist(request, (await context.params).id);
}
