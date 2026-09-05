from datetime import datetime
from typing import Any

import httpx

from .base import (
    AdapterListing,
    AdapterObservation,
    AdapterResult,
    AdapterSticker,
    ConfigurationError,
    MarketAdapter,
    MarketAdapterError,
)
from .http import ReadOnlyHTTP
from .normalize import (
    array_value,
    cents,
    check_query,
    item_identity,
    listing_observation,
    object_value,
    parse_listed_at,
)


class CSFloatAdapter(MarketAdapter):
    market = "CSFLOAT"

    def __init__(
        self, api_key: str | None = None, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._headers = {"Authorization": api_key} if api_key else {}
        self._http = ReadOnlyHTTP(self.market, "https://csfloat.com/api/v1", client=client)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def search_items(self, query: str) -> AdapterResult:
        if not self._headers:
            raise ConfigurationError("Clé CSFLOAT_API_KEY requise pour l'accès API actuel.")
        query = check_query(query)
        params: dict[str, str | int] = {"limit": 50, "sort_by": "lowest_price", "type": "buy_now"}
        if query:
            params["market_hash_name"] = query
        response = await self._http.get("/listings", params, headers=self._headers)
        payload = response.payload
        rows = array_value(payload.get("data") if isinstance(payload, dict) else payload)
        result = AdapterResult(
            warnings=[
                "CSFloat: première page uniquement, 50 annonces maximum; recherche par nom exact."
            ]
        )
        for row in rows:
            try:
                result.listings.append(self._listing(row, response.observed_at))
            except (KeyError, TypeError, ValueError):
                result.warnings.append("CSFloat: annonce invalide, inactive ou enchère ignorée.")
        if rows and not result.listings:
            raise MarketAdapterError("invalid_response", "No valid active CSFloat listings")
        return result

    async def get_listing(self, external_id: str) -> AdapterListing:
        if not self._headers:
            raise ConfigurationError("Clé CSFLOAT_API_KEY requise pour l'accès API actuel.")
        if not external_id.isascii() or not external_id.isdigit() or len(external_id) > 30:
            raise MarketAdapterError("invalid_query", "Invalid CSFloat listing identifier")
        response = await self._http.get(f"/listings/{external_id}", headers=self._headers)
        try:
            return self._listing(response.payload, response.observed_at)
        except (KeyError, TypeError, ValueError):
            raise MarketAdapterError(
                "invalid_response", "Invalid or inactive CSFloat listing"
            ) from None

    async def get_market_stats(self, query: str) -> list[AdapterObservation]:
        return [listing_observation(row) for row in (await self.search_items(query)).listings]

    @staticmethod
    def _listing(value: Any, observed_at: datetime) -> AdapterListing:
        row = object_value(value)
        if row.get("type") != "buy_now" or row.get("state") != "listed":
            raise ValueError("Only active fixed-price listings are supported")
        item = object_value(row["item"])
        stickers = [
            AdapterSticker(name=sticker["name"], slot=sticker.get("slot"), wear=sticker.get("wear"))
            for sticker in item.get("stickers", [])
        ]
        identity = item_identity(
            item["market_hash_name"],
            exterior=item.get("wear_name"),
            stattrak=item.get("is_stattrak"),
            souvenir=item.get("is_souvenir"),
            float_value=item.get("float_value"),
            paint_index=item.get("paint_index"),
            paint_seed=item.get("paint_seed"),
            inspect_link=item.get("inspect_link"),
            stickers=stickers,
        )
        identifier = row["id"]
        if not isinstance(identifier, str) or not identifier.isascii() or not identifier.isdigit():
            raise ValueError("Invalid listing id")
        return AdapterListing(
            external_id=identifier,
            item=identity,
            price=cents(row["price"]),
            currency="USD",
            listing_url=f"https://csfloat.com/item/{identifier}",
            observed_at=observed_at,
            listed_at=parse_listed_at(row.get("created_at")),
        )
