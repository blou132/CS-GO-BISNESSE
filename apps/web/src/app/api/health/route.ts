import { proxyHealth } from "@/lib/proxy";

export async function GET() {
  return proxyHealth();
}
