"""Bounded read-only public-source smoke; no database, credentials or transactions."""

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from app.currencies.ecb import ECBRateClient, ECBRateError
from app.markets.base import MarketAdapterError
from app.markets.skinport import SkinportAdapter
from app.pricing.finance import ExchangeRate
from app.pricing.valuation import MarketEvidence, calculate_liquidity, calculate_reference_price
from app.services.analysis import _liquidity_input


async def main(query):
    adapter, ecb = SkinportAdapter(), ECBRateClient()
    report = {"checked_at": datetime.now(UTC).isoformat(), "database_written": False,
              "transaction_executed": False, "query": query}
    try:
        async with asyncio.timeout(120):
            result = await adapter.search_items(query)
        evidence = [MarketEvidence("skinport", "HISTORICAL_MEDIAN", row.median_price,
                                  row.observed_at, volume=row.volume, window=row.window,
                                  price_original=row.median_price, currency=row.currency,
                                  fx_source="identity:EUR", fx_timestamp=row.observed_at,
                                  timestamp_basis="history_collected_at")
                    for row in result.aggregates
                    if row.market_hash_name == query and row.currency == "EUR"
                    and row.median_price and row.volume != 0]
        reference = calculate_reference_price(evidence)
        liquidity = calculate_liquidity(_liquidity_input(evidence, None))
        report["skinport_rest"] = {
            "status": "degraded" if result.partial_errors else "online",
            "observations": len(result.observations), "aggregates": len(result.aggregates),
            "individual_listings": len(result.listings), "partial_errors": result.partial_errors,
            "reference": asdict(reference) if reference else None,
            "liquidity": asdict(liquidity) if liquidity else None,
            "profit": None, "fees": "UNKNOWN", "executable_opportunity": False,
            "http_requests": list(adapter._http.diagnostics),
        }
    except (MarketAdapterError, TimeoutError) as error:
        report["skinport_rest"] = {"status": "error", "code": getattr(error, "code", "timeout")}
    try:
        rates = await ecb.fetch_latest()
        conversions = []
        for rate in rates:
            fx = ExchangeRate(currency=rate.currency, eur_per_unit=Decimal(1) / rate.currency_per_eur,
                              timestamp=rate.observed_at, source="ECB Data Portal EXR daily reference rates")
            conversions.append({"currency": rate.currency, "date": rate.observed_at,
                                "original_amount": "100", "source": fx.source,
                                "reference_eur_for_100": fx.convert(Decimal(100), now=datetime.now(UTC), max_age_hours=120),
                                "effective_fx": None})
        report["fx"] = conversions
    except (ECBRateError, ValueError):
        report["fx"] = {"status": "unavailable_or_stale"}
    finally:
        await adapter.aclose()
        await ecb.aclose()
    print(json.dumps(report, default=str, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required to contact public official APIs")
    asyncio.run(main(args.query))
