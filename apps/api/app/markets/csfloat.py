from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
        self._headers = {"Authorization": api_key.strip()} if api_key and api_key.strip() else {}
        self._http = ReadOnlyHTTP(self.market, "https://csfloat.com/api/v1", client=client)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def search_items(self, query: str) -> AdapterResult:
        return await self.search(CSFloatSearch(market_hash_name=check_query(query) or None))

    async def search(self, filters: "CSFloatSearch") -> AdapterResult:
        if not self._headers:
            raise ConfigurationError("Clé CSFLOAT_API_KEY requise pour l'accès API actuel.")
        params = filters.parameters()
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
        stickers = [_sticker(object_value(sticker)) for sticker in item.get("stickers", [])]
        scm = object_value(item.get("scm", {}))
        tradable, tradable_at = _tradable(item.get("tradable"))
        identity = item_identity(
            item["market_hash_name"],
            asset_id=_optional_string(item.get("asset_id")),
            def_index=_optional_int(item.get("def_index")),
            exterior=item.get("wear_name"),
            stattrak=item.get("is_stattrak"),
            souvenir=item.get("is_souvenir"),
            float_value=item.get("float_value"),
            paint_index=item.get("paint_index"),
            paint_seed=item.get("paint_seed"),
            rarity=_optional_string(item.get("rarity")),
            quality=_optional_string(item.get("quality")),
            collection=_optional_string(item.get("collection")),
            scm_price=cents(scm["price"]) if scm.get("price") is not None else None,
            scm_volume=_optional_int(scm.get("volume")),
            source_attributes={"scm_currency": "USD"} if scm else {},
            inspect_link=item.get("inspect_link"),
            tradable=tradable,
            tradable_at=tradable_at,
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


class CSFloatSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_hash_name: str | None = Field(default=None, max_length=512)
    strategy: Literal["WATCHLIST", "OPPORTUNITY_SCAN", "DISCOVERY"] = "WATCHLIST"
    min_price_cents: int | None = Field(default=None, ge=0, strict=True)
    max_price_cents: int | None = Field(default=None, ge=0, strict=True)
    min_float: float | None = Field(default=None, ge=0, le=1)
    max_float: float | None = Field(default=None, ge=0, le=1)
    paint_seed: int | None = Field(default=None, ge=0, le=1000)
    paint_index: int | None = Field(default=None, ge=0)
    def_index: int | None = Field(default=None, ge=0)
    collection: str | None = Field(default=None, max_length=128)
    category: Literal[0, 1, 2, 3] | None = None
    stickers: str | None = Field(default=None, pattern=r"^\d+(?:\|\d+)?(?:,\d+(?:\|\d+)?)*$")
    sort_by: (
        Literal["lowest_price", "most_recent", "lowest_float", "best_deal", "float_rank"] | None
    ) = None
    limit: int = Field(default=50, ge=1, le=50)

    @model_validator(mode="after")
    def validate_ranges(self) -> "CSFloatSearch":
        for lower, upper in (
            (self.min_price_cents, self.max_price_cents),
            (self.min_float, self.max_float),
        ):
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("Minimum must not exceed maximum")
        return self

    def parameters(self) -> dict[str, str | int | float]:
        strategy_sort = {
            "WATCHLIST": "lowest_price",
            "OPPORTUNITY_SCAN": "best_deal",
            "DISCOVERY": "most_recent",
        }
        params: dict[str, str | int | float] = {
            "limit": min(self.limit, 20) if self.strategy == "DISCOVERY" else self.limit,
            "sort_by": self.sort_by or strategy_sort[self.strategy],
            "type": "buy_now",
        }
        fields = {
            "market_hash_name": self.market_hash_name,
            "min_price": self.min_price_cents,
            "max_price": self.max_price_cents,
            "min_float": self.min_float,
            "max_float": self.max_float,
            "paint_seed": self.paint_seed,
            "paint_index": self.paint_index,
            "def_index": self.def_index,
            "collection": self.collection,
            "category": self.category,
            "stickers": self.stickers,
        }
        params.update({name: value for name, value in fields.items() if value is not None})
        return params


def _sticker(value: dict[str, Any]) -> AdapterSticker:
    scm = object_value(value.get("scm", {}))
    return AdapterSticker(
        name=value["name"],
        slot=value.get("slot"),
        wear=value.get("wear"),
        steam_price=cents(scm["price"]) if scm.get("price") is not None else None,
        steam_volume=_optional_int(scm.get("volume")),
    )


def _tradable(value: Any) -> tuple[bool | None, datetime | None]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None, None
    if value == 0:
        return True, None
    return False, datetime.fromtimestamp(value, UTC)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Invalid string value")
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Invalid integer value")
    return int(value)
