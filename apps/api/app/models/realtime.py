from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base


class RealtimeReceipt(Base):
    """Compact idempotency ledger; deliberately contains no raw provider payload."""

    __tablename__ = "realtime_receipts"
    event_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(256))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
