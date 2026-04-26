"""
EMBEDDED_HTML — the main single-page app served at /.

Contains the full SPA: top bar, nav drawer, all step views (home, reports,
new check wizard, admin orgs/requirements/users), and the inline JS that
drives them.

This file is intentionally large; the alternative would be fragmenting the
template across files that all need to be reassembled at render time.
If it keeps growing, candidates for extraction: the inline <style> block
(to tools/html/styles.py) and the client JS (to a separate string module).
"""

EMBEDDED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta property="og:title" content="Solclear">
  <meta property="og:description" content="Solar installation compliance, simplified.">
  <meta property="og:image" content="https://app.solclear.co/og-image.svg">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://app.solclear.co">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>Solclear Compliance</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      /* Surfaces */
      --bg: #f8f9fb;
      --bg-card: #fff;
      --bg-input: #fff;
      --bg-elevated: #fff;
      --bg-subtle: #f3f4f6;
      --bg-hover: #f9fafb;
      --header-bg: #111827;
      --sidebar-bg: #111827;
      --sidebar-bg-hover: #1f2937;
      --sidebar-text: #d1d5db;
      --sidebar-text-active: #fff;
      --sidebar-divider: #1f2937;
      --sidebar-section-label: #4b5563;

      /* Text */
      --text: #1a1a2e;
      --text-secondary: #6b7280;
      --text-muted: #9ca3af;
      --text-inverse: #fff;

      /* Borders */
      --border: #e5e7eb;
      --border-light: #f3f4f6;
      --border-strong: #d1d5db;

      /* Semantic */
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

      /* Badge aliases */
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

      /* Shadows */
      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06);
      --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -1px rgba(15, 23, 42, 0.04);
      --shadow-lg: 0 10px 15px -3px rgba(15, 23, 42, 0.1), 0 4px 6px -2px rgba(15, 23, 42, 0.05);

      /* Typography */
      --text-xs: 11px;
      --text-sm: 12px;
      --text-base: 14px;
      --text-md: 15px;
      --text-lg: 16px;
      --text-xl: 18px;
      --text-2xl: 22px;

      /* Shell dimensions */
      --sidebar-width: 240px;
      --tab-bar-height: 64px;
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
      --sidebar-bg: #020617;
      --sidebar-bg-hover: #1e293b;
      --sidebar-text: #cbd5e1;
      --sidebar-text-active: #fff;
      --sidebar-divider: #1e293b;
      --sidebar-section-label: #475569;

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

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); font-size: var(--text-base); line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      min-height: 100dvh;
      transition: background 0.2s, color 0.2s;
    }

    /* ── App shell ───────────────────────────────────────────────────────── */

    .sidebar {
      display: none;
      position: fixed; top: 0; left: 0;
      width: var(--sidebar-width); height: 100vh;
      background: var(--sidebar-bg);
      padding: 20px 16px;
      overflow-y: auto;
      z-index: 50;
      flex-direction: column;
    }
    .sidebar-logo { padding: 4px 4px 20px; border-bottom: 1px solid var(--sidebar-divider); margin-bottom: 12px; }
    .sidebar-section-label {
      font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--sidebar-section-label); padding: 12px 12px 6px; font-weight: 600;
    }
    .sidebar-footer {
      margin-top: auto; padding-top: 16px; border-top: 1px solid var(--sidebar-divider);
      display: flex; flex-direction: column; gap: 4px;
    }
    .sidebar-user {
      font-size: var(--text-xs); color: var(--sidebar-section-label);
      padding: 4px 12px; word-break: break-all;
    }

    .mobile-top-bar {
      background: var(--header-bg); color: var(--text-inverse); padding: 12px 20px;
      display: grid; grid-template-columns: 44px 1fr 44px; align-items: center;
    }
    .mobile-top-bar .logo-center { display: flex; justify-content: center; }

    .main-content {
      min-height: 100dvh;
      padding-bottom: calc(var(--tab-bar-height) + var(--safe-bottom) + 24px);
    }

    .bottom-tabs {
      position: fixed; bottom: 0; left: 0; right: 0;
      background: var(--bg-card); border-top: 1px solid var(--border);
      display: grid; grid-template-columns: repeat(4, 1fr);
      z-index: 40;
      padding-bottom: var(--safe-bottom);
      box-shadow: var(--shadow-md);
    }
    .tab-btn {
      background: none; border: none; cursor: pointer;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 3px; padding: 8px 4px;
      color: var(--text-secondary);
      font-size: 10px; font-weight: 500;
      min-height: var(--tab-bar-height);
      -webkit-tap-highlight-color: transparent;
      font-family: inherit;
    }
    .tab-btn svg { width: 22px; height: 22px; }
    .tab-btn.active { color: var(--accent); }

    /* Account sheet (mobile) */
    .sheet-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
      display: none; opacity: 0; transition: opacity 0.2s ease;
    }
    .sheet-overlay.open { display: block; opacity: 1; }
    .account-sheet {
      position: fixed; bottom: -100%; left: 0; right: 0; z-index: 201;
      background: var(--bg-card); border-radius: 16px 16px 0 0;
      padding: 8px 16px calc(24px + var(--safe-bottom));
      transition: bottom 0.25s ease;
      box-shadow: var(--shadow-lg);
      max-height: 85vh; overflow-y: auto;
    }
    .account-sheet.open { bottom: 0; }
    .sheet-handle {
      width: 40px; height: 4px; border-radius: 2px; background: var(--border);
      margin: 8px auto 16px;
    }

    /* Nav items — shared by sidebar and account sheet */
    .nav-item {
      display: flex; align-items: center; gap: 12px;
      width: 100%; padding: 12px 12px; border-radius: 8px;
      color: var(--sidebar-text); text-decoration: none;
      font-size: var(--text-base); font-weight: 500;
      margin-bottom: 2px; cursor: pointer;
      border: none; background: none; text-align: left;
      font-family: inherit;
    }
    .nav-item svg { width: 18px; height: 18px; flex-shrink: 0; }
    .nav-item:hover, .nav-item:active, .nav-item.active {
      background: var(--sidebar-bg-hover); color: var(--sidebar-text-active);
    }
    .nav-item.nav-item-danger { color: var(--danger); }
    .nav-item.nav-item-danger:hover { background: var(--danger-subtle); color: var(--danger-text); }

    /* Account sheet variant — light surface */
    .account-sheet .nav-item { color: var(--text); }
    .account-sheet .nav-item:hover, .account-sheet .nav-item.active {
      background: var(--bg-hover); color: var(--text);
    }
    .account-sheet .nav-item.nav-item-danger { color: var(--danger); }
    .account-sheet .sidebar-section-label { color: var(--text-muted); }

    /* Theme toggle button */
    .theme-toggle {
      background: none; border: none; color: inherit; cursor: pointer;
      width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
      padding: 0; -webkit-tap-highlight-color: transparent;
      border-radius: 8px;
    }
    .theme-toggle:hover { background: rgba(255,255,255,0.08); }
    .theme-toggle svg { width: 20px; height: 20px; }
    .mobile-top-bar .theme-toggle { color: var(--text-inverse); }

    /* Header actions cluster (bell + theme toggle, etc.) */
    .header-actions { display: flex; align-items: center; gap: 4px; }
    .header-btn {
      background: none; border: none; color: inherit; cursor: pointer;
      width: 44px; height: 44px;
      display: flex; align-items: center; justify-content: center;
      padding: 0; border-radius: 8px;
      -webkit-tap-highlight-color: transparent;
      position: relative;
    }
    .header-btn:hover { background: rgba(255,255,255,0.08); }
    .header-btn svg { width: 20px; height: 20px; }
    /* Unread count badge — small red pill in the upper right of the bell */
    .header-badge {
      position: absolute; top: 4px; right: 4px;
      background: var(--danger); color: #fff;
      font-size: 10px; font-weight: 700;
      min-width: 18px; height: 18px;
      padding: 0 4px; border-radius: 9px;
      display: inline-flex; align-items: center; justify-content: center;
      line-height: 1;
    }

    /* Bell dropdown rows */
    .bell-row {
      display: block; padding: 12px 16px;
      border-bottom: 1px solid var(--border-light);
      text-decoration: none; color: var(--text);
      transition: background 0.1s;
    }
    .bell-row:hover { background: var(--bg-hover); }
    .bell-row.bell-unread { background: var(--accent-subtle); }
    .bell-row.bell-unread:hover { background: var(--bg-hover); }
    .bell-row-title { font-size: var(--text-sm); font-weight: 600; margin-bottom: 2px; }
    .bell-row-body { font-size: var(--text-xs); color: var(--text-muted); line-height: 1.4; }
    .bell-row-time { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

    /* Dev Notes triage tabs + cards */
    .dev-notes-tab {
      background: none; border: none; cursor: pointer;
      padding: 10px 16px;
      font-size: var(--text-sm); font-weight: 500; color: var(--text-secondary);
      border-bottom: 2px solid transparent;
      font-family: inherit;
    }
    .dev-notes-tab:hover { color: var(--text); }
    .dev-notes-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
    .dn-tab-count {
      display: inline-block; margin-left: 6px;
      background: var(--bg-subtle); color: var(--text-muted);
      font-size: 10px; font-weight: 600;
      padding: 1px 6px; border-radius: 9px;
    }
    .dev-notes-tab.active .dn-tab-count { background: var(--accent-subtle); color: var(--accent-text); }
    .dev-note-card {
      background: var(--bg-card); border: 1px solid var(--border);
      border-left: 3px solid var(--warning);
      border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;
      box-shadow: var(--shadow-sm);
    }
    .dev-note-card.dn-acknowledged { border-left-color: var(--accent); }
    .dev-note-card.dn-corrected { border-left-color: var(--success); }
    .dn-meta {
      display: flex; gap: 8px; flex-wrap: wrap;
      font-size: var(--text-xs); color: var(--text-muted);
      margin-bottom: 8px;
    }
    .dn-meta-author { color: var(--text); font-weight: 600; }
    .dn-meta a { color: var(--accent); text-decoration: none; font-weight: 600; }
    .dn-meta a:hover { text-decoration: underline; }
    .dn-body {
      font-size: var(--text-sm); color: var(--text);
      white-space: pre-wrap; line-height: 1.5;
      margin-bottom: 12px;
    }
    .dn-replies {
      border-top: 1px solid var(--border-light);
      padding-top: 10px; margin-top: 10px;
      display: flex; flex-direction: column; gap: 8px;
    }
    .dn-reply {
      background: var(--bg-subtle); border-radius: 6px;
      padding: 8px 12px; font-size: var(--text-sm);
    }
    .dn-reply-meta {
      display: flex; gap: 8px; align-items: baseline;
      font-size: var(--text-xs); color: var(--text-muted);
      margin-bottom: 2px;
    }
    .dn-reply-author { font-weight: 600; color: var(--text); }
    .dn-reply-body { white-space: pre-wrap; line-height: 1.4; }
    .dn-actions {
      display: flex; gap: 6px; flex-wrap: wrap;
      margin-top: 10px;
    }
    .dn-reply-editor textarea {
      width: 100%; min-height: 60px; padding: 8px 10px;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--bg-card); color: var(--text);
      font-family: inherit; font-size: var(--text-sm);
      resize: vertical;
    }
    .dn-reply-editor-actions { display: flex; gap: 6px; margin-top: 6px; }

    /* Steps */
    .step { display: none; padding: 20px; max-width: 960px; margin: 0 auto; }
    .step.active { display: block; }
    .step-label {
      font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--text-muted); font-weight: 600; margin-bottom: 12px;
    }

    /* ── Utility components ──────────────────────────────────────────────── */

    /* Buttons */
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      border: none; border-radius: 10px;
      font-size: var(--text-md); font-weight: 600;
      cursor: pointer; min-height: 44px; padding: 10px 16px;
      transition: background 0.12s, color 0.12s, border-color 0.12s;
      -webkit-tap-highlight-color: transparent;
      font-family: inherit;
      text-decoration: none;
    }
    .btn-primary { background: var(--accent); color: var(--text-inverse); }
    .btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
    .btn-primary:disabled { background: var(--text-muted); cursor: not-allowed; opacity: 0.7; }
    .btn-success { background: var(--success); color: var(--text-inverse); }
    .btn-success:hover:not(:disabled) { filter: brightness(0.95); }
    .btn-danger { background: var(--danger); color: var(--text-inverse); }
    .btn-danger:hover:not(:disabled) { filter: brightness(0.95); }
    .btn-ghost {
      background: transparent; color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-ghost:hover:not(:disabled) { background: var(--bg-hover); border-color: var(--border-strong); }
    .btn-subtle {
      background: var(--bg-subtle); color: var(--text); border: none;
    }
    .btn-subtle:hover:not(:disabled) { background: var(--bg-hover); }
    .btn-link {
      background: none; border: none; color: var(--accent);
      font-size: var(--text-sm); font-weight: 500; cursor: pointer;
      padding: 4px 0; min-height: auto;
    }
    .btn-link:hover { text-decoration: underline; }
    .btn-icon {
      width: 44px; height: 44px; padding: 0;
      background: transparent; border: none; color: var(--text-secondary);
      display: flex; align-items: center; justify-content: center;
      border-radius: 8px; cursor: pointer;
    }
    .btn-icon:hover { background: var(--bg-hover); color: var(--text); }
    .btn-icon svg { width: 20px; height: 20px; }
    .btn-block { width: 100%; }
    .btn-sm { min-height: 32px; padding: 6px 12px; font-size: var(--text-xs); }

    /* Inputs */
    .input, .search-input {
      width: 100%; padding: 12px 14px; font-size: var(--text-md);
      border: 2px solid var(--border); border-radius: 8px;
      outline: none; -webkit-appearance: none;
      background: var(--bg-input); color: var(--text);
      font-family: inherit;
    }
    .input:focus, .search-input:focus { border-color: var(--accent); }
    .input::placeholder, .search-input::placeholder { color: var(--text-muted); }
    .input-sm { padding: 8px 12px; font-size: var(--text-sm); min-height: 40px; }

    /* Badges */
    .badge {
      display: inline-block;
      font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px;
      letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap;
    }
    .badge-pass    { background: var(--badge-pass-bg); color: var(--badge-pass-text); }
    .badge-fail    { background: var(--badge-fail-bg); color: var(--badge-fail-text); }
    .badge-missing { background: var(--badge-missing-bg); color: var(--badge-missing-text); }
    .badge-error   { background: var(--badge-error-bg); color: var(--badge-error-text); }
    .badge-review,
    .badge-needs_review { background: var(--badge-review-bg); color: var(--badge-review-text); }
    .badge-info    { background: var(--accent-subtle); color: var(--accent-text); }
    .badge-neutral { background: var(--bg-subtle); color: var(--text-secondary); }
    .badge-success { background: var(--success-subtle); color: var(--success-text); }
    .badge-warning { background: var(--warning-subtle); color: var(--warning-text); }
    .badge-danger  { background: var(--danger-subtle); color: var(--danger-text); }

    /* Alerts */
    .alert {
      display: flex; gap: 10px; align-items: flex-start;
      padding: 12px 14px; border-radius: 8px;
      font-size: var(--text-sm); line-height: 1.5;
      border: 1px solid transparent;
    }
    .alert-error   { background: var(--danger-subtle); color: var(--danger-text); border-color: var(--danger); }
    .alert-warning { background: var(--warning-subtle); color: var(--warning-text); border-color: var(--warning); }
    .alert-info    { background: var(--accent-subtle); color: var(--accent-text); border-color: var(--accent); }
    .alert-success { background: var(--success-subtle); color: var(--success-text); border-color: var(--success); }
    .alert svg { flex-shrink: 0; width: 18px; height: 18px; }

    /* Empty states */
    .empty-state {
      text-align: center; padding: 48px 20px;
      display: flex; flex-direction: column; align-items: center; gap: 12px;
    }
    .empty-state-icon {
      width: 72px; height: 72px; border-radius: 50%;
      background: var(--bg-subtle); display: flex; align-items: center; justify-content: center;
      color: var(--text-muted);
    }
    .empty-state-icon svg { width: 32px; height: 32px; }
    .empty-state-title { font-size: var(--text-lg); font-weight: 600; color: var(--text); }
    .empty-state-desc { font-size: var(--text-sm); color: var(--text-muted); max-width: 320px; }

    /* Skeleton loaders */
    @keyframes skeletonShimmer {
      0% { background-position: -200px 0; }
      100% { background-position: calc(200px + 100%) 0; }
    }
    .skeleton {
      background: var(--bg-subtle);
      background-image: linear-gradient(90deg, var(--bg-subtle) 0%, var(--bg-hover) 50%, var(--bg-subtle) 100%);
      background-size: 200px 100%; background-repeat: no-repeat;
      border-radius: 6px;
      animation: skeletonShimmer 1.4s infinite linear;
    }
    .skeleton-card {
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 10px; padding: 12px; display: flex; gap: 12px; margin-bottom: 8px;
    }
    .skeleton-thumb { width: 80px; height: 80px; flex-shrink: 0; border-radius: 8px; }
    .skeleton-lines { flex: 1; display: flex; flex-direction: column; gap: 8px; padding: 4px 0; }
    .skeleton-line { height: 12px; }
    .skeleton-line-lg { height: 16px; width: 70%; }
    .skeleton-line-md { width: 50%; }
    .skeleton-line-sm { height: 10px; width: 40%; }

    /* ── Specific components ─────────────────────────────────────────────── */

    /* List items */
    .list-item {
      background: var(--bg-card); border-radius: 8px; padding: 14px 16px; margin-top: 8px;
      border: 2px solid transparent; cursor: pointer; transition: border-color 0.1s, box-shadow 0.15s;
      min-height: 44px; display: flex; flex-direction: column; justify-content: center;
      box-shadow: var(--shadow-sm);
    }
    .list-item:hover, .list-item:active { border-color: var(--accent); box-shadow: var(--shadow-md); }
    .list-item .name { font-weight: 600; font-size: var(--text-base); color: var(--text); }
    .list-item .detail { font-size: var(--text-sm); color: var(--text-secondary); }

    /* Form groups and toggle buttons */
    .param-group { margin-bottom: 16px; }
    .param-group label {
      display: block; font-size: var(--text-xs); text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-secondary); margin-bottom: 6px; font-weight: 600;
    }
    .toggle-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .toggle-btn {
      padding: 10px 20px; border-radius: 8px; border: 2px solid var(--border);
      background: var(--bg-card); color: var(--text); font-size: var(--text-base); font-weight: 500; cursor: pointer;
      min-height: 44px; transition: border-color 0.1s, background 0.1s; flex: 1; text-align: center;
      font-family: inherit;
    }
    .toggle-btn.selected { border-color: var(--accent); background: var(--accent-subtle); color: var(--accent-text); }

    /* Primary Run button — large variant of btn-primary */
    .run-btn {
      width: 100%; padding: 16px; border: none; border-radius: 10px;
      background: var(--accent); color: var(--text-inverse); font-size: var(--text-lg); font-weight: 600;
      cursor: pointer; min-height: 52px; margin-top: 20px;
      transition: background 0.12s;
      font-family: inherit;
    }
    .run-btn:hover:not(:disabled) { background: var(--accent-hover); }
    .run-btn:disabled { background: var(--text-muted); cursor: not-allowed; opacity: 0.7; }

    /* Progress */
    .progress-wrap { padding: 20px; }
    .progress-bar-bg {
      width: 100%; height: 8px; background: var(--border); border-radius: 4px;
      overflow: hidden; margin-bottom: 8px;
    }
    .progress-bar-fill {
      height: 100%; background: var(--accent); border-radius: 4px;
      transition: width 0.3s ease; width: 0%;
    }
    .progress-text { font-size: var(--text-sm); color: var(--text-secondary); margin-bottom: 16px; }

    .status-msg {
      background: var(--accent-subtle); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;
      font-size: var(--text-sm); color: var(--accent-text); display: none;
    }

    /* Result rows */
    .result-row {
      background: var(--bg-card); border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
      border-left: 4px solid var(--border);
      box-shadow: var(--shadow-sm);
      animation: fadeIn 0.2s ease;
    }
    .result-row.pass         { border-left-color: var(--success); }
    .result-row.fail         { border-left-color: var(--danger); }
    .result-row.missing      { border-left-color: var(--warning); }
    .result-row.error        { border-left-color: var(--purple); }
    .result-row.needs_review { border-left-color: var(--review); }

    .result-header { display: flex; align-items: center; gap: 8px; }
    .result-detail { transition: max-height 0.2s ease; }
    .result-row.collapsed .result-detail { display: none; }
    .result-row.collapsed .collapse-arrow { transform: rotate(-90deg); }
    .collapse-arrow { transition: transform 0.2s ease; display: inline-block; color: var(--text-muted); font-size: 10px; }

    .result-id { font-size: 10px; font-weight: 700; color: var(--text-muted); }
    .result-title { font-size: var(--text-sm); font-weight: 500; flex: 1; color: var(--text); }
    .result-reason { font-size: var(--text-sm); color: var(--text-secondary); margin-top: 6px; padding-left: 10px; border-left: 2px solid var(--border-light); }

    .expand-btn {
      margin-top: 4px; background: none; border: none; color: var(--accent);
      font-size: var(--text-xs); font-weight: 500; cursor: pointer; padding: 2px 0;
    }
    .expand-btn:hover { text-decoration: underline; }
    .expand-btn .arrow { font-size: 10px; margin-left: 2px; }

    /* Done banner */
    .done-banner {
      padding: 16px 20px; display: none; align-items: center; justify-content: space-between;
      flex-wrap: wrap; gap: 10px;
    }
    .done-pass { background: var(--success-subtle); border-bottom: 2px solid var(--success); }
    .done-fail { background: var(--danger-subtle); border-bottom: 2px solid var(--danger); }
    .done-label { font-size: var(--text-sm); font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
    .done-pass .done-label { color: var(--success-text); }
    .done-fail .done-label { color: var(--danger-text); }
    .done-stats { font-size: var(--text-sm); color: var(--text-secondary); }
    .cc-link {
      display: inline-block; margin-top: 8px; padding: 10px 16px; background: var(--accent);
      color: var(--text-inverse); border-radius: 8px; text-decoration: none; font-size: var(--text-sm); font-weight: 600;
      min-height: 44px; line-height: 24px;
    }
    .cc-link:hover { background: var(--accent-hover); }

    /* Back button */
    .back-btn {
      background: none; border: none; color: var(--accent); font-size: var(--text-sm);
      font-weight: 500; cursor: pointer; padding: 4px 0; margin-bottom: 12px;
    }
    .back-btn:hover { text-decoration: underline; }

    /* Loader animation */
    .loader-anim { display: flex; justify-content: center; padding: 20px 0 8px; }
    .loader-anim.hidden { display: none; }

    /* Universal spinner */
    .spinner {
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 32px 0; gap: 12px;
    }
    .spinner-text { font-size: var(--text-sm); color: var(--text-muted); }

    /* Project cards */
    .project-card {
      background: var(--bg-card); border-radius: 10px; margin-top: 8px;
      border: 2px solid transparent; cursor: pointer;
      transition: border-color 0.1s, box-shadow 0.15s;
      display: flex; align-items: center; overflow: hidden;
      box-shadow: var(--shadow-sm);
    }
    .project-card:hover, .project-card:active { border-color: var(--accent); box-shadow: var(--shadow-md); }
    .project-card-img {
      width: 80px; height: 80px; object-fit: cover; flex-shrink: 0; background: var(--border);
      align-self: center;
    }
    .project-card-info { padding: 12px 14px; flex: 1; display: flex; flex-direction: column; justify-content: center; }
    .project-card-name { font-weight: 600; font-size: var(--text-sm); color: var(--text); }
    .project-card-addr { font-size: var(--text-xs); color: var(--text-muted); margin-top: 2px; }
    .project-card-meta { font-size: 10px; color: var(--text-muted); margin-top: 4px; display: flex; align-items: center; gap: 6px; }
    .project-card-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--success); }

    /* Home cards */
    .home-cards { display: flex; flex-direction: column; gap: 8px; }
    .home-card {
      background: var(--bg-card); border-radius: 10px; padding: 16px; cursor: pointer;
      display: flex; align-items: center; gap: 14px;
      border: 2px solid transparent;
      transition: border-color 0.1s, box-shadow 0.15s;
      box-shadow: var(--shadow-sm);
    }
    .home-card:hover, .home-card:active { border-color: var(--accent); box-shadow: var(--shadow-md); }
    .home-card-icon {
      width: 44px; height: 44px; border-radius: 10px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
    }
    .home-card-text { flex: 1; }
    .home-card-title { font-size: var(--text-base); font-weight: 600; color: var(--text); }
    .home-card-desc { font-size: var(--text-sm); color: var(--text-muted); margin-top: 2px; }

    /* Filter bars */
    .filter-bar {
      display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
    }
    .filter-bar .search-input { flex: 1; min-width: 160px; font-size: var(--text-sm); }
    .filter-select {
      padding: 10px 12px; border: 2px solid var(--border); border-radius: 8px;
      font-size: var(--text-sm); background: var(--bg-input); color: var(--text);
      min-height: 44px; font-family: inherit;
    }
    .filter-range {
      display: flex; align-items: center; gap: 6px; flex: 1; min-width: 200px;
    }
    .filter-range input {
      flex: 1; padding: 10px 12px; border: 2px solid var(--border); border-radius: 8px;
      font-size: var(--text-sm); background: var(--bg-input); color: var(--text); min-height: 44px;
      font-family: inherit;
    }
    .filter-range .sep { color: var(--text-muted); font-size: var(--text-sm); }

    /* Horizontal scroll wrapper for dense admin content on mobile */
    .table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }

    /* Thin progress bar — used for checklist completion indicators */
    .progress-thin {
      height: 3px; background: var(--border-light);
      border-radius: 2px; overflow: hidden; margin-top: 4px;
    }
    .progress-thin-fill {
      height: 100%; background: var(--accent);
      transition: width 0.3s ease;
    }
    .progress-thin-fill.complete { background: var(--success); }

    /* Project card checklist breakdown */
    .project-checklists {
      margin-top: 6px; display: flex; flex-direction: column; gap: 6px;
    }
    .project-checklist-row { font-size: var(--text-xs); }
    .project-checklist-meta {
      display: flex; gap: 8px; align-items: baseline;
    }
    .project-checklist-name {
      color: var(--text);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      min-width: 0;
    }
    .project-checklist-count {
      color: var(--text-muted); font-weight: 600; flex-shrink: 0;
    }

    /* Loading placeholder shown between stage 1 (project list returned)
       and stage 2 (per-project checklist calls resolve). Without this the
       card looks finished but then suddenly grows a new row of data —
       confusing. Shimmer makes it clear something is still coming. */
    .project-checklists-loading {
      margin-top: 6px; font-size: var(--text-xs);
      color: var(--text-muted); display: inline-block;
      padding: 2px 0;
    }
    .project-checklists-loading::before {
      content: "Loading checklist progress";
      background: linear-gradient(
        90deg,
        var(--text-muted) 0%,
        var(--text) 50%,
        var(--text-muted) 100%
      );
      -webkit-background-clip: text; background-clip: text;
      -webkit-text-fill-color: transparent;
      background-size: 200% 100%;
      animation: checklists-shimmer 1.8s linear infinite;
    }
    @keyframes checklists-shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    /* ── Responsive: desktop ───────────────────────────────────────────── */
    @media (min-width: 1024px) {
      .sidebar { display: flex; }
      .mobile-top-bar { display: none; }
      .bottom-tabs { display: none; }
      .main-content {
        margin-left: var(--sidebar-width);
        padding-bottom: 40px;
      }
      .step { padding: 28px; }
    }

    /* ── Responsive: mobile ────────────────────────────────────────────── */
    @media (max-width: 640px) {
      .step { padding: 16px; }
      .filter-bar .search-input,
      .filter-bar .filter-select,
      .filter-range { width: 100%; min-width: 0; flex-basis: 100%; }
      .project-card-img { width: 96px; height: 96px; }
      .home-card { padding: 14px; }
      .toggle-btn { flex: 1 1 calc(50% - 4px); min-width: calc(50% - 4px); }
    }
  </style>
</head>
<body>

  <!-- Desktop sidebar (≥1024px) -->
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-logo">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" width="100%" role="img" aria-label="Solclear" style="display:block;max-width:200px;">
        <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/></g>
        <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#ffffff" letter-spacing="-2.5">solclear</text>
      </svg>
    </div>
    <button class="nav-item" data-nav="home" onclick="navigate('home')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/></svg>
      Home
    </button>
    <button class="nav-item" data-nav="check" onclick="navigate('check')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M7 12h10"/></svg>
      New Check
    </button>
    <button class="nav-item" data-nav="reports" onclick="navigate('reports')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
      Reports
    </button>

    <!-- Section label gets set by loadMe() to the user's actual role
         (Reviewer / Admin / Superadmin) so a Superadmin doesn't see
         a "ADMIN" header that doesn't quite fit. The .reviewer-plus
         class still keeps it hidden from crew. -->
    <div id="sidebarRoleLabel" class="sidebar-section-label reviewer-plus" style="display:none;">Admin</div>
    <!-- Notifications first under the role section — most-frequently-
         used surface for reviewer/admin/superadmin during dry runs and
         once crews go live. Same toggleBellPanel as the mobile bell. -->
    <button class="nav-item" id="sidebarBellBtn" onclick="toggleBellPanel(event)" title="Notifications">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
      <span style="flex:1;">Notifications</span>
      <span id="sidebarBellBadge" style="display:none;background:var(--danger);color:#fff;font-size:10px;font-weight:700;min-width:18px;height:18px;padding:0 5px;border-radius:9px;align-items:center;justify-content:center;line-height:1;">0</span>
    </button>
    <button class="nav-item reviewer-plus" data-nav="orgs" onclick="navigate('orgs')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 8h1M9 12h1M9 16h1M14 8h1M14 12h1M14 16h1M3 21h18"/></svg>
      Organizations
    </button>
    <button class="nav-item reviewer-plus" data-nav="reqs" onclick="navigate('reqs')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h11"/></svg>
      Requirements
    </button>
    <button class="nav-item superadmin-only" data-nav="costs" onclick="navigate('costs')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
      Costs
    </button>
    <!-- Dev Notes triage tab — superadmin only. The badge shows the
         count of open (awaiting triage) dev notes, refreshed alongside
         the bell. -->
    <button class="nav-item superadmin-only" data-nav="devnotes" onclick="navigate('devnotes')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 13h6M9 17h4"/></svg>
      <span style="flex:1;">Dev Notes</span>
      <span id="sidebarDevNotesBadge" style="display:none;background:var(--warning);color:var(--text-inverse);font-size:10px;font-weight:700;min-width:18px;height:18px;padding:0 5px;border-radius:9px;align-items:center;justify-content:center;line-height:1;">0</span>
    </button>

    <div class="sidebar-footer">
      <button class="nav-item" onclick="toggleTheme()" id="sidebarThemeBtn">
        <svg id="sidebarThemeIconSun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        <svg id="sidebarThemeIconMoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:none;"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <span id="sidebarThemeLabel">Dark mode</span>
      </button>
      <a class="nav-item" href="/change-password" style="text-decoration:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
        Change Password
      </a>
      <a class="nav-item nav-item-danger" href="/logout" style="text-decoration:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
        Sign Out
      </a>
    </div>
  </aside>

  <!-- Mobile top bar (<1024px) -->
  <header class="mobile-top-bar">
    <div></div>
    <div class="logo-center">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 160" height="42" style="flex-shrink:0;" role="img" aria-label="Solclear">
        <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/></g>
        <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#ffffff" letter-spacing="-2.5">solclear</text>
      </svg>
    </div>
    <div class="header-actions">
      <button class="header-btn" id="bellBtn" onclick="toggleBellPanel(event)" title="Notifications" aria-label="Notifications">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        <span id="bellBadge" class="header-badge" style="display:none;">0</span>
      </button>
      <button class="theme-toggle" onclick="toggleTheme()" id="themeBtn" title="Toggle dark mode" aria-label="Toggle dark mode">
        <svg id="themeIconSun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        <svg id="themeIconMoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:none;"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      </button>
    </div>

  </header>

  <!-- Bell dropdown panel — body-level so it's never trapped in any
       ancestor's stacking context. position:fixed anchors it to the
       viewport. toggleBellPanel() flips display + repositions relative
       to whichever bell button (sidebar or top-bar) was clicked. -->
  <div id="bellPanel" style="display:none;position:fixed;top:60px;right:12px;width:360px;max-width:calc(100vw - 24px);max-height:480px;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow-lg);z-index:200;overflow:hidden;flex-direction:column;">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border);">
      <strong style="font-size:var(--text-sm);">Notifications</strong>
      <button onclick="markAllNotificationsRead()" id="bellMarkAll" style="background:none;border:none;color:var(--accent);font-size:var(--text-xs);font-weight:600;cursor:pointer;padding:4px 6px;font-family:inherit;">Mark all read</button>
    </div>
    <div id="bellList" style="overflow-y:auto;max-height:420px;">
      <div style="padding:24px 16px;text-align:center;color:var(--text-muted);font-size:var(--text-sm);">Loading…</div>
    </div>
  </div>

  <main class="main-content">

  <!-- Impersonation banner — shown when a superadmin is acting as another
       user. Lives inside .main-content so it respects the desktop sidebar
       offset. Sticky so 'Stop' stays reachable while scrolling.
       Explicit dark-on-amber colors (not theme tokens) so contrast works
       in both light and dark mode — amber bg looks similar in both, so
       hardcoded #1a1a2e text reads cleanly either way. -->
  <div id="impersonationBanner" style="display:none;background:#f59e0b;color:#1a1a2e;padding:10px 16px;align-items:center;gap:12px;font-size:var(--text-sm);font-weight:500;border-bottom:1px solid rgba(0,0,0,0.18);position:sticky;top:0;z-index:35;">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
    <div style="flex:1;min-width:0;line-height:1.35;">
      <strong>Impersonating</strong> <span id="impersonationTarget">—</span>
      <span style="opacity:0.75;"> · <span id="impersonationInitiator">—</span></span>
    </div>
    <button onclick="stopImpersonate()" style="background:#1a1a2e;color:#fff;border:none;border-radius:6px;padding:6px 12px;font-size:var(--text-xs);font-weight:600;cursor:pointer;flex-shrink:0;min-height:32px;font-family:inherit;">Stop impersonating</button>
  </div>

  <!-- Anthropic platform-status banner — shown when status.anthropic.com
       reports anything other than all-systems-operational. Color coded by
       severity (minor/major/critical all shades of red/amber). Driven by
       the /api/platform_status poll below; hidden until we have a real
       non-operational indicator so we don't cry wolf during transient
       status.anthropic.com blips. -->
  <div id="platformStatusBanner" style="display:none;padding:10px 16px;align-items:center;gap:12px;font-size:var(--text-sm);font-weight:500;border-bottom:1px solid rgba(0,0,0,0.18);position:sticky;top:0;z-index:34;">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>
    <div style="flex:1;min-width:0;line-height:1.35;">
      <strong id="platformStatusTitle">Anthropic API: degraded</strong>
      <span id="platformStatusDetail" style="opacity:0.9;"> — compliance checks may be slower or fail intermittently.</span>
      <a href="https://status.anthropic.com/" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline;margin-left:8px;">status page</a>
    </div>
  </div>

  <!-- Landing page -->
  <div id="homePage" class="step active" style="display:block;">
    <!-- Active-check banner — only shown when the logged-in user has a
         check currently running or recently completed. Driven by
         /api/my_active_check + localStorage dismissal (see applyActiveCheckBanners
         in the script block). Hidden by default; fetchActiveChecks fills
         in the href/text and reveals it. -->
    <a id="runningCheckBanner" href="#" style="display:none;align-items:center;gap:12px;padding:12px 16px;background:var(--accent-subtle);color:var(--accent-text);border:1px solid var(--accent);border-radius:10px;text-decoration:none;margin-bottom:14px;font-size:var(--text-sm);font-weight:500;">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <div style="flex:1;min-width:0;line-height:1.35;">
        <strong>Your check is still running</strong>
        <div id="runningCheckDetail" style="opacity:0.85;font-weight:400;"></div>
      </div>
      <span style="font-weight:600;white-space:nowrap;">View progress →</span>
    </a>

    <div id="completedCheckBanner" style="display:none;align-items:center;gap:12px;padding:12px 16px;background:var(--success-subtle);color:var(--success-text);border:1px solid var(--success);border-radius:10px;margin-bottom:14px;font-size:var(--text-sm);font-weight:500;">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
      <a id="completedCheckLink" href="#" style="flex:1;min-width:0;line-height:1.35;color:inherit;text-decoration:none;">
        <strong>Your check just completed</strong>
        <div id="completedCheckDetail" style="opacity:0.85;font-weight:400;"></div>
      </a>
      <button onclick="dismissCompletedCheckBanner(event)" aria-label="Dismiss" style="background:none;border:none;color:inherit;cursor:pointer;padding:4px;opacity:0.6;flex-shrink:0;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.6">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>

    <div style="padding:4px 0 20px;">
      <div style="font-size:15px;font-weight:600;color:var(--text);">Welcome to Solclear</div>
      <div style="font-size:12px;color:var(--text-muted);">Solar compliance, simplified.</div>
    </div>

    <!-- Action cards -->
    <div class="home-cards">
      <div class="home-card" onclick="showStep(1)">
        <div class="home-card-icon" style="background:#eff6ff;color:#3b82f6;">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </div>
        <div class="home-card-text">
          <div class="home-card-title">New Compliance Check</div>
          <div class="home-card-desc">Run a photo compliance check on a project</div>
        </div>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
      </div>

      <div class="home-card" onclick="showStep('reports')">
        <div class="home-card-icon" style="background:#ecfdf5;color:#10b981;">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
        </div>
        <div class="home-card-text">
          <div class="home-card-title">Recent Reports</div>
          <div class="home-card-desc">View and share previous compliance results</div>
        </div>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
      </div>

      <div class="home-card reviewer-plus" onclick="showStep('orgs')" style="display:none;">
        <div class="home-card-icon" style="background:var(--warning-subtle);color:var(--warning);">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 21h18M9 8h1M9 12h1M9 16h1M14 8h1M14 12h1M14 16h1"/><rect x="5" y="3" width="14" height="18" rx="1"/></svg>
        </div>
        <div class="home-card-text">
          <div class="home-card-title">Organizations</div>
          <div class="home-card-desc">Manage companies, users, and settings</div>
        </div>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
      </div>
    </div>

    <!-- Recent reports preview -->
    <div style="margin-top:28px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#9ca3af;font-weight:600;">Latest Reports</div>
        <button onclick="showStep('reports')" style="background:none;border:none;color:#3b82f6;font-size:12px;font-weight:500;cursor:pointer;">View all</button>
      </div>
      <div id="homeRecentList"></div>
    </div>
  </div>

  <!-- Full reports list -->
  <div id="reportsPage" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">All Reports</div>

    <!-- Filters -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
      <input class="search-input" id="reportSearch" type="text" placeholder="Search by project name..." style="flex:1;min-width:160px;font-size:13px;" oninput="filterReports()">
      <select id="reportStatusFilter" onchange="filterReports()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;">
        <option value="all">All Status</option>
        <option value="passed">Passed Only</option>
        <option value="failed">Has Failures</option>
        <option value="needs_review">Needs Review</option>
      </select>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;align-items:center;">
      <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:200px;">
        <input type="date" id="reportDateFrom" onchange="filterReports()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
        <span style="color:var(--text-muted);font-size:12px;">to</span>
        <input type="date" id="reportDateTo" onchange="filterReports()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
      </div>
      <button onclick="clearDateFilter()" style="background:var(--border-light);border:none;border-radius:8px;padding:10px 14px;font-size:12px;color:var(--text-muted);cursor:pointer;min-height:44px;font-weight:500;">Clear dates</button>
    </div>
    <div id="reportCount" style="font-size:11px;color:var(--text-muted);margin-bottom:8px;"></div>

    <div id="recentList"></div>
  </div>

  <!-- Step 1: Select project -->
  <div id="step1" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Step 1 — Select Project</div>
    <input class="search-input" id="projectSearch" type="text" placeholder="Search by name or address..." autocomplete="off">

    <!-- Date filter -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center;">
      <select id="projectDateField" onchange="filterProjects()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:12px;background:var(--bg-input);color:var(--text);min-height:44px;">
        <option value="updated_at">Last Updated</option>
        <option value="created_at">Date Created</option>
      </select>
      <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:180px;">
        <input type="date" id="projectDateFrom" onchange="filterProjects()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
        <span style="color:var(--text-muted);font-size:12px;">to</span>
        <input type="date" id="projectDateTo" onchange="filterProjects()" style="padding:10px 12px;border:2px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg-input);color:var(--text);min-height:44px;flex:1;">
      </div>
      <button onclick="clearProjectDateFilter()" style="background:var(--border-light);border:none;border-radius:8px;padding:10px 14px;font-size:12px;color:var(--text-muted);cursor:pointer;min-height:44px;font-weight:500;">Clear</button>
    </div>
    <div id="projectCount" style="font-size:11px;color:var(--text-muted);margin:8px 0;"></div>

    <div id="projectListLoading"></div>
    <div id="projectList"></div>
  </div>

  <!-- Step 2: Select checklist -->
  <div id="step2" class="step">
    <button class="back-btn" onclick="showStep(1)">&larr; Back to projects</button>
    <div class="step-label">Step 2 — Select Checklist</div>
    <div id="selectedProject" style="font-weight:600; margin-bottom:12px;"></div>
    <div id="checklistList"></div>
  </div>

  <!-- Step 3: Manufacturer selection -->
  <div id="step3" class="step">
    <button class="back-btn" onclick="showStep(2)">&larr; Back to checklists</button>
    <div class="step-label">Step 3 — Select Manufacturer</div>
    <div id="selectedProjectName2" style="font-weight:600; margin-bottom:4px;"></div>
    <div id="selectedChecklistName" style="font-size:12px; color:#6b7280; margin-bottom:16px;"></div>

    <div class="param-group">
      <label>Inverter / Equipment Manufacturer</label>
      <div class="toggle-row">
        <button class="toggle-btn" data-param="manufacturer" data-value="SolarEdge" onclick="selectMfg(this)">SolarEdge</button>
        <button class="toggle-btn" data-param="manufacturer" data-value="Tesla" onclick="selectMfg(this)">Tesla</button>
        <button class="toggle-btn" data-param="manufacturer" data-value="Enphase" onclick="selectMfg(this)">Enphase</button>
      </div>
    </div>

    <div id="derivedInfo" style="background:#f0fdf4; border-radius:8px; padding:12px 16px; margin-top:12px; font-size:12px; color:#065f46; display:none;">
      Battery, backup, incentive state, and portal access will be auto-detected from the checklist.
    </div>

    <button class="run-btn" id="runBtn" onclick="startCheck()" disabled>Select a manufacturer to continue</button>
  </div>

  <!-- Step 4: Live results -->
  <div id="step4" class="step">
    <div class="done-banner" id="doneBanner"></div>
    <div class="progress-wrap">
      <div class="loader-anim" id="loaderAnim">
        <svg viewBox="0 0 120 120" width="64" height="64">
          <path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="#e5e7eb" stroke-width="8" stroke-linecap="round"/>
          <circle cx="0" cy="0" r="10" fill="#F59E0B">
            <animateMotion dur="1.4s" repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.45 0 0.55 1">
              <mpath href="#sunPath"/>
            </animateMotion>
          </circle>
          <path id="sunPath" d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="none"/>
        </svg>
      </div>
      <div class="status-msg" id="statusMsg"></div>
      <div class="progress-bar-bg"><div class="progress-bar-fill" id="progressFill"></div></div>
      <div class="progress-text" id="progressText">Preparing...</div>
      <!-- Cancel button visible only while a check is actively running.
           cancelRun() hides it + shows "Cancelling…" until the SSE 'cancelled'
           event fires. The current requirement's vision call finishes first
           (can't be interrupted mid-request), then the run stops. -->
      <div id="cancelRunWrap" style="display:none;text-align:right;margin-bottom:8px;">
        <button onclick="cancelRun()" id="cancelRunBtn" class="btn btn-sm btn-ghost" style="border-color:var(--danger);color:var(--danger);">Cancel checks</button>
      </div>
      <div id="resultsToggle" style="display:none;text-align:right;margin-bottom:8px;">
        <button onclick="toggleAllResults()" id="toggleAllBtn" style="background:none;border:1px solid var(--border);border-radius:6px;padding:6px 12px;font-size:11px;color:var(--text-secondary);cursor:pointer;font-weight:500;">Collapse All</button>
      </div>
      <div id="resultsList"></div>
    </div>
  </div>

  <!-- Organizations list -->
  <div id="adminOrgs" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Organizations</div>
    <button class="run-btn superadmin-only" onclick="showCreateOrg()" style="margin-bottom:16px;background:var(--accent);display:none;">+ Create Organization</button>
    <div id="orgsList"></div>
  </div>

  <!-- Create org form -->
  <div id="adminOrgCreate" class="step">
    <button class="back-btn" onclick="showStep('orgs')">&larr; Back to organizations</button>
    <div class="step-label">Create Organization</div>
    <div class="param-group">
      <label>Organization Name</label>
      <input class="search-input" id="newOrgName" type="text" placeholder="e.g. Independent Solar" autocomplete="off">
    </div>
    <div class="param-group">
      <label>Initial Status</label>
      <div class="toggle-row">
        <button class="toggle-btn selected" data-param="org-status" data-value="onboarding" onclick="selectToggle(this)">Onboarding</button>
        <button class="toggle-btn" data-param="org-status" data-value="demo" onclick="selectToggle(this)">Demo</button>
        <button class="toggle-btn" data-param="org-status" data-value="active" onclick="selectToggle(this)">Active</button>
      </div>
    </div>
    <button class="run-btn" onclick="createOrg()">Create Organization</button>
  </div>

  <!-- Org detail -->
  <div id="adminOrgDetail" class="step">
    <button class="back-btn" onclick="showStep('orgs')">&larr; Back to organizations</button>
    <div class="step-label" id="orgDetailLabel">Organization</div>

    <!-- Org info -->
    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div class="param-group">
        <label>Name</label>
        <input class="search-input" id="orgEditName" type="text" style="font-size:14px;">
      </div>
      <div class="param-group">
        <label>Status</label>
        <div class="toggle-row" id="orgStatusToggles">
          <button class="toggle-btn" data-param="org-edit-status" data-value="onboarding" onclick="selectToggle(this)">Onboarding</button>
          <button class="toggle-btn" data-param="org-edit-status" data-value="demo" onclick="selectToggle(this)">Demo</button>
          <button class="toggle-btn" data-param="org-edit-status" data-value="active" onclick="selectToggle(this)">Active</button>
          <button class="toggle-btn" data-param="org-edit-status" data-value="inactive" onclick="selectToggle(this)">Inactive</button>
        </div>
      </div>
      <!-- API keys are sensitive — only superadmin/admin can view or edit them -->
      <div class="param-group admin-write" style="display:none;">
        <label>CompanyCam API Key</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="search-input" id="orgCcKey" type="password" style="font-size:13px;font-family:monospace;flex:1;" placeholder="Not set">
          <button onclick="toggleKeyVis('orgCcKey')" style="background:var(--border-light);border:none;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:12px;min-height:44px;color:var(--text);">Show</button>
        </div>
      </div>
      <div class="param-group admin-write" style="display:none;">
        <label>Anthropic API Key</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="search-input" id="orgAnthKey" type="password" style="font-size:13px;font-family:monospace;flex:1;" placeholder="Not set">
          <button onclick="toggleKeyVis('orgAnthKey')" style="background:var(--border-light);border:none;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:12px;min-height:44px;color:var(--text);">Show</button>
        </div>
      </div>
      <button class="run-btn admin-write" onclick="saveOrg()" style="display:none;background:var(--success);">Save Changes</button>
    </div>

    <!-- Users -->
    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <label style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-secondary);font-weight:600;margin:0;">Users</label>
        <span id="orgUserCount" style="font-size:11px;color:var(--text-muted);"></span>
      </div>
      <div id="orgUsersList"></div>

      <!-- Add user form (admin/superadmin only) -->
      <div class="admin-write" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);">
        <div style="font-size:11px;color:var(--text-secondary);font-weight:600;margin-bottom:8px;">ADD USER</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input class="search-input" id="addUserFirst" type="text" placeholder="First Name" style="flex:1;min-width:100px;font-size:13px;">
          <input class="search-input" id="addUserLast" type="text" placeholder="Last Name" style="flex:1;min-width:100px;font-size:13px;">
          <input class="search-input" id="addUserEmail" type="email" placeholder="Email" style="flex:1;min-width:160px;font-size:13px;">
          <input class="search-input" id="addUserPhone" type="tel" placeholder="Phone (optional)" style="flex:1;min-width:120px;font-size:13px;">
          <!-- Password removed — invite email is sent automatically -->
          <select id="addUserRole" style="padding:8px;border:2px solid var(--border);border-radius:8px;font-size:13px;min-height:44px;">
            <option value="crew">Crew</option>
            <option value="reviewer">Reviewer</option>
            <option value="admin">Admin</option>
          </select>
          <button onclick="addUser()" style="background:var(--accent);color:var(--text-inverse);border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;min-height:44px;">Add</button>
        </div>
      </div>

      <!-- CSV upload (admin/superadmin only) -->
      <div class="admin-write" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);">
        <div style="font-size:11px;color:var(--text-secondary);font-weight:600;margin-bottom:8px;">BULK IMPORT (CSV)</div>
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Format: email, first_name, last_name, role, phone (one per line)</div>
        <input type="file" id="csvUpload" accept=".csv" onchange="uploadCsv()" style="font-size:12px;">
        <div id="csvResult" style="margin-top:8px;font-size:12px;"></div>
      </div>
    </div>
  </div>

  <!-- User detail/edit -->
  <div id="adminUserDetail" class="step">
    <button class="back-btn" id="userDetailBack">&larr; Back to organization</button>
    <div class="step-label" id="userDetailLabel">Edit User</div>

    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div style="display:flex;gap:12px;flex-wrap:wrap;">
        <div class="param-group" style="flex:1;min-width:140px;">
          <label>First Name</label>
          <input class="search-input" id="editUserFirst" type="text" style="font-size:14px;">
        </div>
        <div class="param-group" style="flex:1;min-width:140px;">
          <label>Last Name</label>
          <input class="search-input" id="editUserLast" type="text" style="font-size:14px;">
        </div>
      </div>
      <div class="param-group">
        <label>Email</label>
        <input class="search-input" id="editUserEmail" type="email" style="font-size:14px;">
      </div>
      <div class="param-group">
        <label>Phone</label>
        <input class="search-input" id="editUserPhone" type="tel" style="font-size:14px;" placeholder="Optional">
      </div>
      <div class="param-group">
        <label>Role</label>
        <div class="toggle-row" id="editUserRoleToggles">
          <button class="toggle-btn" data-param="edit-user-role" data-value="crew" onclick="selectToggle(this)">Crew</button>
          <button class="toggle-btn" data-param="edit-user-role" data-value="reviewer" onclick="selectToggle(this)">Reviewer</button>
          <button class="toggle-btn" data-param="edit-user-role" data-value="admin" onclick="selectToggle(this)">Admin</button>
        </div>
      </div>
      <button class="run-btn" onclick="saveUser()" style="background:var(--success);">Save Changes</button>
    </div>

    <div id="userStatusInfo" style="background:var(--bg-card);border-radius:8px;padding:16px;font-size:12px;color:var(--text-secondary);"></div>
  </div>

  <!-- Requirements list -->
  <div id="adminReqs" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Palmetto M1 Requirements</div>

    <!-- Change alert banner (hidden by default) -->
    <div id="changeAlert" class="alert alert-error" style="display:none;flex-direction:column;align-items:stretch;margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <div style="font-size:var(--text-base);font-weight:700;">Requirements Changed</div>
        <button onclick="dismissAlert()" style="margin-left:auto;background:none;border:none;color:inherit;cursor:pointer;font-size:16px;padding:0 4px;" aria-label="Dismiss">&times;</button>
      </div>
      <div id="changeSummary" style="font-size:var(--text-sm);line-height:1.6;margin-top:10px;"></div>
      <div id="changeDiff" style="display:none;margin-top:8px;">
        <button onclick="toggleDiff()" id="diffToggleBtn" class="expand-btn" style="color:inherit;">Show raw diff <span class="arrow">&#9662;</span></button>
        <pre id="changeDiffContent" style="display:none;margin-top:8px;padding:10px;background:var(--bg-card);border-radius:6px;font-size:var(--text-xs);overflow-x:auto;max-height:250px;color:var(--text);border:1px solid var(--border);"></pre>
      </div>
    </div>

    <!-- Monitor status -->
    <div id="monitorCard" style="background:var(--bg-card);border-radius:8px;padding:14px 16px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="font-size:12px;font-weight:600;color:var(--text);">Palmetto M1 Change Detection</div>
          <div id="monitorBadge" style="display:none;"></div>
        </div>
        <button onclick="checkRequirementsNow()" id="checkNowBtn" style="background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 14px;font-size:11px;font-weight:600;cursor:pointer;min-height:32px;">Check Now</button>
      </div>
      <div id="monitorStatus" style="font-size:12px;color:var(--text-muted);"></div>
    </div>

    <!-- Requirements by section -->
    <div id="reqsList"></div>
  </div>

  <!-- Requirement detail/edit -->
  <div id="adminReqDetail" class="step">
    <button class="back-btn" onclick="showStep('reqs')">&larr; Back to requirements</button>
    <div class="step-label" id="reqDetailLabel">Requirement</div>

    <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
      <div class="param-group">
        <label>ID</label>
        <div id="reqEditId" style="font-size:14px;font-weight:600;color:var(--text);"></div>
      </div>
      <div class="param-group">
        <label>Section</label>
        <div id="reqEditSection" style="font-size:13px;color:var(--text-secondary);"></div>
      </div>
      <div class="param-group">
        <label>Title</label>
        <input class="search-input" id="reqEditTitle" type="text" style="font-size:14px;">
      </div>
      <div class="param-group">
        <label>Validation Prompt</label>
        <textarea class="search-input" id="reqEditPrompt" rows="5" style="font-size:13px;resize:vertical;font-family:inherit;"></textarea>
      </div>
      <div class="param-group">
        <label>CompanyCam Task Titles (comma-separated)</label>
        <input class="search-input" id="reqEditTaskTitles" type="text" style="font-size:13px;" placeholder="e.g. Main Breaker, Breaker Rating">
      </div>
      <div class="param-group">
        <label>Keywords (comma-separated)</label>
        <input class="search-input" id="reqEditKeywords" type="text" style="font-size:13px;" placeholder="e.g. main breaker, ampere">
      </div>
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:12px;">Changes are saved in memory. They will reset on server restart until requirements are migrated to the database.</div>
      <button class="run-btn" onclick="saveRequirement()" style="background:var(--success);">Save Changes</button>
    </div>
  </div>

  <!-- Cost dashboard (superadmin only) -->
  <div id="adminCosts" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">API Cost Dashboard</div>

    <!-- Filter bar -->
    <div class="filter-bar" style="margin-bottom:12px;">
      <select id="costOrgFilter" class="filter-select" onchange="loadCosts()">
        <option value="">All organizations</option>
      </select>
      <select id="costUserFilter" class="filter-select" onchange="loadCosts()">
        <option value="">All users</option>
      </select>
    </div>
    <div class="filter-bar" style="margin-bottom:16px;">
      <div class="filter-range">
        <input type="date" id="costDateFrom" onchange="loadCosts()" placeholder="From">
        <span class="sep">to</span>
        <input type="date" id="costDateTo" onchange="loadCosts()" placeholder="To">
      </div>
      <button class="btn btn-subtle btn-sm" onclick="clearCostFilters()">Clear filters</button>
    </div>

    <div id="costSummary" style="margin-top:4px;"></div>
    <div id="costBody" style="margin-top:16px;"></div>
  </div>

  <!-- Dev Notes triage page (superadmin only — gated by route handler).
       Three tabs: Awaiting Triage / In Progress / Resolved. Each row
       shows the original dev note + its reply thread + action buttons. -->
  <div id="adminDevNotes" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Dev Notes</div>

    <nav class="dev-notes-tabs" style="display:flex;gap:0;border-bottom:1px solid var(--border);margin:8px 0 16px;">
      <button class="dev-notes-tab active" data-dn-tab="open" onclick="filterDevNotesTab('open')">
        Awaiting Triage <span class="dn-tab-count" id="dnCountOpen">0</span>
      </button>
      <button class="dev-notes-tab" data-dn-tab="acknowledged" onclick="filterDevNotesTab('acknowledged')">
        In Progress <span class="dn-tab-count" id="dnCountAcknowledged">0</span>
      </button>
      <button class="dev-notes-tab" data-dn-tab="corrected" onclick="filterDevNotesTab('corrected')">
        Resolved <span class="dn-tab-count" id="dnCountCorrected">0</span>
      </button>
    </nav>

    <div id="devNotesList">
      <div style="padding:24px 16px;text-align:center;color:var(--text-muted);font-size:var(--text-sm);">Loading…</div>
    </div>
  </div>

  </main>

  <!-- Mobile bottom tab bar (<1024px) -->
  <nav class="bottom-tabs" id="bottomTabs">
    <button class="tab-btn active" data-tab="home" onclick="navigate('home')" aria-label="Home">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/></svg>
      Home
    </button>
    <button class="tab-btn" data-tab="check" onclick="navigate('check')" aria-label="New Check">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v10M7 12h10"/></svg>
      Check
    </button>
    <button class="tab-btn" data-tab="reports" onclick="navigate('reports')" aria-label="Reports">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
      Reports
    </button>
    <button class="tab-btn" data-tab="account" onclick="openAccountSheet()" aria-label="Account">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 016-6h4a6 6 0 016 6v1"/></svg>
      Account
    </button>
  </nav>

  <!-- Mobile account sheet -->
  <div class="sheet-overlay" id="sheetOverlay" onclick="closeAccountSheet()"></div>
  <aside class="account-sheet" id="accountSheet">
    <div class="sheet-handle"></div>
    <!-- Mobile account sheet's role label — same dynamic label as the
         desktop sidebar (set by loadMe). Different id so we can target
         both. -->
    <div id="accountSheetRoleLabel" class="sidebar-section-label reviewer-plus" style="display:none;">Admin</div>
    <button class="nav-item reviewer-plus" onclick="closeAccountSheet();navigate('orgs')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 8h1M9 12h1M9 16h1M14 8h1M14 12h1M14 16h1M3 21h18"/></svg>
      Organizations
    </button>
    <button class="nav-item reviewer-plus" onclick="closeAccountSheet();navigate('reqs')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h11"/></svg>
      Requirements
    </button>
    <button class="nav-item superadmin-only" onclick="closeAccountSheet();navigate('costs')" style="display:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
      Costs
    </button>
    <div class="sidebar-section-label">Account</div>
    <a class="nav-item" href="/change-password" style="text-decoration:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
      Change Password
    </a>
    <a class="nav-item nav-item-danger" href="/logout" style="text-decoration:none;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
      Sign Out
    </a>
  </aside>

  <script>
    let selectedProjectId = null;
    let selectedProjectName = '';
    let selectedProjectState = '';
    let selectedChecklistId = null;
    let selectedChecklistName = '';
    let selectedManufacturer = null;
    let searchTimer = null;
    let currentOrgId = null;
    let currentUserId = null;

    // ── Account sheet (mobile) ──
    function openAccountSheet() {
      document.getElementById('accountSheet').classList.add('open');
      document.getElementById('sheetOverlay').classList.add('open');
      setActiveTab('account');
    }
    function closeAccountSheet() {
      document.getElementById('accountSheet').classList.remove('open');
      document.getElementById('sheetOverlay').classList.remove('open');
    }

    // Legacy aliases — some inline handlers may still call closeNav/openNav.
    function closeNav() { closeAccountSheet(); }
    function openNav() { openAccountSheet(); }

    // ── Theme toggle ──
    function toggleTheme() {
      const html = document.documentElement;
      const isDark = html.getAttribute('data-theme') === 'dark';
      html.setAttribute('data-theme', isDark ? 'light' : 'dark');
      localStorage.setItem('solclear-theme', isDark ? 'light' : 'dark');
      updateThemeIcon();
    }
    function updateThemeIcon() {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const show = (elId, v) => { const el = document.getElementById(elId); if (el) el.style.display = v; };
      show('themeIconSun', isDark ? 'block' : 'none');
      show('themeIconMoon', isDark ? 'none' : 'block');
      show('sidebarThemeIconSun', isDark ? 'block' : 'none');
      show('sidebarThemeIconMoon', isDark ? 'none' : 'block');
      const label = document.getElementById('sidebarThemeLabel');
      if (label) label.textContent = isDark ? 'Light mode' : 'Dark mode';
    }
    // Apply saved theme on load
    (function() {
      const saved = localStorage.getItem('solclear-theme');
      if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.setAttribute('data-theme', 'dark');
      }
      updateThemeIcon();
    })();

    // ── Nav/tab active state ──
    // Map step names to the tab/sidebar key they belong to (for active highlighting).
    const STEP_TO_NAV = {
      'home': 'home', 'reports': 'reports',
      1: 'check', 2: 'check', 3: 'check', 4: 'check',
      'orgs': 'orgs', 'orgCreate': 'orgs', 'orgDetail': 'orgs', 'userDetail': 'orgs',
      'reqs': 'reqs', 'reqDetail': 'reqs',
      'costs': 'costs',
      'devnotes': 'devnotes',
    };
    const NAV_TO_TAB = { home: 'home', check: 'check', reports: 'reports', orgs: 'account', reqs: 'account', costs: 'account', devnotes: 'account' };

    function setActiveTab(navKey) {
      document.querySelectorAll('.nav-item[data-nav]').forEach(el =>
        el.classList.toggle('active', el.dataset.nav === navKey));
      const tabKey = NAV_TO_TAB[navKey] || navKey;
      document.querySelectorAll('.tab-btn').forEach(el =>
        el.classList.toggle('active', el.dataset.tab === tabKey));
    }

    // navigate() is the sidebar/bottom-tab entry point. It routes to the
    // underlying showStep and keeps active-state in sync.
    function navigate(key) {
      closeAccountSheet();
      if (key === 'check') { showStep(1); setActiveTab('check'); return; }
      showStep(key);
      setActiveTab(STEP_TO_NAV[key] || key);
    }

    // ── Step navigation ──
    function showStep(n) {
      document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
      document.getElementById('homePage').style.display = 'none';
      setActiveTab(STEP_TO_NAV[n] || null);
      if (n === 'home') {
        document.getElementById('homePage').style.display = 'block';
        loadHomeReports();
        // Refresh "your check is still running / just completed" banners
        // every time the user lands on home — otherwise a user who
        // started a check then navigated away wouldn't see the banner
        // until the next page load. Cheap (~one DB query, no fan-out).
        fetchActiveChecks();
        return;
      }
      if (n === 'reports') {
        document.getElementById('reportsPage').classList.add('active');
        loadAllReports();
        return;
      }
      if (n === 'reqs') {
        document.getElementById('adminReqs').classList.add('active');
        loadRequirements();
        loadMonitorStatus();
        return;
      }
      if (n === 'reqDetail') {
        document.getElementById('adminReqDetail').classList.add('active');
        return;
      }
      if (n === 'orgs') {
        document.getElementById('adminOrgs').classList.add('active');
        loadOrgs();
        return;
      }
      if (n === 'orgCreate') {
        document.getElementById('adminOrgCreate').classList.add('active');
        return;
      }
      if (n === 'orgDetail') {
        document.getElementById('adminOrgDetail').classList.add('active');
        return;
      }
      if (n === 'userDetail') {
        document.getElementById('adminUserDetail').classList.add('active');
        return;
      }
      if (n === 'costs') {
        document.getElementById('adminCosts').classList.add('active');
        loadCosts();
        return;
      }
      if (n === 'devnotes') {
        document.getElementById('adminDevNotes').classList.add('active');
        loadDevNotes();
        return;
      }
      document.getElementById('step' + n).classList.add('active');
      if (n === 1 && !projectsLoaded) loadRecentProjects();
    }

    // ── Generic toggle helper ──
    function selectToggle(btn) {
      btn.parentElement.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
    }

    function toggleKeyVis(inputId) {
      const inp = document.getElementById(inputId);
      const btn = inp.nextElementSibling;
      if (inp.type === 'password') { inp.type = 'text'; btn.textContent = 'Hide'; }
      else { inp.type = 'password'; btn.textContent = 'Show'; }
    }

    function statusBadgeHtml(status) {
      const cls = {active:'badge-success', demo:'badge-info', inactive:'badge-neutral', onboarding:'badge-warning'}[status] || 'badge-neutral';
      return '<span class="badge ' + cls + '">' + status.toUpperCase() + '</span>';
    }

    function roleBadgeHtml(role) {
      // Role → semantic badge class. Superadmin uses purple (error) to stand out; the rest map to sensible tones.
      const cls = {superadmin:'badge-error', admin:'badge-info', reviewer:'badge-info', crew:'badge-success'}[role] || 'badge-neutral';
      return '<span class="badge ' + cls + '">' + role + '</span>';
    }

    // ── Organizations ──
    async function loadOrgs() {
      const list = document.getElementById('orgsList');
      list.innerHTML = skeletonCards(3);
      try {
        const r = await fetch('/api/organizations');
        const orgs = await r.json();
        if (!orgs.length) {
          // Only show the "Create" CTA to superadmins — org admins can't
          // spawn new orgs anyway.
          const isSuper = _me && _me.role === 'superadmin';
          list.innerHTML = isSuper
            ? emptyState('No organizations yet',
                         'Create your first organization to onboard a client.',
                         'Create Organization', 'showCreateOrg()')
            : emptyState('No organization found',
                         'Your account is not linked to an organization yet. Ask a superadmin to set it up.');
          return;
        }
        list.innerHTML = orgs.map(o => {
          const borderColor = {active:'var(--success)', demo:'var(--accent)', inactive:'var(--text-muted)', onboarding:'var(--warning)'}[o.status] || 'var(--border)';
          return `
          <div class="list-item" onclick="openOrg(${o.id})" style="border-left:3px solid ${borderColor};">
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="name">${esc(o.name)}</span>
              ${statusBadgeHtml(o.status)}
            </div>
            <div class="detail">${o.user_count} user${o.user_count!==1?'s':''} · ${o.report_count} report${o.report_count!==1?'s':''}</div>
          </div>`;
        }).join('');
      } catch (e) { list.innerHTML = errorAlert('Could not load organizations'); }
    }

    function showCreateOrg() {
      document.getElementById('newOrgName').value = '';
      showStep('orgCreate');
    }

    async function createOrg() {
      const name = document.getElementById('newOrgName').value.trim();
      if (!name) { alert('Name is required'); return; }
      const statusBtn = document.querySelector('[data-param="org-status"].selected');
      const status = statusBtn ? statusBtn.dataset.value : 'onboarding';
      try {
        const r = await fetch('/api/organizations', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name, status})
        });
        const org = await r.json();
        if (org.error) { alert(org.error); return; }
        openOrg(org.id);
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function openOrg(orgId) {
      currentOrgId = orgId;
      showStep('orgDetail');
      try {
        const r = await fetch('/api/organizations/' + orgId);
        const org = await r.json();
        document.getElementById('orgDetailLabel').textContent = org.name;
        document.getElementById('orgEditName').value = org.name || '';
        document.getElementById('orgCcKey').value = '';
        document.getElementById('orgCcKey').placeholder = org.companycam_api_key_set ? 'Key is set (enter new value to change)' : 'Not set';
        document.getElementById('orgAnthKey').value = '';
        document.getElementById('orgAnthKey').placeholder = org.anthropic_api_key_set ? 'Key is set (enter new value to change)' : 'Not set';
        // Status toggles
        document.querySelectorAll('[data-param="org-edit-status"]').forEach(b => {
          b.classList.toggle('selected', b.dataset.value === org.status);
        });
        // Make name/status read-only for reviewers (can see current value,
        // can't change it). Save button is already hidden via .admin-write.
        const canWrite = _me && (_me.role === 'superadmin' || _me.role === 'admin');
        document.getElementById('orgEditName').disabled = !canWrite;
        document.querySelectorAll('[data-param="org-edit-status"]').forEach(b => {
          b.disabled = !canWrite;
          b.style.cursor = canWrite ? 'pointer' : 'default';
        });
        // Render users — renderOrgUsers itself checks role for write actions
        renderOrgUsers(org.users || []);
      } catch (e) { alert('Error loading org: ' + e.message); }
    }

    function renderOrgUsers(users) {
      document.getElementById('orgUserCount').textContent = users.length + ' user' + (users.length !== 1 ? 's' : '');
      const list = document.getElementById('orgUsersList');
      if (!users.length) { list.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">No users yet.</div>'; return; }
      // Reviewers see names/emails/roles only. Write actions (edit on click,
      // activate/deactivate) are admin+superadmin. Impersonate is
      // superadmin-only, and only offered when NOT already impersonating.
      const canWrite = _me && (_me.role === 'superadmin' || _me.role === 'admin');
      const realRole = _me && (_me.real_role || _me.role);
      const canImpersonate = realRole === 'superadmin' && !(_me && _me.is_impersonating);
      const myActiveId = _me && _me.user_id;
      list.innerHTML = users.map(u => {
        const nameLine = `<div style="font-weight:500;font-size:13px;color:${canWrite ? 'var(--accent)' : 'var(--text)'};">${esc(u.full_name || (u.first_name + ' ' + u.last_name))}${u.is_active ? '' : ' <span class="badge badge-danger" style="margin-left:4px;">INACTIVE</span>'}</div>`;
        const emailLine = `<div style="font-size:11px;color:var(--text-muted)">${esc(u.email)}${u.phone ? ' · ' + esc(u.phone) : ''}</div>`;
        const nameBlock = canWrite
          ? `<div style="flex:1;cursor:pointer;" onclick="openUser(${u.id})">${nameLine}${emailLine}</div>`
          : `<div style="flex:1;">${nameLine}${emailLine}</div>`;
        const toggleBtn = canWrite
          ? `<button onclick="toggleUser(${u.id})" style="background:none;border:1px solid ${u.is_active ? 'var(--danger)' : 'var(--success)'};color:${u.is_active ? 'var(--danger)' : 'var(--success)'};border-radius:6px;padding:4px 10px;font-size:10px;font-weight:600;cursor:pointer;min-height:28px;">${u.is_active ? 'Deactivate' : 'Activate'}</button>`
          : '';
        // Only show Impersonate for active users who aren't the current user
        const impersonateBtn = (canImpersonate && u.is_active && u.id !== myActiveId)
          ? `<button onclick="startImpersonate(${u.id}, ${JSON.stringify(u.full_name || u.email || '').replace(/"/g, '&quot;')})" style="background:var(--bg-subtle);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 10px;font-size:10px;font-weight:600;cursor:pointer;min-height:28px;">Impersonate</button>`
          : '';
        return `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border-light);${u.is_active ? '' : 'opacity:0.5;'}">
            ${nameBlock}
            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
              ${roleBadgeHtml(u.role)}
              ${impersonateBtn}
              ${toggleBtn}
            </div>
          </div>`;
      }).join('');
    }

    async function saveOrg() {
      const statusBtn = document.querySelector('[data-param="org-edit-status"].selected');
      const data = {
        name: document.getElementById('orgEditName').value.trim(),
        status: statusBtn ? statusBtn.dataset.value : 'onboarding',
      };
      // Only send API keys if user entered a new value (don't clear existing keys)
      const ccKey = document.getElementById('orgCcKey').value.trim();
      const anthKey = document.getElementById('orgAnthKey').value.trim();
      if (ccKey) data.companycam_api_key = ccKey;
      if (anthKey) data.anthropic_api_key = anthKey;
      try {
        const r = await fetch('/api/organizations/' + currentOrgId, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const org = await r.json();
        if (org.error) { alert(org.error); return; }
        document.getElementById('orgDetailLabel').textContent = org.name;
        alert('Saved!');
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function addUser() {
      const first_name = document.getElementById('addUserFirst').value.trim();
      const last_name = document.getElementById('addUserLast').value.trim();
      const email = document.getElementById('addUserEmail').value.trim();
      const phone = document.getElementById('addUserPhone').value.trim() || null;
      const role = document.getElementById('addUserRole').value;
      if (!email || !first_name || !last_name) { alert('First name, last name, and email required'); return; }
      try {
        const r = await fetch('/api/organizations/' + currentOrgId + '/users', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({email, first_name, last_name, phone, role})
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        document.getElementById('addUserFirst').value = '';
        document.getElementById('addUserLast').value = '';
        document.getElementById('addUserEmail').value = '';
        document.getElementById('addUserPhone').value = '';
        const msg = result.invite_sent
          ? `${first_name} ${last_name} added. An invitation email has been sent to ${email}.`
          : `${first_name} ${last_name} added. (Invite email could not be sent — check Resend configuration.)`;
        alert(msg);
        openOrg(currentOrgId);  // refresh
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function openUser(userId) {
      currentUserId = userId;
      // Set back button to return to the current org
      document.getElementById('userDetailBack').onclick = () => openOrg(currentOrgId);
      showStep('userDetail');
      try {
        const r = await fetch('/api/users/' + userId);
        const u = await r.json();
        document.getElementById('userDetailLabel').textContent = u.full_name || (u.first_name + ' ' + u.last_name);
        document.getElementById('editUserFirst').value = u.first_name || '';
        document.getElementById('editUserLast').value = u.last_name || '';
        document.getElementById('editUserEmail').value = u.email || '';
        document.getElementById('editUserPhone').value = u.phone || '';
        document.querySelectorAll('[data-param="edit-user-role"]').forEach(b => {
          b.classList.toggle('selected', b.dataset.value === u.role);
        });
        // Status info
        const info = document.getElementById('userStatusInfo');
        let statusHtml = '<strong>Status:</strong> ' + (u.is_active ? '<span style="color:#10b981;">Active</span>' : '<span style="color:#ef4444;">Inactive</span>');
        if (u.deactivated_at) statusHtml += ' · Deactivated: ' + formatTimestamp(u.deactivated_at);
        if (u.created_at) statusHtml += ' · Created: ' + formatTimestamp(u.created_at);
        // Show invite status + resend button for users who haven't set a password
        if (!u.has_password) {
          statusHtml += '<div style="margin-top:10px;padding:10px 12px;background:var(--warning-subtle);border-radius:8px;border:1px solid var(--warning);display:flex;align-items:center;gap:12px;flex-wrap:wrap;">';
          statusHtml += '<span style="font-size:var(--text-xs);color:var(--warning-text);flex:1;">⏳ Awaiting invitation — this user hasn\'t set their password yet.</span>';
          statusHtml += `<button onclick="resendInvite(${u.id})" style="background:var(--warning);color:var(--text-inverse);border:none;border-radius:6px;padding:6px 12px;font-size:11px;font-weight:600;cursor:pointer;min-height:32px;white-space:nowrap;">Resend invite</button>`;
          statusHtml += '</div>';
        }
        info.innerHTML = statusHtml;
      } catch (e) { alert('Error loading user: ' + e.message); }
    }

    async function resendInvite(userId) {
      try {
        const r = await fetch('/api/users/' + userId + '/resend-invite', {method: 'POST'});
        const data = await r.json();
        if (data.ok) {
          alert(data.message);
          openUser(userId);  // refresh to reflect any state change
        } else {
          alert(data.error || 'Could not resend invite');
        }
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function saveUser() {
      const roleBtn = document.querySelector('[data-param="edit-user-role"].selected');
      const data = {
        first_name: document.getElementById('editUserFirst').value.trim(),
        last_name: document.getElementById('editUserLast').value.trim(),
        email: document.getElementById('editUserEmail').value.trim(),
        phone: document.getElementById('editUserPhone').value.trim() || null,
        role: roleBtn ? roleBtn.dataset.value : 'crew',
      };
      if (!data.first_name || !data.last_name || !data.email) { alert('First name, last name, and email are required'); return; }
      try {
        const r = await fetch('/api/users/' + currentUserId, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        document.getElementById('userDetailLabel').textContent = result.full_name || (result.first_name + ' ' + result.last_name);
        alert('User updated!');
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function toggleUser(userId) {
      try {
        const r = await fetch('/api/users/' + userId + '/toggle', {method: 'POST'});
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        openOrg(currentOrgId);  // refresh
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function uploadCsv() {
      const file = document.getElementById('csvUpload').files[0];
      if (!file) return;
      const text = await file.text();
      try {
        const r = await fetch('/api/organizations/' + currentOrgId + '/users/csv', {
          method: 'POST',
          headers: {'Content-Type': 'text/csv'},
          body: text
        });
        const result = await r.json();
        const div = document.getElementById('csvResult');
        let html = '<span style="color:#10b981;font-weight:600;">' + result.total + ' users created</span>';
        if (result.errors && result.errors.length) {
          html += '<br><span style="color:#ef4444;">' + result.errors.join('<br>') + '</span>';
        }
        div.innerHTML = html;
        document.getElementById('csvUpload').value = '';
        openOrg(currentOrgId);  // refresh
      } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Recent reports ──
    // ── Requirements ──
    let reqsData = [];

    async function loadRequirements() {
      const list = document.getElementById('reqsList');
      list.innerHTML = skeletonCards(5);
      try {
        const r = await fetch('/api/requirements');
        reqsData = await r.json();
        // Group by section
        const sections = {};
        reqsData.forEach(req => {
          (sections[req.section] = sections[req.section] || []).push(req);
        });
        let html = '';
        for (const [section, reqs] of Object.entries(sections)) {
          html += `<div style="margin-bottom:16px;">
            <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-muted);font-weight:600;padding:8px 0;border-bottom:2px solid var(--border);">${esc(section)}</div>`;
          reqs.forEach(req => {
            let changeBadge = '';
            let borderColor = req.optional ? 'var(--border)' : '#3b82f6';
            if (req.change_status === 'new') {
              changeBadge = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#ecfdf5;color:#065f46;">+ NEW</span>';
              borderColor = '#10b981';
            } else if (req.change_status === 'changed') {
              changeBadge = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fffbeb;color:#92400e;">UPDATED</span>';
              borderColor = '#f59e0b';
            } else if (req.change_status === 'removed') {
              changeBadge = '<span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;background:#fef2f2;color:#991b1b;">REMOVED</span>';
              borderColor = '#ef4444';
            }
            const stubNote = req.is_stub ? '<div style="font-size:11px;color:#f59e0b;margin-top:4px;font-weight:600;">Needs configuration before use in checks</div>' : '';
            html += `
              <div class="list-item" onclick="openRequirement('${req.id}')" style="margin-top:6px;border-left:3px solid ${borderColor};">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                  <span style="font-size:10px;font-weight:700;color:var(--text-muted);min-width:28px;">${req.id}</span>
                  <span style="font-size:13px;font-weight:500;color:var(--text);">${esc(req.title)}</span>
                  ${changeBadge}
                  ${req.optional ? '<span style="font-size:9px;background:var(--border-light);color:var(--text-muted);padding:1px 5px;border-radius:3px;font-weight:600;">OPTIONAL</span>' : ''}
                </div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">Tasks: ${req.task_titles.length ? req.task_titles.join(', ') : 'none mapped'}</div>
                ${stubNote}
              </div>`;
          });
          html += '</div>';
        }
        list.innerHTML = html;
      } catch (e) {
        list.innerHTML = errorAlert('Could not load requirements');
      }
    }

    async function loadMonitorStatus() {
      const el = document.getElementById('monitorStatus');
      try {
        const r = await fetch('/api/requirements/monitor/status');
        const data = await r.json();
        if (data.status === 'no_baseline') {
          el.innerHTML = 'No baseline saved yet. Click "Check Now" to create one.';
        } else {
          const date = formatTimestamp(data.saved_at);
          el.innerHTML = `Last checked: ${date} · Hash: ${data.hash}...`;
        }
      } catch (e) {
        el.innerHTML = 'Could not load monitor status';
      }
    }

    async function checkRequirementsNow() {
      const btn = document.getElementById('checkNowBtn');
      const el = document.getElementById('monitorStatus');
      const badge = document.getElementById('monitorBadge');
      btn.disabled = true;
      btn.textContent = 'Checking...';
      el.innerHTML = 'Fetching Palmetto requirements page...';
      document.getElementById('changeAlert').style.display = 'none';
      try {
        const r = await fetch('/api/requirements/check', {method: 'POST'});
        const data = await r.json();
        // Coverage gap alert (applies to all statuses)
        if (data.missing_ids && data.missing_ids.length) {
          const alert = document.getElementById('changeAlert');
          alert.style.display = 'flex';
          alert.classList.remove('alert-error');
          alert.classList.add('alert-warning');
          document.getElementById('changeSummary').innerHTML =
            '<div><strong>Coverage gap:</strong> ' + data.missing_ids.length + ' requirement(s) found on Palmetto\\'s page that are not configured in our system:</div>' +
            '<div style="margin-top:6px;">' + data.missing_ids.map(id =>
              '<span class="badge badge-danger" style="margin:2px 4px 2px 0;">' + esc(id) + '</span>'
            ).join('') + '</div>' +
            '<div style="margin-top:8px;font-size:var(--text-sm);">Click "Check Now" again after the page has changed to auto-create stubs, or add these manually in the requirements editor.</div>';
          document.getElementById('changeDiff').style.display = 'none';
        }

        if (data.status === 'baseline_created') {
          el.innerHTML = `<span style="color:var(--accent);font-weight:600;">Baseline created.</span> ${data.message} Hash: ${data.hash}...`;
          badge.style.display = 'inline-block';
          badge.innerHTML = '<span class="badge badge-info">BASELINE SET</span>';
        } else if (data.status === 'no_changes') {
          const hasMissing = data.missing_ids && data.missing_ids.length;
          el.innerHTML = `<span style="color:${hasMissing ? 'var(--warning)' : 'var(--success)'};font-weight:600;">${hasMissing ? 'Page unchanged, but coverage gaps found.' : 'No changes detected.'}</span> Hash: ${data.hash}...`;
          badge.style.display = 'inline-block';
          badge.innerHTML = hasMissing
            ? '<span class="badge badge-warning">GAPS FOUND</span>'
            : '<span class="badge badge-pass">UP TO DATE</span>';
        } else if (data.status === 'changes_detected') {
          const isMaterial = data.material !== false;
          if (isMaterial) {
            el.innerHTML = `<span style="color:var(--danger);font-weight:600;">Material changes detected</span> · ${data.added} added, ${data.removed} removed`;
            badge.style.display = 'inline-block';
            badge.innerHTML = '<span class="badge badge-fail">CHANGED</span>';
          } else {
            el.innerHTML = `<span style="color:var(--success);font-weight:600;">No material changes.</span> Minor metadata updates only.`;
            badge.style.display = 'inline-block';
            badge.innerHTML = '<span class="badge badge-pass">UP TO DATE</span>';
          }
          // Only show alert banner for material changes
          const alert = document.getElementById('changeAlert');
          alert.classList.remove('alert-warning');
          alert.classList.add('alert-error');
          if (!isMaterial) { alert.style.display = 'none'; } else { alert.style.display = 'flex'; }
          let rawSummary = data.summary || '';
          // Clean up any JSON/markdown artifacts from AI response
          rawSummary = rawSummary.replace(/^```(?:json)?/gm, '').replace(/```$/gm, '').trim();
          let summaryHtml = esc(rawSummary).replace(/\\n/g, '<br>');
          // Add structured badges
          const parts = [];
          if (data.new_ids && data.new_ids.length) {
            parts.push('<div style="margin-top:8px;"><span class="badge badge-success">NEW</span> ' +
              data.new_ids.map(n => '<strong>' + esc(n.id) + '</strong> — ' + esc(n.title)).join(', ') + '</div>');
          }
          if (data.changed_ids && data.changed_ids.length) {
            parts.push('<div style="margin-top:4px;"><span class="badge badge-warning">UPDATED</span> ' +
              data.changed_ids.map(c => '<strong>' + esc(c) + '</strong>').join(', ') + '</div>');
          }
          if (data.removed_ids && data.removed_ids.length) {
            parts.push('<div style="margin-top:4px;"><span class="badge badge-danger">REMOVED</span> ' +
              data.removed_ids.map(r => '<strong>' + esc(r) + '</strong>').join(', ') + '</div>');
          }
          document.getElementById('changeSummary').innerHTML = summaryHtml + parts.join('');
          document.getElementById('changeDiff').style.display = 'block';
          document.getElementById('changeDiffContent').textContent = data.diff_preview || '';
          document.getElementById('changeDiffContent').style.display = 'none';
          // Refresh requirements list to show badges
          loadRequirements();
        } else if (data.status === 'no_baseline') {
          el.innerHTML = data.message;
        } else if (data.error) {
          el.innerHTML = `<span style="color:#ef4444;">Error: ${esc(data.error)}</span>`;
        }
      } catch (e) {
        el.innerHTML = `<span style="color:#ef4444;">Error: ${e.message}</span>`;
      }
      btn.disabled = false;
      btn.textContent = 'Check Now';
    }

    function dismissAlert() {
      document.getElementById('changeAlert').style.display = 'none';
    }

    function toggleDiff() {
      const content = document.getElementById('changeDiffContent');
      const btn = document.getElementById('diffToggleBtn');
      if (content.style.display === 'none') {
        content.style.display = 'block';
        btn.innerHTML = 'Hide raw diff <span class="arrow">&#9652;</span>';
      } else {
        content.style.display = 'none';
        btn.innerHTML = 'Show raw diff <span class="arrow">&#9662;</span>';
      }
    }

    let currentReqId = null;

    function openRequirement(reqId) {
      currentReqId = reqId;
      const req = reqsData.find(r => r.id === reqId);
      if (!req) return;
      document.getElementById('reqDetailLabel').textContent = req.id + ' — ' + req.title;
      document.getElementById('reqEditId').textContent = req.id;
      document.getElementById('reqEditSection').textContent = req.section;
      document.getElementById('reqEditTitle').value = req.title;
      document.getElementById('reqEditPrompt').value = req.validation_prompt;
      document.getElementById('reqEditTaskTitles').value = req.task_titles.join(', ');
      document.getElementById('reqEditKeywords').value = req.keywords.join(', ');
      showStep('reqDetail');
    }

    async function saveRequirement() {
      const data = {
        title: document.getElementById('reqEditTitle').value.trim(),
        validation_prompt: document.getElementById('reqEditPrompt').value.trim(),
        task_titles: document.getElementById('reqEditTaskTitles').value.split(',').map(s => s.trim()).filter(Boolean),
        keywords: document.getElementById('reqEditKeywords').value.split(',').map(s => s.trim()).filter(Boolean),
      };
      try {
        const r = await fetch('/api/requirements/' + currentReqId, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(data)
        });
        const result = await r.json();
        if (result.error) { alert(result.error); return; }
        alert('Requirement updated (in memory).');
        showStep('reqs');
      } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Reports ──
    function renderReportList(reports) {
      return reports.map(rpt => {
        const nReview = rpt.needs_review || 0;
        const isCancelled = rpt.status === 'cancelled';
        const hasFailures = rpt.failed > 0 || (rpt.missing || 0) > 0;
        // Border rail: gray for cancelled (data is partial so the usual
        // red/green signal is misleading), red for failures/missing, cyan
        // if only items needing review, green if everything's clean.
        let railColor = 'var(--success)';
        if (isCancelled) railColor = 'var(--text-muted)';
        else if (hasFailures) railColor = 'var(--danger)';
        else if (nReview > 0) railColor = 'var(--review)';
        const reviewHint = nReview ? ` · ${nReview} to review` : '';
        // formatTimestamp accepts an epoch-seconds number directly,
        // converts to local tz, returns relative-or-absolute.
        const date = formatTimestamp(rpt.timestamp);
        const img = rpt.featured_image
          ? `<img class="project-card-img" src="${rpt.featured_image}" alt="" loading="lazy">`
          : `<div class="project-card-img"></div>`;
        // Badges: TEST (existing) + CANCELLED if the run was stopped early.
        // Cancelled badge uses warning styling so it stands out as "this
        // report is incomplete by design, not a failed run."
        const testBadge = rpt.is_test ? ' <span class="badge badge-info" style="margin-left:4px;">TEST</span>' : '';
        const cancelBadge = isCancelled ? ' <span class="badge badge-warning" style="margin-left:4px;">CANCELLED</span>' : '';
        const statusLine = isCancelled
          ? `Partial — ${rpt.passed}/${rpt.total} completed before cancel · ${date}`
          : `${rpt.passed}/${rpt.total} passed${reviewHint} · ${date}`;
        return `
          <a href="/report/${rpt.db_report_id || rpt.project_id}" class="project-card" style="text-decoration:none;color:inherit;border-left:4px solid ${railColor};">
            ${img}
            <div class="project-card-info">
              <div class="project-card-name">${esc(rpt.name)}${testBadge}${cancelBadge}</div>
              <div class="project-card-addr">${statusLine}</div>
            </div>
          </a>`;
      }).join('');
    }

    async function loadHomeReports() {
      const list = document.getElementById('homeRecentList');
      list.innerHTML = skeletonCards(2);
      try {
        const r = await fetch('/api/reports');
        const reports = await r.json();
        if (!reports.length) {
          list.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No reports yet. Run your first compliance check!</div>';
          return;
        }
        list.innerHTML = renderReportList(reports.slice(0, 3));
      } catch (e) {
        list.innerHTML = errorAlert('Could not load reports');
      }
    }

    let _allReports = [];

    async function loadAllReports() {
      const list = document.getElementById('recentList');
      list.innerHTML = skeletonCards(4);
      try {
        const r = await fetch('/api/reports');
        _allReports = await r.json();
        // Reset filters
        document.getElementById('reportSearch').value = '';
        document.getElementById('reportStatusFilter').value = 'all';
        document.getElementById('reportDateFrom').value = '';
        document.getElementById('reportDateTo').value = '';
        filterReports();
      } catch (e) {
        list.innerHTML = errorAlert('Could not load reports');
      }
    }

    function clearDateFilter() {
      document.getElementById('reportDateFrom').value = '';
      document.getElementById('reportDateTo').value = '';
      filterReports();
    }

    function filterReports() {
      const search = (document.getElementById('reportSearch').value || '').trim().toLowerCase();
      const status = document.getElementById('reportStatusFilter').value;
      const fromVal = document.getElementById('reportDateFrom').value;
      const toVal = document.getElementById('reportDateTo').value;
      const fromTs = fromVal ? new Date(fromVal + 'T00:00:00').getTime() / 1000 : 0;
      const toTs = toVal ? new Date(toVal + 'T23:59:59').getTime() / 1000 : Infinity;

      const filtered = _allReports.filter(rpt => {
        // Search filter
        if (search && !(rpt.name || '').toLowerCase().includes(search)) return false;
        // Status filter — "passed" means fully clean (no fails and no review items);
        // "failed" means any hard failures; "needs_review" surfaces reports where
        // a human still needs to weigh in on at least one item.
        const nReview = rpt.needs_review || 0;
        if (status === 'passed' && (rpt.failed > 0 || nReview > 0)) return false;
        if (status === 'failed' && rpt.failed === 0) return false;
        if (status === 'needs_review' && nReview === 0) return false;
        // Date range filter
        if (rpt.timestamp < fromTs || rpt.timestamp > toTs) return false;
        return true;
      });

      const list = document.getElementById('recentList');
      const countEl = document.getElementById('reportCount');

      if (!_allReports.length) {
        list.innerHTML = emptyState(
          'No reports yet',
          'Run your first compliance check to see it here.',
          'Start a new check',
          "navigate('check')"
        );
        countEl.textContent = '';
        return;
      }

      if (!filtered.length) {
        list.innerHTML = emptyState(
          'No matches',
          'No reports match your current filters. Try clearing the search or date range.'
        );
        countEl.textContent = '0 of ' + _allReports.length + ' reports';
        return;
      }

      countEl.textContent = filtered.length === _allReports.length
        ? filtered.length + ' report' + (filtered.length !== 1 ? 's' : '')
        : filtered.length + ' of ' + _allReports.length + ' reports';
      list.innerHTML = renderReportList(filtered);
    }

    // Check for rerun parameter, otherwise load home page
    (function checkRerun() {
      const url = new URL(window.location.href);
      const rerunQs = url.searchParams.get('rerun');
      if (rerunQs) {
        // Auto-start a rerun of failed items
        const params = new URLSearchParams(rerunQs);
        showStep(4);
        document.getElementById('resultsList').innerHTML = '';
        document.getElementById('doneBanner').style.display = 'none';
        document.getElementById('loaderAnim').classList.remove('hidden');
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = 'Re-checking failed items...';
        document.getElementById('statusMsg').style.display = 'none';

        fetch('/start?' + params).then(r => r.json()).then(data => {
          if (!data.ok) { alert(data.error); showStep('home'); return; }
          document.getElementById('progressText').textContent = `Checking 0 / ${data.total}...`;
          const cw = document.getElementById('cancelRunWrap');
          const cb = document.getElementById('cancelRunBtn');
          if (cw) cw.style.display = 'block';
          if (cb) { cb.disabled = false; cb.textContent = 'Cancel checks'; }
          _currentRunId = data.run_id || null;
          listenSSE(data.run_id, data.total);
        }).catch(e => { alert('Failed: ' + e.message); showStep('home'); });

        // Clean up URL
        window.history.replaceState({}, '', '/');
        return;
      }
      loadHomeReports();
    })();

    // ── Step 1: Project search ──
    const searchInput = document.getElementById('projectSearch');
    let projectsLoaded = false;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => searchProjects(searchInput.value), 300);
    });

    function renderProjectCard(p) {
      const img = p.featured_image
        ? `<img class="project-card-img" src="${p.featured_image}" alt="" loading="lazy">`
        : `<div class="project-card-img" id="thumb-${p.id}"></div>`;
      const addr = [p.address, p.city, p.state].filter(Boolean).join(', ');

      // Per-checklist breakdown. `p.checklists` is populated by the async
      // enrichment in loadRecentProjects; on initial render (stage 1) it
      // is undefined. We show a shimmering "Loading checklist progress"
      // placeholder during stage 1 so the card doesn't look finished
      // before suddenly growing a new row once stage 2 completes.
      //
      // If p.checklists_error is set (enrichment failed), we fall through
      // silently — no placeholder, no noise. If both are set to valid
      // values we render the real data below.
      let checklistsHtml = '';
      if (Array.isArray(p.checklists) && p.checklists.length) {
        checklistsHtml = '<div class="project-checklists">' + p.checklists.map(c => {
          const total = c.total_tasks || 0;
          const done = c.completed_tasks || 0;
          const pct = total ? Math.round((done / total) * 100) : 0;
          const barCls = (total && done === total) ? 'progress-thin-fill complete' : 'progress-thin-fill';
          const count = total ? `${done}/${total}` : (c.completed_at ? 'Done' : '–');
          const bar = total
            ? `<div class="progress-thin"><div class="${barCls}" style="width:${pct}%"></div></div>`
            : '';
          return `
            <div class="project-checklist-row">
              <div class="project-checklist-meta">
                <span class="project-checklist-name">${esc(c.name)}</span>
                <span class="project-checklist-count">${count}</span>
              </div>
              ${bar}
            </div>`;
        }).join('') + '</div>';
      } else if (p.checklist_count !== undefined) {
        checklistsHtml = `<div class="project-card-meta"><span class="project-card-dot"></span>${p.checklist_count} checklist${p.checklist_count !== 1 ? 's' : ''}</div>`;
      } else if (!p.checklists_error) {
        // Stage 1: enrichment hasn't returned yet for this project.
        checklistsHtml = '<div class="project-checklists-loading"></div>';
      }

      return `
        <div class="project-card" onclick="selectProject('${p.id}', '${esc(p.name)}', '${esc(p.state)}')">
          ${img}
          <div class="project-card-info">
            <div class="project-card-name">${esc(p.name)}</div>
            <div class="project-card-addr">${esc(addr)}</div>
            ${checklistsHtml}
          </div>
        </div>`;
    }

    function loadThumbnails(projects) {
      // Lazy-load thumbnails for projects without a featured_image
      projects.forEach(p => {
        if (p.featured_image) return;
        const el = document.getElementById('thumb-' + p.id);
        if (!el) return;
        fetch('/api/projects/' + p.id + '/thumbnail')
          .then(r => r.json())
          .then(data => {
            if (data.url) {
              const img = document.createElement('img');
              img.className = 'project-card-img';
              img.src = data.url;
              img.loading = 'lazy';
              el.replaceWith(img);
            }
          })
          .catch(() => {});
      });
    }

    let _allProjects = [];

    async function loadRecentProjects() {
      // Load recent projects and async-check for checklists
      const list = document.getElementById('projectList');
      const loading = document.getElementById('projectListLoading');
      loading.innerHTML = skeletonCards(4);
      loading.style.display = 'block';
      list.innerHTML = '';
      // Reset filters
      document.getElementById('projectDateFrom').value = '';
      document.getElementById('projectDateTo').value = '';
      document.getElementById('projectDateField').value = 'updated_at';
      try {
        const r = await fetch('/api/projects');
        const projects = await r.json();
        if (!projects.length) {
          loading.innerHTML = emptyState(
            'No projects found',
            "Check your CompanyCam API key in Organizations, or try a different search."
          );
          return;
        }
        loading.style.display = 'none';

        // Show all projects immediately, then async-enrich with checklist counts
        list.innerHTML = projects.map(p => renderProjectCard(p)).join('');
        loadThumbnails(projects);

        // Async enrich each project with its full checklist array (names +
        // task completion counts). CompanyCam rate limit is 240 req/min —
        // we're well within it for a page of 25 projects.
        const enriched = await Promise.all(projects.map(async p => {
          try {
            const cr = await fetch('/api/projects/' + p.id + '/checklists');
            p.checklists = await cr.json();
            p.checklist_count = Array.isArray(p.checklists) ? p.checklists.length : 0;
          } catch (e) {
            p.checklists = [];
            p.checklist_count = 0;
            // Flag so renderProjectCard stops showing the shimmer on this
            // card (we failed; no point pretending data is still coming).
            p.checklists_error = true;
          }
          return p;
        }));

        // Re-render sorted: projects with checklists first
        _allProjects = enriched.sort((a, b) => b.checklist_count - a.checklist_count);
        filterProjects();
        projectsLoaded = true;
      } catch (e) {
        loading.innerHTML = errorAlert('Could not load projects from CompanyCam');
      }
    }

    function clearProjectDateFilter() {
      document.getElementById('projectDateFrom').value = '';
      document.getElementById('projectDateTo').value = '';
      filterProjects();
    }

    function filterProjects() {
      const field = document.getElementById('projectDateField').value;
      const fromVal = document.getElementById('projectDateFrom').value;
      const toVal = document.getElementById('projectDateTo').value;
      const fromTs = fromVal ? new Date(fromVal + 'T00:00:00').getTime() / 1000 : 0;
      const toTs = toVal ? new Date(toVal + 'T23:59:59').getTime() / 1000 : Infinity;

      const filtered = _allProjects.filter(p => {
        const ts = p[field] || 0;
        return ts >= fromTs && ts <= toTs;
      });

      const list = document.getElementById('projectList');
      const countEl = document.getElementById('projectCount');

      if (!filtered.length && _allProjects.length) {
        list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">No projects match your date filter.</div>';
        countEl.textContent = '0 of ' + _allProjects.length + ' projects';
        return;
      }

      countEl.textContent = (fromVal || toVal)
        ? filtered.length + ' of ' + _allProjects.length + ' projects'
        : '';
      list.innerHTML = filtered.map(p => renderProjectCard(p)).join('');
      loadThumbnails(filtered);
    }

    async function searchProjects(query) {
      const list = document.getElementById('projectList');
      const loading = document.getElementById('projectListLoading');
      if (!query && projectsLoaded) return;  // don't re-fetch if clearing search
      loading.innerHTML = skeletonCards(3);
      loading.style.display = 'block';
      list.innerHTML = '';
      try {
        const r = await fetch('/api/projects?query=' + encodeURIComponent(query));
        const projects = await r.json();
        loading.style.display = 'none';
        if (!projects.length) {
          loading.style.display = 'block';
          loading.innerHTML = emptyState('No matches', 'Try a different search term.');
          return;
        }
        list.innerHTML = projects.map(p => renderProjectCard(p)).join('');
        loadThumbnails(projects);
      } catch (e) { loading.innerHTML = errorAlert('Could not load projects'); }
    }

    function selectProject(id, name, state) {
      selectedProjectId = id;
      selectedProjectName = name;
      selectedProjectState = state || '';
      document.getElementById('selectedProject').textContent = name;
      showStep(2);
      loadChecklists(id);
    }

    // ── Step 2: Checklists ──
    async function loadChecklists(projectId) {
      const list = document.getElementById('checklistList');
      list.innerHTML = spinnerHtml('Loading checklists...');
      try {
        const r = await fetch('/api/projects/' + projectId + '/checklists');
        const cls = await r.json();
        if (!cls.length) { list.innerHTML = emptyState('No checklists', "This project has no CompanyCam checklists. Add one in CompanyCam, then come back."); return; }
        list.innerHTML = cls.map(c => renderChecklistRow(c)).join('');
      } catch (e) { list.innerHTML = errorAlert('Could not load checklists'); }
    }

    function renderChecklistRow(c) {
      const total = c.total_tasks || 0;
      const done = c.completed_tasks || 0;
      const pct = total ? Math.round((done / total) * 100) : 0;
      const barCls = (total && done === total) ? 'progress-thin-fill complete' : 'progress-thin-fill';
      const doneTag = c.completed_at ? ' · <span style="color:var(--success-text);font-weight:600;">Marked complete</span>' : '';
      const detail = total
        ? `${done}/${total} tasks complete${doneTag}`
        : (c.completed_at ? 'Completed' : 'No tasks');
      const bar = total
        ? `<div class="progress-thin"><div class="${barCls}" style="width:${pct}%"></div></div>`
        : '';
      return `
        <div class="list-item" onclick="selectChecklist('${c.id}', '${esc(c.name)}')">
          <div class="name">${esc(c.name)}</div>
          <div class="detail">${detail}</div>
          ${bar}
        </div>`;
    }

    function selectChecklist(id, name) {
      selectedChecklistId = id;
      selectedChecklistName = name;
      document.getElementById('selectedProjectName2').textContent = selectedProjectName;
      document.getElementById('selectedChecklistName').textContent = name;
      document.getElementById('derivedInfo').style.display = 'block';
      selectedManufacturer = null;
      document.querySelectorAll('#step3 .toggle-btn').forEach(b => b.classList.remove('selected'));
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = 'Select a manufacturer to continue';
      showStep(3);
    }

    // ── Step 3: Manufacturer selection ──
    function selectMfg(btn) {
      btn.parentElement.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedManufacturer = btn.dataset.value;
      const runBtn = document.getElementById('runBtn');
      runBtn.disabled = false;
      runBtn.textContent = 'Run Compliance Check';
    }

    // ── Step 4: Run check ──
    async function startCheck() {
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = 'Starting...';

      const qs = new URLSearchParams({
        project_id: selectedProjectId,
        checklist_id: selectedChecklistId,
        manufacturer: selectedManufacturer,
        project_state: selectedProjectState,
      });

      try {
        const r = await fetch('/start?' + qs);
        const data = await r.json();
        if (!data.ok) { alert(data.error); btn.disabled = false; btn.textContent = 'Run Compliance Check'; return; }

        showStep(4);
        document.getElementById('resultsList').innerHTML = '';
        document.getElementById('doneBanner').style.display = 'none';
        document.getElementById('loaderAnim').classList.remove('hidden');
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('progressText').textContent = `Checking 0 / ${data.total}...`;
        document.getElementById('statusMsg').style.display = 'none';
        // Reveal the Cancel button now that a run is in progress.
        const cancelWrap = document.getElementById('cancelRunWrap');
        const cancelBtn = document.getElementById('cancelRunBtn');
        if (cancelWrap) cancelWrap.style.display = 'block';
        if (cancelBtn) { cancelBtn.disabled = false; cancelBtn.textContent = 'Cancel checks'; }

        // Store run_id for the cancel button and future reconnect logic.
        _currentRunId = data.run_id || null;
        listenSSE(data.run_id, data.total);
      } catch (e) {
        alert('Failed to start: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Run Compliance Check';
      }
    }

    // Tracks the currently-in-progress run so cancelRun() knows which
    // run to cancel. Reset to null when a run completes/cancels.
    let _currentRunId = null;

    async function cancelRun() {
      const btn = document.getElementById('cancelRunBtn');
      if (!btn) return;
      if (!confirm('Cancel the remaining compliance checks?\\nThe requirement that is currently running will still finish (about 5-15 seconds).')) return;
      btn.disabled = true;
      btn.textContent = 'Cancelling…';
      try {
        const r = await fetch('/api/cancel', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({run_id: _currentRunId}),
        });
        const data = await r.json();
        if (!data.ok) {
          alert(data.error || 'Could not cancel');
          btn.disabled = false;
          btn.textContent = 'Cancel checks';
        }
        // Otherwise: wait for the SSE 'cancelled' event to finish teardown.
      } catch (e) {
        alert('Cancel request failed: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Cancel checks';
      }
    }

    function listenSSE(runId, total) {
      const es = new EventSource('/stream?run=' + (runId || ''));
      let count = 0;

      es.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.type === 'status') {
          const msg = document.getElementById('statusMsg');
          msg.textContent = data.message;
          msg.style.display = 'block';
          return;
        }

        if (data.type === 'progress') {
          count = data.index;
          const pct = Math.round((count / data.total) * 100);
          document.getElementById('progressFill').style.width = pct + '%';
          document.getElementById('progressText').textContent = `Checking ${count} / ${data.total}...`;
          document.getElementById('statusMsg').style.display = 'none';
          document.getElementById('resultsToggle').style.display = 'block';
          appendResult(data.requirement);
          return;
        }

        if (data.type === 'done' || data.type === 'cancelled') {
          es.close();
          _currentRunId = null;  // run is over — clear so stale cancel doesn't fire
          document.getElementById('loaderAnim').classList.add('hidden');
          const s = data.summary;
          const wasCancelled = data.type === 'cancelled';
          const cancelWrap = document.getElementById('cancelRunWrap');
          if (cancelWrap) cancelWrap.style.display = 'none';

          document.getElementById('progressFill').style.width = wasCancelled
            ? Math.round(((s.passed + s.failed + s.missing + (s.needs_review||0)) / (s.total || 1)) * 100) + '%'
            : '100%';
          document.getElementById('progressText').textContent = wasCancelled
            ? `Cancelled — ${s.passed}/${s.total} completed before stopping`
            : `Complete — ${s.passed}/${s.total} passed`;

          const banner = document.getElementById('doneBanner');
          const nReview = s.needs_review || 0;
          // "Ready for submission" only when nothing needs a human — failures,
          // missing photos, and review items all block the ready state.
          // A cancelled run is never "ready" — partial results by definition.
          const isPass = !wasCancelled && s.failed === 0 && s.missing === 0 && nReview === 0;
          banner.className = 'done-banner ' + (isPass ? 'done-pass' : 'done-fail');
          let ccLink = '';
          if (s.checklist_ids && s.checklist_ids.length) {
            ccLink = `<a class="cc-link" href="https://app.companycam.com/projects/${s.project_id}/todos/${s.checklist_ids[0]}" target="_blank">Open in CompanyCam</a>`;
          }
          // color:#fff overrides .cc-link's var(--text-inverse), which is dark
          // in dark mode and would otherwise be invisible against #111827.
          const reportLink = `<a class="cc-link" href="/report/${s.db_report_id || s.project_id}" style="background:#111827;color:#fff;">View Partial Report</a>`;
          const reviewStat = nReview ? ` · ${nReview} to review` : '';
          const label = wasCancelled
            ? 'CANCELLED — PARTIAL RESULTS'
            : (isPass ? 'READY FOR SUBMISSION' : 'ACTION REQUIRED');
          banner.innerHTML = `
            <div>
              <div class="done-label">${label}</div>
              <div class="done-stats">${s.passed} passed · ${s.failed} failed · ${s.missing} missing${reviewStat} · ${s.total} required</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
                ${reportLink}
                ${ccLink}
              </div>
            </div>
          `;
          banner.style.display = 'flex';

          document.getElementById('runBtn').disabled = false;
          document.getElementById('runBtn').textContent = 'Run Compliance Check';
          return;
        }

        if (data.type === 'error') {
          es.close();
          document.getElementById('loaderAnim').classList.add('hidden');
          document.getElementById('progressText').textContent = 'Error: ' + data.message;
          const cancelWrap = document.getElementById('cancelRunWrap');
          if (cancelWrap) cancelWrap.style.display = 'none';
          document.getElementById('runBtn').disabled = false;
          document.getElementById('runBtn').textContent = 'Run Compliance Check';
        }
      };

      es.onerror = () => {
        // EventSource auto-reconnects on most errors
      };
    }

    function appendResult(req) {
      const list = document.getElementById('resultsList');
      const status = req.status.toLowerCase();
      const badgeCls = 'badge-' + status;
      // Pretty label for the badge (e.g. NEEDS_REVIEW → "NEEDS REVIEW")
      const statusLabel = (req.status === 'NEEDS_REVIEW') ? 'NEEDS REVIEW' : req.status;
      let reason = '';
      if (status !== 'pass' && req.reason) {
        let full = esc(req.reason);
        // Replace "Photo(s) N", "Photos N and M", "Photos N, M, and O" with clickable links
        const urls = req.photo_urls || {};
        function linkPhoto(num) {
          const url = urls[num];
          return url ? `<a href="${url}" target="_blank" style="color:var(--accent);font-weight:500;">${num}</a>` : num;
        }
        full = full.replace(/Photos?\\s+(\\d+(?:\\s*(?:,\\s*(?:and\\s+)?|and\\s+|&amp;\\s*)\\d+)*)/gi, (match) => {
          return match.replace(/(\\d+)/g, (m, num) => linkPhoto(num));
        });
        const plainShort = esc(req.reason);
        const short = plainShort.length > 120 ? plainShort.substring(0, 120).replace(/\\s+\\S*$/, '') + '...' : null;
        if (short) {
          // Short version also gets links
          let shortLinked = esc(req.reason).substring(0, 120).replace(/\\s+\\S*$/, '') + '...';
          shortLinked = shortLinked.replace(/Photos?\\s+(\\d+(?:\\s*(?:,|and|&amp;)\\s*\\d+)*)/gi, (match) => {
            return match.replace(/(\\d+)/g, (m, num) => linkPhoto(num));
          });
          reason = `
            <div class="result-reason result-reason-short">${shortLinked}</div>
            <div class="result-reason result-reason-full" style="display:none">${full}</div>
            <button class="expand-btn" onclick="toggleResultReason(this)">Show more <span class="arrow">&#9662;</span></button>`;
        } else {
          reason = `<div class="result-reason">${full}</div>`;
        }
      }

      // Show the photo that was evaluated (key 1 in photo_urls is the selected winner)
      const evalUrl = (req.photo_urls || {})[1] || (req.photo_urls || {})['1'];
      const photoThumb = evalUrl
        ? `<a href="${evalUrl}" target="_blank" onclick="event.stopPropagation()" style="display:block;margin-top:8px;"><img src="${evalUrl}" style="width:100%;max-width:280px;border-radius:6px;border:2px solid var(--border);" loading="lazy"></a>`
        : '';

      list.insertAdjacentHTML('beforeend', `
        <div class="result-row ${status}" data-req-id="${req.id}" style="cursor:pointer;" onclick="this.classList.toggle('collapsed')">
          <div class="result-header">
            <span class="badge ${badgeCls}">${statusLabel}</span>
            <span class="result-id">${req.id}</span>
            <span class="result-title">${esc(req.title)}</span>
            <span class="collapse-arrow" style="margin-left:auto;color:var(--text-muted);font-size:10px;">&#9662;</span>
          </div>
          <div class="result-detail">
            ${photoThumb}
            ${reason}
          </div>
        </div>
      `);

      // Re-sort all cards into canonical requirement order each time one
      // arrives. With max_workers=2 checks complete out of order, so
      // without this the live view looks jumbled (R4 before R2, etc.).
      _sortResultsList(list);
    }

    // Canonical section order + numeric position within section.
    // Matches the REQUIREMENTS array order in compliance_check.py.
    const _SECTION_ORDER = {PS:0, R:1, E:2, S:3, SC:4, SI:5};
    function _reqSortKey(code) {
      const m = code && code.match(/^([A-Za-z]+)(\\d+)$/);
      if (!m) return 9999;
      const section = _SECTION_ORDER[m[1].toUpperCase()] ?? 9;
      return section * 100 + parseInt(m[2], 10);
    }
    function _sortResultsList(list) {
      const rows = Array.from(list.querySelectorAll('.result-row[data-req-id]'));
      rows.sort((a, b) => _reqSortKey(a.dataset.reqId) - _reqSortKey(b.dataset.reqId));
      rows.forEach(r => list.appendChild(r));  // DOM reorder (stable, no flicker)
    }

    let _allCollapsed = false;
    function toggleAllResults() {
      _allCollapsed = !_allCollapsed;
      document.querySelectorAll('#resultsList .result-row').forEach(row => {
        if (_allCollapsed) row.classList.add('collapsed');
        else row.classList.remove('collapsed');
      });
      document.getElementById('toggleAllBtn').textContent = _allCollapsed ? 'Expand All' : 'Collapse All';
    }

    function toggleResultReason(btn) {
      event.stopPropagation();
      const full = btn.previousElementSibling;
      const short = full.previousElementSibling;
      if (full.style.display === 'none') {
        full.style.display = 'block';
        short.style.display = 'none';
        btn.innerHTML = 'Show less <span class="arrow">&#9652;</span>';
      } else {
        full.style.display = 'none';
        short.style.display = 'block';
        btn.innerHTML = 'Show more <span class="arrow">&#9662;</span>';
      }
    }

    let _spinId = 0;
    function spinnerHtml(msg) {
      const id = 'sp' + (++_spinId);
      return '<div class="spinner">' +
        '<svg viewBox="0 0 120 120" width="40" height="40">' +
        '<path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="var(--border)" stroke-width="8" stroke-linecap="round"/>' +
        '<circle cx="0" cy="0" r="7" fill="#F59E0B"><animateMotion dur="1.4s" repeatCount="indefinite" keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.45 0 0.55 1"><mpath href="#' + id + '"/></animateMotion></circle>' +
        '<path id="' + id + '" d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="none"/>' +
        '</svg>' +
        (msg ? '<div class="spinner-text">' + esc(msg) + '</div>' : '') +
        '</div>';
    }

    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

    // ── UI helpers: empty state, error alert, skeletons ──
    function emptyState(title, desc, ctaLabel, ctaOnClick) {
      const cta = (ctaLabel && ctaOnClick)
        ? '<button class="btn btn-primary" onclick="' + ctaOnClick + '">' + esc(ctaLabel) + '</button>'
        : '';
      const descHtml = desc ? '<div class="empty-state-desc">' + esc(desc) + '</div>' : '';
      return '<div class="empty-state">' +
        '<div class="empty-state-icon"><svg viewBox="0 0 120 120"><circle cx="60" cy="54" r="14" fill="#F59E0B"/><path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round"/></svg></div>' +
        '<div class="empty-state-title">' + esc(title) + '</div>' +
        descHtml + cta + '</div>';
    }
    function errorAlert(msg) {
      return '<div class="alert alert-error">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' +
        '<div>' + esc(msg) + '</div></div>';
    }
    function skeletonCards(n) {
      let s = '';
      for (let i = 0; i < (n || 3); i++) {
        s += '<div class="skeleton-card">' +
          '<div class="skeleton skeleton-thumb"></div>' +
          '<div class="skeleton-lines">' +
            '<div class="skeleton skeleton-line skeleton-line-lg"></div>' +
            '<div class="skeleton skeleton-line skeleton-line-md"></div>' +
            '<div class="skeleton skeleton-line skeleton-line-sm"></div>' +
          '</div></div>';
      }
      return s;
    }

    // ── Current user (role-aware nav) ──
    // Role-visibility classes. Elements carrying any of these start with
    // inline style="display:none" in the markup (so nothing flashes before
    // the role fetch returns). loadMe() reveals the ones this user is
    // allowed to see.
    //   .reviewer-plus  — shown to superadmin / admin / reviewer (hidden for crew)
    //   .admin-write    — shown to superadmin / admin  (hidden for reviewer + crew)
    //   .superadmin-only — shown to superadmin only
    let _me = null;
    function _applyRoleVisibility(role) {
      const visible = [];
      if (role === 'superadmin') visible.push('.superadmin-only', '.admin-write', '.reviewer-plus');
      else if (role === 'admin') visible.push('.admin-write', '.reviewer-plus');
      else if (role === 'reviewer') visible.push('.reviewer-plus');
      // crew: no gated classes revealed
      visible.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => { el.style.display = ''; });
      });
      // Section header text reflects the user's actual role instead of
      // the static "Admin" — a Superadmin doesn't have to wonder why
      // their tools are under an "Admin" heading.
      const labelText = {
        superadmin: 'Superadmin',
        admin: 'Admin',
        reviewer: 'Reviewer',
      }[role] || '';
      ['sidebarRoleLabel', 'accountSheetRoleLabel'].forEach(id => {
        const el = document.getElementById(id);
        if (el && labelText) el.textContent = labelText;
      });
    }
    async function loadMe() {
      try {
        const r = await fetch('/api/me');
        if (!r.ok) return;
        _me = await r.json();
        _applyRoleVisibility(_me && _me.role);
        _applyImpersonationBanner(_me);
        _applyPlatformStatus(_me && _me.platform_status);
      } catch (e) { /* silently ignore — non-critical */ }
    }
    loadMe();
    fetchActiveChecks();  // populate running / recently-completed banners
    refreshBellBadge();   // initial unread count for the top-bar bell

    // ── Top-bar bell (notifications) ──
    // Polls /api/notifications/unread_count every 60s for the badge.
    // The full list is only fetched when the user opens the dropdown
    // (toggleBellPanel) — saves a chunk of bandwidth on idle pages.
    async function refreshBellBadge() {
      try {
        const r = await fetch('/api/notifications/unread_count');
        if (!r.ok) return;
        const data = await r.json();
        _setBellBadge(data.unread_count || 0);
      } catch (e) { /* silently ignore */ }
    }
    setInterval(refreshBellBadge, 60000);

    function _setBellBadge(n) {
      // Two bell entry points (mobile top bar + desktop sidebar nav) so
      // sync both badges. Either may be hidden by the responsive layout
      // — that's fine, we update text either way.
      const text = n > 99 ? '99+' : String(n || 0);
      ['bellBadge', 'sidebarBellBadge'].forEach(id => {
        const badge = document.getElementById(id);
        if (!badge) return;
        if (!n || n <= 0) {
          badge.style.display = 'none';
        } else {
          badge.textContent = text;
          badge.style.display = 'inline-flex';
        }
      });
    }

    async function toggleBellPanel(ev) {
      ev && ev.stopPropagation();
      const panel = document.getElementById('bellPanel');
      if (!panel) return;
      const opening = panel.style.display !== 'flex';
      panel.style.display = opening ? 'flex' : 'none';
      panel.style.flexDirection = 'column';
      if (opening) {
        // Position the panel near whichever button was clicked. On
        // desktop that's the sidebar nav button; on mobile it's the
        // top-bar bell. Falls back to fixed top-right if we can't find
        // a click target (e.g. programmatic open).
        _positionBellPanel(panel, ev && ev.currentTarget);
        await refreshBellPanel();
        // Click-outside to close — installed only while open. Also
        // ignores clicks on either bell button so toggling works.
        setTimeout(() => {
          const handler = (e) => {
            const sidebarBtn = document.getElementById('sidebarBellBtn');
            const topbarBtn = document.getElementById('bellBtn');
            const onBell = (sidebarBtn && sidebarBtn.contains(e.target)) ||
                           (topbarBtn && topbarBtn.contains(e.target));
            if (!panel.contains(e.target) && !onBell) {
              panel.style.display = 'none';
              document.removeEventListener('click', handler);
            }
          };
          document.addEventListener('click', handler);
        }, 0);
      }
    }

    function _positionBellPanel(panel, btn) {
      // Reset any prior positioning
      panel.style.position = 'fixed';
      panel.style.top = '54px';
      panel.style.right = '8px';
      panel.style.left = 'auto';
      if (!btn) return;
      const rect = btn.getBoundingClientRect();
      // If the button is in the desktop sidebar (left side of viewport),
      // open the panel to the right of it. Otherwise (mobile top bar),
      // anchor to top-right under the bell.
      if (rect.right < window.innerWidth / 2) {
        panel.style.left = (rect.right + 8) + 'px';
        panel.style.right = 'auto';
        panel.style.top = Math.max(8, rect.top) + 'px';
      } else {
        panel.style.top = (rect.bottom + 6) + 'px';
        panel.style.right = Math.max(8, window.innerWidth - rect.right) + 'px';
        panel.style.left = 'auto';
      }
    }

    async function refreshBellPanel() {
      const list = document.getElementById('bellList');
      if (!list) return;
      try {
        const r = await fetch('/api/notifications');
        if (!r.ok) throw new Error('Could not load notifications');
        const data = await r.json();
        _setBellBadge(data.unread_count || 0);
        const rows = data.notifications || [];
        if (!rows.length) {
          list.innerHTML = '<div style="padding:24px 16px;text-align:center;color:var(--text-muted);font-size:var(--text-sm);">No notifications yet.</div>';
          return;
        }
        list.innerHTML = rows.map(_renderBellRow).join('');
        // Localize the timestamps we just injected
        if (typeof localizeTimestamps === 'function') localizeTimestamps(list);
      } catch (e) {
        list.innerHTML = '<div style="padding:24px 16px;text-align:center;color:var(--danger);font-size:var(--text-sm);">' + esc(e.message) + '</div>';
      }
    }

    function _renderBellRow(n) {
      const isUnread = !n.read_at;
      const cls = 'bell-row' + (isUnread ? ' bell-unread' : '');
      const href = n.link_url || '#';
      // Note: \\n here so Python's triple-quoted string outputs a literal
      // \\n into the JS regex. Bare \\n would be turned into an actual
      // newline in the source, splitting the regex across two lines and
      // breaking the parser ("Invalid regular expression: missing /").
      const body = n.body ? '<div class="bell-row-body">' + esc(n.body).replace(/\\n/g, '<br>') + '</div>' : '';
      const iso = n.created_at || '';
      const time = iso
        ? '<time class="ts-relative bell-row-time" datetime="' + esc(iso) + '"></time>'
        : '';
      return (
        '<a class="' + cls + '" href="' + esc(href) + '" data-notification-id="' + esc(n.id) + '" ' +
        'onclick="_onBellRowClick(event, ' + n.id + ')">' +
          '<div class="bell-row-title">' + esc(n.title || '') + '</div>' +
          body + time +
        '</a>'
      );
    }

    async function _onBellRowClick(ev, notificationId) {
      // Mark read in the background — don't block the navigation
      fetch('/api/notifications/' + notificationId + '/read', {method: 'POST'})
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.unread_count != null) _setBellBadge(data.unread_count);
        })
        .catch(() => {});
      // Let the <a> navigation proceed naturally; if href is '#' close panel
      const link = ev.currentTarget;
      if (link.getAttribute('href') === '#') {
        ev.preventDefault();
        document.getElementById('bellPanel').style.display = 'none';
      }
    }

    async function markAllNotificationsRead() {
      try {
        const r = await fetch('/api/notifications/read-all', {method: 'POST'});
        if (!r.ok) return;
        const data = await r.json();
        _setBellBadge(data.unread_count || 0);
        await refreshBellPanel();
      } catch (e) { /* silently ignore */ }
    }

    // ── Dev Notes triage tab ──
    // Three sub-tabs by status (open / acknowledged / corrected).
    // _devNotesAll holds the currently-loaded set; filterDevNotesTab
    // re-renders + persists active tab in _devNotesActiveStatus.
    let _devNotesAll = [];
    let _devNotesActiveStatus = 'open';

    async function loadDevNotes() {
      const list = document.getElementById('devNotesList');
      try {
        // Always pull all 3 statuses so the count badges + tab counts
        // are accurate without needing 3 fetches.
        const r = await fetch('/api/dev_notes');
        if (!r.ok) throw new Error('Could not load dev notes');
        const data = await r.json();
        _devNotesAll = data.notes || [];
        _updateDevNoteCounts(data.counts || {});
        _renderDevNotes();
      } catch (e) {
        list.innerHTML = errorAlert('Could not load dev notes: ' + e.message);
      }
    }

    function _updateDevNoteCounts(counts) {
      ['open', 'acknowledged', 'corrected'].forEach(s => {
        const el = document.getElementById('dnCount' + s.charAt(0).toUpperCase() + s.slice(1));
        if (el) el.textContent = counts[s] || 0;
      });
      // Sidebar badge: unread = open count, since that's what the
      // superadmin actually needs to act on.
      const badge = document.getElementById('sidebarDevNotesBadge');
      const open = counts.open || 0;
      if (badge) {
        if (open > 0) {
          badge.textContent = open > 99 ? '99+' : String(open);
          badge.style.display = 'inline-flex';
        } else {
          badge.style.display = 'none';
        }
      }
    }

    function filterDevNotesTab(status) {
      _devNotesActiveStatus = status;
      document.querySelectorAll('.dev-notes-tab').forEach(t =>
        t.classList.toggle('active', t.dataset.dnTab === status));
      _renderDevNotes();
    }

    function _renderDevNotes() {
      const list = document.getElementById('devNotesList');
      const filtered = _devNotesAll.filter(n => (n.dev_status || 'open') === _devNotesActiveStatus);
      if (!filtered.length) {
        const empty = {
          open: 'No dev notes awaiting triage. 🎉',
          acknowledged: 'Nothing in progress.',
          corrected: 'No resolved notes yet.',
        }[_devNotesActiveStatus];
        list.innerHTML = '<div style="padding:32px 16px;text-align:center;color:var(--text-muted);font-size:var(--text-sm);">' + esc(empty) + '</div>';
        return;
      }
      list.innerHTML = filtered.map(_renderDevNoteCard).join('');
      if (typeof localizeTimestamps === 'function') localizeTimestamps(list);
    }

    function _renderDevNoteCard(n) {
      const status = n.dev_status || 'open';
      const cls = 'dev-note-card dn-' + status;
      const author = esc(n.author_name || n.author_email || 'Unknown');
      const reqLine = n.requirement_code
        ? esc(n.requirement_code) + ' — ' + esc(n.requirement_title || '')
        : '';
      const project = n.project_name ? esc(n.project_name) : ('Project ' + esc(n.project_cc_id || ''));
      const reportLink = n.report_id ? '<a href="/report/' + n.report_id + '">Open report</a>' : '';
      const orgLine = n.org_name ? ' · ' + esc(n.org_name) : '';
      const time = n.created_at
        ? '<time class="ts-relative" datetime="' + esc(n.created_at) + '"></time>'
        : '';
      const repliesHtml = (n.replies && n.replies.length)
        ? '<div class="dn-replies">' + n.replies.map(_renderDevNoteReply).join('') + '</div>'
        : '';
      // Action buttons depend on current status. Cancel reply button
      // is hidden unless the editor is open.
      let actions = '';
      if (status === 'open') {
        actions += '<button class="btn btn-sm btn-primary" onclick="setDevNoteStatus(' + n.id + ', \\'acknowledged\\')">Acknowledge</button>';
        actions += '<button class="btn btn-sm btn-subtle" onclick="setDevNoteStatus(' + n.id + ', \\'corrected\\')">Mark corrected</button>';
      } else if (status === 'acknowledged') {
        actions += '<button class="btn btn-sm btn-primary" onclick="setDevNoteStatus(' + n.id + ', \\'corrected\\')">Mark corrected</button>';
        actions += '<button class="btn btn-sm btn-subtle" onclick="setDevNoteStatus(' + n.id + ', \\'open\\')">Reopen</button>';
      } else {
        actions += '<button class="btn btn-sm btn-subtle" onclick="setDevNoteStatus(' + n.id + ', \\'open\\')">Reopen</button>';
      }
      actions += '<button class="btn btn-sm btn-ghost" onclick="openDevNoteReply(' + n.id + ', this)">Reply</button>';

      return (
        '<div class="dev-note-card ' + cls + '" id="devNote-' + n.id + '">' +
          '<div class="dn-meta">' +
            '<span class="dn-meta-author">' + author + '</span>' +
            time +
            (orgLine ? '<span>' + orgLine + '</span>' : '') +
            (reqLine ? '<span>· ' + reqLine + '</span>' : '') +
            '<span style="margin-left:auto;">' + reportLink + '</span>' +
          '</div>' +
          '<div class="dn-body">' + esc(n.body || '').replace(/\\n/g, '<br>') + '</div>' +
          repliesHtml +
          '<div class="dn-actions">' + actions + '</div>' +
        '</div>'
      );
    }

    function _renderDevNoteReply(r) {
      const author = esc(r.author_name || r.author_email || 'Unknown');
      const time = r.created_at
        ? '<time class="ts-relative" datetime="' + esc(r.created_at) + '"></time>'
        : '';
      return (
        '<div class="dn-reply">' +
          '<div class="dn-reply-meta">' +
            '<span class="dn-reply-author">' + author + '</span>' +
            time +
          '</div>' +
          '<div class="dn-reply-body">' + esc(r.body || '').replace(/\\n/g, '<br>') + '</div>' +
        '</div>'
      );
    }

    async function setDevNoteStatus(noteId, newStatus) {
      try {
        const r = await fetch('/api/dev_notes/' + noteId + '/status', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({status: newStatus}),
        });
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        // Easiest correct path: refetch the whole list (counts +
        // ordering may have shifted).
        await loadDevNotes();
      } catch (e) {
        alert('Could not update status: ' + e.message);
      }
    }

    function openDevNoteReply(noteId, btn) {
      const card = document.getElementById('devNote-' + noteId);
      if (!card) return;
      const existing = card.querySelector('.dn-reply-editor');
      if (existing) { existing.remove(); return; }
      const editor = document.createElement('div');
      editor.className = 'dn-reply-editor';
      editor.style.marginTop = '10px';
      editor.innerHTML =
        '<textarea placeholder="Reply to this dev note…"></textarea>' +
        '<div class="dn-reply-editor-actions">' +
          '<button class="btn btn-sm btn-primary">Post reply</button>' +
          '<button class="btn btn-sm btn-subtle">Cancel</button>' +
        '</div>';
      card.querySelector('.dn-actions').insertAdjacentElement('beforebegin', editor);
      const ta = editor.querySelector('textarea');
      ta.focus();
      const [saveBtn, cancelBtn] = editor.querySelectorAll('button');
      cancelBtn.onclick = () => editor.remove();
      saveBtn.onclick = async () => {
        if (!ta.value.trim()) { ta.focus(); return; }
        saveBtn.disabled = true;
        try {
          const r = await fetch('/api/dev_notes/' + noteId + '/reply', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({body: ta.value}),
          });
          const data = await r.json();
          if (data.error) throw new Error(data.error);
          editor.remove();
          // Refresh the full list — keeps replies in chronological
          // order without needing partial DOM updates.
          await loadDevNotes();
        } catch (e) {
          alert('Could not post reply: ' + e.message);
          saveBtn.disabled = false;
        }
      };
    }

    // Home page banners: "your check is still running" / "your check
    // completed" — both driven by /api/my_active_check. Keeps a user who
    // disconnected mid-check from thinking their work was lost.
    //
    // Dismissal for the completed banner uses localStorage so it doesn't
    // re-nag after the user has seen it once. Running banner is not
    // dismissible — it's load-bearing info.
    async function fetchActiveChecks() {
      try {
        const r = await fetch('/api/my_active_check');
        if (!r.ok) return;
        const data = await r.json();
        _applyActiveCheckBanners(data);
      } catch (e) { /* silently ignore */ }
    }

    function _applyActiveCheckBanners(data) {
      const running = data && data.running;
      const rb = document.getElementById('runningCheckBanner');
      if (running && rb) {
        rb.href = '/report/' + running.db_report_id;
        const detail = document.getElementById('runningCheckDetail');
        if (detail) {
          const name = running.project_name || ('Project ' + running.project_id);
          detail.textContent = name + ' — click to see current progress';
        }
        rb.style.display = 'flex';
      } else if (rb) {
        rb.style.display = 'none';
      }

      const completed = data && data.recently_completed;
      const cb = document.getElementById('completedCheckBanner');
      if (completed && cb) {
        const dismissKey = 'dismissed_completed_' + completed.db_report_id;
        if (localStorage.getItem(dismissKey)) {
          cb.style.display = 'none';
          return;
        }
        const link = document.getElementById('completedCheckLink');
        if (link) link.href = '/report/' + completed.db_report_id;
        const detail = document.getElementById('completedCheckDetail');
        if (detail) {
          const name = completed.project_name || ('Project ' + completed.project_id);
          const cancelled = completed.status === 'cancelled';
          const passed = completed.total_passed || 0;
          const total = completed.total_required || 0;
          const result = cancelled
            ? `${name} — cancelled with ${passed}/${total} completed`
            : `${name} — ${passed}/${total} passed`;
          detail.textContent = result;
        }
        cb.dataset.reportId = completed.db_report_id;
        cb.style.display = 'flex';
      } else if (cb) {
        cb.style.display = 'none';
      }
    }

    function dismissCompletedCheckBanner(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      const cb = document.getElementById('completedCheckBanner');
      if (!cb) return;
      const id = cb.dataset.reportId;
      if (id) localStorage.setItem('dismissed_completed_' + id, '1');
      cb.style.display = 'none';
    }

    // Refresh Anthropic platform status every 60s so the banner appears/
    // disappears in near real-time without a page reload. Errors are
    // swallowed — the banner just won't update. Poll interval matches
    // the backend's own status fetch cadence.
    async function refreshPlatformStatus() {
      try {
        const r = await fetch('/api/platform_status');
        if (!r.ok) return;
        const s = await r.json();
        _applyPlatformStatus(s);
      } catch (e) { /* silently ignore */ }
    }
    setInterval(refreshPlatformStatus, 60000);

    // Map Statuspage indicators to banner styles. "none" → hide.
    // "maintenance" shown informationally in blue rather than amber/red.
    const _PLATFORM_STATUS_STYLE = {
      minor:       {bg: '#f59e0b', fg: '#1a1a2e', label: 'degraded'},
      major:       {bg: '#dc2626', fg: '#ffffff', label: 'experiencing a partial outage'},
      critical:    {bg: '#991b1b', fg: '#ffffff', label: 'experiencing a major outage'},
      maintenance: {bg: '#3b82f6', fg: '#ffffff', label: 'under maintenance'},
    };

    function _applyPlatformStatus(s) {
      const banner = document.getElementById('platformStatusBanner');
      if (!banner) return;
      const indicator = s && s.indicator;
      const style = _PLATFORM_STATUS_STYLE[indicator];
      // "none" (all good), "unknown" (poller failing / not yet run), or
      // anything unmapped → hide the banner rather than cry wolf.
      if (!style) {
        banner.style.display = 'none';
        return;
      }
      banner.style.background = style.bg;
      banner.style.color = style.fg;
      document.getElementById('platformStatusTitle').textContent =
        'Anthropic API: ' + style.label;
      // Prefer Anthropic's own description when they provide a useful
      // one (e.g. "Partial Outage — Claude API Degraded Performance");
      // otherwise keep our fallback about slower/failed checks.
      const detail = document.getElementById('platformStatusDetail');
      if (s.description && s.description.toLowerCase() !== 'all systems operational') {
        detail.textContent = ' — ' + s.description + '. Compliance checks may be slower or fail intermittently.';
      } else {
        detail.textContent = ' — compliance checks may be slower or fail intermittently.';
      }
      banner.style.display = 'flex';
    }

    function _applyImpersonationBanner(me) {
      const banner = document.getElementById('impersonationBanner');
      if (!banner) return;
      if (me && me.is_impersonating) {
        document.getElementById('impersonationTarget').textContent =
          (me.full_name || me.email || 'user #' + me.user_id) + ' (' + me.role + ')';
        document.getElementById('impersonationInitiator').textContent =
          'as ' + (me.real_full_name || me.real_email || 'superadmin');
        banner.style.display = 'flex';
      } else {
        banner.style.display = 'none';
      }
    }

    async function startImpersonate(userId, userName) {
      if (!confirm('Impersonate ' + (userName || 'this user') + '? You\\'ll see the app from their perspective until you stop.')) return;
      try {
        const r = await fetch('/api/admin/impersonate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({user_id: userId}),
        });
        const data = await r.json();
        if (!r.ok) { alert(data.error || 'Could not impersonate'); return; }
        // Full reload so the new session cookie + role-gated UI apply cleanly
        window.location.href = '/';
      } catch (e) { alert('Error: ' + e.message); }
    }

    async function stopImpersonate() {
      try {
        const r = await fetch('/api/admin/stop-impersonate', {method: 'POST'});
        if (!r.ok) { alert('Could not stop impersonation'); return; }
        window.location.href = '/';
      } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Cost dashboard ──
    function _fmtUSD(n) {
      if (n == null) return '—';
      if (n >= 1) return '$' + n.toFixed(2);
      if (n >= 0.01) return '$' + n.toFixed(3);
      return '$' + n.toFixed(4);
    }
    // ── Timestamp localization ──
    // Renders a UTC timestamp in the viewer's local tz, with relative
    // ("5 min ago") for recent and absolute ("Apr 17, 2:15 PM") for older.
    // Browser tz detected automatically via Intl. _fmtDate kept as a thin
    // alias for backward compat — same behavior.
    // (This block is duplicated in tools/generate_report_html.py — keep
    // them in sync. Worth extracting to a shared static asset eventually.)
    function formatTimestamp(input, opts) {
      if (!input) return '';
      opts = opts || {};
      const d = _toDate(input);
      if (!d || isNaN(d.getTime())) return String(input);
      const ageMs = Date.now() - d.getTime();
      const sec = Math.round(ageMs / 1000);
      const min = Math.round(sec / 60);
      const hr = Math.round(min / 60);
      const day = Math.round(hr / 24);
      if (opts.absolute) return _absoluteString(d, ageMs);
      if (sec < 30 && sec > -30) return 'just now';
      if (Math.abs(min) < 60) return min + ' min ago';
      if (Math.abs(hr) < 24) return hr + ' hr ago';
      if (Math.abs(day) < 7) return day + (Math.abs(day) === 1 ? ' day ago' : ' days ago');
      return _absoluteString(d, ageMs);
    }
    function formatTimestampAbsolute(input) {
      return formatTimestamp(input, {absolute: true});
    }
    function _absoluteString(d, ageMs) {
      const opts = {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'};
      if (ageMs > 365 * 24 * 60 * 60 * 1000) opts.year = 'numeric';
      return d.toLocaleString('en-US', opts);
    }
    function _toDate(input) {
      if (input == null) return null;
      if (input instanceof Date) return input;
      if (typeof input === 'number') {
        return new Date(input < 1e11 ? input * 1000 : input);
      }
      return new Date(input);
    }
    function localizeTimestamps(root) {
      root = root || document;
      root.querySelectorAll('time.ts-relative').forEach(function(el) {
        const iso = el.getAttribute('datetime');
        if (!iso) return;
        el.textContent = formatTimestamp(iso);
        el.title = formatTimestampAbsolute(iso);
      });
    }
    document.addEventListener('DOMContentLoaded', function() { localizeTimestamps(); });
    setInterval(function() { localizeTimestamps(); }, 60000);

    function _fmtDate(iso) {
      if (!iso) return '—';
      return formatTimestamp(iso);
    }
    function _fmtDay(iso) {
      if (!iso) return '—';
      const d = _toDate(iso);
      if (!d || isNaN(d.getTime())) return '—';
      return d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
    }

    let _costFilterOptionsLoaded = false;
    async function loadCostFilterOptions() {
      if (_costFilterOptionsLoaded) return;
      try {
        const r = await fetch('/api/admin/cost/filter-options');
        if (!r.ok) return;
        const data = await r.json();
        const orgSel = document.getElementById('costOrgFilter');
        const userSel = document.getElementById('costUserFilter');
        // Preserve the "All" option and append DB rows
        orgSel.innerHTML = '<option value="">All organizations</option>' +
          (data.orgs || []).map(o => '<option value="' + o.id + '">' + esc(o.name) + '</option>').join('');
        userSel.innerHTML = '<option value="">All users</option>' +
          (data.users || []).map(u => {
            const label = u.full_name || u.email || ('user ' + u.id);
            return '<option value="' + u.id + '">' + esc(label) + '</option>';
          }).join('');
        _costFilterOptionsLoaded = true;
      } catch (e) { /* non-fatal — dropdowns just stay empty */ }
    }

    function _costFilterQuery() {
      const org = document.getElementById('costOrgFilter').value;
      const user = document.getElementById('costUserFilter').value;
      const from = document.getElementById('costDateFrom').value;
      const to = document.getElementById('costDateTo').value;
      const params = new URLSearchParams();
      if (org) params.set('org_id', org);
      if (user) params.set('user_id', user);
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      const qs = params.toString();
      return qs ? ('?' + qs) : '';
    }

    function clearCostFilters() {
      document.getElementById('costOrgFilter').value = '';
      document.getElementById('costUserFilter').value = '';
      document.getElementById('costDateFrom').value = '';
      document.getElementById('costDateTo').value = '';
      loadCosts();
    }

    async function loadCosts() {
      const summary = document.getElementById('costSummary');
      const body = document.getElementById('costBody');
      summary.innerHTML = spinnerHtml('Loading cost data...');
      body.innerHTML = '';
      await loadCostFilterOptions();
      try {
        const r = await fetch('/api/admin/cost/summary' + _costFilterQuery());
        if (r.status === 403) {
          summary.innerHTML = errorAlert('Superadmin access required.');
          return;
        }
        if (!r.ok) throw new Error('Request failed');
        const data = await r.json();
        summary.innerHTML = renderCostSummary(data.totals);
        body.innerHTML =
          renderCostSection('Spend by purpose', renderByPurpose(data.by_purpose, data.totals)) +
          renderCostSection('Most expensive reports', renderTopReports(data.top_reports)) +
          renderCostSection('Most expensive requirements', renderTopRequirements(data.top_requirements)) +
          renderCostSection('Spend by day (last 30)', renderDailyTrend(data.daily_last_30)) +
          renderCostSection('Recent API calls', renderRecentCalls(data.recent_calls));
      } catch (e) {
        summary.innerHTML = errorAlert('Could not load cost data: ' + e.message);
      }
    }

    function renderCostSummary(t) {
      const cards = [
        {label: 'All time', value: _fmtUSD(t && t.all_time)},
        {label: 'This month', value: _fmtUSD(t && t.this_month)},
        {label: 'Today', value: _fmtUSD(t && t.today)},
        {label: 'API calls (all time)', value: (t && t.call_count != null) ? t.call_count.toLocaleString() : '—'},
      ];
      return '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">' +
        cards.map(c =>
          '<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px 14px;box-shadow:var(--shadow-sm);">' +
          '<div style="font-size:var(--text-xs);color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;font-weight:600;">' + c.label + '</div>' +
          '<div style="font-size:var(--text-xl);font-weight:700;color:var(--text);margin-top:4px;">' + c.value + '</div>' +
          '</div>'
        ).join('') + '</div>';
    }

    function renderCostSection(title, inner) {
      return '<div style="margin-top:20px;">' +
        '<div style="font-size:var(--text-xs);text-transform:uppercase;letter-spacing:0.1em;color:var(--text-muted);font-weight:600;padding:8px 0;border-bottom:2px solid var(--border);margin-bottom:10px;">' + esc(title) + '</div>' +
        inner + '</div>';
    }

    // Friendly labels + colors per purpose. Keep in sync with the
    // `purpose` values written in tools/compliance_check.py and
    // live_server.py recheck endpoint.
    const _PURPOSE_META = {
      vision:    {label: 'Full check (Sonnet)',    color: 'var(--accent)'},
      prefilter: {label: 'Pre-filter (Haiku)',     color: 'var(--success)'},
      recheck:   {label: 'Single-item re-check',   color: 'var(--warning)'},
      unknown:   {label: 'Unknown / legacy',       color: 'var(--text-muted)'},
    };

    function renderByPurpose(rows, totals) {
      if (!rows || !rows.length) {
        return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No cost data recorded yet.</div>';
      }
      // Caption clarifies that "Pre-filter" is broken out separately
      // regardless of whether it ran inside a full vision pass or a
      // single-item recheck. Without this it's easy to read "Single-item
      // re-check" as the full cost of rechecks when in reality a recheck
      // on a heavy requirement also incurs prefilter spend.
      const caption = '<div style="color:var(--text-muted);font-size:var(--text-xs);margin-bottom:8px;">' +
        'Pre-filter spend is shown separately and includes calls triggered by both full vision runs and single-item rechecks.' +
        '</div>';
      const grandTotal = rows.reduce((s, r) => s + (r.total_cost || 0), 0) || 0.0001;
      // Stacked bar at top so the proportion is visible at a glance, then
      // a small table with the underlying numbers.
      const bar = '<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--bg-subtle);margin-bottom:10px;">' +
        rows.map(r => {
          const meta = _PURPOSE_META[r.purpose] || _PURPOSE_META.unknown;
          const pct = ((r.total_cost || 0) / grandTotal) * 100;
          return '<div title="' + esc(meta.label) + ': ' + _fmtUSD(r.total_cost) + '" ' +
            'style="width:' + pct.toFixed(2) + '%;background:' + meta.color + ';"></div>';
        }).join('') + '</div>';
      const table = '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Purpose</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Total</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">% of spend</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Calls</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Avg</th></tr></thead><tbody>' +
        rows.map(r => {
          const meta = _PURPOSE_META[r.purpose] || _PURPOSE_META.unknown;
          const pct = ((r.total_cost || 0) / grandTotal) * 100;
          return '<tr style="border-top:1px solid var(--border-light);">' +
            '<td style="padding:6px;font-weight:600;">' +
              '<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + meta.color + ';margin-right:8px;vertical-align:middle;"></span>' +
              esc(meta.label) +
            '</td>' +
            '<td style="padding:6px;text-align:right;font-weight:600;">' + _fmtUSD(r.total_cost) + '</td>' +
            '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + pct.toFixed(1) + '%</td>' +
            '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + r.call_count + '</td>' +
            '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + _fmtUSD(r.avg_cost) + '</td>' +
            '</tr>';
        }).join('') + '</tbody></table></div>';
      return caption + bar + table;
    }

    function renderTopReports(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No cost data recorded yet.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:8px 6px;color:var(--text-muted);font-weight:600;">Project</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Cost</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Calls</th>' +
        '<th style="text-align:left;padding:8px 6px;color:var(--text-muted);font-weight:600;">Completed</th></tr></thead><tbody>' +
        rows.map(r =>
          '<tr style="border-top:1px solid var(--border-light);">' +
          '<td style="padding:8px 6px;"><a href="/report/' + r.report_id + '" style="color:var(--accent);text-decoration:none;">' + esc(r.project_name) + '</a>' +
          (r.is_test ? ' <span class="badge badge-info" style="margin-left:4px;">TEST</span>' : '') + '</td>' +
          '<td style="padding:8px 6px;text-align:right;font-weight:600;">' + _fmtUSD(r.cost_usd) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + r.call_count + '</td>' +
          '<td style="padding:8px 6px;color:var(--text-muted);">' + _fmtDate(r.completed_at) + '</td>' +
          '</tr>'
        ).join('') + '</tbody></table></div>';
    }

    function renderTopRequirements(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No cost data recorded yet.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:8px 6px;color:var(--text-muted);font-weight:600;">Requirement</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Total</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Avg</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Max</th>' +
        '<th style="text-align:right;padding:8px 6px;color:var(--text-muted);font-weight:600;">Calls</th></tr></thead><tbody>' +
        rows.map(r =>
          '<tr style="border-top:1px solid var(--border-light);">' +
          '<td style="padding:8px 6px;font-weight:600;">' + esc(r.requirement_code) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;font-weight:600;">' + _fmtUSD(r.total_cost) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + _fmtUSD(r.avg_cost) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + _fmtUSD(r.max_cost) + '</td>' +
          '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);">' + r.call_count + '</td>' +
          '</tr>'
        ).join('') + '</tbody></table></div>';
    }

    function renderDailyTrend(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No calls in the last 30 days.</div>';
      // Compute a max for bar scaling
      const max = rows.reduce((m, r) => Math.max(m, r.cost_usd || 0), 0.0001);
      return '<div style="display:flex;flex-direction:column;gap:4px;">' +
        rows.map(r => {
          const pct = (r.cost_usd / max) * 100;
          return '<div style="display:flex;align-items:center;gap:10px;font-size:var(--text-xs);">' +
            '<div style="width:60px;color:var(--text-muted);flex-shrink:0;">' + _fmtDay(r.day) + '</div>' +
            '<div style="flex:1;height:8px;background:var(--bg-subtle);border-radius:4px;overflow:hidden;">' +
              '<div style="height:100%;background:var(--accent);width:' + pct.toFixed(1) + '%;transition:width 0.3s;"></div>' +
            '</div>' +
            '<div style="width:60px;text-align:right;font-weight:600;flex-shrink:0;">' + _fmtUSD(r.cost_usd) + '</div>' +
            '<div style="width:40px;text-align:right;color:var(--text-muted);flex-shrink:0;">' + r.call_count + '</div>' +
            '</div>';
        }).join('') + '</div>';
    }

    function renderRecentCalls(rows) {
      if (!rows || !rows.length) return '<div style="color:var(--text-muted);font-size:var(--text-sm);">No calls yet.</div>';
      return '<div class="table-scroll"><table style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">' +
        '<thead><tr><th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">When</th>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Project</th>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Req</th>' +
        '<th style="text-align:left;padding:6px;color:var(--text-muted);font-weight:600;">Purpose</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Tokens</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">Cost</th>' +
        '<th style="text-align:right;padding:6px;color:var(--text-muted);font-weight:600;">ms</th></tr></thead><tbody>' +
        rows.map(c =>
          '<tr style="border-top:1px solid var(--border-light);">' +
          '<td style="padding:6px;color:var(--text-muted);white-space:nowrap;">' + _fmtDate(c.called_at) + '</td>' +
          '<td style="padding:6px;">' + esc(c.project_name || '—') + '</td>' +
          '<td style="padding:6px;font-weight:600;">' + esc(c.requirement_code || '—') + '</td>' +
          '<td style="padding:6px;color:var(--text-muted);">' + esc(c.purpose || '—') + '</td>' +
          '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + (c.input_tokens || 0) + ' / ' + (c.output_tokens || 0) + '</td>' +
          '<td style="padding:6px;text-align:right;font-weight:600;">' + _fmtUSD(c.cost_usd) + '</td>' +
          '<td style="padding:6px;text-align:right;color:var(--text-muted);">' + (c.duration_ms || '—') + '</td>' +
          '</tr>'
        ).join('') + '</tbody></table></div>';
    }
  </script>

  <div style="text-align:center;padding:32px 20px;font-size:11px;color:var(--text-muted);opacity:0.5;">&copy; 2026 Solclear. All rights reserved.</div>

</body>
</html>"""
