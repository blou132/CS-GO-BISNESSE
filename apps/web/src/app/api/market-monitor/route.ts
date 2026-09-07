import { proxyMonitor } from "@/lib/proxy";

export async function GET() {
  return proxyMonitor();
}
