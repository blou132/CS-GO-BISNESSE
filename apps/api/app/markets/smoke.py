"""Explicit, read-only credential smoke test. Never writes to the database."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from app.core.config import Settings
from app.core.market_credentials import load
from app.markets.base import MarketAdapterError
from app.markets.csfloat import CSFloatAdapter, CSFloatSearch
from app.markets.dmarket import DMarketAdapter
from app.markets.normalize import check_query
from app.services.sync import build_adapters, close_adapters


async def check_source(
    settings: Settings, platform: str, query: str, *, enrich: bool = False
) -> dict[str, object]:
    adapters = build_adapters(settings)
    started = time.monotonic()
    report: dict[str, object] = {
        "platform": platform,
        "authentication": "NOT_TESTED",
        "request": "NOT_SENT",
        "parser": "NOT_TESTED",
        "pagination": "UNKNOWN",
        "rate_limit": "UNKNOWN",
        "database_written": False,
        "transaction_executed": False,
        "secret_exposed": "NO",
    }
    adapter = adapters.get(platform)
    transport = getattr(adapter, "_http", None)
    if transport is not None:
        transport.max_attempts = 1
    try:
        query = check_query(query)
        if not query:
            raise ValueError("An exact item name is required")
        async with asyncio.timeout(120):
            if isinstance(adapter, CSFloatAdapter):
                result = await adapter.search(CSFloatSearch(market_hash_name=query, limit=5))
            elif isinstance(adapter, DMarketAdapter):
                result = await adapter.search_items(query, limit=5, enrich=enrich)
            else:
                result = await adapters[platform].search_items(query)
        report.update(
            {
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
                "authentication": "OK" if platform != "skinport" else "NOT_REQUIRED",
                "request": "OK",
                "parser": "OK",
                "normalized_fields_present": {
                    field: sum(
                        getattr(row.item, field, None) is not None for row in result.listings
                    )
                    for field in (
                        "float_value",
                        "paint_index",
                        "paint_seed",
                        "inspect_link",
                        "tradable",
                        "tradable_at",
                        "doppler_phase",
                    )
                },
                "listings_with_stickers": sum(bool(row.item.stickers) for row in result.listings),
                "warning_count": len(result.warnings),
            }
        )
    except MarketAdapterError as error:
        report.update(
            {
                "platform": platform,
                "status": "not_configured" if error.code == "configuration" else "error",
                "error_code": error.code,
                "authentication": "FAIL" if error.code == "authentication" else "NOT_TESTED",
                "request": "NOT_SENT" if error.code == "configuration" else "FAIL",
                "parser": "FAIL" if error.code == "invalid_response" else "NOT_TESTED",
            }
        )
    except (TimeoutError, ValueError, KeyError):
        report.update(status="error", error_code="invalid_or_timeout")
    except Exception:
        report.update(status="error", error_code="unexpected_error")
    finally:
        try:
            await close_adapters(adapters)
        except Exception:
            report.update(status="error", error_code="client_close_failed")
    report["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
    report["requests"] = list(getattr(transport, "diagnostics", []))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("csfloat", "skinport", "dmarket"), required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--live", action="store_true", help="Authorize read-only upstream requests")
    parser.add_argument(
        "--credentials-file", type=Path, help="Explicit private test credentials file"
    )
    parser.add_argument(
        "--enrich", action="store_true", help="Also read DMarket targets/sales/fees"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; no implicit environment file is loaded")
    try:
        credentials = load(args.credentials_file) if args.credentials_file else {}
        settings = (
            Settings(
                _env_file=None,
                csfloat_api_key=credentials["csfloat_api_key"],
                dmarket_public_key=credentials["dmarket_public_key"],
                dmarket_secret_key=credentials["dmarket_secret_key"],
            )
            if args.credentials_file
            else Settings(_env_file=None)
        )
    except (OSError, ValueError):
        print(
            json.dumps(
                {"status": "error", "error_code": "unsafe_configuration", "secret_exposed": "NO"}
            )
        )
        raise SystemExit(2) from None
    result = asyncio.run(check_source(settings, args.platform, args.query, enrich=args.enrich))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "online" else 2)


if __name__ == "__main__":
    main()
