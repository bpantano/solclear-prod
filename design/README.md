# Solclear — Design surfaces

A self-contained set of **rendered HTML pages** for sharing with Claude
Design (or any other design tool) without exposing the rest of the
codebase, secrets, or `.env` files.

## What's in here

| File                       | What it is                                           |
| -------------------------- | ---------------------------------------------------- |
| `app.html`                 | The main single-page app (shell, nav, all step views) |
| `login.html`               | Sign-in page                                         |
| `forgot-password.html`     | Request a password-reset email                       |
| `reset-password.html`      | Set a new password after clicking the email link     |
| `change-password.html`     | In-app password change (for logged-in users)         |
| `request-demo.html`        | Public lead-capture form                             |
| `report-sample.html`       | Sample compliance report detail page                 |
| `generate.py`              | Re-renders every HTML file from the live source      |

Each file is fully self-contained: inline CSS, inline SVGs, inline JS,
no external asset references except `/favicon.svg` and CompanyCam photo
URLs in the sample report (which may 403 outside an auth'd context —
harmless for visual design work).

## Is it safe to share?

Yes. These files contain **no secrets, API keys, database credentials,
session tokens, or customer PII**. The only runtime values embedded are:

- Public meta tags (Open Graph preview image URL, favicon path)
- Sample report data copied from `report_id=1` in the dev database — a
  superadmin test run, not a customer's real data
- Design-system color tokens, SVG icons, and layout structure

You can zip `design/` and share it freely.

## Refreshing after code changes

When you iterate on `tools/html/embedded.py`, `tools/html/auth_pages.py`,
`tools/html/styles.py`, or `tools/generate_report_html.py`, re-run:

```bash
python -m design.generate
```

That overwrites each `.html` file in this folder with the latest render.
Commit (or don't) as you prefer — the files are small enough that git
diffs are readable.

## The workflow with Claude Design

1. Run `python -m design.generate` to get a fresh snapshot.
2. Upload `design/` (or a zip of it) to Claude Design.
3. Iterate on visual design — get back HTML/CSS suggestions.
4. Bring the changes into the Python sources (`tools/html/embedded.py`
   primarily, since that's where most of the UI lives).
5. Re-run `generate.py` to confirm the change looks right as a static
   render.
6. Test the live app; push when happy.

## Notes

- `app.html` is the largest file (~130KB) because the whole design
  system + utility classes + every view's markup + all client JS lives
  inline. That's by design — the SPA is served as one HTML document.
- Photo URLs in `report-sample.html` point at CompanyCam's imgproxy and
  may return 403 outside a browser with a CC session. For design
  iteration, this is fine — the layout doesn't depend on the images
  loading. If you need placeholder images, find/replace the CompanyCam
  URLs with a placeholder service.
- If the DB isn't reachable when `generate.py` runs (no `.env`,
  Postgres down, etc.), `report-sample.html` falls back to a hand-rolled
  stub with made-up data. Output still makes sense visually.
