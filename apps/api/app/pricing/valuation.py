from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Literal

EvidenceKind = Literal[
    "REALIZED_SALE",
    "HISTORICAL_MEDIAN",
    "BUY_ORDER",
    "LISTING",
]
ReferenceMethod = Literal[
    "REALIZED_SALES_MEDIAN",
    "HISTORICAL_MEDIANS",
    "CURRENT_BUY_ORDERS",
    "CURRENT_LISTINGS",
]
LiquidityCategory = Literal["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]

ZERO = Decimal(0)
HUNDRED = Decimal(100)


@dataclass(frozen=True)
class MarketEvidence:
    platform: str
    kind: EvidenceKind
    value_eur: Decimal
    observed_at: datetime
    volume: int | None = None
    window: str | None = None


@dataclass(frozen=True)
class PriceEngineConfig:
    realized_min_samples: int = 3
    realized_max_age: timedelta = timedelta(days=30)
    aggregate_max_age: timedelta = timedelta(hours=72)
    current_market_max_age: timedelta = timedelta(hours=24)
    base_realized_confidence: int = 55
    base_historical_confidence: int = 42
    base_buy_order_confidence: int = 32
    base_listing_confidence: int = 20
    max_source_bonus: int = 15
    max_depth_bonus: int = 10
    max_volume_bonus: int = 10
    max_freshness_bonus: int = 10
    max_disagreement_penalty: int = 15
    max_spread_penalty: int = 10


@dataclass(frozen=True)
class ReferencePrice:
    value_eur: Decimal
    confidence: int
    calculated_at: datetime
    method: ReferenceMethod
    sources: tuple[str, ...]
    sample_size: int


@dataclass(frozen=True)
class SpreadResult:
    ask_eur: Decimal
    bid_eur: Decimal
    absolute_eur: Decimal
    percentage: Decimal
    ask_source: str
    bid_source: str


@dataclass(frozen=True)
class LiquidityInput:
    volume_24h: int | None = None
    volume_7d: int | None = None
    volume_30d: int | None = None
    listing_count: int | None = None
    buy_order_quantity: int | None = None
    spread_percent: Decimal | None = None
    freshest_at: datetime | None = None


@dataclass(frozen=True)
class LiquidityConfig:
    volume_24h_weight: Decimal = Decimal("0.25")
    volume_7d_weight: Decimal = Decimal("0.15")
    volume_30d_weight: Decimal = Decimal("0.10")
    listing_count_weight: Decimal = Decimal("0.15")
    buy_order_weight: Decimal = Decimal("0.15")
    spread_weight: Decimal = Decimal("0.15")
    freshness_weight: Decimal = Decimal("0.05")
    volume_24h_full_score: int = 25
    volume_7d_full_score: int = 150
    volume_30d_full_score: int = 500
    listing_count_full_score: int = 30
    buy_order_full_score: int = 100
    spread_zero_score_percent: Decimal = Decimal("25")
    freshness_zero_score_age: timedelta = timedelta(hours=24)


@dataclass(frozen=True)
class LiquidityResult:
    score: int
    category: LiquidityCategory
    evidence_completeness: int


@dataclass(frozen=True)
class RiskInput:
    liquidity_score: int | None
    price_confidence: int | None
    spread_percent: Decimal | None
    freshest_at: datetime | None
    source_count: int
    has_fx_exposure: bool = False
    capital_lock_days: int | None = None
    unusual_item: bool = False


@dataclass(frozen=True)
class RiskWeights:
    low_liquidity: Decimal = Decimal("0.25")
    stale_data: Decimal = Decimal("0.15")
    large_spread: Decimal = Decimal("0.15")
    single_source: Decimal = Decimal("0.10")
    fx_exposure: Decimal = Decimal("0.10")
    trade_lock: Decimal = Decimal("0.10")
    low_confidence: Decimal = Decimal("0.10")
    unusual_item: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class RiskResult:
    score: int
    factors: tuple[str, ...]


DEFAULT_PRICE_CONFIG = PriceEngineConfig()
DEFAULT_LIQUIDITY_CONFIG = LiquidityConfig()
DEFAULT_RISK_WEIGHTS = RiskWeights()


def calculate_reference_price(
    evidence: Sequence[MarketEvidence],
    *,
    now: datetime | None = None,
    config: PriceEngineConfig = DEFAULT_PRICE_CONFIG,
) -> ReferencePrice | None:
    current = _aware(now or datetime.now(UTC))
    validated = [_validate_evidence(item, current) for item in evidence]
    tiers: tuple[tuple[ReferenceMethod, list[MarketEvidence]], ...] = (
        (
            "REALIZED_SALES_MEDIAN",
            _recent(validated, "REALIZED_SALE", current, config.realized_max_age),
        ),
        (
            "HISTORICAL_MEDIANS",
            _best_historical_medians(validated, current, config.aggregate_max_age),
        ),
        (
            "CURRENT_BUY_ORDERS",
            _best_per_platform(
                _recent(validated, "BUY_ORDER", current, config.current_market_max_age),
                highest=True,
            ),
        ),
        (
            "CURRENT_LISTINGS",
            _best_per_platform(
                _recent(validated, "LISTING", current, config.current_market_max_age),
                highest=False,
            ),
        ),
    )
    for method, selected in tiers:
        if not selected or (
            method == "REALIZED_SALES_MEDIAN" and len(selected) < config.realized_min_samples
        ):
            continue
        value = median(item.value_eur for item in selected)
        confidence = _price_confidence(method, selected, validated, value, current, config)
        return ReferencePrice(
            value_eur=value,
            confidence=confidence,
            calculated_at=current,
            method=method,
            sources=tuple(sorted({f"{item.platform}:{item.kind}" for item in selected})),
            sample_size=len(selected),
        )
    return None


def calculate_spread(
    evidence: Sequence[MarketEvidence],
    *,
    now: datetime | None = None,
    max_age: timedelta = timedelta(hours=24),
) -> SpreadResult | None:
    current = _aware(now or datetime.now(UTC))
    validated = [_validate_evidence(item, current) for item in evidence]
    asks = _recent(validated, "LISTING", current, max_age)
    bids = _recent(validated, "BUY_ORDER", current, max_age)
    if not asks or not bids:
        return None
    ask = min(asks, key=lambda item: item.value_eur)
    bid = max(bids, key=lambda item: item.value_eur)
    absolute = ask.value_eur - bid.value_eur
    return SpreadResult(
        ask_eur=ask.value_eur,
        bid_eur=bid.value_eur,
        absolute_eur=absolute,
        percentage=absolute / ask.value_eur * HUNDRED,
        ask_source=ask.platform,
        bid_source=bid.platform,
    )


def calculate_liquidity(
    values: LiquidityInput,
    *,
    now: datetime | None = None,
    config: LiquidityConfig = DEFAULT_LIQUIDITY_CONFIG,
) -> LiquidityResult | None:
    current = _aware(now or datetime.now(UTC))
    weighted: list[tuple[Decimal, Decimal]] = []
    _append_count_score(
        weighted, values.volume_24h, config.volume_24h_full_score, config.volume_24h_weight
    )
    _append_count_score(
        weighted, values.volume_7d, config.volume_7d_full_score, config.volume_7d_weight
    )
    _append_count_score(
        weighted, values.volume_30d, config.volume_30d_full_score, config.volume_30d_weight
    )
    _append_count_score(
        weighted,
        values.listing_count,
        config.listing_count_full_score,
        config.listing_count_weight,
    )
    _append_count_score(
        weighted,
        values.buy_order_quantity,
        config.buy_order_full_score,
        config.buy_order_weight,
    )
    if values.spread_percent is not None:
        spread = _valid_non_negative(values.spread_percent, "spread_percent")
        factor_score = max(
            ZERO,
            HUNDRED - spread / config.spread_zero_score_percent * HUNDRED,
        )
        weighted.append((factor_score, config.spread_weight))
    if values.freshest_at is not None:
        age = current - _aware(values.freshest_at)
        if age < timedelta(0):
            raise ValueError("freshest_at ne peut pas être dans le futur.")
        factor_score = max(
            ZERO,
            HUNDRED
            * (
                Decimal(1)
                - Decimal(str(age.total_seconds()))
                / Decimal(str(config.freshness_zero_score_age.total_seconds()))
            ),
        )
        weighted.append((factor_score, config.freshness_weight))
    if not weighted:
        return None
    available_weight = sum((weight for _, weight in weighted), ZERO)
    if available_weight <= ZERO:
        raise ValueError("Les pondérations de liquidité disponibles doivent être positives.")
    total_weight = sum(config.__dict__[name] for name in _LIQUIDITY_WEIGHT_NAMES)
    if total_weight != Decimal(1):
        raise ValueError("Les pondérations de liquidité doivent totaliser 1.")
    raw_score = sum((score * weight for score, weight in weighted), ZERO) / available_weight
    completeness = available_weight / total_weight
    adjusted = raw_score * (Decimal("0.65") + Decimal("0.35") * completeness)
    score = _round_score(adjusted)
    return LiquidityResult(
        score=score,
        category=_liquidity_category(score),
        evidence_completeness=_round_score(completeness * HUNDRED),
    )


def calculate_risk(
    values: RiskInput,
    *,
    now: datetime | None = None,
    weights: RiskWeights = DEFAULT_RISK_WEIGHTS,
) -> RiskResult:
    current = _aware(now or datetime.now(UTC))
    if sum(weights.__dict__.values(), ZERO) != Decimal(1):
        raise ValueError("Les pondérations de risque doivent totaliser 1.")
    if values.source_count < 0:
        raise ValueError("source_count doit être positif ou nul.")
    components: dict[str, Decimal] = {
        "low_liquidity": Decimal(100 - _valid_score(values.liquidity_score, default=25)),
        "single_source": Decimal(100 if values.source_count <= 1 else 0),
        "fx_exposure": Decimal(100 if values.has_fx_exposure else 0),
        "low_confidence": Decimal(100 - _valid_score(values.price_confidence, default=25)),
        "unusual_item": Decimal(100 if values.unusual_item else 0),
    }
    if values.spread_percent is None:
        components["large_spread"] = Decimal(75)
    else:
        spread = _valid_non_negative(values.spread_percent, "spread_percent")
        components["large_spread"] = min(HUNDRED, spread / Decimal(25) * HUNDRED)
    if values.freshest_at is None:
        components["stale_data"] = Decimal(75)
    else:
        age = current - _aware(values.freshest_at)
        if age < timedelta(0):
            raise ValueError("freshest_at ne peut pas être dans le futur.")
        components["stale_data"] = min(
            HUNDRED,
            Decimal(str(age.total_seconds())) / Decimal(86400) * HUNDRED,
        )
    if values.capital_lock_days is None:
        components["trade_lock"] = ZERO
    elif values.capital_lock_days < 0:
        raise ValueError("capital_lock_days doit être positif ou nul.")
    else:
        components["trade_lock"] = min(HUNDRED, Decimal(values.capital_lock_days) / 7 * HUNDRED)
    weighted_score = sum(components[name] * weight for name, weight in weights.__dict__.items())
    factors = tuple(
        _RISK_LABELS[name] for name, value in components.items() if value >= Decimal(50)
    )
    return RiskResult(score=_round_score(weighted_score), factors=factors)


_LIQUIDITY_WEIGHT_NAMES = (
    "volume_24h_weight",
    "volume_7d_weight",
    "volume_30d_weight",
    "listing_count_weight",
    "buy_order_weight",
    "spread_weight",
    "freshness_weight",
)

_RISK_LABELS = {
    "low_liquidity": "Liquidité faible ou inconnue",
    "stale_data": "Données anciennes ou sans horodatage",
    "large_spread": "Spread large ou inconnu",
    "single_source": "Source unique ou absente",
    "fx_exposure": "Exposition au change",
    "trade_lock": "Capital immobilisé par un trade lock",
    "low_confidence": "Confiance de valorisation faible",
    "unusual_item": "Caractéristiques atypiques peu comparables",
}


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _validate_evidence(item: MarketEvidence, now: datetime) -> MarketEvidence:
    if not item.platform.strip():
        raise ValueError("La plateforme d'une preuve est requise.")
    _valid_positive(item.value_eur, "value_eur")
    observed_at = _aware(item.observed_at)
    if observed_at > now:
        raise ValueError("Une preuve de prix ne peut pas être datée dans le futur.")
    if item.volume is not None and item.volume < 0:
        raise ValueError("Le volume doit être positif ou nul.")
    return MarketEvidence(
        platform=item.platform,
        kind=item.kind,
        value_eur=item.value_eur,
        observed_at=observed_at,
        volume=item.volume,
        window=item.window,
    )


def _recent(
    evidence: Sequence[MarketEvidence],
    kind: EvidenceKind,
    now: datetime,
    max_age: timedelta,
) -> list[MarketEvidence]:
    return [item for item in evidence if item.kind == kind and now - item.observed_at <= max_age]


def _best_per_platform(
    evidence: Sequence[MarketEvidence], *, highest: bool
) -> list[MarketEvidence]:
    selected: dict[str, MarketEvidence] = {}
    for item in evidence:
        current = selected.get(item.platform)
        if (
            current is None
            or (
                item.value_eur > current.value_eur
                if highest
                else item.value_eur < current.value_eur
            )
            or (item.value_eur == current.value_eur and item.observed_at > current.observed_at)
        ):
            selected[item.platform] = item
    return list(selected.values())


def _best_historical_medians(
    evidence: Sequence[MarketEvidence], now: datetime, max_age: timedelta
) -> list[MarketEvidence]:
    rank = {"7D": 0, "30D": 1, "24H": 2, "90D": 3}
    candidates = _recent(evidence, "HISTORICAL_MEDIAN", now, max_age)
    selected: dict[str, MarketEvidence] = {}
    for item in candidates:
        current = selected.get(item.platform)
        item_rank = rank.get(item.window or "", len(rank))
        current_rank = rank.get(current.window or "", len(rank)) if current else len(rank) + 1
        if (
            current is None
            or item_rank < current_rank
            or (item_rank == current_rank and item.observed_at > current.observed_at)
        ):
            selected[item.platform] = item
    return list(selected.values())


def _price_confidence(
    method: ReferenceMethod,
    selected: Sequence[MarketEvidence],
    all_evidence: Sequence[MarketEvidence],
    value: Decimal,
    now: datetime,
    config: PriceEngineConfig,
) -> int:
    base = {
        "REALIZED_SALES_MEDIAN": config.base_realized_confidence,
        "HISTORICAL_MEDIANS": config.base_historical_confidence,
        "CURRENT_BUY_ORDERS": config.base_buy_order_confidence,
        "CURRENT_LISTINGS": config.base_listing_confidence,
    }[method]
    source_count = len({item.platform for item in selected})
    source_bonus = min(config.max_source_bonus, source_count * 5)
    depth_bonus = min(config.max_depth_bonus, len(selected) * 2)
    volume = sum(item.volume or 0 for item in selected)
    volume_bonus = min(config.max_volume_bonus, volume // 10)
    newest = max(item.observed_at for item in selected)
    age_hours = Decimal(str((now - newest).total_seconds())) / Decimal(3600)
    freshness_bonus = max(0, config.max_freshness_bonus - int(age_hours // 6))
    disagreement = (
        (max(item.value_eur for item in selected) - min(item.value_eur for item in selected))
        / value
        * HUNDRED
    )
    disagreement_penalty = min(
        config.max_disagreement_penalty,
        int(max(ZERO, disagreement - Decimal(3)) / Decimal(2)),
    )
    spread = calculate_spread(all_evidence, now=now, max_age=config.current_market_max_age)
    spread_penalty = 0
    if spread is not None and spread.percentage > ZERO:
        spread_penalty = min(config.max_spread_penalty, int(spread.percentage / Decimal(3)))
    return max(
        0,
        min(
            100,
            base
            + source_bonus
            + depth_bonus
            + volume_bonus
            + freshness_bonus
            - disagreement_penalty
            - spread_penalty,
        ),
    )


def _append_count_score(
    target: list[tuple[Decimal, Decimal]],
    value: int | None,
    full_score: int,
    weight: Decimal,
) -> None:
    if value is None:
        return
    if value < 0:
        raise ValueError("Les volumes et quantités doivent être positifs ou nuls.")
    if full_score <= 0:
        raise ValueError("Le seuil de score complet doit être strictement positif.")
    target.append((min(HUNDRED, Decimal(value) / full_score * HUNDRED), weight))


def _valid_positive(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= ZERO:
        raise ValueError(f"{name} doit être un Decimal fini strictement positif.")
    return value


def _valid_non_negative(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} doit être un Decimal fini positif ou nul.")
    return value


def _valid_score(value: int | None, *, default: int) -> int:
    result = default if value is None else value
    if not 0 <= result <= 100:
        raise ValueError("Un score doit être compris entre 0 et 100.")
    return result


def _round_score(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _liquidity_category(score: int) -> LiquidityCategory:
    if score < 20:
        return "VERY_LOW"
    if score < 40:
        return "LOW"
    if score < 60:
        return "MEDIUM"
    if score < 80:
        return "HIGH"
    return "VERY_HIGH"
