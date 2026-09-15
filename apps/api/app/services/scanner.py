from dataclasses import dataclass
from decimal import Decimal
from math import ceil
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, and_, asc, desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models import CS2Item, ListingAnalysisSnapshot, MarketListing
from app.schemas.api import Mode, Platform, ScannerFacets, ScannerPage, ScannerSort
from app.services.analysis import row_from_snapshot, row_without_snapshot
from app.services.freshness import fresh_listing


@dataclass(frozen=True)
class ScannerQuery:
    mode: Mode = "live"
    page: int = 1
    page_size: int = 50
    sort: ScannerSort = "opportunity"
    market: Platform | None = None
    weapon: str | None = None
    skin: str | None = None
    exterior: str | None = None
    currency: str | None = None
    pattern_type: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_profit: Decimal | None = None
    min_roi: Decimal | None = None
    max_float: Decimal | None = None
    paint_seed: int | None = None
    min_score: int | None = None
    min_liquidity: int | None = None
    min_confidence: int | None = None
    max_risk: int | None = None
    max_spread: Decimal | None = None
    market_hash_name: str | None = None
    paint_seeds: tuple[int, ...] = ()
    doppler_phase: str | None = None


def build_scanner_page(
    session: Session, query: ScannerQuery, settings: Settings | None = None
) -> ScannerPage:
    statement = _filtered_statement(query, settings)
    total = int(
        session.scalar(
            select(func.count()).select_from(
                statement.with_only_columns(MarketListing.id).order_by(None).subquery()
            )
        )
        or 0
    )
    ordered = _apply_order(statement, query.sort)
    records = session.execute(
        ordered.offset((query.page - 1) * query.page_size).limit(query.page_size)
    ).all()
    items = [
        row_from_snapshot(listing, snapshot)
        if snapshot is not None
        else row_without_snapshot(listing)
        for listing, snapshot in records
    ]
    missing = sum(snapshot is None for _, snapshot in records)
    warnings = [f"{missing} analyse(s) attendent la prochaine synchronisation."] if missing else []
    return ScannerPage(
        mode=query.mode,
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
        pages=ceil(total / query.page_size) if total else 0,
        facets=_facets(session, query.mode),
        warnings=warnings,
    )


def _filtered_statement(
    query: ScannerQuery,
    settings: Settings | None = None,
) -> Select[tuple[MarketListing, ListingAnalysisSnapshot | None]]:
    statement = (
        select(MarketListing, ListingAnalysisSnapshot)
        .join(CS2Item, MarketListing.item_id == CS2Item.id)
        .outerjoin(
            ListingAnalysisSnapshot,
            and_(
                ListingAnalysisSnapshot.mode == MarketListing.mode,
                ListingAnalysisSnapshot.listing_id == MarketListing.id,
            ),
        )
        .options(selectinload(MarketListing.item).selectinload(CS2Item.stickers))
        .where(MarketListing.mode == query.mode, MarketListing.status == "ACTIVE")
    )
    if query.market:
        statement = statement.where(MarketListing.platform == query.market)
    if query.mode == "live":
        statement = statement.where(fresh_listing(settings or Settings(_env_file=None)))
    if query.market_hash_name:
        statement = statement.where(CS2Item.market_hash_name == query.market_hash_name)
    if query.paint_seeds:
        statement = statement.where(CS2Item.paint_seed.in_(query.paint_seeds))
    if query.doppler_phase:
        statement = statement.where(
            func.lower(CS2Item.doppler_phase) == query.doppler_phase.lower()
        )
    if query.weapon:
        statement = statement.where(CS2Item.weapon == query.weapon)
    if query.skin:
        statement = statement.where(CS2Item.skin.icontains(query.skin, autoescape=True))
    if query.exterior:
        statement = statement.where(CS2Item.exterior == query.exterior)
    if query.currency:
        statement = statement.where(MarketListing.currency_original == query.currency)
    if query.pattern_type == "doppler":
        statement = statement.where(CS2Item.doppler_phase.is_not(None))
    elif query.pattern_type == "fade":
        statement = statement.where(CS2Item.fade_percentage.is_not(None))
    elif query.pattern_type == "sticker":
        statement = statement.where(CS2Item.stickers.any())
    if query.min_price is not None:
        statement = statement.where(MarketListing.price_eur_reference >= query.min_price)
    if query.max_price is not None:
        statement = statement.where(MarketListing.price_eur_reference <= query.max_price)
    if query.min_profit is not None:
        statement = statement.where(
            ListingAnalysisSnapshot.potential_profit_eur >= query.min_profit
        )
    if query.min_roi is not None:
        statement = statement.where(ListingAnalysisSnapshot.roi >= query.min_roi)
    if query.max_float is not None:
        statement = statement.where(CS2Item.float_value <= query.max_float)
    if query.paint_seed is not None:
        statement = statement.where(CS2Item.paint_seed == query.paint_seed)
    if query.min_score is not None:
        statement = statement.where(ListingAnalysisSnapshot.opportunity_score >= query.min_score)
    if query.min_liquidity is not None:
        statement = statement.where(ListingAnalysisSnapshot.liquidity_score >= query.min_liquidity)
    if query.min_confidence is not None:
        statement = statement.where(ListingAnalysisSnapshot.confidence >= query.min_confidence)
    if query.max_risk is not None:
        statement = statement.where(ListingAnalysisSnapshot.risk_score <= query.max_risk)
    if query.max_spread is not None:
        statement = statement.where(ListingAnalysisSnapshot.spread_percent <= query.max_spread)
    return cast(Select[tuple[MarketListing, ListingAnalysisSnapshot | None]], statement)


def _apply_order(
    statement: Select[tuple[MarketListing, ListingAnalysisSnapshot | None]],
    sort: ScannerSort,
) -> Select[tuple[MarketListing, ListingAnalysisSnapshot | None]]:
    fields: dict[ScannerSort, ColumnElement[Any]] = {
        "opportunity": desc(ListingAnalysisSnapshot.opportunity_score).nulls_last(),
        "roi": desc(ListingAnalysisSnapshot.roi).nulls_last(),
        "profit": desc(ListingAnalysisSnapshot.potential_profit_eur).nulls_last(),
        "price": asc(MarketListing.price_eur_reference).nulls_last(),
        "float": asc(CS2Item.float_value).nulls_last(),
        "liquidity": desc(ListingAnalysisSnapshot.liquidity_score).nulls_last(),
        "risk": asc(ListingAnalysisSnapshot.risk_score).nulls_last(),
        "confidence": desc(ListingAnalysisSnapshot.confidence).nulls_last(),
        "spread": asc(ListingAnalysisSnapshot.spread_percent).nulls_last(),
        "discount": desc(
            ListingAnalysisSnapshot.estimated_value_eur - MarketListing.price_eur_reference
        ).nulls_last(),
        "recent": desc(MarketListing.observed_at),
    }
    return statement.order_by(fields[sort], MarketListing.observed_at.desc(), MarketListing.id)


def _facets(session: Session, mode: Mode) -> ScannerFacets:
    base = (MarketListing.mode == mode, MarketListing.status == "ACTIVE")
    markets = session.scalars(
        select(MarketListing.platform).where(*base).distinct().order_by(MarketListing.platform)
    )
    weapons = session.scalars(
        select(CS2Item.weapon)
        .join(MarketListing, MarketListing.item_id == CS2Item.id)
        .where(*base, CS2Item.weapon.is_not(None))
        .distinct()
        .order_by(CS2Item.weapon)
    )
    exteriors = session.scalars(
        select(CS2Item.exterior)
        .join(MarketListing, MarketListing.item_id == CS2Item.id)
        .where(*base, CS2Item.exterior.is_not(None))
        .distinct()
        .order_by(CS2Item.exterior)
    )
    currencies = session.scalars(
        select(MarketListing.currency_original)
        .where(*base)
        .distinct()
        .order_by(MarketListing.currency_original)
    )
    return ScannerFacets(
        markets=[cast(Platform, value) for value in markets],
        weapons=[value for value in weapons if value is not None],
        exteriors=[value for value in exteriors if value is not None],
        currencies=list(currencies),
    )
