"""Explicit disposable V0.11 validation; never reads production credentials."""

import argparse
import os
from pathlib import Path
import runpy
import secrets
import socket
import subprocess
from datetime import UTC, datetime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Build, test and remove the isolated stack")
    if not parser.parse_args().run:
        parser.error("--run is required; Docker and cached Playwright tools must be available")
    root = Path(__file__).resolve().parents[2]
    project = "cs2-v011-validation"
    existing = subprocess.check_output([
        "docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"
    ], text=True).strip()
    if existing:
        raise SystemExit("An isolated validation container already exists; refusing to replace it.")
    for port in (3000, 8000):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    evidence = root / "artifacts" / f"v011-{datetime.now(UTC):%Y%m%d-%H%M%S}"
    evidence.mkdir(parents=True)
    env = os.environ.copy()
    env.update({
        "POSTGRES_USER": "cs2", "POSTGRES_DB": "cs2", "POSTGRES_PASSWORD": secrets.token_hex(24),
        "ADMIN_USERNAME": "admin", "CS2_TEST_USERNAME": "admin",
        "CS2_TEST_PASSWORD": secrets.token_urlsafe(24), "SESSION_SECRET": secrets.token_hex(32),
        "SESSION_COOKIE_SECURE": "false", "CSFLOAT_API_KEY": "",
        "DMARKET_PUBLIC_KEY": "", "DMARKET_SECRET_KEY": "",
        "SKINPORT_REALTIME_ENABLED": "false", "SKINPORT_REALTIME_PRICE_UNIT": "unverified",
        "SKINPORT_REALTIME_PRICE_UNIT_SOURCE": "", "MARKET_SYNC_QUERY": "",
        "FX_REFERENCE_SYNC_ENABLED": "false", "MARKET_SYNC_ENABLED": "false",
        "FX_USD_EUR_RATE": "", "FX_RATE_SOURCE": "", "FX_RATE_TIMESTAMP": "",
        "ENVIRONMENT": "development", "APP_BIND_ADDRESS": "127.0.0.1", "APP_PORT": "3000",
        "CS2_TEST_ORIGIN": "http://127.0.0.1:3000", "CS2_TEST_OUTPUT": "/evidence",
    })
    env["ADMIN_PASSWORD_HASH"] = runpy.run_path(str(root / "scripts/generate-admin-password-hash.py"))["password_hash"](env["CS2_TEST_PASSWORD"])
    compose = ["docker", "compose", "--env-file", "/dev/null", "-p", project,
               "-f", str(root / "docker-compose.yml")]

    def run(args, timeout=1800, **kwargs):
        return subprocess.run(args, env=env, cwd=root, check=True, timeout=timeout, **kwargs)

    model = run([*compose, "-f", str(root / "compose.production.yml"), "config", "--format", "json"], capture_output=True).stdout
    run(["python3", str(root / "scripts/tests/production-compose-test.py")], input=model)
    try:
        run([*compose, "config", "--quiet"])
        run([*compose, "build"])
        run([*compose, "up", "-d", "--wait", "--wait-timeout", "180"])
        print("VALIDATION Alembic upgrade/check/downgrade/re-upgrade", flush=True)
        for args in [("upgrade", "head"), ("check",), ("downgrade", "e6f7a8b9c0d1"),
                     ("upgrade", "head"), ("check",)]:
            run([*compose, "exec", "-T", "api", "alembic", *args])
        for script in ("source-registry-browser.mjs", "watchlist-browser.mjs", "realtime-browser.mjs"):
            print(f"VALIDATION browser {script}", flush=True)
            run([
                "docker", "run", "--rm", "--network", "host",
                "-v", "cs2-playwright-tools:/tools:ro", "-v", f"{root}/scripts/tests:/checks:ro",
                "-w", "/tools", "-v", f"{evidence}:/evidence",
                "-e", "CS2_TEST_PASSWORD", "-e", "CS2_TEST_USERNAME", "-e", "CS2_TEST_ORIGIN",
                "-e", "CS2_TEST_OUTPUT", "--entrypoint", "sh",
                "mcr.microsoft.com/playwright:v1.55.0-noble",
                "-c", f"node --input-type=module < /checks/{script}",
            ], timeout=300)
        run(["docker", "cp", f"{root}/scripts/tests/realtime-postgres-check.py",
             f"{project}-api-1:/tmp/realtime-postgres-check.py"])
        run([*compose, "exec", "-T", "-e", "PYTHONPATH=/app", "-e",
             f"CS2_ISOLATED_VALIDATION={project}", "api", "python", "/tmp/realtime-postgres-check.py"])
        print(f"PASS evidence: {evidence}", flush=True)
    finally:
        print(f"CLEANUP isolated {project} stack only", flush=True)
        run([*compose, "down", "-v"], timeout=120)


if __name__ == "__main__":
    main()
