"""One official Socket.IO connection, no retries, no DB writes and no raw payload output."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from importlib.metadata import version

from app.services.realtime import SkinportTransport


async def check(seconds):
    transport = SkinportTransport()
    report = {"checked_at": datetime.now(UTC).isoformat(), "connected": False,
              "events": 0, "types": [], "http_status": None, "error_code": None,
              "database_written": False, "transaction_executed": False}
    kinds = set()

    async def receive(payload):
        if (isinstance(payload, dict) and isinstance(payload.get("eventType"), str)
            and payload.get("eventType") in {"listed", "sold"}):
            kinds.add(payload["eventType"])
            if isinstance(payload.get("sales"), list):
                report["events"] += len(payload["sales"])

    try:
        await asyncio.wait_for(transport.connect(receive), timeout=20)
        report["connected"] = True
        try:
            await asyncio.wait_for(transport.wait(), timeout=seconds)
        except TimeoutError:
            pass
    except Exception:
        report["error_code"] = "connection_failed"
    finally:
        await transport.close()
    report["http_status"] = transport.http_status
    report["types"] = sorted(kinds)
    report["http_metadata"] = transport.diagnostics
    report["client_versions"] = {name: version(name) for name in ("python-socketio", "python-engineio", "aiohttp", "msgpack")}
    report["access_status"] = "BLOCKED_BY_PROVIDER" if transport.http_status in {401, 403} else "UNKNOWN"
    report["cause"] = ("CLOUDFLARE_CHALLENGE" if transport.diagnostics.get("cloudflare_challenge")
                       else "NOT_DETERMINED")
    report["secret_exposed"] = "NO"
    print(json.dumps(report))
    return 0 if report["connected"] and report["events"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--seconds", type=int, choices=range(1, 61), default=30)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required for the single official connection")
    raise SystemExit(asyncio.run(check(args.seconds)))
