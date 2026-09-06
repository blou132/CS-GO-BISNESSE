import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.markets import CSFloatAdapter, DMarketAdapter, SkinportAdapter
from app.markets.base import AdapterResult, MarketAdapter, MarketAdapterError
from app.models import MarketSyncState
from app.services.storage import persist_result


def build_adapters(settings: Settings) -> dict[str, MarketAdapter]:
    return {
        "csfloat": CSFloatAdapter(
            settings.csfloat_api_key.get_secret_value() if settings.csfloat_api_key else None
        ),
        "skinport": SkinportAdapter(),
        "dmarket": DMarketAdapter(
            settings.dmarket_public_key.get_secret_value() if settings.dmarket_public_key else None,
            settings.dmarket_secret_key.get_secret_value() if settings.dmarket_secret_key else None,
        ),
    }


def _state(session: Session, platform: str) -> MarketSyncState:
    value = session.scalar(
        select(MarketSyncState).where(
            MarketSyncState.mode == "live",
            MarketSyncState.platform == platform,
        )
    )
    if value is None:
        value = MarketSyncState(
            mode="live", platform=platform, status="idle", message="Synchronisation non exécutée."
        )
        session.add(value)
    return value


async def synchronize(
    factory: sessionmaker[Session],
    adapters: dict[str, MarketAdapter],
    settings: Settings,
    query: str,
) -> None:
    async def collect(
        platform: str, adapter: MarketAdapter
    ) -> tuple[str, AdapterResult | Exception]:
        try:
            return platform, await adapter.search_items(query)
        except Exception as error:  # converted below to a safe state
            return platform, error

    results = await asyncio.gather(*(collect(name, adapter) for name, adapter in adapters.items()))
    now = datetime.now(UTC)
    for platform, result in results:
        with factory() as session:
            state = _state(session, platform)
            state.last_attempt_at = now
            if isinstance(result, AdapterResult):
                persist_result(session, result, platform, "live", settings)
                state.status = "online"
                state.message = "; ".join(result.warnings) or "Synchronisation réussie."
                state.last_sync_at = now
            else:
                state.status = (
                    "unavailable"
                    if isinstance(result, MarketAdapterError) and result.code == "configuration"
                    else "error"
                )
                state.message = (
                    result.message
                    if isinstance(result, MarketAdapterError)
                    else "Erreur interne pendant la synchronisation."
                )
                state.last_error = state.message
                state.last_error_at = now
            session.commit()


async def close_adapters(adapters: dict[str, MarketAdapter]) -> None:
    await asyncio.gather(*(adapter.aclose() for adapter in adapters.values()))
