import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, unquote

import httpx
from nacl.signing import SigningKey
from pydantic import JsonValue

from .base import (
    AdapterBuyOrder,
    AdapterFeeSchedule,
    AdapterItem,
    AdapterListing,
    AdapterObservation,
    AdapterRealizedSale,
    AdapterResult,
    AdapterSticker,
    ConfigurationError,
    MarketAdapter,
    MarketAdapterError,
    UnsupportedCapabilityError,
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


class DMarketAdapter(MarketAdapter):
    market = "DMARKET"

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._public_key = public_key
        self._secret_key = secret_key
        self._http = ReadOnlyHTTP(self.market, "https://api.dmarket.com", client=client)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _sign(self, request: httpx.Request) -> None:
        if not self._public_key or not self._secret_key:
            raise ConfigurationError("Clés DMARKET_PUBLIC_KEY et DMARKET_SECRET_KEY requises.")
        try:
            public = bytes.fromhex(self._public_key)
            secret = bytes.fromhex(self._secret_key)
            if len(public) != 32 or len(secret) not in (32, 64):
                raise ValueError("Invalid Ed25519 key size")
            signing_key = SigningKey(secret[:32])
            if bytes(signing_key.verify_key) != public:
                raise ValueError("Mismatched Ed25519 keys")
            if len(secret) == 64 and secret[32:] != public:
                raise ValueError("Invalid Ed25519 secret suffix")
        except (ValueError, TypeError):
            raise ConfigurationError("Invalid DMarket Ed25519 key configuration") from None
        timestamp = str(int(time.time()))
        raw_path_query = request.url.raw_path.decode("ascii")
        raw_path, separator, raw_query = raw_path_query.partition("?")
        # DMarket requires decoded path parameters and the exact encoded query string.
        path_query = unquote(raw_path) + (separator + raw_query if separator else "")
        message = (request.method + path_query + timestamp).encode("utf-8")
        signature = signing_key.sign(message).signature.hex()
        request.headers.update(
            {
                "X-Api-Key": public.hex(),
                "X-Sign-Date": timestamp,
                "X-Request-Sign": "dmar ed25519 " + signature,
            }
        )

    async def search_items(self, query: str) -> AdapterResult:
        query = check_query(query)
        params: dict[str, str | int] = {
            "gameId": "a8db",
            "limit": 50,
            "orderBy": "price",
            "orderDir": "asc",
        }
        if query:
            params["title"] = query
        response = await self._http.get("/marketplace-api/v2/offers", params, signer=self._sign)
        payload = response.payload
        if not isinstance(payload, dict):
            raise MarketAdapterError("invalid_response", "Invalid DMarket response object")
        rows = array_value(payload.get("items"))
        result = AdapterResult(
            warnings=[
                "DMarket: première page uniquement, 50 offres maximum; "
                "recherche par préfixe du titre."
            ]
        )
        for row in rows:
            try:
                result.listings.append(self._listing(row, response.observed_at))
            except (KeyError, TypeError, ValueError):
                result.warnings.append("DMarket: offre invalide ou verrouillée ignorée.")
        if rows and not result.listings:
            raise MarketAdapterError("invalid_response", "No valid DMarket offers")
        if query and any(row.item.market_hash_name == query for row in result.listings):
            result.buy_orders.extend(await self.get_buy_orders(query))
            result.realized_sales.extend(await self.get_last_sales(query))
            result.fee_schedules.extend(await self.get_fee_schedules())
        return result

    async def get_listing(self, external_id: str) -> AdapterListing:
        raise UnsupportedCapabilityError("DMarket v2 docs provide no individual offer GET endpoint")

    async def get_market_stats(self, query: str) -> list[AdapterObservation]:
        return [listing_observation(row) for row in (await self.search_items(query)).listings]

    async def get_buy_orders(self, market_hash_name: str) -> list[AdapterBuyOrder]:
        market_hash_name = check_query(market_hash_name)
        if not market_hash_name:
            return []
        path = f"/marketplace-api/v1/targets-by-title/a8db/{quote(market_hash_name, safe='')}"
        response = await self._http.get(path, signer=self._sign)
        payload = object_value(response.payload)
        result: list[AdapterBuyOrder] = []
        for value in array_value(payload.get("orders")):
            try:
                row = object_value(value)
                title = row["title"]
                if title != market_hash_name:
                    raise ValueError("Unexpected target title")
                result.append(
                    AdapterBuyOrder(
                        market_hash_name=title,
                        price=cents(row["price"]),
                        currency="USD",
                        quantity=_non_negative_int(row["amount"]),
                        observed_at=response.observed_at,
                        attributes=object_value(row.get("attributes", {})),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return result

    async def get_last_sales(self, market_hash_name: str) -> list[AdapterRealizedSale]:
        market_hash_name = check_query(market_hash_name)
        if not market_hash_name:
            return []
        response = await self._http.get(
            "/trade-aggregator/v1/last-sales",
            {"gameId": "a8db", "title": market_hash_name, "limit": 20},
            signer=self._sign,
        )
        payload = object_value(response.payload)
        result: list[AdapterRealizedSale] = []
        for value in array_value(payload.get("sales")):
            try:
                row = object_value(value)
                offer_attributes = object_value(row.get("offerAttributes", {}))
                order_attributes = object_value(row.get("orderAttributes", {}))
                sold_at = datetime.fromtimestamp(_non_negative_int(row["date"]), UTC)
                result.append(
                    AdapterRealizedSale(
                        market_hash_name=market_hash_name,
                        item=_sale_item(market_hash_name, offer_attributes),
                        price=_decimal_amount(row["price"]),
                        currency="USD",
                        sold_at=sold_at,
                        observed_at=response.observed_at,
                        transaction_type=row.get("txOperationType"),
                        attributes={
                            "offer": _json_safe(offer_attributes),
                            "order": _json_safe(order_attributes),
                            "identity_basis": "documented_fields",
                        },
                    )
                )
            except (KeyError, TypeError, ValueError, OSError, OverflowError):
                continue
        return result

    async def get_fee_schedules(self) -> list[AdapterFeeSchedule]:
        response = await self._http.get(
            "/exchange/v1/customized-fees",
            {"gameId": "a8db", "offerType": "dmarket", "limit": 100, "offset": 0},
            signer=self._sign,
        )
        payload = object_value(response.payload)
        verified_at = response.observed_at
        result: list[AdapterFeeSchedule] = []
        default = object_value(payload["defaultFee"])
        result.append(
            AdapterFeeSchedule(
                platform="dmarket",
                fee_type="SELL",
                rate=_fraction(default["fraction"]),
                minimum_fee=cents(default["minAmount"]),
                currency="USD",
                source="https://docs.dmarket.com/v1/swagger.html",
                verified_at=verified_at,
                valid_from=verified_at,
                details={"offer_type": "dmarket", "scope": "default"},
            )
        )
        for value in array_value(payload.get("reducedFees")):
            try:
                row = object_value(value)
                result.append(
                    AdapterFeeSchedule(
                        platform="dmarket",
                        fee_type="SELL",
                        rate=_fraction(row["fraction"]),
                        currency="USD",
                        min_amount=cents(row["minPrice"]),
                        max_amount=cents(row["maxPrice"]),
                        applies_to=row["title"],
                        source="https://docs.dmarket.com/v1/swagger.html",
                        verified_at=verified_at,
                        valid_from=verified_at,
                        valid_until=datetime.fromtimestamp(
                            _non_negative_int(row["expiresAt"]), UTC
                        ),
                        details={"offer_type": "dmarket", "scope": "reduced"},
                    )
                )
            except (KeyError, TypeError, ValueError, OSError, OverflowError):
                continue
        return result

    @staticmethod
    def _listing(value: Any, observed_at: datetime) -> AdapterListing:
        row = object_value(value)
        if row.get("locked") is True:
            raise ValueError("Locked offer")
        attributes = object_value(row["attributes"])
        if attributes.get("gameId") != "a8db":
            raise ValueError("Non-CS2 item")
        cs2 = object_value(attributes.get("cs2", {}))
        category = cs2.get("category")
        known_category = category in {"CATEGORY_NORMAL", "CATEGORY_STATTRAK", "CATEGORY_SOUVENIR"}
        phase = cs2.get("phase") or None
        stickers = [
            AdapterSticker(name=sticker["name"], slot=sticker.get("slot"), wear=sticker.get("wear"))
            for sticker in cs2.get("stickers", [])
        ]
        identity = item_identity(
            attributes["title"],
            asset_id=_optional_string(
                attributes.get("steamAssetId") or attributes.get("inGameAssetId")
            ),
            def_index=_optional_int(cs2.get("defIndex")),
            stattrak=(category == "CATEGORY_STATTRAK") if known_category else None,
            souvenir=(category == "CATEGORY_SOUVENIR") if known_category else None,
            float_value=cs2.get("float") or None,
            paint_index=cs2.get("paintIndex"),
            paint_seed=cs2.get("paintSeed"),
            doppler_phase=phase,
            fade_percentage=cs2.get("fadePercent") if "Fade" in attributes["title"] else None,
            rarity=_optional_string(cs2.get("rareInfo")),
            quality=_optional_string(cs2.get("quality")),
            collection=_optional_string(cs2.get("collection")),
            source_attributes={
                name: attributes[name]
                for name in ("productId", "tradeLockDays", "unlockDate")
                if name in attributes and attributes[name] is not None
            },
            inspect_link=cs2.get("inspectInGameUri") or None,
            tradable=attributes.get("tradable"),
            tradable_at=parse_listed_at(attributes.get("unlockDate")),
            stickers=stickers,
        )
        warnings = []
        if attributes.get("tradeLockDays"):
            warnings.append("Steam trade lock: revente/transfert immédiat non garanti.")
        return AdapterListing(
            external_id=row["offerId"],
            item=identity,
            price=cents(row["priceCents"]),
            currency="USD",
            observed_at=observed_at,
            listed_at=parse_listed_at(row.get("createdAt")),
            warnings=warnings,
        )


def _sale_item(name: str, attributes: dict[str, Any]) -> AdapterItem:
    stickers_value = attributes.get("stickers") or []
    stickers = [
        AdapterSticker(name=object_value(sticker)["name"])
        for sticker in array_value(stickers_value)
    ]
    return item_identity(
        name,
        float_value=attributes.get("floatValue"),
        paint_seed=attributes.get("paintSeed"),
        doppler_phase=_optional_string(attributes.get("phaseTitle")),
        stickers=stickers,
    )


def _decimal_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid decimal amount") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amount must be non-negative and finite")
    return amount


def _fraction(value: Any) -> Decimal:
    fraction = _decimal_amount(value)
    if fraction > 1:
        raise ValueError("Fee fraction must not exceed one")
    return fraction


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Invalid integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid integer") from None
    if number < 0 or str(number) != str(value):
        raise ValueError("Invalid non-negative integer")
    return number


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Invalid string value")
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value)


def _json_safe(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _json_safe(item) for key, item in value.items()}
    raise ValueError("Value cannot be represented as JSON")
