"""End-to-end test for the superadmin impersonation flow.

Verifies the full round-trip: superadmin starts impersonating an admin
via the API, the impersonation banner appears, the nav matches the
impersonated role (Costs hidden), stop-impersonate restores the
superadmin session.

Needs TEST_SUPERADMIN_EMAIL / PASSWORD and TEST_ADMIN_EMAIL (the target).
"""
from __future__ import annotations

import os
import pytest
from playwright.sync_api import Page, expect


def _admin_user_id_from_env():
    """Resolve the admin's user_id via the API (no hardcoded IDs)."""
    try:
        return int(os.environ["TEST_ADMIN_USER_ID"])
    except (KeyError, ValueError):
        return None


def test_banner_hidden_when_not_impersonating(page_as_superadmin: Page, base_url: str):
    page_as_superadmin.goto(f"{base_url}/")
    page_as_superadmin.wait_for_load_state("networkidle")
    expect(page_as_superadmin.locator("#impersonationBanner")).to_be_hidden()


def test_impersonate_admin_shows_banner_and_hides_costs(
    page_as_superadmin: Page, base_url: str
):
    admin_id = _admin_user_id_from_env()
    if not admin_id:
        pytest.skip("TEST_ADMIN_USER_ID not set")

    # Start impersonation via the API (avoids relying on UI click flow)
    r = page_as_superadmin.request.post(
        f"{base_url}/api/admin/impersonate",
        data={"user_id": admin_id},
    )
    assert r.status == 200
    body = r.json()
    assert body["ok"] is True
    assert body["impersonating"]["user_id"] == admin_id

    # Reload to let /api/me pick up the new session + loadMe() render the UI
    page_as_superadmin.goto(f"{base_url}/")
    page_as_superadmin.wait_for_load_state("networkidle")

    # Banner shows
    expect(page_as_superadmin.locator("#impersonationBanner")).to_be_visible()
    # Costs nav is now hidden (admin role doesn't get it)
    expect(
        page_as_superadmin.locator('.nav-item[data-nav="costs"]').first
    ).to_be_hidden()


def test_stop_impersonate_restores_superadmin(
    page_as_superadmin: Page, base_url: str
):
    admin_id = _admin_user_id_from_env()
    if not admin_id:
        pytest.skip("TEST_ADMIN_USER_ID not set")

    # Impersonate
    r = page_as_superadmin.request.post(
        f"{base_url}/api/admin/impersonate",
        data={"user_id": admin_id},
    )
    assert r.status == 200

    # Stop
    r2 = page_as_superadmin.request.post(
        f"{base_url}/api/admin/stop-impersonate"
    )
    assert r2.status == 200
    assert r2.json()["impersonating"] is False

    # Costs nav should reappear (superadmin again)
    page_as_superadmin.goto(f"{base_url}/")
    page_as_superadmin.wait_for_load_state("networkidle")
    expect(
        page_as_superadmin.locator('.nav-item[data-nav="costs"]').first
    ).to_be_visible()
    expect(page_as_superadmin.locator("#impersonationBanner")).to_be_hidden()


def test_self_impersonation_rejected(page_as_superadmin: Page, base_url: str):
    """/api/me gives us our own user_id; trying to impersonate it should 400."""
    me = page_as_superadmin.request.get(f"{base_url}/api/me").json()
    my_id = me["user_id"]
    r = page_as_superadmin.request.post(
        f"{base_url}/api/admin/impersonate",
        data={"user_id": my_id},
    )
    assert r.status == 400
