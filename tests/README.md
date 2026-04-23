# Solclear end-to-end tests (Playwright)

Browser-driven tests covering public pages, the role matrix, and the
impersonation flow. All tests hit a **running Solclear server** — they
don't spin one up.

## Prerequisites

1. Install Python deps (one-time):
   ```bash
   conda run pip install playwright pytest-playwright
   ```
2. Install the Chromium browser binary (one-time, ~200 MB):
   ```bash
   conda run playwright install chromium
   ```
3. Start the dev server in another terminal:
   ```bash
   conda run python tools/live_server.py
   ```
4. Set test credentials as environment variables (next section).

## Test credentials

Tests never read from `.env` — credentials come from environment
variables so you can set them fresh per-shell without leaking into
git. Only the roles you provide will run; the rest skip with a clear
message.

```bash
# Minimum to run the login + public-page smoke tests
export TEST_SUPERADMIN_EMAIL="bap.builds@gmail.com"
export TEST_SUPERADMIN_PASSWORD="..."

# Role-matrix tests (each is optional — missing creds skip, not fail)
export TEST_ADMIN_EMAIL="micah@independentsolar.com"
export TEST_ADMIN_PASSWORD="..."
export TEST_REVIEWER_EMAIL="reviewer@example.com"
export TEST_REVIEWER_PASSWORD="..."
export TEST_CREW_EMAIL="jdoe@independentsolar.com"
export TEST_CREW_PASSWORD="..."

# Impersonation tests — the target user's id (check the users table)
export TEST_ADMIN_USER_ID="1"

# Override the base URL if your dev server runs elsewhere
export SOLCLEAR_BASE_URL="http://localhost:8080"  # default
```

## Running the tests

From the repo root:

```bash
conda run pytest tests/                    # all tests
conda run pytest tests/test_public_pages.py   # just public-page smoke tests
conda run pytest tests/test_role_matrix.py -v # verbose role matrix
conda run pytest tests/test_impersonation.py  # impersonation flow
conda run pytest --headed                  # watch browser (debug)
conda run pytest --slowmo=500              # slow motion + headed
```

## Test files

| File                        | What it covers                                        |
| --------------------------- | ----------------------------------------------------- |
| `conftest.py`               | Shared fixtures — logged-in page factory per role     |
| `test_public_pages.py`      | Login / forgot / reset / request-demo render + basic flows (no auth) |
| `test_role_matrix.py`       | Nav visibility per role + API-level 403s              |
| `test_impersonation.py`     | Start / stop impersonation, banner, nav switching     |

## Writing a new test

Use the appropriate `page_as_*` fixture to get a Playwright page with
that role's session already active:

```python
def test_something_admin_specific(page_as_admin, base_url):
    page_as_admin.goto(f"{base_url}/")
    # … assertions
```

For plain unauthenticated tests, use the default `page` fixture from
`pytest-playwright`.

## Troubleshooting

- **All tests fail with "Not authenticated"** — the dev server isn't
  running. Start it in another terminal.
- **Role tests skip** — matching `TEST_<ROLE>_EMAIL/PASSWORD` aren't
  exported in this shell.
- **Cookies not sticking on impersonation** — make sure the session
  cookie from `POST /api/login` is `HTTPOnly` but not `Secure`; see
  `tools/auth.py::set_session_cookie_header` for the exact flags.
- **Want to debug visually?** Pass `--headed --slowmo=500` to pytest;
  the browser will open and run at human speed.
