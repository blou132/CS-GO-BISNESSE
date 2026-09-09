from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.currencies.ecb import (
    ECB_SOURCE,
    ECBRateClient,
    ECBRateError,
    ECBReferenceRate,
    parse_ecb_csv,
    persist_ecb_rates,
)
from app.currencies.scheduler import FXRateScheduler
from app.currencies.service import normalize_price
from app.db.session import build_engine, build_session_factory
from app.models import Base

ECB_FIXTURE = """KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE
EXR.D.CHF.EUR.SP00.A,D,CHF,EUR,SP00,A,2026-09-09,0.9404
EXR.D.CNY.EUR.SP00.A,D,CNY,EUR,SP00,A,2026-09-09,7.8159
EXR.D.GBP.EUR.SP00.A,D,GBP,EUR,SP00,A,2026-09-09,0.85898
EXR.D.JPY.EUR.SP00.A,D,JPY,EUR,SP00,A,2026-09-09,150
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-09-09,1.20
"""
NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def test_ecb_parser_preserves_published_currency_per_eur_orientation() -> None:
    rates = {item.currency: item for item in parse_ecb_csv(ECB_FIXTURE)}
    assert set(rates) == {"USD", "GBP", "JPY", "CHF", "CNY"}
    assert rates["USD"].currency_per_eur == Decimal("1.20")
    assert rates["JPY"].observed_at == datetime(2026, 9, 9, tzinfo=UTC)


def test_ecb_parser_rejects_partial_or_wrong_series() -> None:
    with pytest.raises(ECBRateError, match="manquants"):
        parse_ecb_csv("\n".join(ECB_FIXTURE.splitlines()[:2]))
    with pytest.raises(ECBRateError, match="inattendue"):
        parse_ecb_csv(ECB_FIXTURE.replace(",SP00,A,", ",wrong,A,", 1))


@pytest.mark.asyncio
async def test_ecb_client_uses_bounded_official_daily_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "data-api.ecb.europa.eu"
        assert request.url.path.endswith("/D.USD+GBP+JPY+CHF+CNY.EUR.SP00.A")
        assert request.url.params["lastNObservations"] == "1"
        assert request.url.params["detail"] == "dataonly"
        assert request.url.params["format"] == "csvdata"
        assert request.headers["Accept"] == "text/csv"
        return httpx.Response(200, text=ECB_FIXTURE)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ECBRateClient(http)
    rates = await client.fetch_latest()
    assert len(rates) == 5
    await http.aclose()


def test_persisted_ecb_rate_converts_supported_currencies_to_eur(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'fx.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    rates = parse_ecb_csv(ECB_FIXTURE)
    with factory() as session:
        assert persist_ecb_rates(session, rates) == 5
        assert persist_ecb_rates(session, rates) == 0
        session.commit()
        settings = Settings(_env_file=None)
        usd = normalize_price(Decimal("120"), "USD", settings, NOW, session)
        jpy = normalize_price(Decimal("1500"), "JPY", settings, NOW, session)
    assert usd[0] == Decimal("100")
    assert usd[1] == Decimal(1) / Decimal("1.20")
    assert usd[2] == datetime(2026, 9, 9, tzinfo=UTC)
    assert usd[3] == ECB_SOURCE
    assert jpy[0] == Decimal("10")
    engine.dispose()


def test_newest_eligible_reference_rate_is_used(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        persist_ecb_rates(
            session,
            [
                ECBReferenceRate("USD", Decimal("1.10"), datetime(2026, 9, 8, tzinfo=UTC)),
                ECBReferenceRate("USD", Decimal("1.20"), datetime(2026, 9, 9, tzinfo=UTC)),
            ],
        )
        session.commit()
        converted = normalize_price(Decimal("120"), "USD", Settings(_env_file=None), NOW, session)
    assert converted[0] == Decimal("100")
    engine.dispose()


@pytest.mark.asyncio
async def test_fx_scheduler_persists_rates_and_reports_runtime_state(tmp_path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'scheduler.db'}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)

    class StubClient:
        async def fetch_latest(self) -> list[ECBReferenceRate]:
            return parse_ecb_csv(ECB_FIXTURE)

        async def aclose(self) -> None:
            return None

    settings = Settings(_env_file=None, fx_reference_sync_enabled=True)
    scheduler = FXRateScheduler(factory, settings, StubClient())  # type: ignore[arg-type]
    summary = await scheduler.run_once()
    assert summary.rates_received == 5
    assert summary.rates_created == 5
    assert scheduler.runtime_status == "online"
    assert scheduler.last_success_at is not None
    assert scheduler.next_run_at is not None
    await scheduler.stop()
    engine.dispose()
