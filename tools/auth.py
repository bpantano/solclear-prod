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

# Secret key for signing session cookies
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    import warnings
    warnings.warn("SESSION_SECRET not set — using insecure default. Set this in production!", stacklevel=2)
    SESSION_SECRET = "solclear-local-dev-only-not-for-production"
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


def _is_production() -> bool:
    """Check if running in production (Railway sets RAILWAY_ENVIRONMENT)."""
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))


def set_session_cookie_header(token: str) -> str:
    """Return the Set-Cookie header value for the session."""
    secure = "; Secure" if _is_production() else ""
    return f"{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_MAX_AGE}; HttpOnly; SameSite=Strict{secure}"


def clear_session_cookie_header() -> str:
    """Return the Set-Cookie header value to clear the session."""
    secure = "; Secure" if _is_production() else ""
    return f"{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure}"


# ── Password Reset Tokens ────────────────────────────────────────────────────

RESET_TOKEN_MAX_AGE = 60 * 60  # 1 hour


def create_reset_token(user_id: int, email: str) -> str:
    """Create a signed reset token. Expires in 1 hour."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": int(time.time()) + RESET_TOKEN_MAX_AGE,
    }
    data = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    raw = f"{data}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def validate_reset_token(token: str) -> dict:
    """Validate a reset token. Returns payload dict or None if invalid/expired."""
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


# ── Email via Resend ─────────────────────────────────────────────────────────

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@solclear.io")


def send_reset_email(to_email: str, reset_url: str) -> bool:
    """Send a password reset email via Resend. Returns True on success."""
    if not RESEND_API_KEY:
        print(f"RESEND_API_KEY not set. Reset URL: {reset_url}")
        return False

    import requests
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": "Solclear — Reset Your Password",
                "html": (
                    '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;padding:40px 20px;">'
                    '<div style="text-align:center;margin-bottom:32px;">'
                    f'<img src="{reset_url.rsplit("/reset-password", 1)[0]}/logo.svg" alt="solclear" height="40">'
                    '</div>'
                    '<h2 style="font-size:18px;margin-bottom:8px;color:#1a1a2e;">Reset your password</h2>'
                    '<p style="font-size:14px;color:#6b7280;line-height:1.6;margin-bottom:24px;">'
                    'We received a request to reset your password. Click the button below to choose a new one. This link expires in 1 hour.</p>'
                    f'<a href="{reset_url}" style="display:inline-block;background:#3b82f6;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;">Reset Password</a>'
                    '<p style="font-size:12px;color:#9ca3af;margin-top:24px;line-height:1.5;">'
                    'If you didn\'t request this, you can safely ignore this email. Your password won\'t change until you click the link above.</p>'
                    '</div>'
                ),
            },
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"Failed to send reset email: {e}")
        return False
