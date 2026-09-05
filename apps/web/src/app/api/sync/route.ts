import { proxyApi } from "@/lib/proxy";
export async function POST(request: Request) { return proxyApi(request, "/api/sync"); }
