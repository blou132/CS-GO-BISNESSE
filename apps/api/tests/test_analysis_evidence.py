from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import AggregateMarketStat, BuyOrderObservation, CS2Item, MarketListing
from app.pricing.valuation import MarketEvidence, calculate_liquidity, calculate_spread
from app.services.analysis import MarketData, _build_evidence, _liquidity_input, _peer_floats


def test_old_liquidity_volume_is_not_refreshed_by_one_recent_listing():
    now = datetime.now(UTC)
    values = [
        MarketEvidence(
            "skinport", "HISTORICAL_MEDIAN", Decimal("10"), now - timedelta(days=10), 10000, "24H"
        ),
        MarketEvidence("csfloat", "LISTING", Decimal("10"), now - timedelta(minutes=1)),
    ]
    result = _liquidity_input(values, None, now=now)
    assert result.volume_24h is None
    assert result.listing_count == 1
    score = calculate_liquidity(result, now=now)
    assert score is not None and score.score < 50


def test_database_evidence_ignores_replaced_conditional_and_zero_quantity_bids():
    now = datetime.now(UTC)

    def order(price, age, quantity=1, **attributes):
        return BuyOrderObservation(
            platform="dmarket",
            market_hash_name="TEST Skin",
            price_eur_reference=Decimal(price),
            observed_at=now - timedelta(minutes=age),
            quantity=quantity,
            attributes=attributes,
        )

    old = order("999", 60)
    current = order("90", 1, 2)
    conditional = order("2000", 1, 5, paintSeed="661")
    data = MarketData([], [], [], [], [old, current, conditional])
    values = _build_evidence(data)["TEST Skin"]
    assert [value.value_eur for value in values] == [Decimal("90")]
    assert calculate_spread(values) is None
    data = MarketData([], [], [], [], [old, order("90", 1, 0)])
    assert not _build_evidence(data)


def test_latest_empty_aggregate_does_not_reuse_historical_price():
    now = datetime.now(UTC)
    rows = [
        AggregateMarketStat(
            platform="skinport",
            market_hash_name="TEST Skin",
            window_code="7D",
            median_eur_reference=price,
            volume=volume,
            observed_at=now - timedelta(minutes=age),
        )
        for price, volume, age in [(Decimal("100"), 20, 60), (None, 0, 1)]
    ]
    assert not _build_evidence(MarketData([], [], rows, [], []))


def test_float_sample_requires_distinct_recent_assets_and_same_exterior():
    now = datetime.now(UTC)

    def listing(identifier, age=1, exterior="Factory New"):
        return MarketListing(
            platform="csfloat",
            external_id=identifier,
            status="ACTIVE",
            observed_at=now - timedelta(hours=age),
            item=CS2Item(
                market_hash_name="TEST Skin",
                exterior=exterior,
                asset_id=identifier,
                float_value=Decimal("0.01"),
            ),
        )

    rows = [
        listing("asset-a"),
        listing("asset-a"),
        listing("asset-a"),
        listing("asset-old", age=48),
        listing("asset-other", exterior="Field-Tested"),
    ]
    values = _peer_floats(rows)
    assert values[("TEST Skin", "Factory New")] == [Decimal("0.01")]
    assert values[("TEST Skin", "Field-Tested")] == [Decimal("0.01")]
