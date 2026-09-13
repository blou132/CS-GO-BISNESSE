"""Validate safety properties of the fully merged production Compose model."""

import json
import os
import sys


def main() -> None:
    model = json.load(sys.stdin)
    services = model["services"]

    assert set(services) == {"api", "db", "web"}
    for service in services.values():
        assert service["restart"] == "unless-stopped"
        assert service["healthcheck"]["test"]
        assert service["logging"] == {
            "driver": "json-file",
            "options": {"max-file": "5", "max-size": "10m"},
        }

    assert "ports" not in services["db"]
    assert "ports" not in services["api"]
    assert services["web"]["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 3000,
            "published": "3000",
            "protocol": "tcp",
        }
    ]
    assert set(services["db"]["networks"]) == {"database"}
    assert set(services["api"]["networks"]) == {"application", "database"}
    assert set(services["web"]["networks"]) == {"application"}
    assert model["networks"]["database"]["internal"] is True
    assert services["db"]["volumes"] == [
        {
            "type": "volume",
            "source": "postgres_data",
            "target": "/var/lib/postgresql/data",
            "volume": {},
        }
    ]

    assert services["api"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert services["api"]["command"][0] == "uvicorn"
    assert "alembic" not in services["api"]["command"]
    assert "--reload" not in services["api"]["command"]
    for name in ("api", "web"):
        assert services[name]["read_only"] is True
        assert services[name]["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in services[name]["security_opt"]
    assert "/app/.next/cache:size=64m,uid=1000,gid=1000,mode=0755" in services["web"][
        "tmpfs"
    ]

    api_environment = services["api"]["environment"]
    assert api_environment["FX_MAX_AGE_HOURS"] == "120"
    assert api_environment["FX_REFERENCE_SYNC_ENABLED"] == os.environ.get(
        "FX_REFERENCE_SYNC_ENABLED", "false"
    )
    assert api_environment["FX_REFERENCE_SYNC_INTERVAL_SECONDS"] == os.environ.get(
        "FX_REFERENCE_SYNC_INTERVAL_SECONDS", "21600"
    )
    for name in ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "SESSION_SECRET"):
        assert services["web"]["environment"][name]

    print("Configuration Compose de production conforme.")


if __name__ == "__main__":
    main()
