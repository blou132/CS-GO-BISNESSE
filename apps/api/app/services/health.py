from contextlib import suppress

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.api import ExternalMarketHealth, SystemHealth
from app.services.analysis import PLATFORMS, market_statuses


def system_health(session: Session, settings: Settings) -> SystemHealth:
    try:
        session.execute(text("SELECT 1"))
        statuses = market_statuses(session, "live", settings)
    except SQLAlchemyError:
        with suppress(SQLAlchemyError):
            session.rollback()
        return SystemHealth(
            database="unavailable",
            markets={platform: ExternalMarketHealth(status="unknown") for platform in PLATFORMS},
        )

    return SystemHealth(
        database="healthy",
        markets={
            status.platform: ExternalMarketHealth(
                status=status.status,
                last_attempt_at=status.last_attempt_at,
                last_success_at=status.last_sync_at,
                last_error=status.last_error,
                last_error_at=status.last_error_at,
            )
            for status in statuses
        },
    )
