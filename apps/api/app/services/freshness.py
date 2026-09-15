"""Source-specific listing freshness, including when a collector is stopped."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, and_, or_

from app.core.config import Settings
from app.models import MarketListing


def fresh_listing(settings: Settings) -> ColumnElement[bool]:
    now = datetime.now(UTC)
    return and_(
        MarketListing.observed_at <= now,
        or_(
            and_(
                MarketListing.platform == "skinport",
                MarketListing.observed_at
                >= now - timedelta(seconds=settings.skinport_realtime_stale_seconds),
            ),
            and_(
                MarketListing.platform != "skinport",
                MarketListing.observed_at >= now - timedelta(seconds=settings.stale_after_seconds),
            ),
        ),
    )
