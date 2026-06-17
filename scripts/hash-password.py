#!/usr/bin/env python3
"""Generate a UI_PASSWORD_HASH for .env.

Usage:
    python scripts/hash-password.py             # prompts (hidden input)
    python scripts/hash-password.py mypassword  # non-interactive

Run inside the host venv (so passlib is importable).
"""
import getpass
import sys

from passlib.context import CryptContext

ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def main() -> None:
    password = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Password: ")
    if not password:
        print("Empty password; aborting.", file=sys.stderr)
        raise SystemExit(1)
    print(ctx.hash(password))


if __name__ == "__main__":
    main()
