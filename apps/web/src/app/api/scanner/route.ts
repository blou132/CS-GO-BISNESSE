import { requireApiSession } from "@/lib/auth-server";
import { proxyScanner } from "@/lib/proxy";

export async function GET(request: Request) {
  const unauthorized = await requireApiSession(request);
  return unauthorized ?? proxyScanner(request);
}
