from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import WatchRule
from app.schemas.api import Mode, ScannerSort
from app.schemas.watchlist import WatchFilters, WatchlistPage, WatchRuleInput, WatchRuleView
from app.services.scanner import ScannerQuery


def list_rules(session: Session, mode: Mode, page: int, page_size: int) -> WatchlistPage:
    total = int(
        session.scalar(select(func.count()).select_from(WatchRule).where(WatchRule.mode == mode))
        or 0
    )
    rules = session.scalars(
        select(WatchRule)
        .where(WatchRule.mode == mode)
        .order_by(WatchRule.created_at.desc(), WatchRule.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return WatchlistPage(
        mode=mode,
        items=[WatchRuleView.model_validate(rule) for rule in rules],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size),
    )


def find_rule(session: Session, mode: Mode, rule_id: str) -> WatchRule | None:
    return session.scalar(select(WatchRule).where(WatchRule.mode == mode, WatchRule.id == rule_id))


def save_rule(
    session: Session, mode: Mode, payload: WatchRuleInput, rule: WatchRule | None = None
) -> WatchRuleView:
    if rule is None:
        rule = WatchRule(mode=mode)
        session.add(rule)
    rule.name = payload.name
    rule.enabled = payload.enabled
    # JSON serialization preserves Decimal amounts as strings.
    rule.filters = payload.filters.model_dump(mode="json")
    session.commit()
    session.refresh(rule)
    return WatchRuleView.model_validate(rule)


def matching_query(
    rule: WatchRule, mode: Mode, page: int, page_size: int, sort: ScannerSort
) -> ScannerQuery:
    filters = WatchFilters.model_validate(rule.filters)
    return ScannerQuery(
        mode=mode,
        page=page,
        page_size=page_size,
        sort=sort,
        market_hash_name=filters.market_hash_name,
        market=filters.market,
        max_price=filters.max_price_eur,
        max_float=filters.max_float,
        paint_seeds=tuple(filters.paint_seeds),
        doppler_phase=filters.doppler_phase,
    )
