from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import FXRate
from app.pricing.finance import ExchangeRate
from app.schemas.api import FXReferenceRate, FXStatus


def reference_rate(
    currency: str,
    settings: Settings,
    session: Session | None = None,
    now: datetime | None = None,
) -> ExchangeRate | None:
    code = currency.upper()
    if session is not None:
        current = now or datetime.now(UTC)
        stored = session.scalar(
            select(FXRate)
            .where(
                FXRate.base_currency == "EUR",
                FXRate.quote_currency == code,
                FXRate.rate_type == "REFERENCE",
                FXRate.observed_at <= current,
            )
            .order_by(FXRate.observed_at.desc())
            .limit(1)
        )
        if stored is not None:
            timestamp = (
                stored.observed_at.replace(tzinfo=UTC)
                if stored.observed_at.tzinfo is None
                else stored.observed_at
            )
            return ExchangeRate(
                currency=code,
                eur_per_unit=Decimal(1) / stored.rate,
                timestamp=timestamp,
                source=stored.source,
            )
    if code == "USD" and settings.fx_usd_eur_rate is not None:
        if settings.fx_rate_timestamp is not None and settings.fx_rate_source is not None:
            return ExchangeRate(
                currency=code,
                eur_per_unit=settings.fx_usd_eur_rate,
                timestamp=settings.fx_rate_timestamp,
                source=settings.fx_rate_source,
            )
    return None


def normalize_price(
    amount: Decimal,
    currency: str,
    settings: Settings,
    now: datetime,
    session: Session | None = None,
) -> tuple[Decimal | None, Decimal | None, datetime | None, str | None]:
    if currency == "EUR":
        return amount, Decimal(1), now, "identity:EUR"
    rate = reference_rate(currency, settings, session, now)
    if rate is None:
        return None, None, None, None
    try:
        converted = rate.convert(amount, now=now, max_age_hours=settings.fx_max_age_hours)
    except ValueError:
        return None, None, None, None
    return converted, rate.eur_per_unit, rate.timestamp, rate.source


def build_fx_status(
    session: Session,
    settings: Settings,
    scheduler: object,
) -> FXStatus:
    rates: list[FXReferenceRate] = []
    for currency in ("USD", "GBP", "JPY", "CHF", "CNY"):
        stored = session.scalar(
            select(FXRate)
            .where(
                FXRate.base_currency == "EUR",
                FXRate.quote_currency == currency,
                FXRate.rate_type == "REFERENCE",
            )
            .order_by(FXRate.observed_at.desc())
            .limit(1)
        )
        if stored is None:
            continue
        observed_at = (
            stored.observed_at.replace(tzinfo=UTC)
            if stored.observed_at.tzinfo is None
            else stored.observed_at
        )
        rates.append(
            FXReferenceRate(
                currency=currency,
                currency_per_eur=stored.rate,
                eur_per_unit=Decimal(1) / stored.rate,
                source=stored.source,
                observed_at=observed_at,
            )
        )
    return FXStatus(
        sync_enabled=settings.fx_reference_sync_enabled,
        scheduler_running=bool(getattr(scheduler, "running", False)),
        runtime_status=str(getattr(scheduler, "runtime_status", "unavailable")),
        last_attempt_at=getattr(scheduler, "last_attempt_at", None),
        last_success_at=getattr(scheduler, "last_success_at", None),
        last_error=getattr(scheduler, "last_error", None),
        next_run_at=getattr(scheduler, "next_run_at", None),
        rates=rates,
    )
