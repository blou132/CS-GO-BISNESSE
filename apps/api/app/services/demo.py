from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.markets.base import AdapterItem, AdapterListing, AdapterObservation, AdapterResult
from app.models import MarketListing, MarketSyncState
from app.services.storage import persist_result

DEMO_WARNING = "DEMO — données synthétiques, aucune annonce réelle ni opportunité garantie."

# Les prix et floats de ces exemples sont créés pour tester le parcours, pas issus d'une API.
DEMO_SKINS = [
    ("AK-47", "Vulcan", "Field-Tested", "242.50", "0.1742"),
    ("AWP", "Asiimov", "Field-Tested", "128.30", "0.2139"),
    ("M4A1-S", "Printstream", "Minimal Wear", "214.90", "0.0921"),
    ("USP-S", "Kill Confirmed", "Field-Tested", "47.20", "0.1823"),
    ("Desert Eagle", "Printstream", "Factory New", "96.80", "0.0217"),
    ("AK-47", "Redline", "Field-Tested", "24.60", "0.1611"),
    ("Glock-18", "Vogue", "Minimal Wear", "7.10", "0.1031"),
    ("M4A4", "The Emperor", "Minimal Wear", "37.40", "0.0984"),
]


def ensure_demo(session: Session, settings: Settings) -> None:
    if session.scalar(select(MarketListing.id).where(MarketListing.mode == "demo").limit(1)):
        return
    now = datetime.now(UTC)
    for index, platform in enumerate(("csfloat", "dmarket")):
        result = AdapterResult()
        for number, (weapon, skin, exterior, price, wear) in enumerate(DEMO_SKINS):
            name = f"{weapon} | {skin} ({exterior})"
            amount = Decimal(price) * (Decimal("1") + Decimal(index) * Decimal("0.045"))
            result.listings.append(
                AdapterListing(
                    external_id=f"demo-{platform}-{number}",
                    item=AdapterItem(
                        market_hash_name=name,
                        weapon=weapon,
                        skin=skin,
                        exterior=exterior,
                        float_value=Decimal(wear) + Decimal(index) * Decimal("0.003"),
                        paint_seed=100 + 31 * number,
                        paint_index=None,
                    ),
                    price=amount,
                    currency="EUR",
                    observed_at=now,
                    warnings=[DEMO_WARNING],
                )
            )
            for day in range(1, 8):
                result.observations.append(
                    AdapterObservation(
                        market_hash_name=name,
                        # Historique synthétique pour exercer les calculs du MVP.
                        price=Decimal(price) * Decimal("1.18")
                        + Decimal(day % 3 - 1) * Decimal("1.30"),
                        currency="EUR",
                        observation_type="SALE",
                        timestamp=now - timedelta(days=day),
                        volume=1,
                    )
                )
        persist_result(session, result, platform, "demo", settings)
        session.add(
            MarketSyncState(
                mode="demo",
                platform=platform,
                status="demo",
                message=DEMO_WARNING,
                last_sync_at=now,
                last_attempt_at=now,
            )
        )

    # Skinport's public items endpoint exposes market-name aggregates rather than
    # identifiable listings. Keep the demo contract identical to that live shape.
    skinport = AdapterResult()
    for weapon, skin, exterior, price, _wear in DEMO_SKINS:
        skinport.observations.append(
            AdapterObservation(
                market_hash_name=f"{weapon} | {skin} ({exterior})",
                price=Decimal(price) * Decimal("1.045"),
                currency="EUR",
                observation_type="AGGREGATE",
                timestamp=now,
                volume=None,
            )
        )
    persist_result(session, skinport, "skinport", "demo", settings)
    session.add(
        MarketSyncState(
            mode="demo",
            platform="skinport",
            status="demo",
            message=DEMO_WARNING,
            last_sync_at=now,
            last_attempt_at=now,
        )
    )
    session.commit()
