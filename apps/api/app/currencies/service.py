from datetime import datetime
from decimal import Decimal

from app.core.config import Settings
from app.pricing.finance import ExchangeRate


def reference_rate(currency: str, settings: Settings) -> ExchangeRate | None:
    if currency != "USD" or settings.fx_usd_eur_rate is None:
        return None
    if settings.fx_rate_timestamp is None or settings.fx_rate_source is None:
        return None
    return ExchangeRate(
        currency=currency,
        eur_per_unit=settings.fx_usd_eur_rate,
        timestamp=settings.fx_rate_timestamp,
        source=settings.fx_rate_source,
    )


def normalize_price(
    amount: Decimal,
    currency: str,
    settings: Settings,
    now: datetime,
) -> tuple[Decimal | None, Decimal | None, datetime | None, str | None]:
    if currency == "EUR":
        return amount, Decimal(1), now, "identity:EUR"
    rate = reference_rate(currency, settings)
    if rate is None:
        return None, None, None, None
    try:
        converted = rate.convert(amount, now=now, max_age_hours=settings.fx_max_age_hours)
    except ValueError:
        return None, None, None, None
    return converted, rate.eur_per_unit, rate.timestamp, rate.source
