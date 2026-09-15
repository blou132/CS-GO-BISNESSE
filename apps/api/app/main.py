from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.currencies.scheduler import FXRateScheduler
from app.currencies.service import build_fx_status
from app.db.session import build_engine, build_session_factory
from app.markets.registry import source_catalog
from app.pricing.finance import (
    ProfitInput,
    PurchaseCostInput,
    SaleRevenueInput,
    calculate_net_profit,
    calculate_profit,
)
from app.schemas.api import (
    Dashboard,
    FeeQuoteRequest,
    FeeQuoteResponse,
    FXStatus,
    IntegrationCatalog,
    ItemDetail,
    MarketMonitor,
    Mode,
    NetProfitRequest,
    NetProfitResponse,
    ProfitRequest,
    ProfitResponse,
    ScannerPage,
    ScannerSort,
    SystemHealth,
)
from app.schemas.watchlist import WatchlistPage, WatchRuleInput, WatchRuleView
from app.services.analysis import build_dashboard, build_item_detail, market_statuses
from app.services.demo import ensure_demo
from app.services.fees import calculate_stored_fee
from app.services.health import system_health
from app.services.monitoring import build_market_monitor
from app.services.realtime import SkinportRealtime
from app.services.scanner import ScannerQuery, build_scanner_page
from app.services.scheduler import MarketSyncScheduler
from app.services.sync import (
    SyncAlreadyRunning,
    SyncCoordinator,
    build_adapters,
    close_adapters,
    synchronize,
)
from app.services.watchlist import find_rule, list_rules, matching_query, save_rule

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessions = build_session_factory(engine)
    app.state.adapters = build_adapters(settings)
    app.state.sync_coordinator = SyncCoordinator()
    app.state.market_scheduler = MarketSyncScheduler(
        app.state.sessions,
        app.state.adapters,
        settings,
        app.state.sync_coordinator,
    )
    app.state.fx_scheduler = FXRateScheduler(app.state.sessions, settings)
    app.state.skinport_realtime = SkinportRealtime(app.state.sessions, settings)
    await app.state.market_scheduler.start()
    await app.state.fx_scheduler.start()
    await app.state.skinport_realtime.start()
    try:
        yield
    finally:
        await app.state.skinport_realtime.stop()
        await app.state.fx_scheduler.stop()
        await app.state.market_scheduler.stop()
        await close_adapters(app.state.adapters)
        engine.dispose()


app = FastAPI(
    title="CS2 Arbitrage Hub API",
    version="0.2.0",
    description="API privée en lecture et analyse ; aucune transaction de marché.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)


def sessions(request: Request) -> sessionmaker[Session]:
    return cast(sessionmaker[Session], request.app.state.sessions)


def database_session(
    factory: Annotated[sessionmaker[Session], Depends(sessions)],
) -> Iterator[Session]:
    with factory() as session:
        yield session


DbSession = Annotated[Session, Depends(database_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready(response: Response, session: DbSession) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}


@app.get("/health/status", response_model=SystemHealth, tags=["health"])
def status_view(session: DbSession, settings: SettingsDep) -> SystemHealth:
    return system_health(session, settings)


def _dashboard(session: Session, mode: Mode, settings: Settings) -> Dashboard:
    try:
        if mode == "demo":
            ensure_demo(session, settings)
        return build_dashboard(session, mode, settings)
    except SQLAlchemyError as error:
        session.rollback()
        raise HTTPException(status_code=503, detail="Base de données indisponible.") from error


@app.get("/api/dashboard", response_model=Dashboard, tags=["analysis"])
def dashboard(
    session: DbSession,
    settings: SettingsDep,
    mode: Annotated[Mode, Query()] = "live",
) -> Dashboard:
    return _dashboard(session, mode, settings)


@app.get("/api/scanner", response_model=ScannerPage, tags=["analysis"])
def scanner(
    session: DbSession,
    settings: SettingsDep,
    mode: Annotated[Mode, Query()] = "live",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=10, le=100)] = 50,
    sort: Annotated[ScannerSort, Query()] = "opportunity",
    market: Annotated[Literal["csfloat", "skinport", "dmarket"] | None, Query()] = None,
    weapon: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    skin: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
    exterior: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    currency: Annotated[str | None, Query(pattern="^[A-Z]{3}$")] = None,
    pattern_type: Annotated[Literal["doppler", "fade", "sticker"] | None, Query()] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    min_profit: Annotated[Decimal | None, Query()] = None,
    min_roi: Annotated[Decimal | None, Query()] = None,
    max_float: Annotated[Decimal | None, Query(ge=0, le=1)] = None,
    paint_seed: Annotated[int | None, Query(ge=0, le=1000)] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_liquidity: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_confidence: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_risk: Annotated[int | None, Query(ge=0, le=100)] = None,
    max_spread: Annotated[Decimal | None, Query(ge=0)] = None,
) -> ScannerPage:
    if mode == "demo":
        ensure_demo(session, settings)
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="Le prix minimum dépasse le prix maximum.")
    return build_scanner_page(
        session,
        ScannerQuery(
            mode=mode,
            page=page,
            page_size=page_size,
            sort=sort,
            market=market,
            weapon=weapon,
            skin=skin,
            exterior=exterior,
            currency=currency,
            pattern_type=pattern_type,
            min_price=min_price,
            max_price=max_price,
            min_profit=min_profit,
            min_roi=min_roi,
            max_float=max_float,
            paint_seed=paint_seed,
            min_score=min_score,
            min_liquidity=min_liquidity,
            min_confidence=min_confidence,
            max_risk=max_risk,
            max_spread=max_spread,
        ),
        settings,
    )


@app.post("/api/sync", response_model=Dashboard, tags=["analysis"])
async def sync_markets(
    request: Request,
    session: DbSession,
    settings: SettingsDep,
    mode: Annotated[Mode, Query()] = "live",
    query: Annotated[str | None, Query(min_length=3, max_length=120)] = None,
) -> Dashboard:
    if mode == "demo":
        ensure_demo(session, settings)
        return build_dashboard(session, mode, settings)
    if query is None or not query.strip():
        raise HTTPException(status_code=422, detail="Un nom de skin est requis en mode live.")
    try:
        await synchronize(
            request.app.state.sessions,
            request.app.state.adapters,
            settings,
            query.strip(),
            request.app.state.sync_coordinator,
        )
    except SyncAlreadyRunning as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.expire_all()
    return _dashboard(session, mode, settings)


@app.get("/api/watchlist", response_model=WatchlistPage, tags=["watchlist"])
def watchlist(
    session: DbSession,
    mode: Annotated[Mode, Query()] = "live",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> WatchlistPage:
    return list_rules(session, mode, page, page_size)


@app.post("/api/watchlist", response_model=WatchRuleView, status_code=201, tags=["watchlist"])
def create_watch_rule(
    payload: WatchRuleInput,
    session: DbSession,
    mode: Annotated[Mode, Query()] = "live",
) -> WatchRuleView:
    return save_rule(session, mode, payload)


@app.put("/api/watchlist/{rule_id}", response_model=WatchRuleView, tags=["watchlist"])
def update_watch_rule(
    rule_id: UUID,
    payload: WatchRuleInput,
    session: DbSession,
    mode: Annotated[Mode, Query()] = "live",
) -> WatchRuleView:
    rule = find_rule(session, mode, str(rule_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Règle introuvable dans ce mode.")
    return save_rule(session, mode, payload, rule)


@app.delete("/api/watchlist/{rule_id}", status_code=204, tags=["watchlist"])
def delete_watch_rule(
    rule_id: UUID,
    session: DbSession,
    mode: Annotated[Mode, Query()] = "live",
) -> Response:
    rule = find_rule(session, mode, str(rule_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Règle introuvable dans ce mode.")
    session.delete(rule)
    session.commit()
    return Response(status_code=204)


@app.get("/api/watchlist/{rule_id}/matches", response_model=ScannerPage, tags=["watchlist"])
def watch_rule_matches(
    rule_id: UUID,
    session: DbSession,
    settings: SettingsDep,
    mode: Annotated[Mode, Query()] = "live",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=10, le=100)] = 25,
    sort: Annotated[ScannerSort, Query()] = "recent",
) -> ScannerPage:
    rule = find_rule(session, mode, str(rule_id))
    if rule is None:
        raise HTTPException(status_code=404, detail="Règle introuvable dans ce mode.")
    if not rule.enabled:
        raise HTTPException(status_code=409, detail="Cette règle est en pause.")
    if mode == "demo":
        ensure_demo(session, settings)
    return build_scanner_page(session, matching_query(rule, mode, page, page_size, sort), settings)


@app.get("/api/market-monitor", response_model=MarketMonitor, tags=["analysis"])
def market_monitor(request: Request, session: DbSession, settings: SettingsDep) -> MarketMonitor:
    scheduler = getattr(request.app.state, "market_scheduler", None)
    scheduler_running = bool(scheduler and scheduler.running)
    result = build_market_monitor(session, settings, scheduler_running=scheduler_running)
    stream = request.app.state.skinport_realtime.snapshot()
    result.realtime["skinport"] = stream
    if stream.enabled and stream.status in {"degraded", "disconnected"}:
        result.warnings.append(
            "Skinport temps reel indisponible ou incomplet ; etat REST independant."
        )
    return result


@app.get("/api/integrations", response_model=IntegrationCatalog, tags=["analysis"])
def integrations(session: DbSession, settings: SettingsDep) -> IntegrationCatalog:
    fx_scheduler = getattr(app.state, "fx_scheduler", None)
    return IntegrationCatalog(
        sources=source_catalog(
            settings,
            market_statuses(session, "live", settings),
            {
                "ecb": (
                    str(fx_scheduler.runtime_status) if fx_scheduler is not None else "unavailable"
                )
            },
        ),
        generated_at=datetime.now(UTC),
    )


@app.get("/api/fx", response_model=FXStatus, tags=["analysis"])
def fx_status(request: Request, session: DbSession, settings: SettingsDep) -> FXStatus:
    return build_fx_status(session, settings, getattr(request.app.state, "fx_scheduler", None))


@app.get("/api/items/{listing_id}", response_model=ItemDetail, tags=["analysis"])
def item_detail(
    listing_id: str,
    session: DbSession,
    settings: SettingsDep,
    mode: Annotated[Mode, Query()] = "live",
) -> ItemDetail:
    if mode == "demo":
        ensure_demo(session, settings)
    result = build_item_detail(session, listing_id, mode, settings)
    if result is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable dans ce mode.")
    return result


@app.post("/api/calculations/profit", response_model=ProfitResponse, tags=["calculations"])
def profit(payload: ProfitRequest) -> ProfitResponse:
    result = calculate_profit(ProfitInput(**payload.model_dump()))
    return ProfitResponse(**result.__dict__)


@app.post("/api/calculations/net-profit", response_model=NetProfitResponse, tags=["calculations"])
def net_profit(payload: NetProfitRequest) -> NetProfitResponse:
    result = calculate_net_profit(
        PurchaseCostInput(**payload.purchase.model_dump()),
        SaleRevenueInput(**payload.sale.model_dump()),
        estimated_holding_days=payload.estimated_holding_days,
    )
    return NetProfitResponse(
        purchase=result.purchase.__dict__,
        sale=result.sale.__dict__,
        net_profit_eur=result.net_profit_eur,
        roi_percent=result.roi_percent,
        roi_per_day_percent=result.roi_per_day_percent,
    )


@app.post("/api/calculations/fee", response_model=FeeQuoteResponse, tags=["calculations"])
def fee_quote(payload: FeeQuoteRequest, session: DbSession) -> FeeQuoteResponse:
    result = calculate_stored_fee(session, **payload.model_dump())
    if result is None:
        return FeeQuoteResponse(
            known=False,
            platform=payload.platform,
            fee_type=payload.fee_type,
            base_amount=payload.base_amount,
            currency=payload.currency,
            warning="Aucun barème officiel applicable : frais laissés inconnus.",
        )
    return FeeQuoteResponse(known=True, **result.__dict__)
