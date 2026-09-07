#!/usr/bin/env python3
"""Generate a Docker Compose-safe Scrypt password hash without echoing the password."""

from __future__ import annotations

import base64
import getpass
import hashlib
import os
import sys


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def main() -> int:
    password = getpass.getpass("Mot de passe administrateur : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirmation:
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    if len(password) < 12:
        print("Le mot de passe doit contenir au moins 12 caractères.", file=sys.stderr)
        return 1

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
    print(f"scrypt$16384$8$1${encoded(salt)}${encoded(digest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
