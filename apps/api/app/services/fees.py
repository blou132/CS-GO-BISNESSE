from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlatformFeeSchedule
from app.pricing.fees import FeeCalculation, FeeRule, FeeType, calculate_fee


def calculate_stored_fee(
    session: Session,
    *,
    base_amount: Decimal,
    currency: str,
    platform: str,
    fee_type: FeeType,
    item_name: str | None = None,
    at: datetime | None = None,
) -> FeeCalculation | None:
    current = at or datetime.now(UTC)
    rows = list(
        session.scalars(
            select(PlatformFeeSchedule).where(
                PlatformFeeSchedule.platform == platform,
                PlatformFeeSchedule.fee_type == fee_type,
                PlatformFeeSchedule.valid_from <= current,
            )
        )
    )
    rules = [
        FeeRule(
            platform=row.platform,
            fee_type=cast(FeeType, row.fee_type),
            rate=row.rate,
            fixed_amount=row.fixed_amount,
            minimum_fee=row.minimum_fee,
            currency=row.currency,
            min_amount=row.min_amount,
            max_amount=row.max_amount,
            applies_to=row.applies_to,
            source=row.source,
            verified_at=row.verified_at,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
        )
        for row in rows
    ]
    return calculate_fee(
        base_amount,
        currency,
        platform,
        fee_type,
        rules,
        item_name=item_name,
        at=current,
    )
