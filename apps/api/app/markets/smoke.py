"""Explicit, read-only credential smoke test. Never writes to the database."""

import argparse
import asyncio
import json

from app.core.config import Settings
from app.markets.base import MarketAdapterError
from app.markets.normalize import check_query
from app.services.sync import build_adapters, close_adapters


async def check_source(settings: Settings, platform: str, query: str) -> dict[str, object]:
    adapters = build_adapters(settings)
    try:
        query = check_query(query)
        if not query:
            raise ValueError("An exact item name is required")
        async with asyncio.timeout(120):
            result = await adapters[platform].search_items(query)
        return {
            "platform": platform,
            "status": "degraded" if result.partial_errors else "online",
            "counts": {
                name: len(getattr(result, name))
                for name in (
                    "listings",
                    "observations",
                    "aggregates",
                    "realized_sales",
                    "buy_orders",
                    "fee_schedules",
                )
            },
            "partial_errors": result.partial_errors,
            "database_written": False,
            "transaction_executed": False,
        }
    except MarketAdapterError as error:
        return {
            "platform": platform,
            "status": "not_configured" if error.code == "configuration" else "error",
            "error_code": error.code,
        }
    except (TimeoutError, ValueError, KeyError):
        return {"platform": platform, "status": "error", "error_code": "invalid_or_timeout"}
    finally:
        await close_adapters(adapters)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("csfloat", "skinport", "dmarket"), required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--live", action="store_true", help="Authorize read-only upstream requests")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; credentials must be supplied through the environment")
    result = asyncio.run(check_source(Settings(_env_file=None), args.platform, args.query))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "online" else 2)


if __name__ == "__main__":
    main()
