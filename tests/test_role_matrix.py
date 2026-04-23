"""Assert the role-based nav/gating matrix:

  feature          | superadmin | admin | reviewer | crew
  ---------------- | ---------- | ----- | -------- | ----
  Organizations    |    ✓       |   ✓   |    ✓     |  ✗
  Requirements     |    ✓       |   ✓   |    ✓     |  ✗
  Costs            |    ✓       |   ✗   |    ✗     |  ✗

Each test skips automatically when the corresponding role's
TEST_<ROLE>_EMAIL / TEST_<ROLE>_PASSWORD env vars aren't set, so you
can run a partial matrix locally without creating all four accounts.
"""
from playwright.sync_api import Page, expect


def _wait_for_role_load(page: Page):
    """loadMe() fires on page load and reveals role-gated nav items. Give
    the request a beat before asserting visibility."""
    page.wait_for_load_state("networkidle")


# ── Organizations nav visibility ──────────────────────────────────────

def test_superadmin_sees_organizations_nav(page_as_superadmin: Page, base_url: str):
    page_as_superadmin.goto(f"{base_url}/")
    _wait_for_role_load(page_as_superadmin)
    expect(page_as_superadmin.locator('.nav-item[data-nav="orgs"]').first).to_be_visible()


def test_admin_sees_organizations_nav(page_as_admin: Page, base_url: str):
    page_as_admin.goto(f"{base_url}/")
    _wait_for_role_load(page_as_admin)
    expect(page_as_admin.locator('.nav-item[data-nav="orgs"]').first).to_be_visible()


def test_reviewer_sees_organizations_nav(page_as_reviewer: Page, base_url: str):
    page_as_reviewer.goto(f"{base_url}/")
    _wait_for_role_load(page_as_reviewer)
    expect(page_as_reviewer.locator('.nav-item[data-nav="orgs"]').first).to_be_visible()


def test_crew_does_not_see_organizations_nav(page_as_crew: Page, base_url: str):
    page_as_crew.goto(f"{base_url}/")
    _wait_for_role_load(page_as_crew)
    expect(page_as_crew.locator('.nav-item[data-nav="orgs"]').first).to_be_hidden()


# ── Requirements nav visibility ──────────────────────────────────────

def test_reviewer_sees_requirements_nav(page_as_reviewer: Page, base_url: str):
    page_as_reviewer.goto(f"{base_url}/")
    _wait_for_role_load(page_as_reviewer)
    expect(page_as_reviewer.locator('.nav-item[data-nav="reqs"]').first).to_be_visible()


def test_crew_does_not_see_requirements_nav(page_as_crew: Page, base_url: str):
    page_as_crew.goto(f"{base_url}/")
    _wait_for_role_load(page_as_crew)
    expect(page_as_crew.locator('.nav-item[data-nav="reqs"]').first).to_be_hidden()


# ── Costs nav visibility (superadmin only) ────────────────────────────

def test_superadmin_sees_costs_nav(page_as_superadmin: Page, base_url: str):
    page_as_superadmin.goto(f"{base_url}/")
    _wait_for_role_load(page_as_superadmin)
    expect(page_as_superadmin.locator('.nav-item[data-nav="costs"]').first).to_be_visible()


def test_admin_does_not_see_costs_nav(page_as_admin: Page, base_url: str):
    page_as_admin.goto(f"{base_url}/")
    _wait_for_role_load(page_as_admin)
    expect(page_as_admin.locator('.nav-item[data-nav="costs"]').first).to_be_hidden()


def test_reviewer_does_not_see_costs_nav(page_as_reviewer: Page, base_url: str):
    page_as_reviewer.goto(f"{base_url}/")
    _wait_for_role_load(page_as_reviewer)
    expect(page_as_reviewer.locator('.nav-item[data-nav="costs"]').first).to_be_hidden()


def test_crew_does_not_see_costs_nav(page_as_crew: Page, base_url: str):
    page_as_crew.goto(f"{base_url}/")
    _wait_for_role_load(page_as_crew)
    expect(page_as_crew.locator('.nav-item[data-nav="costs"]').first).to_be_hidden()


# ── API-level gating: endpoints return 403 for the wrong role ─────────

def test_cost_summary_rejects_admin(page_as_admin: Page, base_url: str):
    """Server enforces superadmin-only on /api/admin/cost/summary."""
    r = page_as_admin.request.get(f"{base_url}/api/admin/cost/summary")
    assert r.status == 403


def test_cost_summary_allows_superadmin(page_as_superadmin: Page, base_url: str):
    r = page_as_superadmin.request.get(f"{base_url}/api/admin/cost/summary")
    assert r.status == 200
    data = r.json()
    assert "totals" in data
    assert "top_reports" in data


def test_requirements_rejects_crew(page_as_crew: Page, base_url: str):
    """Crew has no access to the requirements catalog at all."""
    r = page_as_crew.request.get(f"{base_url}/api/requirements")
    assert r.status == 403
