"""
Shared pytest/Playwright fixtures for Solclear end-to-end tests.

Conventions
-----------
- Tests hit a *running* Solclear server (default http://localhost:8080).
  They do NOT spin the server up — start it yourself before running tests.
- Credentials come from environment variables so we never check real
  passwords into git. See tests/README.md for the full list.
- Any test that needs authentication uses one of the `logged_in_*`
  fixtures below which log in via the real HTTP API (POST /api/login)
  and hand back a Playwright `page` with the session cookie already set.
"""
from __future__ import annotations

import os
import pytest
import requests
from pathlib import Path

# Auto-load tests/.env if it exists so you don't have to re-export env
# vars every shell session. This file is gitignored — only test creds
# for roles you've created in the dev environment should go in it.
# It is separate from the repo-root .env (which holds production-style
# credentials and is intentionally never touched by these tests).
_TEST_ENV = Path(__file__).parent / ".env"
if _TEST_ENV.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_TEST_ENV)
    except ImportError:
        # python-dotenv is a transitive dep via the main requirements;
        # if it's missing, just skip silently — users can still export vars.
        pass


BASE_URL = os.environ.get("SOLCLEAR_BASE_URL", "http://localhost:8080")


def _creds_for(role):
    """Pull {EMAIL, PASSWORD} env vars for the given role tag.
    Returns (email, password). If either is missing the test should skip."""
    email = os.environ.get(f"TEST_{role.upper()}_EMAIL")
    password = os.environ.get(f"TEST_{role.upper()}_PASSWORD")
    return email, password


def _skip_if_no_creds(role):
    email, password = _creds_for(role)
    if not email or not password:
        pytest.skip(
            f"TEST_{role.upper()}_EMAIL / TEST_{role.upper()}_PASSWORD not set — "
            f"see tests/README.md"
        )
    return email, password


def _login_and_get_cookies(email, password):
    """Hit /api/login and return the session cookies as Playwright dicts."""
    sess = requests.Session()
    r = sess.post(
        f"{BASE_URL}/api/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    assert data.get("ok"), f"login failed: {data}"
    # requests stored the Set-Cookie in sess.cookies — translate to
    # Playwright's context.add_cookies format.
    from urllib.parse import urlparse
    parsed = urlparse(BASE_URL)
    out = []
    for c in sess.cookies:
        out.append({
            "name": c.name,
            "value": c.value,
            "domain": c.domain or parsed.hostname,
            "path": c.path or "/",
            # HTTP-only cookies don't surface httpOnly from requests, assume True
            "httpOnly": True,
            "secure": False,
        })
    return out


@pytest.fixture(scope="session")
def base_url() -> str:
    """Where the Solclear dev server is reachable."""
    return BASE_URL


@pytest.fixture
def browser_context_args(browser_context_args):
    """Default every browser context to our base_url so page.goto('/login')
    resolves to the right host. pytest-playwright also uses this."""
    return {**browser_context_args, "base_url": BASE_URL, "ignore_https_errors": True}


def _logged_in_page_factory(role: str):
    """Factory building a Playwright page fixture for the given role.
    The fixture logs in over HTTP and returns a page with the cookie set."""
    @pytest.fixture
    def _fixture(browser, browser_context_args):
        email, password = _skip_if_no_creds(role)
        cookies = _login_and_get_cookies(email, password)
        ctx = browser.new_context(**browser_context_args)
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        yield page
        ctx.close()
    return _fixture


# One fixture per role — use whichever your test needs.
page_as_superadmin = _logged_in_page_factory("superadmin")
page_as_admin = _logged_in_page_factory("admin")
page_as_reviewer = _logged_in_page_factory("reviewer")
page_as_crew = _logged_in_page_factory("crew")
