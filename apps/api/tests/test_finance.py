from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.currencies.service import normalize_price
from app.pricing.comparison import float_score, summarize
from app.pricing.finance import (
    ExchangeRate,
    ProfitInput,
    PurchaseCostInput,
    SaleRevenueInput,
    calculate_net_profit,
    calculate_profit,
    effective_purchase_cost,
)
from app.pricing.opportunity import (
    OpportunityComponents,
    OpportunityWeights,
    calculate_opportunity_score,
)


def test_profit_includes_every_fee_and_roi_uses_total_cost() -> None:
    result = calculate_profit(
        ProfitInput(
            purchase_price=Decimal("100"),
            sale_price=Decimal("140"),
            purchase_fee=Decimal("2"),
            payment_fee=Decimal("1"),
            fx_fee=Decimal("3"),
            trade_fee=Decimal("4"),
            sale_fee=Decimal("7"),
            withdrawal_fee=Decimal("2"),
        )
    )
    assert result.total_cost == Decimal("110")
    assert result.net_revenue == Decimal("131")
    assert result.net_profit == Decimal("21")
    assert result.roi == Decimal("21") / Decimal("110") * Decimal("100")


def test_zero_cost_has_no_roi() -> None:
    assert calculate_profit(ProfitInput(Decimal(0), Decimal(0))).roi is None


def test_net_profit_exposes_purchase_and_sale_breakdowns() -> None:
    result = calculate_net_profit(
        PurchaseCostInput(
            item_price_eur=Decimal("100"),
            purchase_fee_eur=Decimal("2"),
            payment_fee_eur=Decimal("1"),
            fx_fee_eur=Decimal("3"),
            deposit_fee_eur=Decimal("4"),
            trade_fee_eur=Decimal("5"),
        ),
        SaleRevenueInput(
            estimated_sale_price_eur=Decimal("150"),
            sale_fee_eur=Decimal("7"),
            withdrawal_fee_eur=Decimal("2"),
            fx_fee_eur=Decimal("1"),
            trade_fee_eur=Decimal("0.50"),
        ),
        estimated_holding_days=5,
    )
    assert result.purchase.total_cost_eur == Decimal("115")
    assert result.sale.net_revenue_eur == Decimal("139.50")
    assert result.net_profit_eur == Decimal("24.50")
    assert result.roi_percent == Decimal("24.50") / Decimal("115") * Decimal("100")
    assert result.roi_per_day_percent == result.roi_percent / Decimal(5)


def test_effective_fx_rejects_reference_rate_and_stale_rate() -> None:
    now = datetime.now(UTC)
    reference = ExchangeRate("USD", Decimal("0.85"), now, "test-source")
    with pytest.raises(ValueError, match="référence"):
        effective_purchase_cost(Decimal("10"), reference)
    stale = ExchangeRate("USD", Decimal("0.85"), now - timedelta(days=4), "test", "effective")
    with pytest.raises(ValueError, match="périmé"):
        stale.convert(Decimal("10"), now=now, max_age_hours=72)


def test_price_normalization_preserves_reference_rate_provenance() -> None:
    now = datetime.now(UTC)
    settings = Settings(
        _env_file=None,
        fx_usd_eur_rate=Decimal("0.85"),
        fx_rate_source="synthetic-test-rate",
        fx_rate_timestamp=now,
    )
    converted, rate, timestamp, source = normalize_price(Decimal("10"), "USD", settings, now)
    assert converted == Decimal("8.50")
    assert rate == Decimal("0.85")
    assert timestamp == now
    assert source == "synthetic-test-rate"

    eur = normalize_price(Decimal("10"), "EUR", Settings(_env_file=None), now)
    assert eur == (Decimal("10"), Decimal(1), now, "identity:EUR")


def test_price_summary_and_float_score() -> None:
    summary = summarize([Decimal("2"), Decimal("1"), Decimal("4")])
    assert summary is not None
    assert summary.lowest == Decimal("1")
    assert summary.median == Decimal("2")
    assert summary.mean == Decimal("7") / Decimal("3")
    assert (
        float_score(
            Decimal("0.10"),
            [
                Decimal("0.05"),
                Decimal("0.10"),
                Decimal("0.20"),
                Decimal("0.30"),
                Decimal("0.40"),
            ],
        )
        == 70
    )
    assert float_score(Decimal("0.10"), [Decimal("0.1")]) is None


def test_opportunity_score_uses_centralized_configurable_weights() -> None:
    components = OpportunityComponents(80, 60, 40, 20, 90, 50)
    assert calculate_opportunity_score(components) == 59
    price_only = OpportunityWeights(
        price_discount=Decimal(1),
        liquidity=Decimal(0),
        sales_history=Decimal(0),
        float_quality=Decimal(0),
        market_confidence=Decimal(0),
        risk=Decimal(0),
    )
    assert calculate_opportunity_score(components, price_only) == 80
    with pytest.raises(ValueError, match="totaliser 1"):
        calculate_opportunity_score(
            components,
            OpportunityWeights(price_discount=Decimal("0.31")),
        )
