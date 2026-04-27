"""
Tool: generate_report_html.py
Purpose: Render the compliance report detail page.

Two render paths share this file:
- CLI: produces a self-contained .html file from a .tmp/compliance_{id}.json.
- Live server: _serve_report passes a db-backed report dict; the page becomes
  interactive (mark resolved, add note, re-check a single item) when
  db_report_id is present.

Shared design tokens come from tools/html/styles.py so light/dark mode stays
consistent with the rest of the app.

Usage:
  python tools/generate_report_html.py --project_id <id>
  python tools/generate_report_html.py --project_id <id> --no_open
"""

import argparse
import json
import os
import re
import sys
import webbrowser
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

from tools.html.styles import DESIGN_TOKENS_CSS

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
API_BASE = "https://api.companycam.com/v2"

# Status rendering config. Keys are the raw status strings from the engine.
_STATUS_CONFIG = {
    "PASS":            ("pass",         "PASS"),
    "FAIL":            ("fail",         "FAIL"),
    "MISSING":         ("missing",      "MISSING"),
    "ERROR":           ("error",        "ERROR"),
    "NEEDS_REVIEW":    ("needs_review", "NEEDS REVIEW"),
    "FOUND_NO_VISION": ("skip",         "SKIPPED"),
    "N/A":             ("na",           "N/A"),
}
# Statuses that belong in the "Needs attention" tab. NEEDS_REVIEW is a
# first-class attention state — it's an item a reviewer must confirm.
_ATTENTION_STATUSES = {"FAIL", "MISSING", "ERROR", "NEEDS_REVIEW"}
# Kept for internal detection of hard failures vs review items.
_FAILURE_STATUSES = {"FAIL", "MISSING", "ERROR"}
# Sort order within a section. Failures first, then needs-review, then
# missing, errors, skipped, pass last.
_STATUS_SORT_ORDER = {"FAIL": 0, "NEEDS_REVIEW": 1, "MISSING": 2, "ERROR": 3, "FOUND_NO_VISION": 4, "PASS": 5}


def fetch_project(project_id: str) -> dict:
    token = os.getenv("COMPANYCAM_API_KEY")
    if not token:
        return {}
    try:
        resp = requests.get(
            f"{API_BASE}/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def status_badge(status: str) -> str:
    cls, label = _STATUS_CONFIG.get(status, ("na", status))
    return f'<span class="badge badge-{cls}">{label}</span>'


def linkify_photos(text: str, photo_urls: dict) -> str:
    """Replace 'Photo(s) N', 'Photos N and M', 'Photos N, M' with clickable links."""
    if not photo_urls:
        return text
    def link_number(match):
        num = match.group(1)
        url = photo_urls.get(num) or photo_urls.get(int(num))
        if url:
            return f'<a href="{url}" target="_blank" style="color:var(--accent);font-weight:500;">{num}</a>'
        return num
    def replacer(match):
        return re.sub(r'(\d+)', link_number, match.group(0))
    return re.sub(
        r'Photos?\s+(\d+(?:\s*(?:,\s*(?:and\s+)?|and\s+|&\s*)\d+)*)',
        replacer,
        text,
        flags=re.IGNORECASE,
    )


def truncate_reason(reason: str, limit: int = 120) -> tuple:
    """Return (short, full) — short is truncated if needed."""
    if not reason:
        return "", ""
    clean = " ".join(reason.split())
    if len(clean) <= limit:
        return clean, ""
    return clean[:limit].rsplit(" ", 1)[0] + "...", clean


def _esc(s) -> str:
    """Escape for HTML attributes/text. Handles None safely."""
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _format_note_timestamp_utc_fallback(iso_ts: str) -> str:
    """Server-side fallback for the <time datetime> element's text content.
    The client's localizeTimestamps() runs on load and replaces this with
    the user's local-tz relative-or-absolute display, so this only shows
    on JS-disabled browsers or in the brief flash before JS runs.

    Format: 'Apr 24, 18:00 UTC' — explicit tz tag so a JS-disabled reader
    isn't confused about which tz they're seeing. UTC is honest, since
    we don't know the reader's tz at server-render time."""
    if not iso_ts:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime("%b %-d, %H:%M UTC")
    except Exception:
        return iso_ts


def _render_note(note: dict) -> str:
    """Render one note row in the comment thread. Notes are immutable, so
    there's no edit/delete UI — just author, timestamp, and body.

    Timestamp is wrapped in <time datetime="UTC_ISO" class="ts-relative">
    with a UTC fallback as text content. The client-side localizeTimestamps()
    rewrites it to the user's local timezone with relative-or-absolute
    formatting on page load (and after any DOM mutation that adds notes).

    Dev-visibility notes get the `note-dev` modifier class so reviewers
    can distinguish their bug-tracker comments from public crew notes.
    A pill shows the dev-status ('open', 'acknowledged', 'corrected')
    when present."""
    author = note.get("author_name") or note.get("author_email") or "Unknown author"
    iso = note.get("created_at", "") or ""
    fallback = _format_note_timestamp_utc_fallback(iso)
    body = _esc(note.get("body", ""))
    visibility = note.get("visibility") or "public"
    visibility_cls = "note-dev" if visibility == "dev" else "note-public"
    dev_pill = ""
    if visibility == "dev":
        status = note.get("dev_status") or "open"
        dev_pill = f'<span class="note-dev-pill note-dev-{_esc(status)}">{_esc(status.upper())}</span>'
    time_html = (
        f'<time class="ts-relative req-note-time" datetime="{_esc(iso)}">{_esc(fallback)}</time>'
        if iso else ""
    )
    return (
        f'<div class="req-note {visibility_cls}">'
        f'<div class="req-note-meta">'
        f'<span class="req-note-author">{_esc(author)}</span>'
        f'{time_html}'
        f'{dev_pill}'
        f'</div>'
        f'<div class="req-note-body">{body}</div>'
        f'</div>'
    )


def render_requirement(req: dict, is_interactive: bool, checklist_id: str, project_id: str) -> str:
    status = req.get("status", "")
    code = req.get("id", "")
    photo_urls = req.get("photo_urls", {}) or {}
    is_failure = status in _FAILURE_STATUSES or status == "NEEDS_REVIEW"
    is_resolved = bool(req.get("resolved_at"))

    optional_tag = '<span class="optional-tag">optional</span>' if req.get("optional") else ""

    # Reason with show-more/less toggle for long text
    reason_html = ""
    if status not in ("PASS", "N/A", "FOUND_NO_VISION") and req.get("reason"):
        short, full = truncate_reason(req["reason"])
        if full:
            short_linked = linkify_photos(short, photo_urls)
            full_linked = linkify_photos(full, photo_urls)
            reason_html = f'''
      <p class="reason reason-short">{short_linked}</p>
      <div class="reason-full" style="display:none"><p class="reason">{full_linked}</p></div>
      <button class="expand-btn" onclick="toggleReason(this)">Show more <span class="arrow">&#9662;</span></button>'''
        else:
            reason_html = f'<p class="reason">{linkify_photos(short, photo_urls)}</p>'

    # Photo thumbnail (the evaluated winner is key 1)
    eval_url = photo_urls.get(1) or photo_urls.get("1")
    photo_html = ""
    if eval_url and status not in ("N/A", "FOUND_NO_VISION"):
        photo_html = (
            f'<a href="{_esc(eval_url)}" target="_blank" class="req-photo-link">'
            f'<img src="{_esc(eval_url)}" alt="Evaluated photo" loading="lazy" class="req-photo">'
            f'</a>'
        )

    # Resolved chip — shown when the item is marked resolved
    resolved_chip = ""
    if is_resolved:
        by = _esc(req.get("resolved_by_name") or "Unknown")
        resolved_chip = f'<span class="badge badge-success resolved-chip" title="Resolved by {by}">Resolved</span>'

    # Notes thread — comment-thread style, oldest-first, immutable.
    # `notes_thread` is populated by live_server._serve_report from the
    # new notes table (migration 005). Legacy reports prior to the table
    # surface as empty threads. Each note renders author + timestamp +
    # body; dev-visibility notes (filtered server-side by viewer role)
    # get a slightly different style to distinguish from public ones.
    notes_thread = req.get("notes_thread") or []
    note_html = ""
    if notes_thread:
        note_html = '<div class="req-notes-thread">' + "".join(
            _render_note(n) for n in notes_thread
        ) + '</div>'

    # Actions — available on every interactive non-N/A row, including
    # PASS rows. Reviewers need to be able to flag a PASS that looks
    # wrong (note + dev note) or challenge it (re-check). "Mark resolved"
    # is the only failure-only action since a PASS has nothing to resolve.
    actions_html = ""
    if is_interactive and status != "N/A":
        # Deep-link to the CompanyCam checklist (no direct task-level URL,
        # so we link to the checklist for the project).
        cc_task_url = (
            f"https://app.companycam.com/projects/{_esc(project_id)}/todos/{_esc(checklist_id)}"
            if project_id and checklist_id else ""
        )
        cc_btn = (
            f'<a href="{cc_task_url}" target="_blank" class="btn btn-sm btn-ghost" onclick="event.stopPropagation()">Open in CompanyCam ↗</a>'
            if cc_task_url else ""
        )
        # Resolve button only makes sense when something needs resolving.
        resolve_btn = ""
        if is_failure:
            resolve_label = "Undo resolve" if is_resolved else "Mark resolved"
            resolve_btn = (
                f'<button class="btn btn-sm btn-subtle" data-role="resolve-btn" '
                f'onclick="event.stopPropagation();toggleResolved(this, \'{_esc(code)}\')">{resolve_label}</button>'
            )
        # Dev note button is gated to reviewer/admin/superadmin via the
        # .reviewer-plus class — same pattern used elsewhere. Crew never
        # sees this button server-rendered (we'd ideally check role here)
        # but the report HTML is currently role-agnostic, so we use the
        # CSS class which is hidden by default + revealed by loadMe().
        actions_html = f'''
      <div class="req-actions">
        {cc_btn}
        {resolve_btn}
        <button class="btn btn-sm btn-subtle" onclick="event.stopPropagation();openNoteEditor(this, '{_esc(code)}', 'public')">Add note</button>
        <button class="btn btn-sm btn-subtle reviewer-plus" style="display:none;" onclick="event.stopPropagation();openNoteEditor(this, '{_esc(code)}', 'dev')">Flag bug</button>
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();recheckItem(this, '{_esc(code)}')">Re-check</button>
      </div>'''

    # PASS rows start collapsed so the page leads with failures
    # PASS rows start collapsed by default — but if the thread has any
    # notes, keep it expanded so conversation is visible at a glance.
    collapsed_class = " collapsed" if status == "PASS" and not notes_thread else ""
    click_handler = ' onclick="this.classList.toggle(\'collapsed\')"' if status == "PASS" else ""

    resolved_data = ' data-resolved="1"' if is_resolved else ""
    return f'''
    <div class="requirement req-{status.lower()}{collapsed_class}" data-status="{_esc(status)}" data-id="{_esc(code)}"{resolved_data}{click_handler}>
      <div class="req-header">
        {status_badge(status)}
        <span class="req-id">{_esc(code)}</span>
        <span class="req-title">{_esc(req.get("title", ""))}</span>
        {resolved_chip}
        {optional_tag}
      </div>
      {photo_html}
      {reason_html}
      {note_html}
      <!-- Palmetto reference photo toggle — JS populates on first open -->
      <div class="req-reference-toggle" style="margin-top:8px;">
        <button class="btn btn-sm btn-subtle" style="font-size:10px;"
                onclick="event.stopPropagation();toggleReferencePhotos(this,'{_esc(code)}')">
          📋 See Palmetto reference
        </button>
        <div class="req-reference-photos" style="display:none;margin-top:8px;"></div>
      </div>
      {actions_html}
    </div>'''


def render_section(section_name: str, reqs: list, is_interactive: bool,
                   checklist_id: str, project_id: str) -> str:
    applicable = [r for r in reqs if r.get("status") != "N/A"]
    if not applicable:
        return ""

    passed = sum(1 for r in applicable if r["status"] == "PASS")
    total = len(applicable)
    failed = sum(1 for r in applicable if r["status"] in _FAILURE_STATUSES)
    review = sum(1 for r in applicable if r["status"] == "NEEDS_REVIEW")

    sorted_reqs = sorted(applicable, key=lambda r: _STATUS_SORT_ORDER.get(r["status"], 5))
    rows = "".join(render_requirement(r, is_interactive, checklist_id, project_id) for r in sorted_reqs)

    # score-clean only when fully clean; score-review when only review items remain;
    # score-issues for hard failures (which take priority over review).
    if failed > 0:
        score_class = "score-issues"
    elif review > 0:
        score_class = "score-review"
    else:
        score_class = "score-clean"
    return f'''
  <div class="section">
    <div class="section-header">
      <h2>{_esc(section_name)}</h2>
      <span class="section-score {score_class}">{passed}/{total}</span>
    </div>
    {rows}
  </div>'''


def _report_style_block() -> str:
    """Report-specific styles (layout + utility classes). Tokens come from DESIGN_TOKENS_CSS."""
    return """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text);
      font-size: var(--text-base); line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      min-height: 100dvh;
      padding-bottom: 64px;
    }

    /* Top bar */
    .report-topbar {
      background: var(--header-bg); color: var(--text-inverse);
      padding: 12px 20px;
      display: flex; align-items: center; justify-content: space-between;
      position: sticky; top: 0; z-index: 30;
    }
    .report-topbar a {
      color: #9ca3af; text-decoration: none;
      font-size: var(--text-sm); font-weight: 500;
      display: inline-flex; align-items: center; gap: 6px;
    }
    .report-topbar a:hover { color: #fff; }
    .theme-toggle {
      background: none; border: none; color: inherit; cursor: pointer;
      width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
      border-radius: 8px;
    }
    .theme-toggle:hover { background: rgba(255,255,255,0.08); }
    .theme-toggle svg { width: 20px; height: 20px; }

    /* Sticky summary card */
    .report-summary {
      position: sticky; top: 56px; z-index: 20;
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      padding: 16px 20px;
      box-shadow: var(--shadow-sm);
    }
    .summary-inner { max-width: 920px; margin: 0 auto; display: flex; flex-direction: column; gap: 10px; }
    .summary-main { display: flex; align-items: center; gap: 14px; }
    .summary-ring { flex-shrink: 0; }
    .summary-ring circle { fill: none; stroke-width: 5; transform: rotate(-90deg); transform-origin: 50% 50%; }
    .ring-bg { stroke: var(--border); }
    .ring-fill { stroke-linecap: round; transition: stroke-dashoffset 0.5s ease; }
    .summary-pass .ring-fill { stroke: var(--success); }
    .summary-fail .ring-fill { stroke: var(--danger); }
    .ring-text { font-size: 11px; font-weight: 700; fill: var(--text); text-anchor: middle; dominant-baseline: central; }
    .summary-text { flex: 1; min-width: 0; }
    .summary-headline { font-size: var(--text-xl); font-weight: 700; color: var(--text); }
    .summary-project { font-size: var(--text-sm); color: var(--text-muted); margin-top: 2px; }
    .summary-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .chip {
      display: inline-flex; align-items: center; gap: 4px;
      font-size: var(--text-xs); font-weight: 600;
      padding: 3px 8px; border-radius: 12px;
      background: var(--bg-subtle); color: var(--text-secondary);
    }
    .chip-pass { background: var(--success-subtle); color: var(--success-text); }
    .chip-fail { background: var(--danger-subtle); color: var(--danger-text); }
    .chip-missing { background: var(--warning-subtle); color: var(--warning-text); }
    .chip-error { background: var(--purple-subtle); color: var(--purple-text); }
    .chip-review { background: var(--review-subtle); color: var(--review-text); }
    .summary-ctas { display: flex; flex-wrap: wrap; gap: 8px; }

    /* Buttons */
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      border: none; border-radius: 10px; padding: 10px 16px;
      font-size: var(--text-md); font-weight: 600;
      cursor: pointer; min-height: 44px;
      text-decoration: none; font-family: inherit;
      transition: background 0.12s, color 0.12s, border-color 0.12s;
      -webkit-tap-highlight-color: transparent;
    }
    .btn-primary { background: var(--accent); color: var(--text-inverse); }
    .btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
    .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-ghost { background: transparent; color: var(--text); border: 1px solid var(--border); }
    .btn-ghost:hover:not(:disabled) { background: var(--bg-hover); border-color: var(--border-strong); }
    .btn-subtle { background: var(--bg-subtle); color: var(--text); border: none; }
    .btn-subtle:hover:not(:disabled) { background: var(--bg-hover); }
    /* btn-warning reserved for dev-note / bug-flagging actions — amber
       to signal "this is a diagnostic / internal channel" separate from
       the primary (accent) and ghost styles. */
    .btn-warning { background: var(--warning); color: var(--text-inverse); }
    .btn-warning:hover:not(:disabled) { filter: brightness(0.92); }
    .btn-sm { min-height: 32px; padding: 6px 12px; font-size: var(--text-xs); }

    /* Dev-note editor: warning-toned border so the author knows this
       note won't be shown to crew. Helps prevent accidentally filing
       a bug note in the wrong channel. */
    .note-editor-dev textarea {
      border-color: var(--warning) !important;
      background: var(--warning-subtle);
    }

    /* Tabs */
    .report-tabs {
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      display: flex;
      max-width: 920px; margin: 0 auto;
      overflow-x: auto; -webkit-overflow-scrolling: touch;
      position: sticky; top: calc(56px + 100px); z-index: 10;
    }
    .report-tab {
      background: none; border: none; cursor: pointer;
      padding: 12px 16px;
      font-size: var(--text-sm); font-weight: 500; color: var(--text-secondary);
      border-bottom: 2px solid transparent;
      white-space: nowrap;
      font-family: inherit;
    }
    .report-tab .count {
      display: inline-block;
      padding: 1px 7px; margin-left: 4px;
      font-size: 10px; font-weight: 700;
      background: var(--bg-subtle); color: var(--text-secondary);
      border-radius: 10px;
    }
    .report-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
    .report-tab.active .count { background: var(--accent-subtle); color: var(--accent-text); }

    /* Body */
    .report-body { max-width: 920px; margin: 20px auto; padding: 0 16px; }

    .section { margin-bottom: 24px; }
    .section-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 8px 0;
      border-bottom: 2px solid var(--text);
      margin-bottom: 8px;
    }
    .section-header h2 {
      font-size: var(--text-xs); text-transform: uppercase;
      letter-spacing: 0.1em; font-weight: 700; color: var(--text);
    }
    .section-score {
      font-size: var(--text-xs); font-weight: 700;
      padding: 2px 8px; border-radius: 10px;
    }
    .score-clean  { background: var(--success-subtle); color: var(--success-text); }
    .score-issues { background: var(--danger-subtle); color: var(--danger-text); }
    .score-review { background: var(--review-subtle); color: var(--review-text); }

    /* Requirement rows */
    .requirement {
      background: var(--bg-card); border-radius: 8px;
      padding: 12px 14px; margin-bottom: 8px;
      border-left: 4px solid var(--border);
      box-shadow: var(--shadow-sm);
      transition: all 0.15s ease;
    }
    .req-pass         { border-left-color: var(--success); }
    .req-fail         { border-left-color: var(--danger); }
    .req-missing      { border-left-color: var(--warning); }
    .req-error        { border-left-color: var(--purple); }
    .req-needs_review { border-left-color: var(--review); }

    .requirement.collapsed {
      padding: 8px 14px;
      opacity: 0.7;
      cursor: pointer;
    }
    .requirement.collapsed:hover { opacity: 1; }
    .requirement.collapsed .reason,
    .requirement.collapsed .reason-full,
    .requirement.collapsed .expand-btn,
    .requirement.collapsed .req-photo-link,
    .requirement.collapsed .req-actions,
    .requirement.collapsed .req-note { display: none !important; }

    .req-header {
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    }
    .req-id { font-size: 10px; font-weight: 700; color: var(--text-muted); min-width: 28px; }
    .req-title { font-size: var(--text-sm); font-weight: 500; flex: 1; color: var(--text); min-width: 120px; }
    .resolved-chip { font-weight: 600; }
    .optional-tag {
      font-size: 9px; background: var(--bg-subtle); color: var(--text-muted);
      padding: 1px 5px; border-radius: 3px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.04em;
    }

    /* Badges */
    .badge {
      display: inline-block;
      font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px;
      letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap;
    }
    .badge-pass         { background: var(--badge-pass-bg); color: var(--badge-pass-text); }
    .badge-fail         { background: var(--badge-fail-bg); color: var(--badge-fail-text); }
    .badge-missing      { background: var(--badge-missing-bg); color: var(--badge-missing-text); }
    .badge-error        { background: var(--badge-error-bg); color: var(--badge-error-text); }
    .badge-needs_review { background: var(--badge-review-bg); color: var(--badge-review-text); }
    .badge-skip         { background: var(--bg-subtle); color: var(--text-muted); }
    .badge-na           { background: var(--bg-subtle); color: var(--text-muted); }
    .badge-success      { background: var(--success-subtle); color: var(--success-text); }

    .req-photo-link { display: block; margin-top: 10px; }
    .req-photo {
      display: block; max-width: 100%;
      border-radius: 6px; border: 2px solid var(--border);
    }
    @media (min-width: 640px) { .req-photo { max-width: 280px; } }

    .reason {
      margin-top: 8px; font-size: var(--text-sm); color: var(--text-secondary);
      line-height: 1.6; padding-left: 10px;
      border-left: 2px solid var(--border-light);
    }
    .expand-btn {
      margin-top: 4px; background: none; border: none;
      color: var(--accent); font-size: var(--text-xs); font-weight: 500;
      cursor: pointer; padding: 2px 0; font-family: inherit;
    }
    .expand-btn:hover { text-decoration: underline; }
    .expand-btn .arrow { font-size: 10px; margin-left: 2px; }

    /* Notes thread (comment-thread style, oldest-first). Each note is
       immutable; follow-ups are their own rows. Public notes have an
       accent rail; dev-visibility notes have a different rail + a
       status pill so they're visually distinct for reviewer eyes. */
    .req-notes-thread {
      margin-top: 10px; display: flex; flex-direction: column; gap: 8px;
    }
    .req-note {
      padding: 10px 12px;
      background: var(--bg-subtle); border-radius: 6px;
      font-size: var(--text-sm); color: var(--text);
      line-height: 1.5;
      border-left: 3px solid var(--accent);
    }
    .req-note.note-dev {
      border-left-color: var(--warning);
      background: var(--warning-subtle);
    }
    .req-note-meta {
      display: flex; gap: 8px; align-items: center;
      font-size: var(--text-xs); color: var(--text-muted);
      margin-bottom: 4px; flex-wrap: wrap;
    }
    .req-note-author { font-weight: 600; color: var(--text); }
    .req-note-time { opacity: 0.8; }
    .req-note-body { white-space: pre-wrap; }
    .note-dev-pill {
      display: inline-block; padding: 1px 6px; border-radius: 10px;
      font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
      background: var(--warning); color: var(--text-inverse);
    }
    .note-dev-acknowledged { background: var(--accent); }
    .note-dev-corrected { background: var(--success); }
    .note-editor {
      margin-top: 10px; display: flex; flex-direction: column; gap: 8px;
    }
    .note-editor textarea {
      width: 100%; min-height: 60px;
      padding: 8px 10px;
      border: 2px solid var(--border); border-radius: 6px;
      background: var(--bg-input); color: var(--text);
      font-family: inherit; font-size: var(--text-sm);
      resize: vertical;
    }
    .note-editor textarea:focus { outline: none; border-color: var(--accent); }
    .note-editor-actions { display: flex; gap: 8px; }

    /* Actions bar */
    .req-actions {
      margin-top: 10px;
      display: flex; gap: 6px; flex-wrap: wrap;
      padding-top: 10px; border-top: 1px solid var(--border-light);
    }

    /* Re-checking state — fade the row but keep header crisp so the
       running badge + button-spinner are unmissable. Block clicks so
       the user can't fire a second recheck while one is in flight. */
    .req-rechecking { pointer-events: none; }
    .req-rechecking .req-photo,
    .req-rechecking .req-reason,
    .req-rechecking .req-actions { opacity: 0.5; }

    /* Running badge: cyan with a pulsing dot. Replaces the status badge
       in the row header for the duration of the recheck. */
    .badge-running {
      background: var(--review-subtle); color: var(--review-text);
      display: inline-flex; align-items: center; gap: 6px;
    }
    .badge-running::before {
      content: ""; width: 6px; height: 6px; border-radius: 50%;
      background: var(--review-text);
      animation: badge-pulse 1.1s ease-in-out infinite;
    }
    @keyframes badge-pulse {
      0%, 100% { opacity: 0.35; transform: scale(0.85); }
      50%      { opacity: 1;    transform: scale(1.15); }
    }

    /* Inline button spinner used while the recheck request is in flight. */
    .btn-spinner {
      display: inline-block; width: 12px; height: 12px;
      border: 2px solid currentColor; border-right-color: transparent;
      border-radius: 50%; vertical-align: -2px; margin-right: 6px;
      animation: btn-spin 0.7s linear infinite;
    }
    @keyframes btn-spin { to { transform: rotate(360deg); } }

    /* Palmetto reference photos */
    .requirement.collapsed .req-reference-toggle { display: none !important; }
    .req-reference-photos {
      display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px;
    }
    .req-reference-photos img {
      width: 120px; height: 90px; object-fit: cover;
      border-radius: 6px; border: 1px solid var(--border);
      cursor: pointer;
    }
    .req-reference-photos img:hover { opacity: 0.85; }
    .req-reference-empty {
      font-size: 11px; color: var(--text-muted); padding: 4px 0;
    }

    /* Alerts */
    .alert {
      display: flex; gap: 10px; align-items: center;
      padding: 10px 14px; border-radius: 8px;
      font-size: var(--text-sm); line-height: 1.5;
      border: 1px solid transparent;
      margin: 10px 0;
    }
    .alert-error { background: var(--danger-subtle); color: var(--danger-text); border-color: var(--danger); }
    .alert-success { background: var(--success-subtle); color: var(--success-text); border-color: var(--success); }

    /* Footer */
    .report-footer {
      text-align: center; padding: 24px 20px;
      font-size: var(--text-xs); color: var(--text-muted); opacity: 0.7;
    }

    /* Mobile */
    @media (max-width: 640px) {
      .summary-main { flex-direction: row; align-items: flex-start; }
      .summary-headline { font-size: var(--text-lg); }
      .report-body { padding: 0 12px; }
      .requirement { padding: 12px; }
      .req-actions { gap: 6px; }
      .req-actions .btn { flex: 1 1 calc(50% - 3px); min-width: calc(50% - 3px); }
    }
    """


def _report_script_block(db_report_id, is_interactive, cc_url, failed_ids, params,
                         project_id, checklist_ids, is_cancelled=False) -> str:
    """JavaScript for theme toggle, tabs, and (when interactive) resolve/note/recheck."""
    # RERUN_PARAMS powers both the "Re-run N failed items" button (needs
    # rerun_ids) and the "Run full check again" button on cancelled
    # reports (strips rerun_ids client-side). Populate whenever we have
    # enough data to kick off SOME rerun action — failed items exist OR
    # the report was cancelled (so full-rerun is useful).
    rerun_params_js = "null"
    if is_interactive and (failed_ids or is_cancelled):
        qs_params = {
            "project_id": project_id,
            "checklist_id": checklist_ids[0] if checklist_ids else "",
            "manufacturer": params.get("manufacturer", "SolarEdge") or "SolarEdge",
            "project_state": "",
            "rerun_ids": ",".join(failed_ids) if failed_ids else "",
        }
        rerun_params_js = json.dumps(qs_params)

    return f"""
    // ── Theme ──
    (function() {{
      const saved = localStorage.getItem('solclear-theme');
      if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
        document.documentElement.setAttribute('data-theme', 'dark');
      }}
      updateThemeIcon();
    }})();

    // ── Role-based visibility ──
    // The report page is standalone (not part of the SPA) so it needs
    // its own /api/me fetch to reveal reviewer-plus / admin-write /
    // superadmin-only elements. Mirrors the SPA's _applyRoleVisibility.
    // Without this, the "Flag bug" dev-note button would be forever
    // hidden even for reviewers/admins/superadmins.
    (async function() {{
      try {{
        const r = await fetch('/api/me');
        if (!r.ok) return;
        const me = await r.json();
        const role = me && me.role;
        const visible = [];
        if (role === 'superadmin') visible.push('.superadmin-only', '.admin-write', '.reviewer-plus');
        else if (role === 'admin') visible.push('.admin-write', '.reviewer-plus');
        else if (role === 'reviewer') visible.push('.reviewer-plus');
        visible.forEach(sel => {{
          document.querySelectorAll(sel).forEach(el => {{ el.style.display = ''; }});
        }});
      }} catch (e) {{ /* non-critical */ }}
    }})();
    function toggleTheme() {{
      const html = document.documentElement;
      const isDark = html.getAttribute('data-theme') === 'dark';
      html.setAttribute('data-theme', isDark ? 'light' : 'dark');
      localStorage.setItem('solclear-theme', isDark ? 'light' : 'dark');
      updateThemeIcon();
    }}
    function updateThemeIcon() {{
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const sun = document.getElementById('themeIconSun');
      const moon = document.getElementById('themeIconMoon');
      if (sun) sun.style.display = isDark ? 'block' : 'none';
      if (moon) moon.style.display = isDark ? 'none' : 'block';
    }}

    // ── Show-more/less for long reason text ──
    // Palmetto reference photo toggle. Lazy-loads photos on first open
    // so we don't fetch for every requirement on page load.
    async function toggleReferencePhotos(btn, reqCode) {{
      const container = btn.nextElementSibling;  // .req-reference-photos
      if (container.style.display !== 'none') {{
        container.style.display = 'none';
        btn.textContent = '📋 See Palmetto reference';
        return;
      }}
      // Already populated — just show
      if (container.dataset.loaded) {{
        container.style.display = 'flex';
        btn.textContent = '📋 Hide Palmetto reference';
        return;
      }}
      // Fetch from API
      btn.textContent = 'Loading…';
      btn.disabled = true;
      try {{
        const r = await fetch('/api/reference_photos/' + encodeURIComponent(reqCode));
        const data = await r.json();
        const photos = data.photos || [];
        if (!photos.length) {{
          container.innerHTML = '<span class="req-reference-empty">No reference photos available for this requirement.</span>';
        }} else {{
          container.innerHTML = photos.map(p =>
            '<a href="' + p.url + '" target="_blank" onclick="event.stopPropagation()">' +
            '<img src="' + p.url + '" alt="' + (p.alt_text || 'Reference') + '" loading="lazy" title="' + (p.alt_text || 'Palmetto reference photo') + '">' +
            '</a>'
          ).join('');
        }}
        container.dataset.loaded = '1';
        container.style.display = 'flex';
        btn.textContent = '📋 Hide Palmetto reference';
        rewirePhotoLinks(container);  // wire lightbox on dynamically-added photos
      }} catch (e) {{
        container.innerHTML = '<span class="req-reference-empty">Could not load reference photos.</span>';
        container.style.display = 'flex';
        btn.textContent = '📋 See Palmetto reference';
      }} finally {{
        btn.disabled = false;
      }}
    }}

    function toggleReason(btn) {{
      const full = btn.previousElementSibling;
      const short = full.previousElementSibling;
      if (full.style.display === 'none') {{
        full.style.display = 'block';
        short.style.display = 'none';
        btn.innerHTML = 'Show less <span class="arrow">&#9652;</span>';
      }} else {{
        full.style.display = 'none';
        short.style.display = 'block';
        btn.innerHTML = 'Show more <span class="arrow">&#9662;</span>';
      }}
    }}

    // ── Tabs ──
    function filterTab(tab) {{
      document.querySelectorAll('.report-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
      document.querySelectorAll('.requirement').forEach(row => {{
        const status = row.dataset.status;
        const resolved = row.dataset.resolved === '1';
        // Attention tab includes hard failures AND items flagged for review.
        const needsAttention = ['FAIL','MISSING','ERROR','NEEDS_REVIEW'].includes(status);
        let show = false;
        if (tab === 'all') show = true;
        else if (tab === 'passed') show = status === 'PASS';
        else /* attention */ show = needsAttention && !resolved;
        row.style.display = show ? '' : 'none';
      }});
      // Hide empty sections for clarity
      document.querySelectorAll('.section').forEach(sec => {{
        const anyVisible = Array.from(sec.querySelectorAll('.requirement'))
          .some(r => r.style.display !== 'none');
        sec.style.display = anyVisible ? '' : 'none';
      }});
    }}

    // Default tab: if any attention items exist, start there; otherwise show All.
    (function() {{
      const anyAttention = Array.from(document.querySelectorAll('.requirement'))
        .some(r => {{
          const s = r.dataset.status;
          return ['FAIL','MISSING','ERROR','NEEDS_REVIEW'].includes(s) && r.dataset.resolved !== '1';
        }});
      filterTab(anyAttention ? 'attention' : 'all');
    }})();

    // ── Rerun failed items (non-interactive fallback: navigates to SPA) ──
    const RERUN_PARAMS = {rerun_params_js};
    function rerunFailed() {{
      if (!RERUN_PARAMS) return;
      const qs = new URLSearchParams(RERUN_PARAMS);
      window.location.href = "/?rerun=" + encodeURIComponent(qs.toString());
    }}

    // Full re-run for cancelled reports: same params but WITHOUT rerun_ids,
    // so /start runs every applicable requirement from scratch. Button is
    // only rendered on reports where status=='cancelled' (see CTAs block).
    function rerunFull() {{
      if (!RERUN_PARAMS) return;
      if (!confirm('Run the full compliance check again from scratch? This will re-run every requirement, not just the failed ones.')) return;
      const qs = new URLSearchParams(RERUN_PARAMS);
      qs.delete('rerun_ids');
      window.location.href = "/?rerun=" + encodeURIComponent(qs.toString());
    }}

    // ── Interactive report actions ──
    const REPORT_ID = {json.dumps(db_report_id)};
    const IS_INTERACTIVE = {json.dumps(is_interactive)};

    function _updateTabCounts() {{
      const counts = {{attention: 0, passed: 0, all: 0}};
      document.querySelectorAll('.requirement').forEach(r => {{
        const s = r.dataset.status;
        const needsAttention = ['FAIL','MISSING','ERROR','NEEDS_REVIEW'].includes(s);
        const resolved = r.dataset.resolved === '1';
        counts.all++;
        if (s === 'PASS') counts.passed++;
        if (needsAttention && !resolved) counts.attention++;
      }});
      const set = (tab, n) => {{
        const el = document.querySelector('.report-tab[data-tab="' + tab + '"] .count');
        if (el) el.textContent = n;
      }};
      set('attention', counts.attention);
      set('passed', counts.passed);
      set('all', counts.all);
    }}

    async function toggleResolved(btn, reqCode) {{
      if (!IS_INTERACTIVE || !REPORT_ID) return;
      btn.disabled = true;
      try {{
        const r = await fetch('/api/report/' + REPORT_ID + '/item/' + reqCode + '/resolve', {{method: 'POST'}});
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        const row = btn.closest('.requirement');
        const nowResolved = !!data.resolved_at;
        row.dataset.resolved = nowResolved ? '1' : '';
        btn.textContent = nowResolved ? 'Undo resolve' : 'Mark resolved';
        // Update/insert resolved chip in the header
        let chip = row.querySelector('.resolved-chip');
        if (nowResolved) {{
          if (!chip) {{
            chip = document.createElement('span');
            chip.className = 'badge badge-success resolved-chip';
            chip.textContent = 'Resolved';
            row.querySelector('.req-header').appendChild(chip);
          }}
          if (data.resolved_by_name) chip.title = 'Resolved by ' + data.resolved_by_name;
        }} else if (chip) {{
          chip.remove();
        }}
        _updateTabCounts();
        // If on 'attention' tab and the item just got resolved, hide it
        const activeTab = document.querySelector('.report-tab.active')?.dataset.tab;
        if (activeTab === 'attention' && nowResolved) {{ row.style.display = 'none'; }}
      }} catch (e) {{
        alert('Could not update: ' + e.message);
      }} finally {{
        btn.disabled = false;
      }}
    }}

    // Notes are immutable comment-thread style (see project_demo_backlog_ind_solar.md).
    // Add-note flow: click button → textarea appears → Save posts a new
    // note → server returns the full refreshed thread → we replace the
    // thread DOM with the new one. Each author gets their own row; no
    // edit-in-place, no delete. Follow-ups are just another Save click.
    //
    // `visibility` is 'public' (crew + reviewer + admin all see it) or
    // 'dev' (reviewer+ only — bug ticket against Solclear itself).
    // Dev notes have amber styling and a triage pill to distinguish from
    // public notes.
    function openNoteEditor(btn, reqCode, visibility) {{
      if (!IS_INTERACTIVE || !REPORT_ID) return;
      visibility = visibility || 'public';
      const row = btn.closest('.requirement');
      const existing = row.querySelector('.note-editor');
      if (existing) {{ existing.remove(); return; }}
      const isDev = visibility === 'dev';
      const placeholder = isDev
        ? 'Describe the Solclear issue — wrong verdict, bad photo pick, confusing UI, etc. Only you and the dev team see this.'
        : 'Add a note for the crew or reviewer…';
      const submitLabel = isDev ? 'Flag bug' : 'Post note';
      const editor = document.createElement('div');
      editor.className = 'note-editor' + (isDev ? ' note-editor-dev' : '');
      editor.innerHTML =
        '<textarea placeholder="' + placeholder + '"></textarea>' +
        '<div class="note-editor-actions">' +
          '<button class="btn btn-sm ' + (isDev ? 'btn-warning' : 'btn-primary') + '">' + submitLabel + '</button>' +
          '<button class="btn btn-sm btn-subtle">Cancel</button>' +
        '</div>';
      const actions = row.querySelector('.req-actions');
      row.insertBefore(editor, actions);
      const ta = editor.querySelector('textarea');
      ta.focus();
      const [saveBtn, cancelBtn] = editor.querySelectorAll('button');
      cancelBtn.onclick = () => editor.remove();
      saveBtn.onclick = async () => {{
        if (!ta.value.trim()) {{ ta.focus(); return; }}
        saveBtn.disabled = true;
        try {{
          const r = await fetch('/api/report/' + REPORT_ID + '/item/' + reqCode + '/note', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{note: ta.value, visibility: visibility}})
          }});
          const data = await r.json();
          if (data.error) throw new Error(data.error);
          // Replace the entire thread with the refreshed version from
          // server. Includes the new note + any others added concurrently
          // by other users since the page loaded.
          _replaceNotesThread(row, data.notes || []);
          editor.remove();
        }} catch (e) {{
          alert('Could not post note: ' + e.message);
          saveBtn.disabled = false;
        }}
      }};
    }}

    function _replaceNotesThread(row, notes) {{
      let thread = row.querySelector('.req-notes-thread');
      if (!thread) {{
        thread = document.createElement('div');
        thread.className = 'req-notes-thread';
        const actions = row.querySelector('.req-actions');
        row.insertBefore(thread, actions);
      }}
      thread.innerHTML = notes.map(_renderNoteEl).join('');
      // Localize fresh DOM so tooltips/relative format are correct
      // immediately rather than waiting for the next 60s tick.
      localizeTimestamps(thread);
      if (!notes.length) thread.remove();
    }}

    function _renderNoteEl(n) {{
      const author = _esc(n.author_name || n.author_email || 'Unknown author');
      const iso = n.created_at || '';
      // Emit <time class="ts-relative"> so the periodic localizeTimestamps()
      // tick keeps the relative age fresh ("just now" → "1 min ago" → ...)
      // for as long as the user has the page open.
      const timeHtml = iso
        ? '<time class="ts-relative req-note-time" datetime="' + _esc(iso) + '">' + _esc(formatTimestamp(iso)) + '</time>'
        : '';
      const body = _esc(n.body || '');
      const isDev = n.visibility === 'dev';
      const visCls = isDev ? 'note-dev' : 'note-public';
      let devPill = '';
      if (isDev) {{
        const s = (n.dev_status || 'open').toLowerCase();
        devPill = '<span class="note-dev-pill note-dev-' + _esc(s) + '">' + _esc(s.toUpperCase()) + '</span>';
      }}
      return (
        '<div class="req-note ' + visCls + '">' +
          '<div class="req-note-meta">' +
            '<span class="req-note-author">' + author + '</span>' +
            timeHtml +
            devPill +
          '</div>' +
          '<div class="req-note-body">' + body + '</div>' +
        '</div>'
      );
    }}

    // ── Timestamp localization ──
    // Renders a UTC timestamp in the viewer's local tz, with a relative
    // form ("5 min ago") for recent values and an absolute form
    // ("Apr 17, 2:15 PM") for older. Browser's tz is auto-detected via
    // Intl — no user setup required.
    //
    // Server-rendered timestamps use <time class="ts-relative" datetime="UTC_ISO">
    // with a UTC fallback as text. localizeTimestamps() walks the DOM,
    // rewrites textContent + sets a tooltip with the full absolute. Runs
    // on load + after DOM mutations + every 60s so relative ages stay fresh.
    function formatTimestamp(input, opts) {{
      if (!input) return '';
      opts = opts || {{}};
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
    }}
    function formatTimestampAbsolute(input) {{
      return formatTimestamp(input, {{absolute: true}});
    }}
    function _absoluteString(d, ageMs) {{
      const opts = {{month:'short', day:'numeric', hour:'numeric', minute:'2-digit'}};
      // Include year only when it's an old timestamp — keeps recent
      // notes scannable while disambiguating archival ones.
      if (ageMs > 365 * 24 * 60 * 60 * 1000) opts.year = 'numeric';
      return d.toLocaleString('en-US', opts);
    }}
    function _toDate(input) {{
      if (input == null) return null;
      if (input instanceof Date) return input;
      if (typeof input === 'number') {{
        // Heuristic: < 1e11 => epoch seconds (year ≤ ~5138), else ms
        return new Date(input < 1e11 ? input * 1000 : input);
      }}
      return new Date(input);
    }}
    function localizeTimestamps(root) {{
      root = root || document;
      root.querySelectorAll('time.ts-relative').forEach(function(el) {{
        const iso = el.getAttribute('datetime');
        if (!iso) return;
        el.textContent = formatTimestamp(iso);
        el.title = formatTimestampAbsolute(iso);
      }});
    }}
    document.addEventListener('DOMContentLoaded', function() {{ localizeTimestamps(); }});
    // Refresh relative ages every 60s so "5 min ago" doesn't go stale
    // while a user has the page open. Cheap — pure DOM walk, no network.
    setInterval(function() {{ localizeTimestamps(); }}, 60000);

    // Legacy alias — used by _renderNoteEl below. Returns a relative-or-
    // absolute string in the viewer's local tz, same as <time> elements
    // render once localizeTimestamps runs.
    function _fmtNoteTime(iso) {{ return formatTimestamp(iso); }}

    function _esc(s) {{
      const div = document.createElement('div');
      div.textContent = s == null ? '' : String(s);
      return div.innerHTML;
    }}

    // ── Lightbox ──
    function openLightbox(url) {{
      const lb = document.getElementById('photoLightbox');
      const img = document.getElementById('photoLightboxImg');
      if (!lb || !img) return;
      img.src = url;
      lb.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }}
    function closeLightbox(ev) {{
      // Only close when clicking the backdrop (not the image itself)
      if (ev && ev.target === document.getElementById('photoLightboxImg')) return;
      const lb = document.getElementById('photoLightbox');
      if (lb) lb.style.display = 'none';
      document.body.style.overflow = '';
    }}
    document.addEventListener('keydown', function(e) {{
      if (e.key === 'Escape') closeLightbox();
    }});
    // Intercept all photo links on the page and open lightbox instead
    // of a new tab. Runs after DOM is ready; also called after dynamic
    // content is injected (reference photos, etc.).
    function rewirePhotoLinks(root) {{
      root = root || document;
      root.querySelectorAll('a.req-photo-link, .req-reference-photos a').forEach(function(a) {{
        if (a.dataset.lightboxWired) return;
        a.dataset.lightboxWired = '1';
        a.addEventListener('click', function(e) {{
          e.preventDefault();
          e.stopPropagation();
          openLightbox(a.href);
        }});
      }});
    }}
    document.addEventListener('DOMContentLoaded', function() {{ rewirePhotoLinks(); }});

    async function recheckItem(btn, reqCode) {{
      if (!IS_INTERACTIVE || !REPORT_ID) return;
      const row = btn.closest('.requirement');
      row.classList.add('req-rechecking');
      // Swap the status badge to a "RUNNING" pill with a pulsing dot so
      // the user sees the row state changed, not just a faded button.
      const badge = row.querySelector('.badge');
      const _origBadgeClass = badge ? badge.className : '';
      const _origBadgeText  = badge ? badge.textContent : '';
      if (badge) {{
        badge.className = 'badge badge-running';
        badge.textContent = 'RUNNING';
      }}
      // Spinner inside the button itself so the click target shows progress.
      const _origBtnHTML = btn.innerHTML;
      btn.innerHTML = '<span class="btn-spinner"></span>Re-checking…';
      btn.disabled = true;
      try {{
        const r = await fetch('/api/recheck/' + REPORT_ID + '/' + reqCode, {{method: 'POST'}});
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        // Update row visuals without a page reload
        const newStatus = data.status || '';
        row.dataset.status = newStatus;
        row.className = 'requirement req-' + newStatus.toLowerCase();
        // Update badge (class + display label)
        const badge = row.querySelector('.badge');
        if (badge) {{
          const cfg = {{PASS:'pass', FAIL:'fail', MISSING:'missing', ERROR:'error', NEEDS_REVIEW:'needs_review'}};
          const labels = {{PASS:'PASS', FAIL:'FAIL', MISSING:'MISSING', ERROR:'ERROR', NEEDS_REVIEW:'NEEDS REVIEW'}};
          const cls = cfg[newStatus] || 'na';
          badge.className = 'badge badge-' + cls;
          badge.textContent = labels[newStatus] || newStatus;
        }}
        // Resolved state is cleared server-side on recheck
        row.dataset.resolved = '';
        const chip = row.querySelector('.resolved-chip');
        if (chip) chip.remove();
        const resolveBtn = row.querySelector('[data-role="resolve-btn"]');
        if (resolveBtn) resolveBtn.textContent = 'Mark resolved';
        _updateTabCounts();
        // Update only THIS row's visibility for the active tab — avoids
        // calling filterTab() which rebuilds the entire list, loses scroll
        // position, and closes any open lightbox or note editor.
        const activeTab = document.querySelector('.report-tab.active')?.dataset.tab;
        if (activeTab && activeTab !== 'all') {{
          const isAttention = ['FAIL','MISSING','ERROR','NEEDS_REVIEW'].includes(newStatus);
          const show = (activeTab === 'attention') ? isAttention
                     : (activeTab === 'passed')    ? newStatus === 'PASS'
                     : true;
          row.style.display = show ? '' : 'none';
        }}
      }} catch (e) {{
        alert('Could not re-check: ' + e.message);
        // Restore the original badge so the row goes back to its prior state.
        if (badge) {{
          badge.className = _origBadgeClass;
          badge.textContent = _origBadgeText;
        }}
      }} finally {{
        row.classList.remove('req-rechecking');
        btn.innerHTML = _origBtnHTML;
        btn.disabled = false;
      }}
    }}
    """


def generate_html(report: dict, project: dict) -> str:
    reqs = report.get("requirements", [])
    params = report.get("params", {})
    project_id = report.get("project_id", "")
    db_report_id = report.get("db_report_id")
    is_interactive = bool(db_report_id)

    name = project.get("name") or f"Project {project_id}"
    address = project.get("address", {}) or {}
    addr_str = ", ".join(filter(None, [
        address.get("street_address_1"),
        address.get("city"),
        address.get("state"),
    ]))
    # Render-time timestamp wrapped in <time> so the client localizes
    # to the user's tz. Server fallback is UTC for clarity if JS doesn't
    # run. Use timezone-aware UTC datetime so the ISO string includes
    # offset and the client knows the source tz.
    from datetime import datetime, timezone
    _gen_dt = datetime.now(timezone.utc)
    generated_iso = _gen_dt.isoformat()
    generated_fallback = _gen_dt.strftime("%B %-d, %Y at %H:%M UTC")
    generated = f'<time class="ts-relative" datetime="{_esc(generated_iso)}">{_esc(generated_fallback)}</time>'

    required = [r for r in reqs if r["status"] != "N/A" and not r.get("optional")]
    n_pass    = sum(1 for r in required if r["status"] == "PASS")
    n_fail    = sum(1 for r in required if r["status"] == "FAIL")
    n_missing = sum(1 for r in required if r["status"] == "MISSING")
    n_error   = sum(1 for r in required if r["status"] == "ERROR")
    n_review  = sum(1 for r in required if r["status"] == "NEEDS_REVIEW")
    n_total   = len(required)
    n_attention = n_fail + n_missing + n_error + n_review

    # "Ready for submission" only when there's nothing left needing a human.
    # The summary-fail rail covers both hard failures and review items —
    # they both block ready state, though only hard failures are red.
    # Running reports take precedence over the usual labels — no point
    # telling a user their check is "ready for submission" when half
    # the requirements haven't run yet.
    is_running_status = report.get("status") == "running"
    summary_class = "summary-pass" if n_attention == 0 else "summary-fail"
    if is_running_status:
        summary_label = "CHECK IN PROGRESS"
        summary_class = "summary-fail"  # gray/amber rail feels right while running
    elif n_fail + n_missing + n_error > 0:
        summary_label = "ACTION REQUIRED"
    elif n_review > 0:
        summary_label = "REVIEW REQUIRED"
    else:
        summary_label = "READY FOR SUBMISSION"
    pct = round((n_pass / n_total) * 100) if n_total else 0

    checklist_ids = report.get("checklist_ids", []) or []
    checklist_id = checklist_ids[0] if checklist_ids else ""
    cc_url = (
        f"https://app.companycam.com/projects/{project_id}/todos/{checklist_id}"
        if checklist_ids and project_id else ""
    )

    # Group by section, preserving first-seen order
    sections: dict = {}
    for r in reqs:
        sections.setdefault(r["section"], []).append(r)
    sections_html = "".join(
        render_section(sec, secreqs, is_interactive, checklist_id, project_id)
        for sec, secreqs in sections.items()
    )

    # Collect failed IDs for the "rerun failed" action
    failed_ids = [
        r["id"] for r in reqs
        if r.get("status") in ("FAIL", "MISSING", "ERROR") and r.get("status") != "N/A"
    ]

    # CTAs
    # Cancelled reports get an extra "Run full check again" button because
    # "Re-run failed items" only covers the FAILURES from the partial set —
    # it doesn't cover requirements that were never attempted due to the
    # cancel. Completed reports don't need this (re-running a complete
    # report from scratch is rare and wasteful).
    is_cancelled = report.get("status") == "cancelled"
    ctas = []
    if cc_url:
        ctas.append(f'<a href="{_esc(cc_url)}" target="_blank" class="btn btn-primary">Open in CompanyCam ↗</a>')
    if is_cancelled and is_interactive:
        ctas.append('<button class="btn btn-ghost" onclick="rerunFull()">Run full check again</button>')
    if failed_ids:
        ctas.append(f'<button class="btn btn-ghost" onclick="rerunFailed()">Re-run {len(failed_ids)} failed item{"s" if len(failed_ids) != 1 else ""}</button>')
    ctas_html = "".join(ctas)

    # Pre-compute chips (only show chips with counts > 0 to reduce noise)
    chips = []
    chips.append(f'<span class="chip chip-pass">✓ {n_pass} passed</span>')
    if n_fail:    chips.append(f'<span class="chip chip-fail">✗ {n_fail} failed</span>')
    if n_missing: chips.append(f'<span class="chip chip-missing">⊘ {n_missing} missing</span>')
    if n_review:  chips.append(f'<span class="chip chip-review">⟳ {n_review} review</span>')
    if n_error:   chips.append(f'<span class="chip chip-error">⚠ {n_error} error</span>')
    chips_html = "".join(chips)

    ring_dasharray = round(2 * 3.14159 * 18, 1)
    ring_dashoffset = round(2 * 3.14159 * 18 * (1 - pct / 100), 1)

    style = DESIGN_TOKENS_CSS + _report_style_block()
    script = _report_script_block(db_report_id, is_interactive, cc_url, failed_ids, params,
                                  project_id, checklist_ids, is_cancelled=is_cancelled)

    # Auto-refresh while a check is still running so a user who reconnected
    # mid-run sees partial results accumulate without manual reloads. 10s
    # balances "catches new requirements quickly" against "doesn't hammer
    # the server." Stops once status flips to complete/cancelled — no
    # refresh needed on a frozen report.
    is_running = report.get("status") == "running"
    refresh_meta = '<meta http-equiv="refresh" content="10">' if is_running else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  {refresh_meta}
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <title>M1 Compliance — {_esc(name)}</title>
  <style>{style}</style>
</head>
<body>

  <header class="report-topbar">
    <a href="/"><span>&larr;</span> Back to Solclear</a>
    <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark mode">
      <svg id="themeIconSun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      <svg id="themeIconMoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:none;"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    </button>
  </header>

  <div class="report-summary {summary_class}">
    <div class="summary-inner">
      <div class="summary-main">
        <svg class="summary-ring" width="52" height="52" viewBox="0 0 44 44">
          <circle class="ring-bg" cx="22" cy="22" r="18"/>
          <circle class="ring-fill" cx="22" cy="22" r="18"
            stroke-dasharray="{ring_dasharray}"
            stroke-dashoffset="{ring_dashoffset}"/>
          <text class="ring-text" x="22" y="22">{pct}%</text>
        </svg>
        <div class="summary-text">
          <div class="summary-headline">{(f"{n_pass} passed so far · " + summary_label + " · auto-refreshing") if is_running_status else (f"{n_pass} of {n_total} passed · " + summary_label)}</div>
          <div class="summary-project">{_esc(name)}{(' — ' + _esc(addr_str)) if addr_str else ''}</div>
          <div class="summary-chips">{chips_html}</div>
        </div>
      </div>
      <div class="summary-ctas">{ctas_html}</div>
    </div>
  </div>

  <nav class="report-tabs">
    <button class="report-tab" data-tab="attention" onclick="filterTab('attention')">Needs attention <span class="count">{n_attention}</span></button>
    <button class="report-tab" data-tab="passed" onclick="filterTab('passed')">Passed <span class="count">{n_pass}</span></button>
    <button class="report-tab" data-tab="all" onclick="filterTab('all')">All <span class="count">{n_total}</span></button>
  </nav>

  <div class="report-body">
    {sections_html}
  </div>

  <div class="report-footer">
    Solclear Compliance &middot; Palmetto LightReach M1 &middot; {generated} &middot; ID: {_esc(project_id)}
  </div>

  <!-- Lightbox overlay — shown when user clicks any photo. Avoids
       opening a new tab for every inspection. Closed by clicking the
       backdrop, the X button, or pressing Escape. -->
  <div id="photoLightbox" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:999;align-items:center;justify-content:center;" onclick="closeLightbox(event)">
    <button onclick="closeLightbox()" aria-label="Close" style="position:absolute;top:16px;right:20px;background:none;border:none;color:#fff;font-size:28px;cursor:pointer;line-height:1;padding:4px 8px;opacity:0.8;">&#x2715;</button>
    <img id="photoLightboxImg" src="" alt="" style="max-width:90vw;max-height:88vh;object-fit:contain;border-radius:6px;box-shadow:0 8px 40px rgba(0,0,0,0.6);" onclick="event.stopPropagation()">
  </div>

  <script>{script}</script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate HTML compliance report")
    parser.add_argument("--project_id", required=True)
    parser.add_argument("--no_open", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    report_path = TMP_DIR / f"compliance_{args.project_id}.json"
    if not report_path.exists():
        print(f"ERROR: {report_path} not found. Run compliance_check.py first.", file=sys.stderr)
        sys.exit(1)

    with open(report_path) as f:
        report = json.load(f)

    print(f"Fetching project details...", file=sys.stderr)
    project = fetch_project(args.project_id)

    html = generate_html(report, project)

    output_path = TMP_DIR / f"report_{args.project_id}.html"
    with open(output_path, "w") as f:
        f.write(html)

    print(f"Report saved to {output_path}", file=sys.stderr)

    if not args.no_open:
        webbrowser.open(output_path.resolve().as_uri())


if __name__ == "__main__":
    main()
