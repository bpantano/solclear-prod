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

Two options — pick whichever fits your workflow:

### Option 1 (recommended): `tests/.env` file

Copy `tests/.env.example` to `tests/.env` and fill in the values. The
file is gitignored, so passwords never reach the repo. `conftest.py`
auto-loads it on every test run.

```bash
cp tests/.env.example tests/.env
# edit tests/.env with real values for the roles you want to test
```

### Option 2: shell env vars (per-session)

Export the values in your shell. Useful for CI or one-off runs.

```bash
export TEST_SUPERADMIN_EMAIL="you@example.com"
export TEST_SUPERADMIN_PASSWORD="..."
export TEST_ADMIN_EMAIL="..."
export TEST_ADMIN_PASSWORD="..."
# … etc. See tests/.env.example for the full list.
```

Only roles you populate will run; the rest skip with a clear message —
so you can validate incrementally as you add users in your dev env.

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
