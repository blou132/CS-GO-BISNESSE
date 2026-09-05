from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class OpportunityWeights:
    price_discount: Decimal = Decimal("0.30")
    liquidity: Decimal = Decimal("0.20")
    sales_history: Decimal = Decimal("0.20")
    float_quality: Decimal = Decimal("0.15")
    market_confidence: Decimal = Decimal("0.10")
    risk: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class OpportunityComponents:
    price_discount: int
    liquidity: int
    sales_history: int
    float_quality: int
    market_confidence: int
    risk: int


DEFAULT_OPPORTUNITY_WEIGHTS = OpportunityWeights()


def calculate_opportunity_score(
    components: OpportunityComponents,
    weights: OpportunityWeights = DEFAULT_OPPORTUNITY_WEIGHTS,
) -> int:
    values = components.__dict__
    if any(not 0 <= value <= 100 for value in values.values()):
        raise ValueError("Chaque composante du score doit être comprise entre 0 et 100.")
    weight_values = weights.__dict__
    if any(weight < 0 for weight in weight_values.values()) or sum(
        weight_values.values(), Decimal(0)
    ) != Decimal(1):
        raise ValueError("Les pondérations doivent être positives et totaliser 1.")
    score = sum(Decimal(values[name]) * weight for name, weight in weight_values.items())
    return int(score.quantize(Decimal(1), rounding=ROUND_HALF_UP))
