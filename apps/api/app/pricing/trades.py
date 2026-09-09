from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

ZERO = Decimal(0)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class TradeItemValue:
    market_hash_name: str
    quantity: int = 1
    platform_unit_value: Decimal | None = None
    real_unit_cash_value_eur: Decimal | None = None


@dataclass(frozen=True)
class TradeQuoteInput:
    platform: str
    given_items: tuple[TradeItemValue, ...]
    received_items: tuple[TradeItemValue, ...]
    fees_eur: Decimal
    display_currency: str
    created_at: datetime
    expires_at: datetime | None
    source_quality: int
    valuation_confidence: int


@dataclass(frozen=True)
class TradeQuoteResult:
    platform_given_value: Decimal | None
    platform_received_value: Decimal | None
    real_given_cash_value_eur: Decimal | None
    real_received_cash_value_eur: Decimal | None
    fees_eur: Decimal
    net_cash_difference_eur: Decimal | None
    real_value_ratio: Decimal | None
    effective_spread_percent: Decimal | None
    confidence: int
    warnings: tuple[str, ...]


def evaluate_trade_quote(
    values: TradeQuoteInput, *, now: datetime | None = None
) -> TradeQuoteResult:
    current = _aware(now or datetime.now(UTC))
    if not values.platform.strip():
        raise ValueError("La plateforme de trade est requise.")
    if not values.given_items or not values.received_items:
        raise ValueError("Les deux côtés du trade doivent contenir au moins un item.")
    if len(values.display_currency) != 3 or not values.display_currency.isalpha():
        raise ValueError("La devise d'affichage doit contenir trois lettres.")
    _non_negative(values.fees_eur, "fees_eur")
    if not 0 <= values.source_quality <= 100 or not 0 <= values.valuation_confidence <= 100:
        raise ValueError("Qualité de source et confiance doivent être comprises entre 0 et 100.")
    created_at = _aware(values.created_at)
    if created_at > current:
        raise ValueError("Une quote ne peut pas être créée dans le futur.")
    if values.expires_at is not None and _aware(values.expires_at) < created_at:
        raise ValueError("Une quote ne peut pas expirer avant sa création.")
    for item in (*values.given_items, *values.received_items):
        _validate_item(item)

    platform_given = _complete_total(values.given_items, "platform_unit_value")
    platform_received = _complete_total(values.received_items, "platform_unit_value")
    cash_given = _complete_total(values.given_items, "real_unit_cash_value_eur")
    cash_received = _complete_total(values.received_items, "real_unit_cash_value_eur")
    warnings: list[str] = []
    if (
        platform_given is not None
        and platform_received is not None
        and platform_given == platform_received
    ):
        warnings.append("Valeurs plateforme égales : cela n'implique pas des valeurs cash égales.")
    if cash_given is None or cash_received is None:
        warnings.append(
            "Valorisation cash incomplète : spread et différence nette laissés inconnus."
        )
    if values.expires_at is not None and _aware(values.expires_at) < current:
        warnings.append("Quote expirée.")

    if cash_given is not None and cash_received is not None:
        net_cash = cash_received - cash_given - values.fees_eur
        ratio = cash_received / cash_given if cash_given else None
        spread = (
            (cash_given + values.fees_eur - cash_received) / cash_given * HUNDRED
            if cash_given
            else None
        )
    else:
        net_cash = None
        ratio = None
        spread = None
    completeness = _cash_completeness((*values.given_items, *values.received_items))
    confidence = round(
        min(values.source_quality, values.valuation_confidence)
        * (Decimal("0.5") + completeness / 2)
    )
    return TradeQuoteResult(
        platform_given_value=platform_given,
        platform_received_value=platform_received,
        real_given_cash_value_eur=cash_given,
        real_received_cash_value_eur=cash_received,
        fees_eur=values.fees_eur,
        net_cash_difference_eur=net_cash,
        real_value_ratio=ratio,
        effective_spread_percent=spread,
        confidence=confidence,
        warnings=tuple(warnings),
    )


def _complete_total(items: tuple[TradeItemValue, ...], field: str) -> Decimal | None:
    values = [getattr(item, field) for item in items]
    if any(value is None for value in values):
        return None
    return sum(
        (
            value * item.quantity
            for item, value in zip(items, values, strict=True)
            if value is not None
        ),
        ZERO,
    )


def _cash_completeness(items: tuple[TradeItemValue, ...]) -> Decimal:
    known = sum(item.real_unit_cash_value_eur is not None for item in items)
    return Decimal(known) / Decimal(len(items))


def _validate_item(item: TradeItemValue) -> None:
    if not item.market_hash_name.strip():
        raise ValueError("Le nom de marché d'un item est requis.")
    if item.quantity <= 0:
        raise ValueError("La quantité d'un item doit être strictement positive.")
    for field in ("platform_unit_value", "real_unit_cash_value_eur"):
        value = getattr(item, field)
        if value is not None:
            _non_negative(value, field)


def _non_negative(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} doit être un Decimal fini positif ou nul.")
    return value


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
