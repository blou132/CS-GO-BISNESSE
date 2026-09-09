from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import (
    AggregateMarketStat,
    BuyOrderObservation,
    MarketListing,
    MarketOpportunity,
    MarketSyncState,
    PriceObservation,
    RealizedSale,
)
from app.schemas.api import MarketMetrics, MarketMonitor, MarketStatus
from app.services.analysis import market_statuses


def build_market_monitor(
    session: Session,
    settings: Settings,
    *,
    scheduler_running: bool = False,
) -> MarketMonitor:
    statuses = market_statuses(session, "live", settings)
    warnings: list[str] = []
    if not settings.market_sync_enabled:
        warnings.append(
            "Monitoring périodique désactivé; seules les synchronisations manuelles tournent."
        )
    elif not settings.market_sync_query.strip():
        warnings.append("Monitoring périodique activé sans requête de marché configurée.")
    if any(status.status == "not_configured" for status in statuses):
        warnings.append("Une ou plusieurs plateformes optionnelles attendent leurs clés serveur.")
    if any(status.status in {"error", "unavailable"} for status in statuses):
        warnings.append("Une ou plusieurs plateformes ont échoué lors de la dernière tentative.")
    if any(status.status in {"stale", "very_stale"} for status in statuses):
        warnings.append("Une ou plusieurs plateformes ont des données anciennes.")

    return MarketMonitor(
        sync_enabled=settings.market_sync_enabled,
        sync_query_configured=bool(settings.market_sync_query.strip()),
        scheduler_running=scheduler_running,
        platforms=statuses,
        metrics=_metrics(session, "live", statuses),
        warnings=warnings,
    )


def _metrics(session: Session, mode: str, statuses: list[MarketStatus]) -> MarketMetrics:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)
    success_times = [
        _aware(status.last_success_at) for status in statuses if status.last_success_at is not None
    ]
    average_freshness = (
        round(sum((now - value).total_seconds() for value in success_times) / len(success_times))
        if success_times
        else None
    )
    return MarketMetrics(
        total_listings=_count(
            session,
            select(func.count()).select_from(MarketListing).where(MarketListing.mode == mode),
        ),
        active_listings=_count(
            session,
            select(func.count())
            .select_from(MarketListing)
            .where(MarketListing.mode == mode, MarketListing.status == "ACTIVE"),
        ),
        price_observations=_count(
            session,
            select(func.count()).select_from(PriceObservation).where(PriceObservation.mode == mode),
        ),
        aggregate_market_stats=_count(
            session,
            select(func.count())
            .select_from(AggregateMarketStat)
            .where(AggregateMarketStat.mode == mode),
        ),
        realized_sales=_count(
            session,
            select(func.count()).select_from(RealizedSale).where(RealizedSale.mode == mode),
        ),
        buy_order_observations=_count(
            session,
            select(func.count())
            .select_from(BuyOrderObservation)
            .where(BuyOrderObservation.mode == mode),
        ),
        active_opportunities=_count(
            session,
            select(func.count())
            .select_from(MarketOpportunity)
            .where(MarketOpportunity.mode == mode, MarketOpportunity.status == "ACTIVE"),
        ),
        sync_errors_24h=_count(
            session,
            select(func.count())
            .select_from(MarketSyncState)
            .where(
                MarketSyncState.mode == "live",
                or_(
                    MarketSyncState.last_failure_at >= day_ago,
                    MarketSyncState.last_error_at >= day_ago,
                ),
            ),
        ),
        average_freshness_seconds=average_freshness,
    )


def _count(session: Session, statement: Any) -> int:
    value = session.scalar(statement)
    return int(value or 0)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
