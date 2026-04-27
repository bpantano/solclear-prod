"""
EMBEDDED_HTML — the main single-page app served at /.

HTML + CSS lives in this file. JavaScript lives in tools/html/app.js
and is inlined at import time (see bottom of this file). Keeping JS in
a real .js file means editors can lint it, syntax errors surface
immediately, and quote-escaping bugs in Python strings are eliminated.

Style tokens: tools/html/styles.py (shared with the report page).

To edit JavaScript: open tools/html/app.js — it is a real JS file,
fully lintable by VS Code / ESLint. Changes take effect on next server
restart (embedded.py reads + inlines app.js at import time).
"""

from pathlib import Path as _Path


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
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      Analytics
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

    <!-- Sub-tabs: Settings | Users | Activity -->
    <nav style="display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:16px;">
      <button class="dev-notes-tab active" data-org-tab="settings" onclick="switchOrgTab('settings')">Settings</button>
      <button class="dev-notes-tab" data-org-tab="users" onclick="switchOrgTab('users')">Users <span id="orgUserCount" style="font-size:10px;color:var(--text-muted);margin-left:4px;"></span></button>
      <button class="dev-notes-tab" data-org-tab="activity" onclick="switchOrgTab('activity')">Activity</button>
    </nav>

    <!-- Settings tab -->
    <div id="orgTabSettings">
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
    </div>

    <!-- Users tab -->
    <div id="orgTabUsers" style="display:none;">
      <div style="background:var(--bg-card);border-radius:8px;padding:16px;margin-bottom:16px;">
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

    <!-- Activity tab -->
    <div id="orgTabActivity" style="display:none;">
      <div id="orgAuditLog"></div>
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
    <div class="step-label">Analytics</div>

    <!-- Analytics sub-tabs: Costs | Performance -->
    <nav style="display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:16px;">
      <button id="analyticsTabCosts" class="dev-notes-tab active" onclick="switchAnalyticsTab('costs')">Costs</button>
      <button id="analyticsTabPerf" class="dev-notes-tab" onclick="switchAnalyticsTab('performance')">Performance</button>
      <button id="analyticsTabActivity" class="dev-notes-tab" onclick="switchAnalyticsTab('activity')">Activity</button>
    </nav>

    <!-- Costs sub-page -->
    <div id="analyticsCosts">
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

    <!-- Performance sub-page -->
    <div id="analyticsPerf" style="display:none;">
      <p style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:16px;">
        Wall-clock time per requirement from photo download through AI decisioning. Sorted slowest first. Colour: <span style="color:var(--success);font-weight:600;">green</span> &lt;10s, <span style="color:var(--warning);font-weight:600;">amber</span> 10–30s, <span style="color:var(--danger);font-weight:600;">red</span> &gt;30s.
      </p>
      <div id="perfBody"><div style="color:var(--text-muted);font-size:var(--text-sm);">Loading…</div></div>
    </div>

    <!-- Activity tab — all users including superadmin (org_id=NULL) -->
    <div id="analyticsActivity" style="display:none;">
      <p style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:16px;">
        All user actions across all organizations. Includes superadmin activity (no org) that does not appear in org-specific Activity tabs.
      </p>
      <div id="analyticsActivityBody"><div style="color:var(--text-muted);font-size:var(--text-sm);">Loading…</div></div>
    </div>
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
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      Analytics
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
_APP_JS_PLACEHOLDER_
</script>

  <div style="text-align:center;padding:32px 20px;font-size:11px;color:var(--text-muted);opacity:0.5;">&copy; 2026 Solclear. All rights reserved.</div>

</body>
</html>"""


# Inline app.js at import time. The JS file is a real .js file that
# editors lint and validate — no more Python string escaping surprises.
# The placeholder is replaced with the file contents so the served HTML
# is identical to the old single-file approach.
_APP_JS = (_Path(__file__).parent / "app.js").read_text(encoding="utf-8")
EMBEDDED_HTML = EMBEDDED_HTML.replace("_APP_JS_PLACEHOLDER_", _APP_JS)
