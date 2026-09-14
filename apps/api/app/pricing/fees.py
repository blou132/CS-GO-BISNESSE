from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

FeeType = Literal["BUY", "SELL", "DEPOSIT", "WITHDRAW", "TRADE", "PAYMENT", "FX"]
ZERO = Decimal(0)
MAX_FEE_AGE = timedelta(days=7)


@dataclass(frozen=True)
class FeeRule:
    platform: str
    fee_type: FeeType
    rate: Decimal | None
    fixed_amount: Decimal | None
    minimum_fee: Decimal | None
    currency: str | None
    min_amount: Decimal | None
    max_amount: Decimal | None
    applies_to: str | None
    source: str
    verified_at: datetime
    valid_from: datetime
    valid_until: datetime | None = None


@dataclass(frozen=True)
class FeeCalculation:
    platform: str
    fee_type: FeeType
    base_amount: Decimal
    fee_amount: Decimal
    currency: str
    rate: Decimal | None
    fixed_amount: Decimal | None
    minimum_fee: Decimal | None
    minimum_applied: bool
    applies_to: str | None
    source: str
    verified_at: datetime


def calculate_fee(
    base_amount: Decimal,
    currency: str,
    platform: str,
    fee_type: FeeType,
    rules: Sequence[FeeRule],
    *,
    item_name: str | None = None,
    at: datetime | None = None,
    max_age: timedelta = MAX_FEE_AGE,
) -> FeeCalculation | None:
    _non_negative(base_amount, "base_amount")
    code = currency.upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("La devise doit être un code ISO alphabétique sur trois lettres.")
    if not platform.strip():
        raise ValueError("La plateforme est requise.")
    current = _aware(at or datetime.now(UTC))
    if max_age <= timedelta(0):
        raise ValueError("La fraîcheur maximale des frais doit être positive.")
    candidates: list[FeeRule] = []
    for rule in rules:
        _validate_rule(rule)
        if rule.platform != platform or rule.fee_type != fee_type:
            continue
        if not timedelta(0) <= current - _aware(rule.verified_at) <= max_age:
            continue
        if rule.currency is not None and rule.currency != code:
            continue
        if rule.applies_to is not None and rule.applies_to != item_name:
            continue
        if _aware(rule.valid_from) > current:
            continue
        if rule.valid_until is not None and _aware(rule.valid_until) < current:
            continue
        if rule.min_amount is not None and base_amount < rule.min_amount:
            continue
        if rule.max_amount is not None and base_amount > rule.max_amount:
            continue
        candidates.append(rule)
    if not candidates:
        return None
    candidates.sort(
        key=lambda rule: (
            rule.applies_to is not None,
            _aware(rule.valid_from),
            _aware(rule.verified_at),
        ),
        reverse=True,
    )
    selected = candidates[0]
    priority = (
        selected.applies_to is not None,
        _aware(selected.valid_from),
        _aware(selected.verified_at),
    )
    for candidate in candidates[1:]:
        if (
            candidate.applies_to is not None,
            _aware(candidate.valid_from),
            _aware(candidate.verified_at),
        ) != priority:
            break
        if (candidate.rate, candidate.fixed_amount, candidate.minimum_fee) != (
            selected.rate,
            selected.fixed_amount,
            selected.minimum_fee,
        ):
            return None  # Conflicting equally applicable terms must not depend on row order.
    variable = base_amount * selected.rate if selected.rate is not None else ZERO
    fixed = selected.fixed_amount or ZERO
    amount = variable + fixed
    minimum_applied = selected.minimum_fee is not None and amount < selected.minimum_fee
    if minimum_applied:
        amount = selected.minimum_fee or amount
    return FeeCalculation(
        platform=platform,
        fee_type=fee_type,
        base_amount=base_amount,
        fee_amount=amount,
        currency=code,
        rate=selected.rate,
        fixed_amount=selected.fixed_amount,
        minimum_fee=selected.minimum_fee,
        minimum_applied=minimum_applied,
        applies_to=selected.applies_to,
        source=selected.source,
        verified_at=_aware(selected.verified_at),
    )


def _validate_rule(rule: FeeRule) -> None:
    if not rule.platform.strip() or not rule.source.strip():
        raise ValueError("Une règle de frais exige plateforme et source.")
    if rule.rate is None and rule.fixed_amount is None:
        raise ValueError("Une règle de frais exige un taux ou un montant fixe.")
    if rule.rate is not None and (not rule.rate.is_finite() or not ZERO <= rule.rate <= 1):
        raise ValueError("Le taux de frais doit être compris entre 0 et 1.")
    for name in ("fixed_amount", "minimum_fee", "min_amount", "max_amount"):
        value = getattr(rule, name)
        if value is not None:
            _non_negative(value, name)
    if (
        rule.min_amount is not None
        and rule.max_amount is not None
        and rule.min_amount > rule.max_amount
    ):
        raise ValueError("La tranche minimale ne peut pas dépasser la tranche maximale.")
    if rule.currency is not None and (
        len(rule.currency) != 3
        or not rule.currency.isalpha()
        or rule.currency != rule.currency.upper()
    ):
        raise ValueError("La devise d'une règle doit être un code ISO majuscule.")
    if rule.currency is None and (
        rule.fixed_amount is not None
        or rule.minimum_fee is not None
        or rule.min_amount is not None
        or rule.max_amount is not None
    ):
        raise ValueError("Une composante monétaire exige une devise explicite.")
    if rule.valid_until is not None and _aware(rule.valid_until) < _aware(rule.valid_from):
        raise ValueError("La fin de validité précède le début de validité.")


def _non_negative(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} doit être un Decimal fini positif ou nul.")
    return value


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
