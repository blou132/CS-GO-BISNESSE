from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.session import build_engine, build_session_factory
from app.models import Base, PlatformFeeSchedule
from app.pricing.fees import FeeRule, calculate_fee
from app.services.fees import calculate_stored_fee

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def rule(**overrides) -> FeeRule:
    values = {
        "platform": "dmarket",
        "fee_type": "SELL",
        "rate": Decimal("0.02"),
        "fixed_amount": None,
        "minimum_fee": Decimal("0.02"),
        "currency": "USD",
        "min_amount": None,
        "max_amount": None,
        "applies_to": None,
        "source": "https://docs.dmarket.com/v1/swagger.html",
        "verified_at": NOW,
        "valid_from": NOW - timedelta(days=1),
        "valid_until": None,
    }
    values.update(overrides)
    return FeeRule(**values)  # type: ignore[arg-type]


def test_fee_prefers_applicable_item_specific_rule() -> None:
    result = calculate_fee(
        Decimal("100"),
        "USD",
        "dmarket",
        "SELL",
        [
            rule(),
            rule(
                rate=Decimal("0.015"),
                applies_to="AK-47 | Redline (Field-Tested)",
                min_amount=Decimal("1"),
                max_amount=Decimal("500"),
            ),
        ],
        item_name="AK-47 | Redline (Field-Tested)",
        at=NOW,
    )
    assert result is not None
    assert result.fee_amount == Decimal("1.500")
    assert result.rate == Decimal("0.015")
    assert result.applies_to == "AK-47 | Redline (Field-Tested)"


def test_fee_falls_back_to_default_outside_specific_range() -> None:
    result = calculate_fee(
        Decimal("600"),
        "USD",
        "dmarket",
        "SELL",
        [rule(), rule(rate=Decimal("0.01"), applies_to="item", max_amount=Decimal("500"))],
        item_name="item",
        at=NOW,
    )
    assert result is not None
    assert result.fee_amount == Decimal("12.00")
    assert result.applies_to is None


def test_fee_applies_minimum_and_excludes_expired_or_wrong_currency() -> None:
    result = calculate_fee(
        Decimal("0.50"),
        "USD",
        "dmarket",
        "SELL",
        [
            rule(rate=Decimal("0.01"), minimum_fee=Decimal("0.02")),
            rule(rate=Decimal("0.001"), valid_until=NOW - timedelta(seconds=1)),
            rule(rate=Decimal("0.001"), currency="EUR"),
        ],
        at=NOW,
    )
    assert result is not None
    assert result.fee_amount == Decimal("0.02")
    assert result.minimum_applied is True


def test_fee_is_unknown_without_sourced_applicable_rule() -> None:
    assert calculate_fee(Decimal("10"), "EUR", "skinport", "SELL", [], at=NOW) is None
    with pytest.raises(ValueError, match="taux ou un montant fixe"):
        calculate_fee(
            Decimal("10"),
            "USD",
            "dmarket",
            "SELL",
            [rule(rate=None, fixed_amount=None)],
            at=NOW,
        )


def test_stored_fee_schedule_is_used_without_hardcoded_fallback(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'fees.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        session.add(
            PlatformFeeSchedule(
                platform="dmarket",
                fee_type="SELL",
                rate=Decimal("0.02"),
                fixed_amount=None,
                minimum_fee=Decimal("0.02"),
                currency="USD",
                min_amount=None,
                max_amount=None,
                applies_to=None,
                source="https://docs.dmarket.com/v1/swagger.html",
                verified_at=NOW,
                valid_from=NOW - timedelta(days=1),
                valid_until=None,
            )
        )
        session.commit()
        result = calculate_stored_fee(
            session,
            base_amount=Decimal("100"),
            currency="USD",
            platform="dmarket",
            fee_type="SELL",
            at=NOW,
        )
    assert result is not None
    assert result.fee_amount == Decimal("2.00")
    assert result.source == "https://docs.dmarket.com/v1/swagger.html"
    engine.dispose()


@pytest.mark.parametrize("verified_at", [NOW + timedelta(seconds=1), NOW - timedelta(days=8)])
def test_future_or_old_fee_verification_is_not_usable(verified_at):
    assert (
        calculate_fee(
            Decimal("100"), "USD", "dmarket", "SELL", [rule(verified_at=verified_at)], at=NOW
        )
        is None
    )


def test_ambiguous_fee_rules_never_depend_on_query_order():
    rules = [rule(rate=Decimal("0.01")), rule(rate=Decimal("0.05"))]
    for values in (rules, list(reversed(rules))):
        assert calculate_fee(Decimal("100"), "USD", "dmarket", "SELL", values, at=NOW) is None


def test_fixed_fee_without_currency_is_rejected():
    with pytest.raises(ValueError, match="devise explicite"):
        calculate_fee(Decimal("100"), "USD", "dmarket", "SELL", [rule(currency=None)], at=NOW)
