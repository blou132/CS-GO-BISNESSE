from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models import CS2Item, MarketListing, MarketOpportunity, MarketSyncState, PriceObservation
from app.pricing.comparison import float_score, summarize
from app.pricing.finance import ProfitInput, calculate_profit
from app.pricing.opportunity import OpportunityComponents, calculate_opportunity_score
from app.schemas.api import (
    Comparison,
    Dashboard,
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
)

PLATFORMS: tuple[Platform, ...] = ("csfloat", "skinport", "dmarket")
INTEGRATION_STATUS: dict[Platform, IntegrationStatus] = {
    "csfloat": "OFFICIAL_API",
    "skinport": "PARTIAL",
    "dmarket": "OFFICIAL_API",
}
DEMO_SALE_FEE_RATE = Decimal("0.10")


@dataclass(frozen=True)
class Analysis:
    estimated_value: Decimal | None
    potential_profit: Decimal | None
    roi: Decimal | None
    opportunity_score: int | None
    float_score: int | None
    liquidity: int | None
    confidence: int | None
    warnings: list[str]


def _quantize(value: Decimal | None) -> Decimal | None:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if value is not None else None


def _analyse(
    listing: MarketListing,
    observations: list[PriceObservation],
    peer_floats: list[Decimal],
    mode: Mode,
) -> Analysis:
    score_float = float_score(listing.item.float_value, peer_floats)
    sales = [
        item
        for item in observations
        if item.observation_type == "SALE" and item.price_eur_reference is not None
    ]
    sale_summary = summarize([cast(Decimal, item.price_eur_reference) for item in sales])
    if sale_summary is None or sale_summary.sample_size < 3:
        return Analysis(
            None,
            None,
            None,
            None,
            score_float,
            None,
            None,
            ["Historique de ventes réalisé insuffisant : valeur et profit laissés inconnus."],
        )

    estimated = sale_summary.median
    volume = sum(item.volume or 0 for item in sales)
    liquidity = min(100, volume * 5)
    confidence = min(90, 35 + sale_summary.sample_size * 4)
    warnings = ["Valeur médiane issue de ventes observées ; elle ne constitue pas un prix garanti."]

    potential_profit: Decimal | None = None
    roi: Decimal | None = None
    opportunity: int | None = None
    if mode == "demo" and listing.price_eur_reference is not None:
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
        history_component = min(100, sale_summary.sample_size * 5)
        float_component = score_float if score_float is not None else 0
        risk_component = 50
        opportunity = calculate_opportunity_score(
            OpportunityComponents(
                price_discount=price_component,
                liquidity=liquidity,
                sales_history=history_component,
                float_quality=float_component,
                market_confidence=confidence,
                risk=risk_component,
            )
        )
        warnings.append(
            "DEMO — profit calculé avec 10 % de frais de vente synthétiques et zéro autre frais."
        )
    elif listing.price_eur_reference is not None:
        warnings.append(
            "Frais effectifs et plateforme de revente inconnus : profit et ROI non calculés."
        )
    return Analysis(
        _quantize(estimated),
        _quantize(potential_profit),
        roi.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if roi is not None else None,
        opportunity,
        score_float,
        liquidity,
        confidence,
        warnings,
    )


def _load(session: Session, mode: Mode) -> tuple[list[MarketListing], list[PriceObservation]]:
    listings = list(
        session.scalars(
            select(MarketListing)
            .where(MarketListing.mode == mode, MarketListing.status == "ACTIVE")
            .options(selectinload(MarketListing.item).selectinload(CS2Item.stickers))
            .order_by(MarketListing.observed_at.desc(), MarketListing.id)
        )
    )
    observations = list(
        session.scalars(
            select(PriceObservation)
            .where(PriceObservation.mode == mode)
            .order_by(PriceObservation.timestamp.desc())
        )
    )
    return listings, observations


def _row(
    listing: MarketListing,
    observations_by_name: dict[str, list[PriceObservation]],
    floats_by_name: dict[str, list[Decimal]],
    mode: Mode,
) -> ScannerRow:
    analysis = _analyse(
        listing,
        observations_by_name.get(listing.item.market_hash_name, []),
        floats_by_name.get(listing.item.market_hash_name, []),
        mode,
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
        confidence=analysis.confidence,
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
        if mode == "live" and status == "online":
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
    listings, observations = _load(session, mode)
    by_name: dict[str, list[PriceObservation]] = defaultdict(list)
    floats: dict[str, list[Decimal]] = defaultdict(list)
    for observation in observations:
        by_name[observation.market_hash_name].append(observation)
    for listing in listings:
        if listing.item.float_value is not None:
            floats[listing.item.market_hash_name].append(listing.item.float_value)
    rows = [_row(listing, by_name, floats, mode) for listing in listings]
    statuses = market_statuses(session, mode, settings)
    last_sync = max(
        (status.last_sync_at for status in statuses if status.last_sync_at is not None),
        default=None,
    )
    warnings: list[str] = []
    if mode == "demo":
        warnings.append("DEMO — toutes les données sont des fixtures synthétiques isolées du réel.")
    if any(row.price_eur_reference is None for row in rows):
        warnings.append("Certains prix n'ont pas de taux EUR sourcé et ne sont pas comparables.")
    if any(status.status in {"error", "unavailable", "stale", "very_stale"} for status in statuses):
        warnings.append("Une ou plusieurs plateformes sont indisponibles ou périmées.")
    if any(status.status == "not_configured" for status in statuses):
        warnings.append("Certaines plateformes optionnelles ne sont pas configurées.")
    return Dashboard(
        mode=mode,
        listings=rows,
        markets=statuses,
        last_sync_at=last_sync,
        warnings=warnings,
    )


def build_item_detail(
    session: Session,
    listing_id: str,
    mode: Mode,
    settings: Settings,
) -> ItemDetail | None:
    dashboard = build_dashboard(session, mode, settings)
    row = next((item for item in dashboard.listings if item.id == listing_id), None)
    if row is None:
        return None
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
    return ItemDetail(
        mode=mode,
        item=row,
        comparisons=comparisons,
        history=[Observation.model_validate(item) for item in observations],
        warnings=dashboard.warnings,
    )


def refresh_opportunities(session: Session, mode: Mode, settings: Settings) -> int:
    listings, observations = _load(session, mode)
    by_name: dict[str, list[PriceObservation]] = defaultdict(list)
    floats: dict[str, list[Decimal]] = defaultdict(list)
    for observation in observations:
        by_name[observation.market_hash_name].append(observation)
    for listing in listings:
        if listing.item.float_value is not None:
            floats[listing.item.market_hash_name].append(listing.item.float_value)

    now = datetime.now(UTC)
    active_listing_ids: set[str] = set()
    count = 0
    for listing in listings:
        analysis = _analyse(
            listing,
            by_name.get(listing.item.market_hash_name, []),
            floats.get(listing.item.market_hash_name, []),
            mode,
        )
        if analysis.opportunity_score is None:
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

    existing = session.scalars(
        select(MarketOpportunity).where(
            MarketOpportunity.mode == mode,
            MarketOpportunity.status == "ACTIVE",
        )
    )
    for opportunity in existing:
        if opportunity.listing_id not in active_listing_ids:
            opportunity.status = "INACTIVE"
            opportunity.updated_at = now
    session.flush()
    return count
