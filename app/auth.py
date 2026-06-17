"""Single-password auth backed by a signed session cookie.

Uses pbkdf2_sha256 (pure-Python, no compiled bcrypt) so it installs cleanly
on ARMv6 without a build toolchain.
"""
from __future__ import annotations

import time

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from .config import settings

COOKIE_NAME = "psui_session"

_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="piserviceui-session")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str) -> bool:
    if not settings.ui_password_hash:
        return False
    try:
        return _pwd.verify(password, settings.ui_password_hash)
    except ValueError:
        return False


def issue_session(response: Response) -> None:
    token = _serializer.dumps({"ts": int(time.time())})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def _token_valid(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=settings.session_max_age)
        return True
    except (BadSignature, SignatureExpired):
        return False


async def require_auth(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token or not _token_valid(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return True
