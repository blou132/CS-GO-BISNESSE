from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def non_negative(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} doit être un Decimal fini positif ou nul.")
    return value


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Fee:
    rate_percent: Decimal = ZERO
    fixed: Decimal = ZERO

    def amount(self, base: Decimal) -> Decimal:
        non_negative(base, "base")
        non_negative(self.rate_percent, "rate_percent")
        non_negative(self.fixed, "fixed")
        if self.rate_percent > HUNDRED:
            raise ValueError("Un taux de frais ne peut pas dépasser 100 %.")
        return base * self.rate_percent / HUNDRED + self.fixed


@dataclass(frozen=True)
class ProfitInput:
    purchase_price: Decimal
    sale_price: Decimal
    purchase_fee: Decimal = ZERO
    payment_fee: Decimal = ZERO
    fx_fee: Decimal = ZERO
    trade_fee: Decimal = ZERO
    sale_fee: Decimal = ZERO
    withdrawal_fee: Decimal = ZERO


@dataclass(frozen=True)
class ProfitResult:
    total_cost: Decimal
    net_revenue: Decimal
    net_profit: Decimal
    roi: Decimal | None


def calculate_profit(values: ProfitInput) -> ProfitResult:
    """Tous les montants sont déjà exprimés dans la même devise comptable."""
    for name in values.__dataclass_fields__:
        non_negative(getattr(values, name), name)
    total = (
        values.purchase_price
        + values.purchase_fee
        + values.payment_fee
        + values.fx_fee
        + values.trade_fee
    )
    revenue = values.sale_price - values.sale_fee - values.withdrawal_fee
    profit = revenue - total
    return ProfitResult(total, revenue, profit, profit / total * HUNDRED if total else None)


@dataclass(frozen=True)
class ExchangeRate:
    currency: str
    eur_per_unit: Decimal
    timestamp: datetime
    source: str
    kind: str = "reference"

    def convert(
        self,
        amount: Decimal,
        *,
        now: datetime | None = None,
        max_age_hours: int = 72,
    ) -> Decimal:
        non_negative(amount, "amount")
        if not self.eur_per_unit.is_finite() or self.eur_per_unit <= ZERO:
            raise ValueError("Le taux doit être strictement positif et fini.")
        if not self.source.strip() or self.timestamp.tzinfo is None:
            raise ValueError("La source et la date avec fuseau sont requises.")
        if self.kind not in {"reference", "effective"}:
            raise ValueError("Type de taux inconnu.")
        current = now or datetime.now(UTC)
        age = current - self.timestamp
        if age < timedelta(0) or age > timedelta(hours=max_age_hours):
            raise ValueError("Taux futur ou périmé.")
        return amount * self.eur_per_unit


def effective_purchase_cost(amount: Decimal, rate: ExchangeRate) -> Decimal:
    if rate.kind != "effective":
        raise ValueError("Un taux de référence ne représente pas un coût de transaction réel.")
    return rate.convert(amount)
