from datetime import UTC, datetime
from decimal import Decimal, DecimalException
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from .base import (
    AdapterAggregateStat,
    AdapterItem,
    AdapterListing,
    AdapterObservation,
    AdapterRealizedSale,
    AdapterResult,
    AdapterSticker,
    MarketAdapter,
    MarketAdapterError,
    UnsupportedCapabilityError,
    optional_enrichment,
)
from .http import ReadOnlyHTTP
from .normalize import array_value, check_query, object_value


class SkinportAdapter(MarketAdapter):
    market = "SKINPORT"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        min_interval: float = 38,
    ) -> None:
        self._http = ReadOnlyHTTP(
            self.market,
            "https://api.skinport.com/v1",
            client=client,
            cache_ttl=300,
            min_interval=min_interval,
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
        matched_names: list[str] = []
        for value in rows:
            try:
                row = object_value(value)
                name = row["market_hash_name"]
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Invalid name")
                if query and query not in name.casefold():
                    continue
                matched_names.append(name)
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
        if matched_names:
            names = list(dict.fromkeys(matched_names))[:20]
            result.aggregates.extend(
                await optional_enrichment(result, "sales_history", self.get_sales_history(names))
            )
            if len(set(matched_names)) > 20:
                result.warnings.append("Skinport: historique limité aux 20 premiers noms retenus.")
        return result

    async def get_listing(self, external_id: str) -> AdapterListing:
        raise UnsupportedCapabilityError("Skinport REST items provides no individual listings")

    async def get_market_stats(self, query: str) -> list[AdapterObservation]:
        return (await self.search_items(query)).observations

    async def get_sales_history(
        self,
        market_hash_names: str | list[str],
    ) -> list[AdapterAggregateStat]:
        names = [market_hash_names] if isinstance(market_hash_names, str) else market_hash_names
        names = list(dict.fromkeys(check_query(name) for name in names if name.strip()))
        if not names:
            return []
        if len(names) > 20:
            raise MarketAdapterError("invalid_query", "Skinport history is limited to 20 names")
        response = await self._http.get(
            "/sales/history",
            {
                "app_id": 730,
                "currency": "EUR",
                "market_hash_name": ",".join(names),
            },
            headers={"Accept-Encoding": "br"},
        )
        rows = array_value(response.payload)
        result: list[AdapterAggregateStat] = []
        periods = {
            "last_24_hours": "24H",
            "last_7_days": "7D",
            "last_30_days": "30D",
            "last_90_days": "90D",
        }
        for value in rows:
            try:
                row = object_value(value)
                name = row["market_hash_name"]
                currency = row["currency"]
                if name not in names or currency != "EUR":
                    raise ValueError("Invalid Skinport history identity")
                for source_window, window in periods.items():
                    stats = row.get(source_window)
                    if stats is None:
                        continue
                    period = object_value(stats)
                    result.append(
                        AdapterAggregateStat(
                            market_hash_name=name,
                            window=window,
                            min_price=period.get("min"),
                            max_price=period.get("max"),
                            avg_price=period.get("avg"),
                            median_price=period.get("median"),
                            volume=period.get("volume"),
                            currency=currency,
                            observed_at=response.observed_at,
                        )
                    )
            except (KeyError, TypeError, ValueError):
                continue
        if rows and not result:
            raise MarketAdapterError("invalid_response", "No valid Skinport history data")
        return result


def normalize_sale_feed(
    value: Any,
    observed_at: datetime,
    *,
    price_unit: Literal["unverified", "minor", "major"] = "unverified",
    price_unit_source: str = "",
) -> AdapterResult:
    payload = object_value(value)
    event_type = payload.get("eventType")
    if not isinstance(event_type, str) or event_type not in {"listed", "sold"}:
        raise ValueError("Unsupported Skinport sale feed event")
    if price_unit == "unverified" or not price_unit_source.startswith("https://"):
        raise ValueError("unverified_price_unit")
    rows = array_value(payload.get("sales"))
    result = AdapterResult()
    for value in rows:
        try:
            row = object_value(value)
            external_id = _string_identifier(row.get("saleId"))
            if not external_id.isascii() or not external_id.isdecimal() or int(external_id) <= 0:
                raise ValueError("Invalid sale ID")
            if row.get("appid") != 730 or row.get("currency") != "EUR":
                raise ValueError("Unexpected feed game or currency")
            if row.get("saleStatus") not in {None, event_type}:
                raise ValueError("Conflicting sale status")
            currency = row["currency"]
            name = row["marketHashName"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Missing Skinport item name")
            item = AdapterItem(
                market_hash_name=name,
                asset_id=_optional_identifier(row.get("assetid")),
                float_value=row.get("wear"),
                paint_index=row.get("finish"),
                paint_seed=row.get("pattern"),
                exterior=row.get("exterior"),
                stattrak=row.get("stattrak"),
                souvenir=row.get("souvenir"),
                rarity=row.get("rarity"),
                quality=row.get("quality"),
                collection=row.get("collection"),
                inspect_link=row.get("link"),
                source_attributes={
                    **_source_attributes(row),
                    "timestamp_basis": "feed_observed_at",
                    "price_unit": price_unit,
                    "price_unit_source": price_unit_source,
                },
                stickers=_stickers(row.get("stickers")),
                tradable_at=datetime.fromisoformat(row["lock"].replace("Z", "+00:00"))
                if isinstance(row.get("lock"), str)
                else None,
            )
            raw_price = row["salePrice"]
            if isinstance(raw_price, bool) or (
                price_unit == "minor" and not isinstance(raw_price, int)
            ):
                raise ValueError("Invalid price unit")
            price = Decimal(str(raw_price)) / (100 if price_unit == "minor" else 1)
            if not price.is_finite() or not 0 < price <= Decimal("999999999999.99999999"):
                raise ValueError("Invalid price")
            url = row.get("url")
            listing_url = (
                url
                if isinstance(url, str)
                and urlparse(url).scheme == "https"
                and urlparse(url).netloc == "skinport.com"
                else None
            )
            if event_type == "listed":
                result.listings.append(
                    AdapterListing(
                        external_id=external_id,
                        item=item,
                        price=price,
                        currency=currency,
                        listing_url=listing_url,
                        warnings=["Horodatage de reception du feed ; annonce non revalidee."],
                        observed_at=observed_at,
                    )
                )
            else:
                result.realized_sales.append(
                    AdapterRealizedSale(
                        external_id=external_id,
                        market_hash_name=name,
                        item=item,
                        price=price,
                        currency=currency,
                        sold_at=observed_at,
                        observed_at=observed_at,
                        transaction_type=row.get("saleType"),
                        attributes={
                            **_source_attributes(row),
                            "timestamp_basis": "feed_observed_at",
                            "price_unit": price_unit,
                            "price_unit_source": price_unit_source,
                        },
                    )
                )
        except (KeyError, TypeError, ValueError, DecimalException):
            result.warnings.append("Skinport feed: événement incomplet ignoré.")
    return result


def _string_identifier(value: Any) -> str:
    identifier = _optional_identifier(value)
    if identifier is None:
        raise ValueError("Missing identifier")
    return identifier


def _optional_identifier(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Invalid identifier")
    return str(value)


def _stickers(value: Any) -> list[AdapterSticker]:
    if value is None:
        return []
    return [
        AdapterSticker(
            name=object_value(sticker)["name"],
            slot=object_value(sticker).get("slot"),
            wear=object_value(sticker).get("wear"),
        )
        for sticker in array_value(value)
    ]


def _source_attributes(row: dict[str, Any]) -> dict[str, str | int | bool | None]:
    names = ("productId", "itemId", "saleStatus", "saleType", "lock")
    result: dict[str, str | int | bool | None] = {}
    for name in names:
        if name not in row:
            continue
        value = row[name]
        if isinstance(value, (str, int, bool)) or value is None:
            result[name] = value
    return result
