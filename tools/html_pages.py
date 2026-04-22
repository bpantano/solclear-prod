"""
HTML page templates for Solclear.

Split across tools/html/ for maintainability:
- tools/html/styles.py       Shared CSS fragments for auth pages
- tools/html/auth_pages.py   Login, forgot/reset/change password, request demo
- tools/html/embedded.py     The main single-page app (EMBEDDED_HTML)

This module re-exports the public names so existing imports keep working:
    from tools.html_pages import LOGIN_HTML, EMBEDDED_HTML, ...
"""

from tools.html.auth_pages import (
    LOGIN_HTML,
    FORGOT_PASSWORD_HTML,
    RESET_PASSWORD_HTML,
    CHANGE_PASSWORD_HTML,
    REQUEST_DEMO_HTML,
)
from tools.html.embedded import EMBEDDED_HTML

__all__ = [
    "LOGIN_HTML",
    "FORGOT_PASSWORD_HTML",
    "RESET_PASSWORD_HTML",
    "CHANGE_PASSWORD_HTML",
    "REQUEST_DEMO_HTML",
    "EMBEDDED_HTML",
]
