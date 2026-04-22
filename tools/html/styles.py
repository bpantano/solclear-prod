"""
Shared style fragments reused across auth pages, the embedded SPA, and the
standalone report detail page.

- DESIGN_TOKENS_CSS: CSS custom properties (colors, shadows, typography) for
  :root and [data-theme="dark"]. Include this anywhere you want the shared
  design system. The embedded SPA currently inlines its own copy in
  tools/html/embedded.py; the standalone report page uses this constant.
- _AUTH_PAGE_STYLE / _AUTH_PAGE_LOGO: simple self-contained styles for the
  login/forgot/reset/change/demo pages.
"""


# Design tokens shared by the embedded SPA and the standalone report page.
# Keep this aligned with the :root + [data-theme="dark"] block in
# tools/html/embedded.py. When adding a new token, update both places.
DESIGN_TOKENS_CSS = """
    :root {
      --bg: #f8f9fb;
      --bg-card: #fff;
      --bg-input: #fff;
      --bg-elevated: #fff;
      --bg-subtle: #f3f4f6;
      --bg-hover: #f9fafb;
      --header-bg: #111827;

      --text: #1a1a2e;
      --text-secondary: #6b7280;
      --text-muted: #9ca3af;
      --text-inverse: #fff;

      --border: #e5e7eb;
      --border-light: #f3f4f6;
      --border-strong: #d1d5db;

      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --accent-subtle: #eff6ff;
      --accent-text: #1d4ed8;
      --success: #10b981;
      --success-subtle: #ecfdf5;
      --success-text: #065f46;
      --danger: #ef4444;
      --danger-subtle: #fef2f2;
      --danger-text: #991b1b;
      --warning: #f59e0b;
      --warning-subtle: #fffbeb;
      --warning-text: #92400e;
      --purple: #8b5cf6;
      --purple-subtle: #f5f3ff;
      --purple-text: #5b21b6;
      --review: #06b6d4;
      --review-subtle: #ecfeff;
      --review-text: #155e75;

      --badge-pass-bg: var(--success-subtle);
      --badge-pass-text: var(--success-text);
      --badge-fail-bg: var(--danger-subtle);
      --badge-fail-text: var(--danger-text);
      --badge-missing-bg: var(--warning-subtle);
      --badge-missing-text: var(--warning-text);
      --badge-error-bg: var(--purple-subtle);
      --badge-error-text: var(--purple-text);
      --badge-review-bg: var(--review-subtle);
      --badge-review-text: var(--review-text);

      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06);
      --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -1px rgba(15, 23, 42, 0.04);
      --shadow-lg: 0 10px 15px -3px rgba(15, 23, 42, 0.1), 0 4px 6px -2px rgba(15, 23, 42, 0.05);

      --text-xs: 11px;
      --text-sm: 12px;
      --text-base: 14px;
      --text-md: 15px;
      --text-lg: 16px;
      --text-xl: 18px;
      --text-2xl: 22px;

      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }

    [data-theme="dark"] {
      --bg: #0f172a;
      --bg-card: #1e293b;
      --bg-input: #1e293b;
      --bg-elevated: #293548;
      --bg-subtle: #1a2236;
      --bg-hover: #253149;
      --header-bg: #020617;

      --text: #e2e8f0;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --text-inverse: #0f172a;

      --border: #334155;
      --border-light: #1e293b;
      --border-strong: #475569;

      --accent: #60a5fa;
      --accent-hover: #3b82f6;
      --accent-subtle: rgba(59, 130, 246, 0.15);
      --accent-text: #93c5fd;
      --success: #34d399;
      --success-subtle: #064e3b;
      --success-text: #6ee7b7;
      --danger: #f87171;
      --danger-subtle: #7f1d1d;
      --danger-text: #fca5a5;
      --warning: #fbbf24;
      --warning-subtle: #78350f;
      --warning-text: #fcd34d;
      --purple: #a78bfa;
      --purple-subtle: #3730a3;
      --purple-text: #c4b5fd;
      --review: #22d3ee;
      --review-subtle: #164e63;
      --review-text: #a5f3fc;

      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.2);
      --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
      --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
    }
"""

# Styles for the simple auth-flow pages (login, forgot, reset, change password,
# request demo). Intentionally self-contained: these pages render before the
# user is logged in and don't need the full app shell.
_AUTH_PAGE_STYLE = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0; font-size: 14px; line-height: 1.5;
      min-height: 100dvh; display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 20px;
    }
    .card { width: 100%; max-width: 380px; background: #1e293b; border-radius: 16px; padding: 32px 28px; text-align: center; }
    .logo { margin-bottom: 24px; text-align: center; }
    .title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
    .sub { font-size: 12px; color: #64748b; margin-bottom: 24px; }
    .pw-wrap { position: relative; }
    .pw-toggle {
      position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
      background: none; border: none; color: #64748b; cursor: pointer; padding: 4px;
      display: flex; align-items: center;
    }
    .pw-toggle:hover { color: #94a3b8; }
    .pw-toggle svg { width: 20px; height: 20px; }
    .input {
      width: 100%; padding: 14px 16px; border: 2px solid #334155; border-radius: 10px;
      background: #0f172a; color: #e2e8f0; font-size: 15px; outline: none;
      margin-bottom: 12px; -webkit-appearance: none;
    }
    .input:focus { border-color: #3b82f6; }
    .input::placeholder { color: #475569; }
    .btn {
      width: 100%; padding: 14px; border: none; border-radius: 10px;
      background: #3b82f6; color: #fff; font-size: 15px; font-weight: 600;
      cursor: pointer; min-height: 50px; margin-top: 8px;
    }
    .btn:disabled { background: #475569; cursor: not-allowed; }
    .error { background: #7f1d1d; color: #fca5a5; border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 12px; display: none; }
    .success { background: #064e3b; color: #6ee7b7; border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 12px; display: none; }
    .link { color: #3b82f6; text-decoration: none; font-size: 13px; }
    .link:hover { text-decoration: underline; }
    .footer { margin-top: 24px; font-size: 11px; color: #334155; }
"""

_AUTH_PAGE_LOGO = """
      <div style="display:inline-flex;align-items:center;gap:10px;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="36" height="36" style="flex-shrink:0;">
          <circle cx="60" cy="54" r="14" fill="#F59E0B"/>
          <path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="#e2e8f0" stroke-width="8" stroke-linecap="round"/>
        </svg>
        <span style="font-size:28px;font-weight:600;letter-spacing:-1px;color:#e2e8f0;">solclear</span>
      </div>
"""
