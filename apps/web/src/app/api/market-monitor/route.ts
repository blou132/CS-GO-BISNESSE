import { requireApiSession } from "@/lib/auth-server";
import { proxyMonitor } from "@/lib/proxy";

export async function GET(request: Request) {
  const unauthorized = await requireApiSession(request);
  return unauthorized ?? proxyMonitor();
}
