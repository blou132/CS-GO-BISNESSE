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


@dataclass(frozen=True)
class PurchaseCostInput:
    item_price_eur: Decimal
    purchase_fee_eur: Decimal = ZERO
    payment_fee_eur: Decimal = ZERO
    fx_fee_eur: Decimal = ZERO
    deposit_fee_eur: Decimal = ZERO
    trade_fee_eur: Decimal = ZERO


@dataclass(frozen=True)
class PurchaseCostBreakdown:
    item_price_eur: Decimal
    purchase_fee_eur: Decimal
    payment_fee_eur: Decimal
    fx_fee_eur: Decimal
    deposit_fee_eur: Decimal
    trade_fee_eur: Decimal
    total_cost_eur: Decimal


@dataclass(frozen=True)
class SaleRevenueInput:
    estimated_sale_price_eur: Decimal
    sale_fee_eur: Decimal = ZERO
    withdrawal_fee_eur: Decimal = ZERO
    fx_fee_eur: Decimal = ZERO
    trade_fee_eur: Decimal = ZERO


@dataclass(frozen=True)
class SaleRevenueBreakdown:
    estimated_sale_price_eur: Decimal
    sale_fee_eur: Decimal
    withdrawal_fee_eur: Decimal
    fx_fee_eur: Decimal
    trade_fee_eur: Decimal
    net_revenue_eur: Decimal


@dataclass(frozen=True)
class NetProfitResult:
    purchase: PurchaseCostBreakdown
    sale: SaleRevenueBreakdown
    net_profit_eur: Decimal
    roi_percent: Decimal | None
    roi_per_day_percent: Decimal | None


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


def calculate_purchase_cost(values: PurchaseCostInput) -> PurchaseCostBreakdown:
    for name in values.__dataclass_fields__:
        non_negative(getattr(values, name), name)
    total = sum((getattr(values, name) for name in values.__dataclass_fields__), ZERO)
    return PurchaseCostBreakdown(**values.__dict__, total_cost_eur=total)


def calculate_sale_revenue(values: SaleRevenueInput) -> SaleRevenueBreakdown:
    for name in values.__dataclass_fields__:
        non_negative(getattr(values, name), name)
    deductions = (
        values.sale_fee_eur + values.withdrawal_fee_eur + values.fx_fee_eur + values.trade_fee_eur
    )
    return SaleRevenueBreakdown(
        **values.__dict__,
        net_revenue_eur=values.estimated_sale_price_eur - deductions,
    )


def calculate_net_profit(
    purchase_input: PurchaseCostInput,
    sale_input: SaleRevenueInput,
    *,
    estimated_holding_days: int | None = None,
) -> NetProfitResult:
    if estimated_holding_days is not None and estimated_holding_days < 0:
        raise ValueError("La durée de détention doit être positive ou nulle.")
    purchase = calculate_purchase_cost(purchase_input)
    sale = calculate_sale_revenue(sale_input)
    profit = sale.net_revenue_eur - purchase.total_cost_eur
    roi = profit / purchase.total_cost_eur * HUNDRED if purchase.total_cost_eur != ZERO else None
    roi_per_day = (
        roi / estimated_holding_days
        if roi is not None and estimated_holding_days is not None and estimated_holding_days > 0
        else None
    )
    return NetProfitResult(purchase, sale, profit, roi, roi_per_day)


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
