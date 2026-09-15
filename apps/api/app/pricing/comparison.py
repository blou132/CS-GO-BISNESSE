from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median


@dataclass(frozen=True)
class PriceSummary:
    lowest: Decimal
    mean: Decimal
    median: Decimal
    sample_size: int


def summarize(prices: Sequence[Decimal]) -> PriceSummary | None:
    if not prices:
        return None
    if any(not price.is_finite() or price < 0 for price in prices):
        raise ValueError("Prix invalides.")
    return PriceSummary(
        min(prices), sum(prices, Decimal(0)) / len(prices), median(prices), len(prices)
    )


def float_score(
    value: Decimal | None, peers: Sequence[Decimal], *, min_samples: int = 5
) -> int | None:
    """Rang inversé avec ex aequo à mi-rang ; au moins cinq exemplaires comparables."""
    if min_samples < 5:
        raise ValueError("At least five comparable samples are required.")
    if value is None or len(peers) < min_samples:
        return None
    if any(not number.is_finite() or not 0 <= number <= 1 for number in [value, *peers]):
        raise ValueError("Float hors intervalle [0, 1].")
    better = sum(number > value for number in peers)
    ties = sum(number == value for number in peers)
    return round(100 * (better + ties / 2) / len(peers))
