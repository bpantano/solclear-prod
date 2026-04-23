"""Smoke tests for pages that don't require authentication."""
from playwright.sync_api import Page, expect


def test_login_page_renders(page: Page, base_url: str):
    page.goto(f"{base_url}/login")
    expect(page).to_have_title("Solclear — Sign In")
    expect(page.locator("#loginEmail")).to_be_visible()
    expect(page.locator("#loginPassword")).to_be_visible()
    expect(page.locator("#loginBtn")).to_be_visible()


def test_login_page_shows_forgot_password_link(page: Page, base_url: str):
    page.goto(f"{base_url}/login")
    expect(page.get_by_text("Forgot password?", exact=False)).to_be_visible()


def test_login_page_shows_request_demo_link(page: Page, base_url: str):
    page.goto(f"{base_url}/login")
    expect(page.get_by_text("Request a Demo", exact=False)).to_be_visible()


def test_bad_credentials_show_error(page: Page, base_url: str):
    page.goto(f"{base_url}/login")
    page.locator("#loginEmail").fill("nobody@example.com")
    page.locator("#loginPassword").fill("wrong-password")
    page.locator("#loginBtn").click()
    # Error banner appears (display:block) with a message
    error = page.locator("#loginError")
    expect(error).to_be_visible(timeout=5000)
    # Should still be on login page, not redirected to app
    expect(page).to_have_url(f"{base_url}/login")


def test_request_demo_page_renders(page: Page, base_url: str):
    page.goto(f"{base_url}/request-demo")
    expect(page.locator("#demoName")).to_be_visible()
    expect(page.locator("#demoEmail")).to_be_visible()
    expect(page.locator("#demoPhone")).to_be_visible()
    expect(page.locator("#demoBtn")).to_be_visible()


def test_request_demo_requires_contact_info(page: Page, base_url: str):
    """Either email OR phone must be present — neither should error."""
    page.goto(f"{base_url}/request-demo")
    page.locator("#demoName").fill("Smoke Test")
    # Leave email and phone blank
    page.locator("#demoBtn").click()
    error = page.locator("#errMsg")
    expect(error).to_be_visible(timeout=3000)
    expect(error).to_contain_text("email address or phone number")
