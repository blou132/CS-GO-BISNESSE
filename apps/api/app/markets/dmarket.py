import time
from datetime import datetime
from typing import Any

import httpx
from nacl.signing import SigningKey

from .base import (
    AdapterListing,
    AdapterObservation,
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
        # This adapter uses a fixed path. The raw query is signed exactly as transmitted.
        path_query = request.url.raw_path.decode("ascii")
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
        return result

    async def get_listing(self, external_id: str) -> AdapterListing:
        raise UnsupportedCapabilityError("DMarket v2 docs provide no individual offer GET endpoint")

    async def get_market_stats(self, query: str) -> list[AdapterObservation]:
        return [listing_observation(row) for row in (await self.search_items(query)).listings]

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
            stattrak=(category == "CATEGORY_STATTRAK") if known_category else None,
            souvenir=(category == "CATEGORY_SOUVENIR") if known_category else None,
            float_value=cs2.get("float") or None,
            paint_index=cs2.get("paintIndex"),
            paint_seed=cs2.get("paintSeed"),
            doppler_phase=phase,
            fade_percentage=cs2.get("fadePercent") if "Fade" in attributes["title"] else None,
            inspect_link=cs2.get("inspectInGameUri") or None,
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
