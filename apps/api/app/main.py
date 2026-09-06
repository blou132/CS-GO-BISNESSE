from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory
from app.pricing.finance import ProfitInput, calculate_profit
from app.schemas.api import Dashboard, ItemDetail, Mode, ProfitRequest, ProfitResponse, SystemHealth
from app.services.analysis import build_dashboard, build_item_detail
from app.services.demo import ensure_demo
from app.services.health import system_health
from app.services.sync import build_adapters, close_adapters, synchronize

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessions = build_session_factory(engine)
    app.state.adapters = build_adapters(settings)
    yield
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
    await synchronize(
        request.app.state.sessions, request.app.state.adapters, settings, query.strip()
    )
    session.expire_all()
    return _dashboard(session, mode, settings)


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
