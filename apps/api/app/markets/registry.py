"""Immutable registry of reviewed market and trade data sources."""

from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.schemas.api import MarketStatus

SourceType = Literal["MARKETPLACE", "TRADE", "REFERENCE"]
AccessStatus = Literal[
    "OFFICIAL_API",
    "PUBLIC_API",
    "REQUIRES_APPROVAL",
    "RESEARCH_REQUIRED",
    "UNAVAILABLE",
]


@dataclass(frozen=True)
class MarketSource:
    id: str
    name: str
    source_type: SourceType
    access_status: AccessStatus
    auth_required: bool
    capabilities: tuple[str, ...]
    official_url: str
    documentation_url: str | None
    note: str
    verified_at: str = "2026-09-08"


SOURCES: tuple[MarketSource, ...] = (
    MarketSource(
        id="csfloat",
        name="CSFloat",
        source_type="MARKETPLACE",
        access_status="OFFICIAL_API",
        auth_required=True,
        capabilities=(
            "LISTINGS",
            "FLOAT",
            "PAINT_SEED",
            "STICKERS",
            "DOPPLER_PHASE",
        ),
        official_url="https://csfloat.com/",
        documentation_url="https://docs.csfloat.com/",
        note="API listings officielle; clé développeur requise pour la collecte live.",
    ),
    MarketSource(
        id="skinport",
        name="Skinport",
        source_type="MARKETPLACE",
        access_status="PUBLIC_API",
        auth_required=False,
        capabilities=("AGGREGATES", "REALIZED_SALES", "WEBSOCKET", "CURRENCIES"),
        official_url="https://skinport.com/",
        documentation_url="https://docs.skinport.com/",
        note="Items et historique agrégé publics; flux live listed/sold documenté.",
    ),
    MarketSource(
        id="dmarket",
        name="DMarket",
        source_type="MARKETPLACE",
        access_status="OFFICIAL_API",
        auth_required=True,
        capabilities=(
            "LISTINGS",
            "REALIZED_SALES",
            "BUY_ORDERS",
            "FLOAT",
            "PAINT_SEED",
            "STICKERS",
            "DOPPLER_PHASE",
            "FEES",
        ),
        official_url="https://dmarket.com/",
        documentation_url="https://docs.dmarket.com/v1/swagger.html",
        note="API officielle signée Ed25519; intégration strictement read-only.",
    ),
    MarketSource(
        id="skinbaron",
        name="SkinBaron",
        source_type="MARKETPLACE",
        access_status="REQUIRES_APPROVAL",
        auth_required=True,
        capabilities=("LISTINGS", "REALIZED_SALES", "AGGREGATES", "FLOAT", "STICKERS"),
        official_url="https://skinbaron.de/",
        documentation_url="https://skinbaron.de/misc/apidoc/",
        note="API officielle disponible après approbation explicite du compte.",
    ),
    MarketSource(
        id="gamerpay",
        name="GamerPay",
        source_type="MARKETPLACE",
        access_status="UNAVAILABLE",
        auth_required=False,
        capabilities=(),
        official_url="https://gamerpay.gg/shutting-down",
        documentation_url=None,
        note="Plateforme officiellement fermée depuis le 29 mai 2026.",
    ),
    MarketSource(
        id="steam",
        name="Steam Community Market",
        source_type="REFERENCE",
        access_status="RESEARCH_REQUIRED",
        auth_required=False,
        capabilities=("AGGREGATES", "CURRENCIES"),
        official_url="https://steamcommunity.com/market/",
        documentation_url=None,
        note="Aucune API officielle de données de marché documentée pour cette intégration.",
    ),
    MarketSource(
        id="tradeit_gg",
        name="Tradeit.gg",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=False,
        capabilities=(),
        official_url="https://tradeit.gg/",
        documentation_url=None,
        note=(
            "Aucune API développeur publique officielle identifiée; "
            "ne pas confondre avec tradeit.app."
        ),
    ),
    MarketSource(
        id="cs_money",
        name="CS.MONEY",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=False,
        capabilities=(),
        official_url="https://cs.money/",
        documentation_url=None,
        note="L'automatisation tierce exige un accord préalable selon les conditions officielles.",
    ),
    MarketSource(
        id="swap_gg",
        name="Swap.gg",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=False,
        capabilities=(),
        official_url="https://swap.gg/",
        documentation_url=None,
        note="Aucune documentation d'API développeur publique officielle identifiée.",
    ),
    MarketSource(
        id="skinsmonkey",
        name="SkinsMonkey",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=False,
        capabilities=(),
        official_url="https://skinsmonkey.com/",
        documentation_url=None,
        note="Aucune documentation d'API développeur publique officielle identifiée.",
    ),
    MarketSource(
        id="ecb",
        name="Banque centrale européenne",
        source_type="REFERENCE",
        access_status="PUBLIC_API",
        auth_required=False,
        capabilities=("CURRENCIES",),
        official_url="https://data.ecb.europa.eu/",
        documentation_url="https://data.ecb.europa.eu/help/api/overview",
        note=(
            "Taux de référence informatifs; ils ne représentent pas "
            "un taux de transaction effectif."
        ),
    ),
)


def source_catalog(
    settings: Settings,
    statuses: list[MarketStatus],
    reference_runtime: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    runtime: dict[str, str] = {status.platform: status.status for status in statuses}
    runtime.update(reference_runtime or {})
    configured = {
        "csfloat": settings.csfloat_api_key is not None,
        "skinport": True,
        "dmarket": settings.dmarket_public_key is not None
        and settings.dmarket_secret_key is not None,
        "ecb": True,
    }
    return [
        {
            **source.__dict__,
            "configured": configured.get(source.id, False),
            "runtime_status": runtime.get(source.id, "not_integrated"),
        }
        for source in SOURCES
    ]
