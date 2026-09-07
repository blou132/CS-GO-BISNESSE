#!/usr/bin/env python3
"""Generate a Docker Compose-safe Scrypt password hash without echoing the password."""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import os
import re
import secrets
import sys
import tempfile
from pathlib import Path


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


AUTH_DEFAULTS = {
    "SESSION_COOKIE_SECURE": "false",
    "SESSION_TTL_SECONDS": "28800",
    "LOGIN_RATE_LIMIT_MAX_ATTEMPTS": "5",
    "LOGIN_RATE_LIMIT_WINDOW_SECONDS": "900",
}


def password_hash(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=64,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt$16384$8$1${encoded(salt)}${encoded(digest)}"


def requested_password() -> str:
    password = getpass.getpass("Mot de passe administrateur : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirmation:
        raise ValueError("Les mots de passe ne correspondent pas.")
    if len(password) < 12:
        raise ValueError("Le mot de passe doit contenir au moins 12 caractères.")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Mettre à jour ce fichier sans afficher le hash.")
    parser.add_argument("--username", default="admin", help="Identifiant écrit avec --env-file.")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.username):
        parser.error("--username doit contenir 1 à 64 caractères sûrs.")

    try:
        generated_hash = password_hash(requested_password())
        if args.env_file:
            update_env_file(args.env_file, args.username, generated_hash)
            print(f"Configuration administrateur mise à jour dans {args.env_file}.")
        else:
            print(generated_hash)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


def update_env_file(path: Path, username: str, generated_hash: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("--env-file doit désigner un fichier régulier existant, pas un lien symbolique.")
    original = path.read_text(encoding="utf-8")
    current = env_values(original)
    session_secret = unquote(current.get("SESSION_SECRET", ""))
    if len(session_secret) < 32:
        session_secret = secrets.token_hex(32)

    replacements = {
        "ADMIN_USERNAME": username,
        "ADMIN_PASSWORD_HASH": f"'{generated_hash}'",
        "SESSION_SECRET": session_secret,
    }
    for key, value in AUTH_DEFAULTS.items():
        replacements[key] = current.get(key) or value
    rendered = replace_env_values(original, replacements)

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def env_values(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def replace_env_values(content: str, replacements: dict[str, str]) -> str:
    output: list[str] = []
    written: set[str] = set()
    for line in content.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        key = match.group(1) if match else None
        if key in replacements:
            if key not in written:
                output.append(f"{key}={replacements[key]}")
                written.add(key)
            continue
        output.append(line)
    for key, value in replacements.items():
        if key not in written:
            output.append(f"{key}={value}")
    return "\n".join(output) + "\n"


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
