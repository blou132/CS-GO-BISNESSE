"""Explicit user-owned test credentials. Never reads or changes production configuration."""

import argparse
import fcntl
import getpass
import io
import json
import os
import re
import stat
import sys
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path

from dotenv.parser import parse_stream
from nacl.signing import SigningKey

KEYS = ("CSFLOAT_API_KEY", "DMARKET_PUBLIC_KEY", "DMARKET_SECRET_KEY")
MAX_SIZE = 65536


def default_path() -> Path:
    return Path.home() / ".config/cs2-arbitrage-hub/markets.env"


def private_directory(directory: Path, *, create: bool = False) -> None:
    if not directory.is_absolute():
        raise ValueError("An absolute credential directory is required")
    if any(parent.is_symlink() for parent in (directory, *directory.parents)):
        raise ValueError("Symlinked credential directories are refused")
    if create:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Credential directory must be user-owned with mode 0700")
    # A dedicated external directory also protects against force-added env files.
    if any((parent / ".git").exists() for parent in (directory, *directory.parents)):
        raise ValueError("Credentials must be stored outside Git working trees")


def read_private(path: Path) -> str:
    private_directory(path.parent)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size > MAX_SIZE
        ):
            raise ValueError("Credential file must be regular, user-owned and mode 0600")
        content = handle.read(MAX_SIZE + 1)
    if len(content.encode("utf-8")) > MAX_SIZE:
        raise ValueError("Credential file is too large")
    return content


def values(content: str) -> dict[str, str]:
    result = {}
    for binding in parse_stream(io.StringIO(content)):
        if binding.error:
            raise ValueError("Invalid dotenv syntax; no credentials changed")
        if binding.key:
            if binding.key in result:
                raise ValueError("Duplicate dotenv variable; no credentials changed")
            result[binding.key] = binding.value or ""
    return result


def validate(credentials: dict[str, str]) -> None:
    for key in KEYS:
        value = credentials.get(key, "")
        if value and not re.fullmatch(r"[A-Za-z0-9_.:/+=-]{16,4096}", value):
            raise ValueError(f"Invalid format for {key}")
        if value.startswith(("github_pat_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_")):
            raise ValueError("GitHub tokens must not be used as marketplace credentials")
    public = credentials.get("DMARKET_PUBLIC_KEY", "")
    secret = credentials.get("DMARKET_SECRET_KEY", "")
    if bool(public) != bool(secret):
        raise ValueError("Both DMarket keys are required together")
    if public:
        try:
            public_bytes, secret_bytes = bytes.fromhex(public), bytes.fromhex(secret)
            if len(public_bytes) != 32 or len(secret_bytes) not in (32, 64):
                raise ValueError
            if bytes(SigningKey(secret_bytes[:32]).verify_key) != public_bytes:
                raise ValueError
            if len(secret_bytes) == 64 and secret_bytes[32:] != public_bytes:
                raise ValueError
        except ValueError:
            raise ValueError("Invalid or mismatched DMarket Ed25519 pair") from None


def load(path: Path) -> dict[str, str]:
    current = values(read_private(path))
    result = {key.lower(): current.get(key, "") for key in KEYS}
    validate(current)
    return result


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".markets-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save(path: Path, updates: dict[str, str]) -> bool:
    if not set(updates).issubset(KEYS):
        raise ValueError("Only marketplace credentials may be changed")
    private_directory(path.parent, create=True)
    lock = os.open(path.parent / ".credential-lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        original = read_private(path) if path.exists() or path.is_symlink() else ""
        current = values(original)
        merged = current | updates
        validate(merged)
        changed = {key: value for key, value in updates.items() if current.get(key, "") != value}
        if not changed:
            return False
        rendered = []
        remaining = changed.copy()
        for binding in parse_stream(io.StringIO(original)):
            if binding.key in remaining:
                rendered.append(f"{binding.key}='{remaining.pop(binding.key)}'\n")
            else:
                rendered.append(binding.original.string)
        content = "".join(rendered)
        if content and not content.endswith("\n"):
            content += "\n"
        content += "".join(f"{key}='{value}'\n" for key, value in remaining.items())
        if original:
            backup = path.parent / f"{path.name}.backup-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}"
            _atomic_write(backup, original)
        _atomic_write(path, content)
        backups = sorted(
            entry
            for entry in path.parent.iterdir()
            if re.fullmatch(re.escape(path.name) + r"\.backup-\d{8}T\d{12}Z", entry.name)
        )
        for backup in backups[:-3]:
            read_private(backup)
            backup.unlink()
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Print configuration booleans only")
    args = parser.parse_args()
    path = default_path()
    try:
        if args.status:
            current = load(path) if path.exists() else {}
            print(
                json.dumps(
                    {
                        key: "CONFIGURED" if current.get(key.lower()) else "NOT_CONFIGURED"
                        for key in KEYS
                    }
                )
            )
            return 0
        if not sys.stdin.isatty():
            raise ValueError("An interactive terminal with hidden input is required")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            updates = {
                key: value
                for key in KEYS
                if (value := getpass.getpass(f"{key} (empty: keep existing): "))
            }
        changed = save(path, updates)
        print("Credentials saved securely" if changed else "No credentials changed")
        return 0
    except (OSError, ValueError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        # Never print exception text: parsers and OS errors may embed input data.
        print(
            "Credential operation refused; check terminal, permissions and key formats.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
