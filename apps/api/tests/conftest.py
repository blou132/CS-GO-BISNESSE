"""Offline by default; external provider tests need a separate explicit opt-in."""

import os

import pytest


def pytest_collection_modifyitems(items):
    integration_modules = {
        "test_api.py",
        "test_storage.py",
        "test_monitoring.py",
        "test_watchlist.py",
        "test_realtime.py",
    }
    for item in items:
        if item.get_closest_marker("live"):
            if os.environ.get("RUN_LIVE_MARKET_TESTS") != "1":
                item.add_marker(pytest.mark.skip(reason="LIVE tests require explicit opt-in"))
        elif not item.get_closest_marker("integration"):
            item.add_marker(
                pytest.mark.integration
                if item.path.name in integration_modules
                else pytest.mark.unit
            )
