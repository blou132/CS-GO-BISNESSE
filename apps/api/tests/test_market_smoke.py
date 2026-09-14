from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.markets import smoke
from app.markets.base import AdapterResult, MarketAdapterError


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [False, True])
async def test_smoke_reports_only_counts_and_closes_clients(monkeypatch, partial):
    errors = {"sales_history": "rate_limited"} if partial else {}
    adapter = SimpleNamespace(
        search_items=AsyncMock(return_value=AdapterResult(partial_errors=errors))
    )
    clients = {"skinport": adapter}
    close = AsyncMock()
    monkeypatch.setattr(smoke, "build_adapters", lambda settings: clients)
    monkeypatch.setattr(smoke, "close_adapters", close)
    result = await smoke.check_source(Settings(_env_file=None), "skinport", "TEST Skin")
    assert result["status"] == ("degraded" if partial else "online")
    assert result["database_written"] is False
    assert result["transaction_executed"] is False
    assert all(value == 0 for value in result["counts"].values())
    close.assert_awaited_once_with(clients)


@pytest.mark.asyncio
async def test_smoke_redacts_configuration_error_and_closes_clients(monkeypatch):
    adapter = SimpleNamespace(
        search_items=AsyncMock(side_effect=MarketAdapterError("configuration", "TEST PRIVATE TEXT"))
    )
    close = AsyncMock()
    monkeypatch.setattr(smoke, "build_adapters", lambda settings: {"csfloat": adapter})
    monkeypatch.setattr(smoke, "close_adapters", close)
    result = await smoke.check_source(Settings(_env_file=None), "csfloat", "TEST Skin")
    assert result == {
        "platform": "csfloat",
        "status": "not_configured",
        "error_code": "configuration",
    }
    close.assert_awaited_once()


def test_smoke_requires_explicit_live_option_before_building_clients(monkeypatch):
    monkeypatch.setattr("sys.argv", ["smoke", "--platform", "skinport", "--query", "TEST Skin"])
    monkeypatch.setattr(smoke, "build_adapters", lambda settings: pytest.fail("No client expected"))
    with pytest.raises(SystemExit) as error:
        smoke.main()
    assert error.value.code == 2
