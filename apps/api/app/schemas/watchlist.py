from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.api import Mode, Money, Platform

PaintSeed = Annotated[int, Field(strict=True, ge=0, le=1000)]
DopplerPhase = Literal[
    "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Ruby", "Sapphire", "Black Pearl", "Emerald"
]


class WatchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    market_hash_name: str = Field(min_length=3, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$")
    market: Platform | None = None
    max_price_eur: Money | None = None
    max_float: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    paint_seeds: list[PaintSeed] = Field(default_factory=list, max_length=100)
    doppler_phase: DopplerPhase | None = None

    @field_validator("paint_seeds")
    @classmethod
    def distinct_seeds(cls, values: list[int]) -> list[int]:
        return sorted(set(values))


class WatchRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f\x7f]+$")
    enabled: bool = Field(default=True, strict=True)
    filters: WatchFilters


class WatchRuleView(WatchRuleInput):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    mode: Mode
    created_at: datetime
    updated_at: datetime


class WatchlistPage(BaseModel):
    mode: Mode
    items: list[WatchRuleView]
    total: int
    page: int
    page_size: int
    pages: int
