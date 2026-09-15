from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models import (
    AggregateMarketStat,
    BuyOrderObservation,
    CS2Item,
    ListingAnalysisSnapshot,
    MarketListing,
    MarketOpportunity,
    MarketSyncState,
    PriceObservation,
    RealizedSale,
)
from app.pricing.comparison import float_score, summarize
from app.pricing.finance import ProfitInput, calculate_profit
from app.pricing.opportunity import OpportunityComponents, calculate_opportunity_score
from app.pricing.valuation import (
    DEFAULT_PRICE_CONFIG,
    LiquidityCategory,
    LiquidityInput,
    MarketEvidence,
    ReferenceMethod,
    RiskInput,
    calculate_liquidity,
    calculate_reference_price,
    calculate_risk,
    calculate_spread,
)
from app.schemas.api import (
    Comparison,
    CurrentMarketSnapshot,
    Dashboard,
    EvidenceSource,
    Freshness,
    IntegrationStatus,
    ItemDetail,
    MarketAvailability,
    MarketStatus,
    Mode,
    Observation,
    Platform,
    ScannerRow,
    Sticker,
    ValuationProvenance,
)

PLATFORMS: tuple[Platform, ...] = ("csfloat", "skinport", "dmarket")
INTEGRATION_STATUS: dict[Platform, IntegrationStatus] = {
    "csfloat": "OFFICIAL_API",
    "skinport": "PARTIAL",
    "dmarket": "OFFICIAL_API",
}
DEMO_SALE_FEE_RATE = Decimal("0.10")
MAX_DASHBOARD_LISTINGS = 100
FloatGroup = tuple[str, str | None]


@dataclass(frozen=True)
class Analysis:
    estimated_value: Decimal | None
    potential_profit: Decimal | None
    roi: Decimal | None
    opportunity_score: int | None
    float_score: int | None
    liquidity: int | None
    liquidity_category: LiquidityCategory | None
    liquidity_evidence_completeness: int | None
    confidence: int | None
    reference_method: ReferenceMethod | None
    reference_sources: tuple[str, ...]
    reference_calculated_at: datetime | None
    spread_eur: Decimal | None
    spread_percent: Decimal | None
    risk_score: int | None
    risk_factors: tuple[str, ...]
    warnings: list[str]


@dataclass(frozen=True)
class MarketData:
    listings: list[MarketListing]
    observations: list[PriceObservation]
    aggregates: list[AggregateMarketStat]
    realized_sales: list[RealizedSale]
    buy_orders: list[BuyOrderObservation]


def _quantize(value: Decimal | None) -> Decimal | None:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if value is not None else None


def _analyse(
    listing: MarketListing,
    evidence: list[MarketEvidence],
    peer_floats: list[Decimal],
    mode: Mode,
    min_float_samples: int = 5,
) -> Analysis:
    now = datetime.now(UTC)
    score_float = (
        float_score(listing.item.float_value, peer_floats, min_samples=min_float_samples)
        if timedelta(0) <= now - _aware(listing.observed_at) <= timedelta(hours=24)
        else None
    )
    reference = calculate_reference_price(evidence, now=now)
    spread = calculate_spread(evidence, now=now)
    liquidity_result = calculate_liquidity(
        _liquidity_input(evidence, spread.percentage if spread is not None else None),
        now=now,
    )
    newest = max((item.observed_at for item in evidence), default=None)
    capital_lock_days = _capital_lock_days(listing, now)
    risk = calculate_risk(
        values=_risk_input(
            listing,
            liquidity_result.score if liquidity_result else None,
            reference.confidence if reference else None,
            max(Decimal(0), spread.percentage) if spread else None,
            newest,
            capital_lock_days,
            len(reference.sources) if reference else 0,
        ),
        now=now,
    )
    warnings = _reference_warnings(reference.method if reference else None)
    if liquidity_result is not None and liquidity_result.evidence_completeness < 50:
        warnings.append("Liquidité calculée avec moins de la moitié des signaux disponibles.")
    if capital_lock_days:
        warnings.append(
            f"Trade lock observé : capital immobilisé environ {capital_lock_days} jour(s)."
        )

    estimated = reference.value_eur if reference else None

    potential_profit: Decimal | None = None
    roi: Decimal | None = None
    opportunity: int | None = None
    if mode == "demo" and listing.price_eur_reference is not None and estimated is not None:
        sale_fee = estimated * DEMO_SALE_FEE_RATE
        result = calculate_profit(
            ProfitInput(
                purchase_price=listing.price_eur_reference,
                sale_price=estimated,
                sale_fee=sale_fee,
            )
        )
        potential_profit = result.net_profit
        roi = result.roi
        discount = max(Decimal(0), (estimated - listing.price_eur_reference) / estimated * 100)
        price_component = min(100, int(discount * 5))
        history_component = min(100, reference.sample_size * 5) if reference else 0
        float_component = score_float if score_float is not None else 0
        opportunity = calculate_opportunity_score(
            OpportunityComponents(
                price_discount=price_component,
                liquidity=liquidity_result.score if liquidity_result else 0,
                sales_history=history_component,
                float_quality=float_component,
                market_confidence=reference.confidence if reference else 0,
                risk=100 - risk.score,
            )
        )
        warnings.append(
            "DEMO — profit calculé avec 10 % de frais de vente synthétiques et zéro autre frais."
        )
    elif listing.price_eur_reference is not None and estimated is not None:
        warnings.append(
            "Frais effectifs et plateforme de revente inconnus : profit et ROI non calculés."
        )
    return Analysis(
        _quantize(estimated),
        _quantize(potential_profit),
        roi.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if roi is not None else None,
        opportunity,
        score_float,
        liquidity_result.score if liquidity_result else None,
        liquidity_result.category if liquidity_result else None,
        liquidity_result.evidence_completeness if liquidity_result else None,
        reference.confidence if reference else None,
        reference.method if reference else None,
        reference.sources if reference else (),
        reference.calculated_at if reference else None,
        _quantize(spread.absolute_eur) if spread else None,
        (spread.percentage.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if spread else None),
        risk.score,
        risk.factors,
        warnings,
    )


def _load_listings(
    session: Session,
    mode: Mode,
    *,
    listing_limit: int | None = None,
    market_hash_names: set[str] | None = None,
) -> list[MarketListing]:
    listing_query = (
        select(MarketListing)
        .join(CS2Item, MarketListing.item_id == CS2Item.id)
        .where(MarketListing.mode == mode, MarketListing.status == "ACTIVE")
        .options(selectinload(MarketListing.item).selectinload(CS2Item.stickers))
        .order_by(MarketListing.observed_at.desc(), MarketListing.id)
    )
    if market_hash_names is not None:
        listing_query = listing_query.where(CS2Item.market_hash_name.in_(market_hash_names))
    if listing_limit is not None:
        listing_query = listing_query.limit(listing_limit)
    return list(session.scalars(listing_query))


def _load(
    session: Session,
    mode: Mode,
    *,
    market_hash_names: set[str] | None = None,
) -> MarketData:
    listings = _load_listings(session, mode, market_hash_names=market_hash_names)
    names = {listing.item.market_hash_name for listing in listings}
    if not names:
        return MarketData([], [], [], [], [])
    observations = list(
        session.scalars(
            select(PriceObservation)
            .where(
                PriceObservation.mode == mode,
                PriceObservation.market_hash_name.in_(names),
                PriceObservation.timestamp
                >= datetime.now(UTC) - DEFAULT_PRICE_CONFIG.realized_max_age,
            )
            .order_by(PriceObservation.timestamp.desc())
        )
    )
    aggregates = list(
        session.scalars(
            select(AggregateMarketStat)
            .where(
                AggregateMarketStat.mode == mode,
                AggregateMarketStat.market_hash_name.in_(names),
                AggregateMarketStat.observed_at
                >= datetime.now(UTC) - DEFAULT_PRICE_CONFIG.aggregate_max_age,
            )
            .order_by(AggregateMarketStat.observed_at.desc())
        )
    )
    realized_sales = list(
        session.scalars(
            select(RealizedSale)
            .where(
                RealizedSale.mode == mode,
                RealizedSale.market_hash_name.in_(names),
                RealizedSale.sold_at >= datetime.now(UTC) - DEFAULT_PRICE_CONFIG.realized_max_age,
            )
            .order_by(RealizedSale.sold_at.desc())
        )
    )
    buy_orders = list(
        session.scalars(
            select(BuyOrderObservation)
            .where(
                BuyOrderObservation.mode == mode,
                BuyOrderObservation.market_hash_name.in_(names),
                BuyOrderObservation.observed_at
                >= datetime.now(UTC) - DEFAULT_PRICE_CONFIG.current_market_max_age,
            )
            .order_by(BuyOrderObservation.observed_at.desc())
        )
    )
    return MarketData(listings, observations, aggregates, realized_sales, buy_orders)


def _row(
    listing: MarketListing,
    evidence_by_name: dict[str, list[MarketEvidence]],
    floats_by_name: dict[FloatGroup, list[Decimal]],
    mode: Mode,
    min_float_samples: int = 5,
) -> ScannerRow:
    analysis = _analyse(
        listing,
        evidence_by_name.get(listing.item.market_hash_name, []),
        floats_by_name.get((listing.item.market_hash_name, listing.item.exterior), []),
        mode,
        min_float_samples,
    )
    return ScannerRow(
        id=listing.id,
        market_hash_name=listing.item.market_hash_name,
        weapon=listing.item.weapon,
        skin=listing.item.skin,
        exterior=listing.item.exterior,
        platform=cast(Platform, listing.platform),
        price_original=listing.price_original,
        currency_original=listing.currency_original,
        price_eur_reference=listing.price_eur_reference,
        float_value=listing.item.float_value,
        paint_seed=listing.item.paint_seed,
        paint_index=listing.item.paint_index,
        doppler_phase=listing.item.doppler_phase,
        fade_percentage=listing.item.fade_percentage,
        inspect_link=listing.item.inspect_link,
        listing_url=listing.listing_url,
        observed_at=listing.observed_at,
        estimated_value_eur=analysis.estimated_value,
        potential_profit_eur=analysis.potential_profit,
        roi=analysis.roi,
        opportunity_score=analysis.opportunity_score,
        float_score=analysis.float_score,
        liquidity=analysis.liquidity,
        liquidity_category=analysis.liquidity_category,
        liquidity_evidence_completeness=analysis.liquidity_evidence_completeness,
        confidence=analysis.confidence,
        reference_method=analysis.reference_method,
        reference_sources=list(analysis.reference_sources),
        reference_calculated_at=analysis.reference_calculated_at,
        spread_eur=analysis.spread_eur,
        spread_percent=analysis.spread_percent,
        risk_score=analysis.risk_score,
        risk_factors=list(analysis.risk_factors),
        stickers=[Sticker.model_validate(sticker) for sticker in listing.item.stickers],
        warnings=[*listing.warnings, *analysis.warnings],
    )


def market_statuses(session: Session, mode: Mode, settings: Settings) -> list[MarketStatus]:
    states = {
        state.platform: state
        for state in session.scalars(select(MarketSyncState).where(MarketSyncState.mode == mode))
    }
    result: list[MarketStatus] = []
    now = datetime.now(UTC)
    for platform in PLATFORMS:
        state = states.get(platform)
        configured = _platform_configured(platform, settings)
        if state is None:
            status: MarketAvailability = "idle"
            message = "Synchronisation non exécutée."
            if not configured:
                status = "not_configured"
                message = _not_configured_message(platform)
            result.append(
                MarketStatus(
                    platform=platform,
                    integration_status=INTEGRATION_STATUS[platform],
                    status=status,
                    message=message,
                    freshness="unknown",
                    configured=configured,
                )
            )
            continue
        success_at = state.last_success_at or state.last_sync_at
        freshness = _freshness(success_at, settings, now)
        status = cast(MarketAvailability, state.status)
        if mode == "live" and not configured:
            status = "not_configured"
            message = _not_configured_message(platform)
        else:
            message = state.message
        if mode == "live" and status in {"online", "degraded"}:
            if freshness == "very_stale":
                status = "very_stale"
            elif freshness == "stale":
                status = "stale"
        result.append(
            MarketStatus(
                platform=platform,
                integration_status=INTEGRATION_STATUS[platform],
                status=status,
                message=message,
                freshness=freshness,
                configured=configured,
                last_sync_at=success_at,
                last_success_at=success_at,
                last_attempt_at=state.last_attempt_at,
                last_failure_at=state.last_failure_at or state.last_error_at,
                last_duration_ms=state.last_duration_ms,
                last_items_received=state.last_items_received,
                last_items_created=state.last_items_created,
                last_items_updated=state.last_items_updated,
                last_error=state.last_error_message or state.last_error,
                last_error_code=state.last_error_code,
                last_error_at=state.last_failure_at or state.last_error_at,
                consecutive_failures=state.consecutive_failures,
                next_run_at=state.next_run_at,
            )
        )
    return result


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _platform_configured(platform: Platform, settings: Settings) -> bool:
    if platform == "csfloat":
        return settings.csfloat_api_key is not None
    if platform == "dmarket":
        return settings.dmarket_public_key is not None and settings.dmarket_secret_key is not None
    return True


def _not_configured_message(platform: Platform) -> str:
    if platform == "csfloat":
        return "Clé CSFloat non configurée; connecteur optionnel en attente."
    if platform == "dmarket":
        return "Clés DMarket non configurées; connecteur optionnel en attente."
    return "Connecteur non configuré."


def _freshness(
    last_success_at: datetime | None,
    settings: Settings,
    now: datetime | None = None,
) -> Freshness:
    if last_success_at is None:
        return "unknown"
    current = now or datetime.now(UTC)
    age = (current - _aware(last_success_at)).total_seconds()
    if age > settings.very_stale_after_seconds:
        return "very_stale"
    if age > settings.stale_after_seconds:
        return "stale"
    return "fresh"


def build_dashboard(session: Session, mode: Mode, settings: Settings) -> Dashboard:
    selected = _load_listings(session, mode, listing_limit=MAX_DASHBOARD_LISTINGS)
    names = {listing.item.market_hash_name for listing in selected}
    data = (
        _load(session, mode, market_hash_names=names) if names else MarketData([], [], [], [], [])
    )
    evidence_by_name = _build_evidence(data)
    floats = _peer_floats(data.listings)
    rows = [
        _row(listing, evidence_by_name, floats, mode, settings.float_min_samples)
        for listing in selected
    ]
    statuses = market_statuses(session, mode, settings)
    last_sync = max(
        (status.last_sync_at for status in statuses if status.last_sync_at is not None),
        default=None,
    )
    return Dashboard(
        mode=mode,
        listings=rows,
        markets=statuses,
        last_sync_at=last_sync,
        warnings=_analysis_warnings(rows, statuses, mode),
    )


def build_item_detail(
    session: Session,
    listing_id: str,
    mode: Mode,
    settings: Settings,
) -> ItemDetail | None:
    listing = session.scalar(
        select(MarketListing)
        .where(
            MarketListing.mode == mode,
            MarketListing.status == "ACTIVE",
            MarketListing.id == listing_id,
        )
        .options(selectinload(MarketListing.item).selectinload(CS2Item.stickers))
    )
    if listing is None:
        return None
    data = _load(session, mode, market_hash_names={listing.item.market_hash_name})
    evidence_by_name = _build_evidence(data)
    row = _row(
        listing,
        evidence_by_name,
        _peer_floats(data.listings),
        mode,
        settings.float_min_samples,
    )
    observations = list(
        session.scalars(
            select(PriceObservation)
            .where(
                PriceObservation.mode == mode,
                PriceObservation.market_hash_name == row.market_hash_name,
            )
            .order_by(PriceObservation.timestamp.desc())
        )
    )
    grouped: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for observation in observations:
        if observation.price_eur_reference is not None:
            grouped[(observation.platform, observation.observation_type)].append(
                observation.price_eur_reference
            )
    summaries = {
        key: summary
        for key, prices in grouped.items()
        if (summary := summarize(prices)) is not None
    }
    medians_by_type: dict[str, list[Decimal]] = defaultdict(list)
    for (_platform, observation_type), summary in summaries.items():
        medians_by_type[observation_type].append(summary.median)

    comparisons: list[Comparison] = []
    for (platform, observation_type), summary in sorted(summaries.items()):
        peers = medians_by_type[observation_type]
        reference = min(peers) if len(peers) >= 2 else None
        gap = summary.median - reference if reference is not None else None
        gap_percent = gap / reference * 100 if gap is not None and reference else None
        comparisons.append(
            Comparison(
                platform=cast(Platform, platform),
                observation_type=observation_type,
                lowest_eur=_quantize(summary.lowest),
                mean_eur=_quantize(summary.mean),
                median_eur=_quantize(summary.median),
                median_gap_to_best_eur=_quantize(gap),
                median_gap_to_best_percent=(
                    gap_percent.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    if gap_percent is not None
                    else None
                ),
                sample_size=summary.sample_size,
            )
        )
    reference_price = calculate_reference_price(evidence_by_name.get(row.market_hash_name, []))
    comparable_count = len(
        _peer_floats(data.listings).get((row.market_hash_name, row.exterior), [])
    )
    return ItemDetail(
        mode=mode,
        item=row,
        comparisons=comparisons,
        market_snapshots=_market_snapshots(
            data,
            row.market_hash_name,
            settings,
        ),
        history=[Observation.model_validate(item) for item in observations],
        provenance=ValuationProvenance(
            buy=EvidenceSource(
                platform=listing.platform,
                kind="LISTING",
                record_id=listing.id,
                external_id=listing.external_id,
                value_eur=listing.price_eur_reference,
                price_original=listing.price_original,
                currency=listing.currency_original,
                observed_at=listing.observed_at,
                fx_source=listing.fx_rate_source,
                fx_timestamp=listing.fx_rate_timestamp,
                timestamp_basis=cast(
                    str | None, listing.item.source_attributes.get("timestamp_basis")
                ),
            ),
            reference=[
                EvidenceSource.model_validate(value) for value in reference_price.evidence[:50]
            ]
            if reference_price
            else [],
            reference_sample_size=reference_price.sample_size if reference_price else 0,
            comparable_count=comparable_count,
            float_min_samples=settings.float_min_samples,
            float_status="AVAILABLE" if row.float_score is not None else "INSUFFICIENT_DATA",
            fee_status="DEMO_SYNTHETIC" if mode == "demo" else "UNKNOWN",
            eligibility="DEMO" if mode == "demo" else "REFERENCE_ONLY",
        ),
        warnings=_analysis_warnings(
            [row],
            market_statuses(session, mode, settings),
            mode,
        ),
    )


def _analysis_warnings(
    rows: list[ScannerRow],
    statuses: list[MarketStatus],
    mode: Mode,
) -> list[str]:
    warnings: list[str] = []
    if mode == "demo":
        warnings.append("DEMO — toutes les données sont des fixtures synthétiques isolées du réel.")
    if any(row.price_eur_reference is None for row in rows):
        warnings.append("Certains prix n'ont pas de taux EUR sourcé et ne sont pas comparables.")
    if any(
        status.status in {"error", "unavailable", "degraded", "stale", "very_stale"}
        for status in statuses
    ):
        warnings.append("Une ou plusieurs plateformes sont indisponibles ou périmées.")
    if any(status.status == "not_configured" for status in statuses):
        warnings.append("Certaines plateformes optionnelles ne sont pas configurées.")
    return warnings


def refresh_opportunities(
    session: Session, mode: Mode, settings: Settings, *, market_hash_names: set[str] | None = None
) -> int:
    data = _load(session, mode, market_hash_names=market_hash_names)
    evidence_by_name = _build_evidence(data)
    floats = _peer_floats(data.listings)

    now = datetime.now(UTC)
    snapshot_query = select(ListingAnalysisSnapshot).where(ListingAnalysisSnapshot.mode == mode)
    if market_hash_names is not None:
        snapshot_query = (
            snapshot_query.join(MarketListing)
            .join(CS2Item)
            .where(CS2Item.market_hash_name.in_(market_hash_names))
        )
    snapshots = {snapshot.listing_id: snapshot for snapshot in session.scalars(snapshot_query)}
    active_listing_ids: set[str] = set()
    count = 0
    for listing in data.listings:
        analysis = _analyse(
            listing,
            evidence_by_name.get(listing.item.market_hash_name, []),
            floats.get((listing.item.market_hash_name, listing.item.exterior), []),
            mode,
            settings.float_min_samples,
        )
        snapshot = snapshots.get(listing.id)
        if snapshot is None:
            snapshot = ListingAnalysisSnapshot(mode=mode, listing_id=listing.id)
            session.add(snapshot)
        _update_snapshot(snapshot, analysis, now)
        if analysis.opportunity_score is None:
            continue
        if (
            listing.observed_at
            and (now - _aware(listing.observed_at)).total_seconds() > settings.stale_after_seconds
        ):
            continue
        opportunity = session.scalar(
            select(MarketOpportunity).where(
                MarketOpportunity.mode == mode,
                MarketOpportunity.listing_id == listing.id,
            )
        )
        if opportunity is None:
            opportunity = MarketOpportunity(
                mode=mode,
                listing_id=listing.id,
                detected_at=now,
                created_at=now,
            )
            session.add(opportunity)
        opportunity.platform = listing.platform
        opportunity.market_hash_name = listing.item.market_hash_name
        opportunity.status = "ACTIVE"
        opportunity.score = analysis.opportunity_score
        opportunity.estimated_value_eur = analysis.estimated_value
        opportunity.potential_profit_eur = analysis.potential_profit
        opportunity.roi = analysis.roi
        opportunity.reason = (
            "Score calculé à partir du prix, de l'historique, de la liquidité et du float."
        )
        opportunity.last_seen_at = now
        opportunity.updated_at = now
        active_listing_ids.add(listing.id)
        count += 1

    existing_query = select(MarketOpportunity).where(
        MarketOpportunity.mode == mode,
        MarketOpportunity.status == "ACTIVE",
    )
    if market_hash_names is not None:
        existing_query = existing_query.where(
            MarketOpportunity.market_hash_name.in_(market_hash_names)
        )
    existing = session.scalars(existing_query)
    for opportunity in existing:
        if opportunity.listing_id not in active_listing_ids:
            opportunity.status = "INACTIVE"
            opportunity.updated_at = now
    session.flush()
    return count


def _update_snapshot(
    snapshot: ListingAnalysisSnapshot,
    analysis: Analysis,
    calculated_at: datetime,
) -> None:
    snapshot.estimated_value_eur = analysis.estimated_value
    snapshot.potential_profit_eur = analysis.potential_profit
    snapshot.roi = analysis.roi
    snapshot.opportunity_score = analysis.opportunity_score
    snapshot.float_score = analysis.float_score
    snapshot.liquidity_score = analysis.liquidity
    snapshot.liquidity_category = analysis.liquidity_category
    snapshot.liquidity_evidence_completeness = analysis.liquidity_evidence_completeness
    snapshot.confidence = analysis.confidence
    snapshot.reference_method = analysis.reference_method
    snapshot.reference_sources = list(analysis.reference_sources)
    snapshot.reference_calculated_at = analysis.reference_calculated_at
    snapshot.spread_eur = analysis.spread_eur
    snapshot.spread_percent = analysis.spread_percent
    snapshot.risk_score = analysis.risk_score
    snapshot.risk_factors = list(analysis.risk_factors)
    snapshot.warnings = analysis.warnings
    snapshot.calculated_at = calculated_at


def row_from_snapshot(
    listing: MarketListing,
    snapshot: ListingAnalysisSnapshot,
) -> ScannerRow:
    return ScannerRow(
        id=listing.id,
        market_hash_name=listing.item.market_hash_name,
        weapon=listing.item.weapon,
        skin=listing.item.skin,
        exterior=listing.item.exterior,
        platform=cast(Platform, listing.platform),
        price_original=listing.price_original,
        currency_original=listing.currency_original,
        price_eur_reference=listing.price_eur_reference,
        float_value=listing.item.float_value,
        paint_seed=listing.item.paint_seed,
        paint_index=listing.item.paint_index,
        doppler_phase=listing.item.doppler_phase,
        fade_percentage=listing.item.fade_percentage,
        inspect_link=listing.item.inspect_link,
        listing_url=listing.listing_url,
        observed_at=listing.observed_at,
        estimated_value_eur=snapshot.estimated_value_eur,
        potential_profit_eur=snapshot.potential_profit_eur,
        roi=snapshot.roi,
        opportunity_score=snapshot.opportunity_score,
        float_score=snapshot.float_score,
        liquidity=snapshot.liquidity_score,
        liquidity_category=cast(LiquidityCategory | None, snapshot.liquidity_category),
        liquidity_evidence_completeness=snapshot.liquidity_evidence_completeness,
        confidence=snapshot.confidence,
        reference_method=snapshot.reference_method,
        reference_sources=snapshot.reference_sources,
        reference_calculated_at=snapshot.reference_calculated_at,
        spread_eur=snapshot.spread_eur,
        spread_percent=snapshot.spread_percent,
        risk_score=snapshot.risk_score,
        risk_factors=snapshot.risk_factors,
        stickers=[Sticker.model_validate(sticker) for sticker in listing.item.stickers],
        warnings=[*listing.warnings, *snapshot.warnings],
    )


def row_without_snapshot(listing: MarketListing) -> ScannerRow:
    return ScannerRow(
        id=listing.id,
        market_hash_name=listing.item.market_hash_name,
        weapon=listing.item.weapon,
        skin=listing.item.skin,
        exterior=listing.item.exterior,
        platform=cast(Platform, listing.platform),
        price_original=listing.price_original,
        currency_original=listing.currency_original,
        price_eur_reference=listing.price_eur_reference,
        float_value=listing.item.float_value,
        paint_seed=listing.item.paint_seed,
        paint_index=listing.item.paint_index,
        doppler_phase=listing.item.doppler_phase,
        fade_percentage=listing.item.fade_percentage,
        inspect_link=listing.item.inspect_link,
        listing_url=listing.listing_url,
        observed_at=listing.observed_at,
        stickers=[Sticker.model_validate(sticker) for sticker in listing.item.stickers],
        warnings=[*listing.warnings, "Analyse en attente de la prochaine synchronisation."],
    )


def _peer_floats(listings: list[MarketListing]) -> dict[FloatGroup, list[Decimal]]:
    now = datetime.now(UTC)
    result: dict[FloatGroup, list[Decimal]] = defaultdict(list)
    seen: set[tuple[FloatGroup, str]] = set()
    for listing in sorted(listings, key=lambda row: row.observed_at, reverse=True):
        group = (listing.item.market_hash_name, listing.item.exterior)
        identity = listing.item.asset_id or f"{listing.platform}:{listing.external_id}"
        key = (group, identity)
        if key in seen:
            continue
        seen.add(key)
        value = listing.item.float_value
        if (
            listing.status == "ACTIVE"
            and value is not None
            and value.is_finite()
            and 0 <= value <= 1
            and timedelta(0) <= now - _aware(listing.observed_at) <= timedelta(hours=24)
        ):
            result[group].append(value)
    return result


def _build_evidence(data: MarketData) -> dict[str, list[MarketEvidence]]:
    now = datetime.now(UTC)
    result: dict[str, list[MarketEvidence]] = defaultdict(list)
    for listing in data.listings:
        if _usable_price(
            listing.price_eur_reference,
            listing.observed_at,
            now,
            DEFAULT_PRICE_CONFIG.current_market_max_age,
        ):
            result[listing.item.market_hash_name].append(
                MarketEvidence(
                    platform=listing.platform,
                    kind="LISTING",
                    value_eur=cast(Decimal, listing.price_eur_reference),
                    observed_at=listing.observed_at,
                    record_id=listing.id,
                    external_id=listing.external_id,
                    price_original=listing.price_original,
                    currency=listing.currency_original,
                    fx_source=listing.fx_rate_source,
                    fx_timestamp=listing.fx_rate_timestamp,
                    timestamp_basis=cast(
                        str | None, (listing.item.source_attributes or {}).get("timestamp_basis")
                    ),
                )
            )
    for sale in data.realized_sales:
        if _usable_price(
            sale.price_eur_reference, sale.sold_at, now, DEFAULT_PRICE_CONFIG.realized_max_age
        ):
            result[sale.market_hash_name].append(
                MarketEvidence(
                    platform=sale.platform,
                    kind="REALIZED_SALE",
                    value_eur=cast(Decimal, sale.price_eur_reference),
                    observed_at=sale.sold_at,
                    volume=1,
                    record_id=sale.id,
                    external_id=sale.external_id,
                    price_original=sale.price_original,
                    currency=sale.currency_original,
                    fx_source=sale.fx_rate_source,
                    fx_timestamp=sale.fx_rate_timestamp,
                    timestamp_basis=cast(
                        str | None, (sale.attributes or {}).get("timestamp_basis")
                    ),
                )
            )
    for aggregate in _current_aggregates(data.aggregates):
        if (
            _usable_price(
                aggregate.median_eur_reference,
                aggregate.observed_at,
                now,
                DEFAULT_PRICE_CONFIG.aggregate_max_age,
            )
            and aggregate.volume != 0
        ):
            result[aggregate.market_hash_name].append(
                MarketEvidence(
                    platform=aggregate.platform,
                    kind="HISTORICAL_MEDIAN",
                    value_eur=cast(Decimal, aggregate.median_eur_reference),
                    observed_at=aggregate.observed_at,
                    volume=aggregate.volume,
                    window=aggregate.window_code,
                    record_id=aggregate.id,
                    price_original=aggregate.median_price,
                    currency=aggregate.currency,
                    fx_source=aggregate.fx_rate_source,
                    fx_timestamp=aggregate.fx_rate_timestamp,
                )
            )
    for order in _current_orders(data.buy_orders, now):
        if order.price_eur_reference is not None:
            result[order.market_hash_name].append(
                MarketEvidence(
                    platform=order.platform,
                    kind="BUY_ORDER",
                    value_eur=order.price_eur_reference,
                    observed_at=order.observed_at,
                    volume=order.quantity,
                    record_id=order.id,
                    price_original=order.price_original,
                    currency=order.currency_original,
                    fx_source=order.fx_rate_source,
                    fx_timestamp=order.fx_rate_timestamp,
                )
            )
    # Legacy/demo SALE observations predate the dedicated realized_sales table.
    for observation in data.observations:
        if (
            observation.observation_type == "SALE"
            and _usable_price(
                observation.price_eur_reference,
                observation.timestamp,
                now,
                DEFAULT_PRICE_CONFIG.realized_max_age,
            )
            and observation.volume != 0
        ):
            result[observation.market_hash_name].append(
                MarketEvidence(
                    platform=observation.platform,
                    kind="REALIZED_SALE",
                    value_eur=cast(Decimal, observation.price_eur_reference),
                    observed_at=observation.timestamp,
                    volume=observation.volume,
                    record_id=observation.id,
                    price_original=observation.price,
                    currency=observation.currency,
                    fx_source=observation.fx_rate_source,
                    fx_timestamp=observation.fx_rate_timestamp,
                )
            )
    return result


def _usable_price(
    value: Decimal | None, observed_at: datetime, now: datetime, max_age: timedelta
) -> bool:
    return (
        value is not None
        and value.is_finite()
        and value > 0
        and timedelta(0) <= now - _aware(observed_at) <= max_age
    )


def _current_aggregates(rows: list[AggregateMarketStat]) -> list[AggregateMarketStat]:
    latest: dict[tuple[str, str, str], AggregateMarketStat] = {}
    for row in rows:
        key = (row.platform, row.market_hash_name, row.window_code)
        previous = latest.get(key)
        if previous is None or row.observed_at > previous.observed_at:
            latest[key] = row
    return list(latest.values())


def _current_orders(rows: list[BuyOrderObservation], now: datetime) -> list[BuyOrderObservation]:
    latest: dict[tuple[str, str], datetime] = {}
    for row in rows:
        key = (row.platform, row.market_hash_name)
        latest[key] = max(latest.get(key, row.observed_at), row.observed_at)
    return [
        row
        for row in rows
        if row.observed_at == latest[(row.platform, row.market_hash_name)]
        and row.quantity > 0
        and _usable_price(
            row.price_eur_reference,
            row.observed_at,
            now,
            DEFAULT_PRICE_CONFIG.current_market_max_age,
        )
        # Conditional bids are not interchangeable with an unrestricted bid for this skin.
        and all(value is None or value == "" or value == "any" for value in row.attributes.values())
    ]


def _liquidity_input(
    evidence: list[MarketEvidence], spread_percent: Decimal | None, *, now: datetime | None = None
) -> LiquidityInput:
    current_time = now or datetime.now(UTC)
    evidence = [
        item
        for item in evidence
        if timedelta(0) <= current_time - _aware(item.observed_at) <= timedelta(hours=24)
    ]
    aggregates: dict[tuple[str, str], MarketEvidence] = {}
    for item in evidence:
        if item.kind != "HISTORICAL_MEDIAN" or item.window is None:
            continue
        key = (item.platform, item.window)
        current = aggregates.get(key)
        if current is None or item.observed_at > current.observed_at:
            aggregates[key] = item

    orders_by_platform: dict[str, list[MarketEvidence]] = defaultdict(list)
    for item in evidence:
        if item.kind == "BUY_ORDER":
            orders_by_platform[item.platform].append(item)
    current_orders: list[MarketEvidence] = []
    for orders in orders_by_platform.values():
        newest = max(item.observed_at for item in orders)
        current_orders.extend(item for item in orders if item.observed_at == newest)

    def volume(window: str) -> int | None:
        values = [item.volume for item in aggregates.values() if item.window == window]
        known = [item for item in values if item is not None]
        return sum(known) if known else None

    freshness_values = [item.observed_at for item in evidence]
    return LiquidityInput(
        volume_24h=volume("24H"),
        volume_7d=volume("7D"),
        volume_30d=volume("30D"),
        listing_count=(
            sum(item.kind == "LISTING" for item in evidence)
            if any(item.kind == "LISTING" for item in evidence)
            else None
        ),
        buy_order_quantity=(
            sum(item.volume or 0 for item in current_orders) if current_orders else None
        ),
        spread_percent=max(Decimal(0), spread_percent) if spread_percent is not None else None,
        freshest_at=max(freshness_values) if freshness_values else None,
    )


def _risk_input(
    listing: MarketListing,
    liquidity_score: int | None,
    confidence: int | None,
    spread_percent: Decimal | None,
    newest: datetime | None,
    capital_lock_days: int | None,
    source_count: int,
) -> RiskInput:
    return RiskInput(
        liquidity_score=liquidity_score,
        price_confidence=confidence,
        spread_percent=spread_percent,
        freshest_at=newest,
        source_count=source_count,
        has_fx_exposure=listing.currency_original != "EUR",
        capital_lock_days=capital_lock_days,
        unusual_item=bool(
            listing.item.doppler_phase
            or listing.item.fade_percentage is not None
            or listing.item.stickers
        ),
    )


def _capital_lock_days(listing: MarketListing, now: datetime) -> int | None:
    if listing.item.tradable_at is None:
        return None
    remaining = (_aware(listing.item.tradable_at) - now).total_seconds()
    return max(0, ceil(remaining / 86400))


def _reference_warnings(method: ReferenceMethod | None) -> list[str]:
    if method is None:
        return ["Aucune preuve EUR récente exploitable : valeur et profit laissés inconnus."]
    if method == "REALIZED_SALES_MEDIAN":
        return ["Valeur médiane issue de ventes observées ; elle ne constitue pas un prix garanti."]
    if method == "HISTORICAL_MEDIANS":
        return ["Valeur issue de médianes historiques agrégées, sans vente unitaire garantie."]
    if method == "CURRENT_BUY_ORDERS":
        return ["Valeur de repli issue de la demande actuelle ; le bid peut disparaître."]
    return ["Confiance faible : valeur de repli issue uniquement des prix demandés actuels."]


def _market_snapshots(
    data: MarketData,
    market_hash_name: str,
    settings: Settings,
) -> list[CurrentMarketSnapshot]:
    now = datetime.now(UTC)
    result: list[CurrentMarketSnapshot] = []
    for platform in PLATFORMS:
        listings = [
            item
            for item in data.listings
            if item.platform == platform
            and item.item.market_hash_name == market_hash_name
            and item.price_eur_reference is not None
        ]
        orders = [
            item
            for item in _current_orders(data.buy_orders, now)
            if item.platform == platform and item.market_hash_name == market_hash_name
        ]
        current_orders: list[BuyOrderObservation] = []
        if orders:
            latest_order_at = max(item.observed_at for item in orders)
            current_orders = [item for item in orders if item.observed_at == latest_order_at]
        aggregates = [
            item
            for item in data.aggregates
            if item.platform == platform and item.market_hash_name == market_hash_name
        ]
        median_7d = _latest_aggregate(aggregates, "7D")
        median_30d = _latest_aggregate(aggregates, "30D")
        sales = [
            item
            for item in data.realized_sales
            if item.platform == platform and item.market_hash_name == market_hash_name
        ]
        timestamps = [
            *(item.observed_at for item in listings),
            *(item.observed_at for item in current_orders),
            *(item.observed_at for item in aggregates),
            *(item.observed_at for item in sales),
        ]
        freshest_at = max(timestamps) if timestamps else None
        currencies = sorted(
            {
                *(item.currency_original for item in listings),
                *(item.currency_original for item in current_orders),
                *(item.currency for item in aggregates),
                *(item.currency_original for item in sales),
            }
        )
        result.append(
            CurrentMarketSnapshot(
                platform=platform,
                ask_eur=_quantize(
                    min(
                        (cast(Decimal, item.price_eur_reference) for item in listings),
                        default=None,
                    )
                ),
                bid_eur=_quantize(
                    max(
                        (cast(Decimal, item.price_eur_reference) for item in current_orders),
                        default=None,
                    )
                ),
                median_7d_eur=_quantize(median_7d.median_eur_reference if median_7d else None),
                median_30d_eur=_quantize(median_30d.median_eur_reference if median_30d else None),
                volume_30d=median_30d.volume if median_30d else None,
                currencies=currencies,
                freshest_at=freshest_at,
                freshness=_freshness(freshest_at, settings, now),
            )
        )
    return result


def _latest_aggregate(
    aggregates: list[AggregateMarketStat], window: str
) -> AggregateMarketStat | None:
    matching = [item for item in aggregates if item.window_code == window]
    return max(matching, key=lambda item: item.observed_at, default=None)
