import { requireApiSession } from "@/lib/auth-server";
import { proxyApi } from "@/lib/proxy";
export async function POST(request: Request) {
  const unauthorized = await requireApiSession(request);
  return unauthorized ?? proxyApi(request, "/api/sync");
}
