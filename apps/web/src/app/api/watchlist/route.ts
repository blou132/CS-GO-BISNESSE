import { proxyWatchlist } from "@/lib/watchlist-proxy";

export async function GET(request: Request) {
  return proxyWatchlist(request);
}

export async function POST(request: Request) {
  return proxyWatchlist(request);
}
