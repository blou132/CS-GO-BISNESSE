#!/usr/bin/env python3
"""Configure test-only market credentials interactively using the isolated API image."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    if sys.argv[1:] not in ([], ["--status"]):
        raise SystemExit("Usage: configure-market-credentials.py [--status]")
    directory = Path.home() / ".config/cs2-arbitrage-hub"
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise SystemExit("Symlinked credential directories are refused")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = directory.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o777 != 0o700:
        raise SystemExit("Credential directory must be user-owned with mode 0700")
    if any((p / ".git").exists() for p in (directory, *directory.parents)):
        raise SystemExit("Credential storage must be outside Git")
    image = "cs2-v012-validation-api"
    check = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    if check.returncode:
        raise SystemExit("Build the test image first: docker build -t cs2-v012-validation-api -f apps/api/Dockerfile .")
    command = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true", "--user", f"{os.getuid()}:{os.getgid()}",
               "-e", "HOME=/credentials", "-v", f"{directory}:/credentials/.config/cs2-arbitrage-hub"]
    if not sys.argv[1:]:
        if not sys.stdin.isatty():
            raise SystemExit("An interactive terminal is required; no secrets on stdin/arguments")
        command += ["-it"]
    return subprocess.call([*command, image, "python", "-m", "app.core.market_credentials", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
