"""One password for everybody who opens the page.

``ACCESS_PASSWORD`` unset means the API is open, which is fine on a network only
you can reach. With a password set every call wants a cookie that this module
signs, so there is nothing to store and a restart keeps everybody signed in.
``SESSION_SECRET`` signs the cookie. Unset, the secret is derived from the
password, so changing the password signs everybody out.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

COOKIE_NAME = "speech2speech_access"
# A year. The cookie carries its own expiry, so a stolen one does not last forever.
COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def password() -> str:
    """The configured password, empty when the page is open to everybody."""
    return (os.environ.get("ACCESS_PASSWORD") or "").strip()


def required() -> bool:
    return bool(password())


def _secret() -> bytes:
    explicit = (os.environ.get("SESSION_SECRET") or "").strip()
    if explicit:
        return explicit.encode("utf-8")
    # No secret given, so the password itself keys the signature. Changing the
    # password then invalidates every cookie that is out there.
    return hashlib.sha256(b"speech2speech:" + password().encode("utf-8")).digest()


def _sign(expires_at: int) -> str:
    mac = hmac.new(_secret(), str(expires_at).encode("ascii"), hashlib.sha256)
    return mac.hexdigest()


def make_token(now: float | None = None) -> str:
    """A cookie value that says until when it counts, and is signed."""
    expires_at = int((now if now is not None else time.time()) + COOKIE_MAX_AGE)
    return f"{expires_at}.{_sign(expires_at)}"


def token_valid(token: str | None, now: float | None = None) -> bool:
    """Whether this cookie was signed with the current secret and has not run out."""
    if not token or "." not in token:
        return False
    raw_expiry, _, signature = token.partition(".")
    try:
        expires_at = int(raw_expiry)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(expires_at)):
        return False
    return expires_at > (now if now is not None else time.time())


def password_matches(given: str) -> bool:
    """A constant time comparison, so a wrong guess tells nothing about the length."""
    expected = password()
    if not expected:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))
