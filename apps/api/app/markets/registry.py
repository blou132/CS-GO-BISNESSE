"""Immutable registry of reviewed market and trade data sources."""

from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings
from app.schemas.api import MarketStatus

SourceType = Literal["MARKETPLACE", "TRADE", "REFERENCE", "AGGREGATOR"]
Capability = Literal[
    "LISTINGS",
    "REALIZED_SALES",
    "AGGREGATES",
    "BUY_ORDERS",
    "FLOAT",
    "PAINT_SEED",
    "STICKERS",
    "DOPPLER_PHASE",
    "FADE_PERCENT",
    "TRADE_QUOTES",
    "FEES",
    "WEBSOCKET",
    "CURRENCIES",
]
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
    auth_required: bool | None
    capabilities: tuple[Capability, ...]
    official_url: str
    documentation_url: str | None
    note: str
    verified_at: str = "2026-09-08"
    roles: tuple[str, ...] = ()


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
            "CURRENCIES",
        ),
        official_url="https://csfloat.com/",
        documentation_url="https://docs.csfloat.com/",
        note="API listings officielle; clé développeur requise pour la collecte live.",
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="skinport",
        name="Skinport",
        source_type="MARKETPLACE",
        access_status="PUBLIC_API",
        auth_required=False,
        capabilities=(
            "AGGREGATES",
            "LISTINGS",
            "REALIZED_SALES",
            "FLOAT",
            "PAINT_SEED",
            "STICKERS",
            "WEBSOCKET",
            "CURRENCIES",
        ),
        official_url="https://skinport.com/",
        documentation_url="https://docs.skinport.com/",
        note="Items et historique agrégé publics; flux live listed/sold documenté.",
        verified_at="2026-09-13",
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
            "FADE_PERCENT",
            "FEES",
            "CURRENCIES",
        ),
        official_url="https://dmarket.com/",
        documentation_url="https://docs.dmarket.com/v1/swagger.html",
        note="API officielle signée Ed25519; intégration strictement read-only.",
        verified_at="2026-09-13",
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
        verified_at="2026-09-13",
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
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="skinsniper",
        name="SkinSniper",
        source_type="AGGREGATOR",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://skinsniper.com/",
        documentation_url=None,
        note=(
            "Référence et découverte de marchés uniquement. API mentionnée par l'extension, "
            "sans contrat développeur public identifié ; aucun prix ni spread importé."
        ),
        verified_at="2026-09-13",
        roles=("AGGREGATOR", "REFERENCE_SOURCE", "MARKET_DISCOVERY_SOURCE"),
    ),
    MarketSource(
        id="white_market",
        name="White.Market",
        source_type="MARKETPLACE",
        access_status="REQUIRES_APPROVAL",
        auth_required=True,
        capabilities=(
            "LISTINGS",
            "FLOAT",
            "PAINT_SEED",
            "STICKERS",
            "DOPPLER_PHASE",
            "WEBSOCKET",
            "CURRENCIES",
        ),
        official_url="https://white.market/",
        documentation_url="https://api.white.market/docs_partner/index.html",
        note=(
            "API partenaire GraphQL/JWT et exports publics documentés ; "
            "accès à confirmer, aucune collecte branchée."
        ),
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="waxpeer",
        name="Waxpeer",
        source_type="MARKETPLACE",
        access_status="OFFICIAL_API",
        auth_required=True,
        capabilities=("LISTINGS", "AGGREGATES", "BUY_ORDERS", "DOPPLER_PHASE"),
        official_url="https://waxpeer.com/",
        documentation_url="https://api.waxpeer.com/docs",
        note=(
            "Contrat officiel trouvé, non intégré. Certains GET achètent ou suppriment : "
            "un futur client devra autoriser chaque route de lecture explicitement."
        ),
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="haloskins",
        name="HaloSkins",
        source_type="MARKETPLACE",
        access_status="REQUIRES_APPROVAL",
        auth_required=True,
        capabilities=(
            "LISTINGS",
            "AGGREGATES",
            "FLOAT",
            "PAINT_SEED",
            "STICKERS",
            "DOPPLER_PHASE",
            "WEBSOCKET",
            "CURRENCIES",
        ),
        official_url="https://www.haloskins.com/",
        documentation_url="https://www.haloskins.com/html/openDoc/catalogue.html",
        note="API officielle après approbation de la clé ; lectures documentées, non intégrées.",
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="buff_market",
        name="BUFF Market",
        source_type="MARKETPLACE",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://buff.market/",
        documentation_url=None,
        note="Aucun contrat API développeur officiel identifié ; distinct de BUFF 163.",
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="buff_163",
        name="BUFF 163",
        source_type="MARKETPLACE",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://buff.163.com/",
        documentation_url=None,
        note="Documentation officielle exploitable non vérifiée ; aucun endpoint privé utilisé.",
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="skinflow",
        name="Skinflow",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://skinflow.gg/",
        documentation_url=None,
        note=(
            "Parcours de trade publics, aucun contrat API tiers identifié ; "
            "crédits non assimilés au cash."
        ),
        verified_at="2026-09-13",
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
        auth_required=None,
        capabilities=(),
        official_url="https://tradeit.gg/",
        documentation_url=None,
        note=(
            "Aucune API développeur publique officielle identifiée; "
            "ne pas confondre avec tradeit.app."
        ),
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="cs_money",
        name="CS.MONEY",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://cs.money/",
        documentation_url=None,
        note="L'automatisation tierce exige un accord préalable selon les conditions officielles.",
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="swap_gg",
        name="Swap.gg",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://swap.gg/",
        documentation_url=None,
        note="Aucune documentation d'API développeur publique officielle identifiée.",
        verified_at="2026-09-13",
    ),
    MarketSource(
        id="skinsmonkey",
        name="SkinsMonkey",
        source_type="TRADE",
        access_status="RESEARCH_REQUIRED",
        auth_required=None,
        capabilities=(),
        official_url="https://skinsmonkey.com/",
        documentation_url=None,
        note="Aucune documentation d'API développeur publique officielle identifiée.",
        verified_at="2026-09-13",
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

# These are wired to collection, not a claim of a successful authenticated live test.
COLLECTED_CAPABILITIES: dict[str, tuple[Capability, ...]] = {
    "csfloat": ("LISTINGS", "FLOAT", "PAINT_SEED", "STICKERS", "CURRENCIES"),
    "skinport": ("AGGREGATES", "CURRENCIES"),
    "dmarket": (
        "LISTINGS",
        "REALIZED_SALES",
        "BUY_ORDERS",
        "FLOAT",
        "PAINT_SEED",
        "STICKERS",
        "DOPPLER_PHASE",
        "FADE_PERCENT",
        "FEES",
        "CURRENCIES",
    ),
    "ecb": ("CURRENCIES",),
}


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
            "api_discovery_status": (
                "API_FOUND"
                if source.access_status in {"OFFICIAL_API", "PUBLIC_API"}
                else "PARTNER_API"
                if source.access_status == "REQUIRES_APPROVAL"
                else "API_NOT_FOUND"
            ),
            "collected_capabilities": COLLECTED_CAPABILITIES.get(source.id, ()),
            "configured": configured.get(source.id, False),
            "runtime_status": runtime.get(source.id, "not_integrated"),
        }
        for source in SOURCES
    ]
