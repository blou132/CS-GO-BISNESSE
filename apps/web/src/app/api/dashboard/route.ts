import { proxyApi } from "@/lib/proxy";
export async function GET(request: Request) { return proxyApi(request, "/api/dashboard"); }
