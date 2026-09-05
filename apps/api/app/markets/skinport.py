from datetime import UTC, datetime

import httpx

from .base import (
    AdapterListing,
    AdapterObservation,
    AdapterResult,
    MarketAdapter,
    MarketAdapterError,
    UnsupportedCapabilityError,
)
from .http import ReadOnlyHTTP
from .normalize import array_value, check_query, object_value


class SkinportAdapter(MarketAdapter):
    market = "SKINPORT"

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._http = ReadOnlyHTTP(
            self.market,
            "https://api.skinport.com/v1",
            client=client,
            cache_ttl=300,
            min_interval=38,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def search_items(self, query: str) -> AdapterResult:
        query = check_query(query).casefold()
        response = await self._http.get(
            "/items",
            {"app_id": 730, "currency": "EUR", "tradable": "true"},
            headers={"Accept-Encoding": "br"},
        )
        rows = array_value(response.payload)
        result = AdapterResult(
            warnings=[
                "Skinport: minimum des prix affichés agrégés par nom; "
                "aucun exemplaire ni vente réalisée."
            ]
        )
        malformed = 0
        for value in rows:
            try:
                row = object_value(value)
                name = row["market_hash_name"]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Invalid name")
                if query and query not in name.casefold():
                    continue
                if row.get("min_price") is None or row.get("quantity") == 0:
                    continue  # No current offer, so no invented price or listing.
                updated_at = row["updated_at"]
                if isinstance(updated_at, bool) or not isinstance(updated_at, (int, float)):
                    raise ValueError("Invalid update timestamp")
                result.observations.append(
                    AdapterObservation(
                        market_hash_name=name,
                        price=row["min_price"],
                        currency=row["currency"],
                        observation_type="AGGREGATE",
                        timestamp=datetime.fromtimestamp(updated_at, UTC),
                        volume=None,  # quantity is current supply, not sales volume.
                    )
                )
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                malformed += 1
        if malformed:
            result.warnings.append(f"Skinport: {malformed} agrégat(s) invalide(s) ignoré(s).")
        if malformed and malformed == len(rows):
            raise MarketAdapterError("invalid_response", "No valid Skinport aggregate data")
        return result

    async def get_listing(self, external_id: str) -> AdapterListing:
        raise UnsupportedCapabilityError("Skinport REST items provides no individual listings")

    async def get_market_stats(self, query: str) -> list[AdapterObservation]:
        return (await self.search_items(query)).observations
