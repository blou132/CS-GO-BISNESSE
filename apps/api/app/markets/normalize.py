"""Lossless decimal normalization; absent optional attributes stay unknown."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .base import AdapterItem, AdapterListing, AdapterObservation, MarketAdapterError

EXTERIOR = re.compile(r" \((Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)\)$")


def object_value(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Expected object")
    return value


def array_value(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise MarketAdapterError("invalid_response", "Marketplace response must contain an array")
    return value


def cents(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("Price cents are required")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid price cents") from None
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise ValueError("Price must be non-negative integer cents")
    return amount / Decimal(100)


def item_identity(name: Any, **attributes: Any) -> AdapterItem:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing market hash name")
    match = EXTERIOR.search(name)
    exterior = match.group(1) if match else None
    basic = name[: match.start()] if match else name
    basic = basic.removeprefix("★ ").removeprefix("StatTrak™ ").removeprefix("Souvenir ")
    parts = basic.split(" | ", maxsplit=1)
    return AdapterItem(
        market_hash_name=name,
        weapon=parts[0] if len(parts) == 2 else None,
        skin=parts[1] if len(parts) == 2 else None,
        exterior=attributes.pop("exterior", None) or exterior,
        **attributes,
    )


def listing_observation(listing: AdapterListing) -> AdapterObservation:
    return AdapterObservation(
        market_hash_name=listing.item.market_hash_name,
        price=listing.price,
        currency=listing.currency,
        observation_type="LISTING",
        timestamp=listing.observed_at,
    )


def parse_listed_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid listing timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_query(query: str) -> str:
    query = query.strip()
    if len(query) > 512 or any(ord(char) < 32 for char in query):
        raise MarketAdapterError("invalid_query", "Invalid marketplace search query")
    return query
