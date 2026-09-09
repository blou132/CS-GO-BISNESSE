from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.pricing.trades import TradeItemValue, TradeQuoteInput, evaluate_trade_quote

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def test_trade_quote_separates_platform_credits_from_real_cash_value() -> None:
    result = evaluate_trade_quote(
        TradeQuoteInput(
            platform="fixture-trade-provider",
            given_items=(
                TradeItemValue(
                    "Skin A",
                    platform_unit_value=Decimal("130"),
                    real_unit_cash_value_eur=Decimal("100"),
                ),
            ),
            received_items=(
                TradeItemValue(
                    "Skin B",
                    platform_unit_value=Decimal("130"),
                    real_unit_cash_value_eur=Decimal("90"),
                ),
            ),
            fees_eur=Decimal("2"),
            display_currency="EUR",
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=2),
            source_quality=90,
            valuation_confidence=80,
        ),
        now=NOW,
    )
    assert result.platform_given_value == Decimal("130")
    assert result.platform_received_value == Decimal("130")
    assert result.real_given_cash_value_eur == Decimal("100")
    assert result.real_received_cash_value_eur == Decimal("90")
    assert result.net_cash_difference_eur == Decimal("-12")
    assert result.real_value_ratio == Decimal("0.9")
    assert result.effective_spread_percent == Decimal("12")
    assert result.confidence == 80
    assert "n'implique pas" in result.warnings[0]


def test_trade_quote_never_sums_partial_cash_valuations() -> None:
    result = evaluate_trade_quote(
        TradeQuoteInput(
            platform="fixture-trade-provider",
            given_items=(
                TradeItemValue("Known", real_unit_cash_value_eur=Decimal("10")),
                TradeItemValue("Unknown", real_unit_cash_value_eur=None),
            ),
            received_items=(TradeItemValue("Received", real_unit_cash_value_eur=Decimal("12")),),
            fees_eur=Decimal(0),
            display_currency="EUR",
            created_at=NOW,
            expires_at=None,
            source_quality=100,
            valuation_confidence=90,
        ),
        now=NOW,
    )
    assert result.real_given_cash_value_eur is None
    assert result.net_cash_difference_eur is None
    assert result.real_value_ratio is None
    assert result.effective_spread_percent is None
    assert result.confidence < 90
    assert "incomplète" in result.warnings[0]


def test_trade_quote_marks_expired_data() -> None:
    result = evaluate_trade_quote(
        TradeQuoteInput(
            platform="fixture-trade-provider",
            given_items=(TradeItemValue("A", real_unit_cash_value_eur=Decimal("10")),),
            received_items=(TradeItemValue("B", real_unit_cash_value_eur=Decimal("11")),),
            fees_eur=Decimal(0),
            display_currency="EUR",
            created_at=NOW - timedelta(minutes=10),
            expires_at=NOW - timedelta(minutes=5),
            source_quality=70,
            valuation_confidence=70,
        ),
        now=NOW,
    )
    assert "Quote expirée." in result.warnings
