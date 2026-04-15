"""
Auth module for Solclear.
Handles password hashing, session creation/validation, and user lookup.

Sessions are signed cookies using HMAC — no external dependencies.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from http.cookies import SimpleCookie
from urllib.parse import quote, unquote

import bcrypt
from dotenv import load_dotenv

load_dotenv()

# Secret key for signing session cookies — generate a random one if not set
SESSION_SECRET = os.getenv("SESSION_SECRET", "solclear-dev-secret-change-in-prod")
SESSION_COOKIE_NAME = "solclear_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_session_token(user_id: int, role: str, org_id: int = None) -> str:
    """Create a signed session token containing user info and expiry. Base64-encoded for cookie safety."""
    payload = {
        "user_id": user_id,
        "role": role,
        "org_id": org_id,
        "exp": int(time.time()) + SESSION_MAX_AGE,
    }
    data = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    raw = f"{data}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def validate_session_token(token: str) -> dict:
    """Validate a session token. Returns the payload dict or None if invalid/expired."""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        if "." not in raw:
            return None
        data, sig = raw.rsplit(".", 1)
        expected_sig = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(data)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_session_from_request(headers) -> dict:
    """Extract and validate session from request Cookie header. Returns payload or None."""
    cookie_header = headers.get("Cookie", "")
    if not cookie_header:
        return None
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    if SESSION_COOKIE_NAME not in cookies:
        return None
    return validate_session_token(cookies[SESSION_COOKIE_NAME].value)


def set_session_cookie_header(token: str) -> str:
    """Return the Set-Cookie header value for the session."""
    return f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_MAX_AGE}; HttpOnly; SameSite=Lax"


def clear_session_cookie_header() -> str:
    """Return the Set-Cookie header value to clear the session."""
    return f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
