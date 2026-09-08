import { requireApiSession } from "@/lib/auth-server";
import { proxyIntegrations } from "@/lib/proxy";

export async function GET(request: Request) {
  const unauthorized = await requireApiSession(request);
  return unauthorized ?? proxyIntegrations();
}
