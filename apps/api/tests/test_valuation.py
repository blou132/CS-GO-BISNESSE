from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.pricing.valuation import (
    LiquidityInput,
    MarketEvidence,
    RiskInput,
    calculate_liquidity,
    calculate_reference_price,
    calculate_risk,
    calculate_spread,
)

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def evidence(
    platform: str,
    kind: str,
    value: str,
    *,
    age: timedelta = timedelta(minutes=5),
    volume: int | None = None,
    window: str | None = None,
) -> MarketEvidence:
    return MarketEvidence(  # type: ignore[arg-type]
        platform=platform,
        kind=kind,
        value_eur=Decimal(value),
        observed_at=NOW - age,
        volume=volume,
        window=window,
    )


def test_reference_price_prioritizes_realized_sales() -> None:
    values = [
        evidence("skinport", "HISTORICAL_MEDIAN", "125", volume=30, window="7D"),
        evidence("dmarket", "BUY_ORDER", "118", volume=4),
        evidence("csfloat", "LISTING", "130"),
        evidence("dmarket", "REALIZED_SALE", "119"),
        evidence("dmarket", "REALIZED_SALE", "121"),
        evidence("skinport", "REALIZED_SALE", "120"),
    ]
    result = calculate_reference_price(values, now=NOW)
    assert result is not None
    assert result.method == "REALIZED_SALES_MEDIAN"
    assert result.value_eur == Decimal("120")
    assert result.sample_size == 3
    assert result.sources == (
        "dmarket:REALIZED_SALE",
        "skinport:REALIZED_SALE",
    )
    assert 0 <= result.confidence <= 100


def test_reference_price_degrades_without_enough_sales() -> None:
    values = [
        evidence("dmarket", "REALIZED_SALE", "120"),
        evidence("skinport", "HISTORICAL_MEDIAN", "123", volume=20, window="30D"),
        evidence("skinport", "HISTORICAL_MEDIAN", "121", volume=8, window="7D"),
        evidence("dmarket", "BUY_ORDER", "116", volume=2),
    ]
    result = calculate_reference_price(values, now=NOW)
    assert result is not None
    assert result.method == "HISTORICAL_MEDIANS"
    assert result.value_eur == Decimal("121")
    assert result.sources == ("skinport:HISTORICAL_MEDIAN",)


def test_reference_price_falls_back_to_best_ask_per_platform() -> None:
    values = [
        evidence("csfloat", "LISTING", "110"),
        evidence("csfloat", "LISTING", "120"),
        evidence("dmarket", "LISTING", "114"),
    ]
    result = calculate_reference_price(values, now=NOW)
    assert result is not None
    assert result.method == "CURRENT_LISTINGS"
    assert result.value_eur == Decimal("112")
    assert result.sample_size == 2
    assert result.confidence < 60


def test_single_source_low_volume_never_has_high_confidence():
    reference = calculate_reference_price(
        [evidence("skinport", "HISTORICAL_MEDIAN", "26.10", volume=1, window="7D")],
        now=NOW,
    )
    assert reference is not None and reference.confidence < 60


def test_spread_uses_lowest_ask_and_highest_bid() -> None:
    result = calculate_spread(
        [
            evidence("csfloat", "LISTING", "105"),
            evidence("dmarket", "LISTING", "100"),
            evidence("dmarket", "BUY_ORDER", "90"),
            evidence("skinport", "BUY_ORDER", "92"),
        ],
        now=NOW,
    )
    assert result is not None
    assert result.ask_eur == Decimal("100")
    assert result.bid_eur == Decimal("92")
    assert result.absolute_eur == Decimal("8")
    assert result.percentage == Decimal("8")
    assert result.ask_source == "dmarket"
    assert result.bid_source == "skinport"


def test_liquidity_has_category_and_evidence_completeness() -> None:
    result = calculate_liquidity(
        LiquidityInput(
            volume_24h=20,
            volume_7d=100,
            volume_30d=400,
            listing_count=20,
            buy_order_quantity=75,
            spread_percent=Decimal("5"),
            freshest_at=NOW - timedelta(minutes=10),
        ),
        now=NOW,
    )
    assert result is not None
    assert result.category == "HIGH"
    assert 70 <= result.score < 80
    assert result.evidence_completeness == 100


def test_liquidity_does_not_treat_one_signal_as_complete() -> None:
    result = calculate_liquidity(LiquidityInput(listing_count=30), now=NOW)
    assert result is not None
    assert result.score == 70
    assert result.evidence_completeness == 15
    assert calculate_liquidity(LiquidityInput(), now=NOW) is None


def test_risk_increases_for_sparse_stale_wide_spread_data() -> None:
    safe = calculate_risk(
        RiskInput(
            liquidity_score=85,
            price_confidence=90,
            spread_percent=Decimal("3"),
            freshest_at=NOW - timedelta(minutes=5),
            source_count=3,
        ),
        now=NOW,
    )
    risky = calculate_risk(
        RiskInput(
            liquidity_score=15,
            price_confidence=25,
            spread_percent=Decimal("30"),
            freshest_at=NOW - timedelta(days=2),
            source_count=1,
            has_fx_exposure=True,
            capital_lock_days=7,
            unusual_item=True,
        ),
        now=NOW,
    )
    assert safe.score < 20
    assert risky.score > 80
    assert "Source unique ou absente" in risky.factors
    assert "Capital immobilisé par un trade lock" in risky.factors


def test_invalid_or_future_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="strictement positif"):
        calculate_reference_price([evidence("test", "LISTING", "0")], now=NOW)
    with pytest.raises(ValueError, match="futur"):
        calculate_reference_price(
            [
                MarketEvidence(
                    platform="test",
                    kind="LISTING",
                    value_eur=Decimal("1"),
                    observed_at=NOW + timedelta(seconds=1),
                )
            ],
            now=NOW,
        )


def test_replaced_or_empty_buy_order_snapshot_never_reuses_old_high_bid():
    old = evidence("dmarket", "BUY_ORDER", "999", age=timedelta(hours=1), volume=10)
    ask = evidence("csfloat", "LISTING", "100")
    current = evidence("dmarket", "BUY_ORDER", "90", volume=2)
    result = calculate_spread([old, current, ask], now=NOW)
    assert result is not None and result.bid_eur == Decimal("90")
    empty = evidence("dmarket", "BUY_ORDER", "90", volume=0)
    assert calculate_spread([old, empty, ask], now=NOW) is None


def test_zero_volume_history_does_not_resurrect_older_median():
    old = evidence(
        "skinport", "HISTORICAL_MEDIAN", "999", volume=30, window="7D", age=timedelta(hours=2)
    )
    empty = evidence("skinport", "HISTORICAL_MEDIAN", "100", volume=0, window="7D")
    ask = evidence("csfloat", "LISTING", "95")
    result = calculate_reference_price([old, empty, ask], now=NOW)
    assert result is not None and result.method == "CURRENT_LISTINGS"


def test_one_recent_sale_does_not_refresh_confidence_of_old_sample():
    old = [evidence("dmarket", "REALIZED_SALE", "100", age=timedelta(days=20)) for _ in range(8)]
    mixed = calculate_reference_price([*old, evidence("dmarket", "REALIZED_SALE", "100")], now=NOW)
    fresh = calculate_reference_price(
        [evidence("dmarket", "REALIZED_SALE", "100") for _ in range(9)], now=NOW
    )
    assert mixed is not None and fresh is not None
    assert mixed.confidence < fresh.confidence
