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


def _render_note(note: dict, is_interactive: bool = False, code: str = "") -> str:
    """Render one note row in the comment thread. Notes are immutable, so
    there's no edit/delete UI — just author, timestamp, and body.

    Timestamp is wrapped in <time datetime="UTC_ISO" class="ts-relative">
    with a UTC fallback as text content. The client-side localizeTimestamps()
    rewrites it to the user's local timezone with relative-or-absolute
    formatting on page load (and after any DOM mutation that adds notes).

    Dev-visibility notes get the `note-dev` modifier class so reviewers
    can distinguish their bug-tracker comments from public crew notes.
    A pill shows the dev-status ('open', 'acknowledged', 'corrected')
    when present. `is_reply` renders the note indented without status pill.
    `code` is needed to wire the Reply button onclick."""
    author = note.get("author_name") or note.get("author_email") or "Unknown author"
    iso = note.get("created_at", "") or ""
    fallback = _format_note_timestamp_utc_fallback(iso)
    body = _esc(note.get("body", ""))
    visibility = note.get("visibility") or "public"
    is_reply = bool(note.get("parent_note_id"))
    visibility_cls = "note-dev" if visibility == "dev" else "note-public"
    reply_cls = " note-reply" if is_reply else ""
    dev_pill = ""
    if visibility == "dev" and not is_reply:
        status = note.get("dev_status") or "open"
        dev_pill = f'<span class="note-dev-pill note-dev-{_esc(status)}">{_esc(status.upper())}</span>'
    time_html = (
        f'<time class="ts-relative req-note-time" datetime="{_esc(iso)}">{_esc(fallback)}</time>'
        if iso else ""
    )
    # Reply button — only on top-level dev notes in interactive reports
    reply_btn = ""
    note_id = note.get("id", "")
    reply_btn = ""
    if visibility == "dev" and not is_reply and is_interactive and code:
        reply_btn = (
            f'<button class="btn-note-reply reviewer-plus" style="display:none;" '
            f'data-reply-note-id="{note_id}" data-reply-req-code="{_esc(code)}" '
            f'onclick="event.stopPropagation();openReplyEditor(this.dataset.replyNoteId,this.dataset.replyReqCode)">'
            f'Reply</button>'
        )
    note_id_label = (
        f'<span style="font-size:10px;opacity:0.5;margin-left:2px;">#{note_id}</span>'
        if visibility == "dev" and not is_reply and note_id else ""
    )
    return (
        f'<div class="req-note {visibility_cls}{reply_cls}" data-note-id="{_esc(str(note_id))}">'
        f'<div class="req-note-meta">'
        f'<span class="req-note-author">{_esc(author)}</span>'
        f'{note_id_label}'
        f'{time_html}'
        f'{dev_pill}'
        f'{reply_btn}'
        f'</div>'
        f'<div class="req-note-body">{body}</div>'
        f'</div>'
    )


def render_requirement(req: dict, is_interactive: bool, checklist_id: str, project_id: str) -> str:
    status = req.get("status", "")
    code = req.get("id", "")
    photo_urls = req.get("photo_urls", {}) or {}
    photo_captions = req.get("photo_captions", {}) or {}
    is_failure = status in _FAILURE_STATUSES or status == "NEEDS_REVIEW"
    is_resolved = bool(req.get("resolved_at"))
    is_manually_verified = bool(req.get("manually_verified"))

    optional_tag = '<span class="optional-tag">optional</span>' if req.get("optional") else ""

    # Reason — full text always rendered; CSS line-clamp handles truncation.
    # JS (initExpandableReasons) detects overflow after load and injects the
    # gradient-fade + "Read more" pill only when text actually overflows.
    # On desktop wide lines mean fewer overflows; mobile benefits most.
    reason_html = ""
    if status not in ("PASS", "N/A", "FOUND_NO_VISION") and req.get("reason"):
        full_linked = linkify_photos(req["reason"], photo_urls)
        reason_html = f'<div class="reason-expandable" onclick="expandReason(event, this)">{full_linked}</div>'

    # Photo display — single thumbnail for one evidence photo, grid for multiple.
    # photo_urls keys are 1-based; key 1 is always the primary/winner photo.
    sorted_keys = sorted(photo_urls.keys(), key=lambda k: int(k) if str(k).isdigit() else 0)
    evidence_pairs = [
        (k, url)
        for k in sorted_keys
        if (url := (photo_urls.get(k) or photo_urls.get(str(k))))
    ][:4]
    photo_html = ""
    if evidence_pairs and status not in ("N/A", "FOUND_NO_VISION"):
        def _caption_attr(rank_key):
            cap = photo_captions.get(rank_key) or photo_captions.get(str(rank_key))
            return f' data-caption="{_esc(cap)}"' if cap else ""

        if len(evidence_pairs) == 1:
            k, u = evidence_pairs[0]
            photo_html = (
                f'<a href="{_esc(u)}" target="_blank" class="req-photo-link"{_caption_attr(k)}>'
                f'<img src="{_esc(u)}" alt="Evaluated photo" loading="lazy" class="req-photo">'
                f'</a>'
            )
        else:
            grid_items = "".join(
                f'<a href="{_esc(u)}" target="_blank" class="req-photo-link"{_caption_attr(k)} style="flex:1;min-width:0;">'
                f'<img src="{_esc(u)}" alt="Evidence photo" loading="lazy" '
                f'style="width:100%;height:72px;object-fit:cover;border-radius:4px;display:block;">'
                f'</a>'
                for k, u in evidence_pairs
            )
            photo_html = (
                f'<div style="display:flex;gap:4px;margin-top:4px;">{grid_items}</div>'
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
        # Group replies under their parent notes
        top_level = [n for n in notes_thread if not n.get("parent_note_id")]
        replies_by_parent: dict = {}
        for n in notes_thread:
            pid = n.get("parent_note_id")
            if pid:
                replies_by_parent.setdefault(pid, []).append(n)
        parts = []
        for n in top_level:
            parts.append(_render_note(n, is_interactive=is_interactive, code=code))
            for reply in replies_by_parent.get(n.get("id"), []):
                parts.append(_render_note(reply, is_interactive=is_interactive, code=code))
        note_html = '<div class="req-notes-thread">' + "".join(parts) + '</div>'

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
        actions_html = f'''
      <div class="req-actions">
        {cc_btn}
        {resolve_btn}
        <button class="btn btn-sm btn-subtle" onclick="event.stopPropagation();openNoteEditor(this, '{_esc(code)}', 'public')">Add note</button>
        <button class="btn btn-sm btn-subtle reviewer-plus" style="display:none;" onclick="event.stopPropagation();openNoteEditor(this, '{_esc(code)}', 'dev')">Flag bug</button>
        <button class="btn btn-sm btn-subtle reviewer-plus" style="display:none;border-color:var(--accent);color:var(--accent);" onclick="event.stopPropagation();openPhotoPicker('{_esc(code)}', '{_esc(req.get('title',''))}')">Select photo</button>
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();recheckItem(this, '{_esc(code)}')">Re-check</button>
      </div>'''

    # PASS rows start collapsed so the page leads with failures
    # PASS rows start collapsed by default — but if the thread has any
    # notes, keep it expanded so conversation is visible at a glance.
    collapsed_class = " collapsed" if status == "PASS" and not notes_thread else ""
    click_handler = ' onclick="this.classList.toggle(\'collapsed\')"' if status == "PASS" else ""

    manual_badge = '<span class="badge badge-info" style="font-size:10px;margin-left:4px;" title="Photo selected manually by a reviewer">Manual</span>' if is_manually_verified else ""
    resolved_data = ' data-resolved="1"' if is_resolved else ""
    manually_verified_data = ' data-manually-verified="1"' if is_manually_verified else ""
    return f'''
    <div class="requirement req-{status.lower()}{collapsed_class}" data-status="{_esc(status)}" data-id="{_esc(code)}"{resolved_data}{manually_verified_data}{click_handler}>
      <div class="req-header">
        {status_badge(status)}
        {resolved_chip}
        {manual_badge}
        <span class="req-id">{_esc(code)}</span>
        <span class="req-title">{_esc(req.get("title", ""))}</span>
        {optional_tag}
      </div>
      <div data-role="photo-container">{photo_html}</div>
      <div data-role="reason-container">{reason_html}</div>
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

    # Render in natural requirement code order so "All" tab is predictable.
    # "Needs attention" tab filters by JS show/hide without reordering.
    rows = "".join(render_requirement(r, is_interactive, checklist_id, project_id) for r in applicable)

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
      background: none; border: none; color: #fff; cursor: pointer;
      width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
      border-radius: 8px;
    }
    .theme-toggle:hover { background: rgba(128,128,128,0.2); }
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
    .requirement.collapsed .reason-expandable,
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

    .req-photo-link { display: block; margin-top: 10px; position: relative; }
    .req-photo {
      display: block; max-width: 100%;
      border-radius: 6px; border: 2px solid var(--border);
    }
    @media (min-width: 640px) { .req-photo { max-width: 280px; } }

    /* Hover tooltip for photo selection reasoning */
    .req-photo-link[data-caption]::after {
      content: attr(data-caption);
      position: absolute;
      bottom: calc(100% + 6px);
      left: 0;
      background: rgba(0,0,0,0.88);
      color: #fff;
      font-size: 11px;
      line-height: 1.5;
      padding: 6px 10px;
      border-radius: 6px;
      white-space: normal;
      width: 220px;
      z-index: 200;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.15s;
    }
    .req-photo-link[data-caption]:hover::after { opacity: 1; }

    .reason {
      margin-top: 8px; font-size: var(--text-sm); color: var(--text-secondary);
      line-height: 1.6; padding-left: 10px;
      border-left: 2px solid var(--border-light);
    }
    /* Expandable reason text — CSS line-clamp truncates on mobile;
       JS adds the gradient + pill only when text actually overflows.
       Desktop wide lines rarely overflow 3 lines so the pill stays hidden. */
    .reason-expandable {
      display: -webkit-box;
      -webkit-line-clamp: 5;
      -webkit-box-orient: vertical;
      overflow: hidden;
      cursor: pointer;
      position: relative;
      margin-top: 6px;
      font-size: var(--text-sm);
      color: var(--text-secondary);
      line-height: 1.55;
      user-select: none;
    }
    .reason-expandable.expanded {
      display: block;
      overflow: visible;
      cursor: default;
    }
    .reason-expandable .reason-fade {
      position: absolute; bottom: 0; left: 0; right: 0;
      height: 2.8em; pointer-events: none;
      background: linear-gradient(transparent, var(--bg-card));
    }
    .reason-expandable.expanded .reason-fade { display: none; }
    .reason-expandable .read-more-pill {
      position: absolute; bottom: 0; right: 0;
      background: var(--bg-card);
      color: var(--accent);
      font-size: 11px; font-weight: 600;
      padding: 2px 10px; border-radius: 10px;
      border: 1px solid var(--border);
      cursor: pointer; pointer-events: auto;
    }
    .reason-expandable.expanded .read-more-pill { display: none; }
    /* Requirement collapsed — hide reason entirely */
    .requirement.collapsed .reason-expandable { display: none; }

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
    .req-note.note-reply {
      margin-left: 20px; margin-top: 4px;
      border-left-color: var(--border); background: var(--bg-card);
      font-size: var(--text-xs);
    }
    .btn-note-reply {
      margin-left: auto; background: none;
      border: 1px solid currentColor; border-radius: 4px;
      color: var(--text-secondary); font-size: 11px; cursor: pointer;
      padding: 2px 8px; font-weight: 500; white-space: nowrap; opacity: 0.75;
    }
    .btn-note-reply:hover { opacity: 1; color: var(--accent); }
    /* On dev notes (amber bg), use the warning text color so button is legible */
    .note-dev .btn-note-reply { color: var(--warning-text); }
    .note-dev .btn-note-reply:hover { color: var(--warning-text); opacity: 1; }
    .note-reply-editor {
      margin-left: 20px; margin-top: 4px;
      padding: 8px 10px; background: var(--bg-card);
      border-radius: 6px; border: 1px solid var(--border);
    }
    .note-reply-editor textarea {
      width: 100%; min-height: 56px; resize: vertical;
      background: var(--bg); border: 1px solid var(--border);
      border-radius: 4px; padding: 6px 8px; font-size: var(--text-xs);
      color: var(--text); font-family: inherit;
    }
    .note-reply-editor-actions {
      display: flex; gap: 6px; justify-content: flex-end; margin-top: 6px;
    }
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

    // ── Expandable reason text ──
    // CSS line-clamp handles the visual truncation. initExpandableReasons()
    // detects which elements are actually overflowing and injects the gradient
    // fade + "Read more ↓" pill. expandReason() handles the click-to-expand.
    function initExpandableReasons() {{
      document.querySelectorAll('.reason-expandable').forEach(function(el) {{
        // Skip already-processed elements
        if (el.dataset.initialized) return;
        el.dataset.initialized = '1';
        // Only add UI if content actually overflows the clamped height.
        // +4px tolerance for sub-pixel rounding.
        if (el.scrollHeight <= el.clientHeight + 4) return;
        el.classList.add('clamped');
        const fade = document.createElement('div');
        fade.className = 'reason-fade';
        const pill = document.createElement('span');
        pill.className = 'read-more-pill';
        pill.textContent = 'Read more ↓';
        el.appendChild(fade);
        el.appendChild(pill);
      }});
    }}
    function expandReason(event, el) {{
      // Let link clicks inside the reason pass through normally
      if (event.target.tagName === 'A') return;
      // Only expand if actually clamped
      if (!el.classList.contains('clamped')) return;
      event.stopPropagation();  // don't collapse the requirement row
      el.classList.add('expanded');
    }}
    // Run on load + re-run after fonts settle (fonts affect clientHeight)
    document.addEventListener('DOMContentLoaded', function() {{
      initExpandableReasons();
      setTimeout(initExpandableReasons, 300);
    }});

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

    // ── Photo picker ────────────────────────────────────────────────────────
    let _pickerReqCode = null;
    let _pickerAllPhotos = [];
    let _pickerSelected = {{}};   // photoId -> photo object
    let _pickerPhotoMap = {{}};   // photoId -> photo object (all loaded photos)

    async function openPhotoPicker(reqCode, reqTitle) {{
      if (!IS_INTERACTIVE || !REPORT_ID) return;
      _pickerReqCode = reqCode;
      _pickerSelected = {{}};
      _pickerPhotoMap = {{}};
      document.getElementById('pickerReqTitle').textContent = reqTitle || reqCode;
      document.getElementById('pickerRunBtn').disabled = true;
      document.getElementById('pickerSelCount').textContent = '';
      document.getElementById('pickerGrid').innerHTML = '<div style="color:var(--text-muted);font-size:13px;grid-column:1/-1;padding:24px 0;text-align:center;">Loading photos…</div>';
      document.getElementById('photoPickerOverlay').style.display = 'flex';
      document.body.style.overflow = 'hidden';
      try {{
        const r = await fetch('/api/report/' + REPORT_ID + '/photos');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();
        const groups = data.groups || [];
        const ungrouped = data.ungrouped || [];
        // Flatten all photos into the map for selection lookup
        groups.forEach(function(g) {{
          g.photos.forEach(function(p) {{ _pickerPhotoMap[p.id] = p; }});
        }});
        ungrouped.forEach(function(p) {{ _pickerPhotoMap[p.id] = p; }});
        renderPickerGrouped(groups, ungrouped);
      }} catch (e) {{
        document.getElementById('pickerGrid').innerHTML =
          '<div style="color:var(--danger);font-size:13px;grid-column:1/-1;padding:24px 0;text-align:center;">Could not load photos: ' + _esc(e.message) + '</div>';
      }}
    }}

    function closePhotoPicker() {{
      document.getElementById('photoPickerOverlay').style.display = 'none';
      document.body.style.overflow = '';
    }}

    function _pickerPhotoHtml(p) {{
      const sel = _pickerSelected[p.id] ? 'outline:3px solid var(--accent);outline-offset:-2px;' : '';
      const check = _pickerSelected[p.id]
        ? '<div style="position:absolute;top:3px;right:3px;background:var(--accent);color:#fff;border-radius:50%;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;pointer-events:none;">✓</div>'
        : '';
      return [
        '<div data-picker-id="', _esc(p.id), '"',
        ' onclick="togglePickerPhoto(this.dataset.pickerId)"',
        ' style="position:relative;cursor:pointer;border-radius:6px;overflow:hidden;width:96px;height:96px;flex-shrink:0;', sel, '">',
        '<img src="', _esc(p.thumbnail_url), '" loading="lazy" style="width:100%;height:100%;object-fit:cover;display:block;">',
        check,
        '</div>'
      ].join('');
    }}

    function _pickerSectionHtml(label) {{
      return '<div style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin:16px 0 8px;padding-bottom:4px;border-bottom:1px solid var(--border);">' + _esc(label) + '</div>';
    }}

    function renderPickerGrouped(groups, ungrouped) {{
      const grid = document.getElementById('pickerGrid');
      if (!groups.length && !ungrouped.length) {{
        grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:24px 0;text-align:center;">No photos in cache — run a full check first.</div>';
        return;
      }}
      let html = '';
      groups.forEach(function(g) {{
        const label = g.section && g.task ? g.section + ' · ' + g.task : (g.section || g.task || 'Task');
        html += _pickerSectionHtml(label);
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        g.photos.forEach(function(p) {{ html += _pickerPhotoHtml(p); }});
        html += '</div>';
      }});
      if (ungrouped.length) {{
        html += _pickerSectionHtml('All other photos');
        html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
        ungrouped.forEach(function(p) {{ html += _pickerPhotoHtml(p); }});
        html += '</div>';
      }}
      grid.innerHTML = html;
    }}

    function togglePickerPhoto(photoId) {{
      if (_pickerSelected[photoId]) {{
        delete _pickerSelected[photoId];
      }} else {{
        if (Object.keys(_pickerSelected).length >= 4) {{
          alert('Maximum 4 photos can be selected.');
          return;
        }}
        _pickerSelected[photoId] = _pickerPhotoMap[photoId];
      }}
      const n = Object.keys(_pickerSelected).length;
      document.getElementById('pickerRunBtn').disabled = n === 0;
      document.getElementById('pickerSelCount').textContent = n > 0 ? n + ' selected' : '';
      // Update checkmark overlays in place without re-fetching
      document.querySelectorAll('[data-picker-id]').forEach(function(el) {{
        const pid = el.dataset.pickerId;
        const sel = !!_pickerSelected[pid];
        el.style.outline = sel ? '3px solid var(--accent)' : '';
        el.style.outlineOffset = sel ? '-2px' : '';
        let check = el.querySelector('.picker-check');
        if (sel && !check) {{
          check = document.createElement('div');
          check.className = 'picker-check';
          check.style.cssText = 'position:absolute;top:3px;right:3px;background:var(--accent);color:#fff;border-radius:50%;width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;pointer-events:none;';
          check.textContent = '✓';
          el.appendChild(check);
        }} else if (!sel && check) {{
          check.remove();
        }}
      }});
    }}

    async function runCheckWithSelectedPhotos() {{
      if (!_pickerReqCode || Object.keys(_pickerSelected).length === 0) return;
      const runBtn = document.getElementById('pickerRunBtn');
      runBtn.disabled = true;
      runBtn.textContent = 'Running…';
      const ids = Object.keys(_pickerSelected);
      const row = document.querySelector('.requirement[data-id="' + _pickerReqCode + '"]');
      closePhotoPicker();
      // Show running state on the requirement row so the user knows the check is active
      const _pickerBadge = row ? row.querySelector('.badge:not(.badge-info):not(.resolved-chip)') : null;
      const _pickerOrigClass = _pickerBadge ? _pickerBadge.className : '';
      const _pickerOrigText  = _pickerBadge ? _pickerBadge.textContent : '';
      if (row) {{
        row.classList.add('req-rechecking');
        if (_pickerBadge) {{ _pickerBadge.className = 'badge badge-running'; _pickerBadge.textContent = 'RUNNING'; }}
      }}
      try {{
        const r = await fetch('/api/recheck/' + REPORT_ID + '/' + encodeURIComponent(_pickerReqCode), {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{manual_photo_ids: ids}}),
        }});
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        // Reuse recheckItem update logic to refresh the row
        if (row) _applyRecheckResult(row, data);
      }} catch (e) {{
        alert('Photo check failed: ' + e.message);
        if (row) row.classList.remove('req-rechecking');
        if (_pickerBadge) {{ _pickerBadge.className = _pickerOrigClass; _pickerBadge.textContent = _pickerOrigText; }}
      }} finally {{
        runBtn.textContent = 'Run check';
        runBtn.disabled = false;
      }}
    }}

    function _applyRecheckResult(row, data) {{
      const newStatus = data.status || '';
      row.dataset.status = newStatus;
      row.className = 'requirement req-' + newStatus.toLowerCase();
      const badge = row.querySelector('.badge:not(.badge-info):not(.resolved-chip)');
      if (badge) {{
        const cfg = {{PASS:'pass', FAIL:'fail', MISSING:'missing', ERROR:'error', NEEDS_REVIEW:'needs_review'}};
        const labels = {{PASS:'PASS', FAIL:'FAIL', MISSING:'MISSING', ERROR:'ERROR', NEEDS_REVIEW:'NEEDS REVIEW'}};
        badge.className = 'badge badge-' + (cfg[newStatus] || 'na');
        badge.textContent = labels[newStatus] || newStatus;
      }}
      // Manual badge
      let manualBadge = row.querySelector('.badge.badge-info');
      if (data.manually_verified) {{
        if (!manualBadge) {{
          manualBadge = document.createElement('span');
          manualBadge.className = 'badge badge-info';
          manualBadge.style.fontSize = '10px';
          manualBadge.title = 'Photo selected manually by a reviewer';
          manualBadge.textContent = 'Manual';
          // Insert after the status badge (first child of req-header)
          const header = row.querySelector('.req-header');
          if (header) {{
            const statusBadge = header.querySelector('.badge:not(.badge-info):not(.resolved-chip)');
            if (statusBadge && statusBadge.nextSibling) {{
              header.insertBefore(manualBadge, statusBadge.nextSibling);
            }} else if (header.firstChild) {{
              header.insertBefore(manualBadge, header.firstChild.nextSibling);
            }} else {{
              header.appendChild(manualBadge);
            }}
          }}
        }}
        row.dataset.manuallyVerified = '1';
      }} else if (manualBadge) {{
        manualBadge.remove();
        delete row.dataset.manuallyVerified;
      }}
      // Reason + photos (reuse existing logic)
      const reasonContainer = row.querySelector('[data-role="reason-container"]');
      if (reasonContainer) {{
        const shouldShowReason = !['PASS','N/A','FOUND_NO_VISION'].includes(newStatus) && data.reason;
        if (shouldShowReason) {{
          const linked = _linkifyPhotos(data.reason, data.photo_urls || {{}});
          reasonContainer.innerHTML = '<div class="reason-expandable" onclick="expandReason(event,this)">' + linked + '</div>';
          if (typeof initExpandableReasons === 'function') initExpandableReasons(reasonContainer);
          // Auto-translate new reason text if user is in Spanish mode
          const reasonEl = reasonContainer.querySelector('.reason-expandable');
          if (reasonEl && typeof translateSingleReason === 'function') {{
            translateSingleReason(reasonEl, data.reason);
          }}
        }} else {{
          reasonContainer.innerHTML = '';
        }}
      }}
      const photoContainer = row.querySelector('[data-role="photo-container"]');
      if (photoContainer) {{
        const photoUrls = data.photo_urls || {{}};
        const photoCaptions = data.photo_captions || {{}};
        const pairs = Object.keys(photoUrls).sort((a,b) => +a - +b)
          .map(k => ({{k, url: photoUrls[k], cap: photoCaptions[k] || ''}}))
          .filter(p => p.url).slice(0,4);
        function _captionAttr(cap) {{ return cap ? ' data-caption="' + _esc(cap) + '"' : ''; }}
        if (!pairs.length) {{
          photoContainer.innerHTML = '';
        }} else if (pairs.length === 1) {{
          const p = pairs[0];
          photoContainer.innerHTML = '<a href="' + _esc(p.url) + '" target="_blank" class="req-photo-link"' + _captionAttr(p.cap) + '><img src="' + _esc(p.url) + '" alt="Evaluated photo" loading="lazy" class="req-photo"></a>';
        }} else {{
          photoContainer.innerHTML = '<div style="display:flex;gap:4px;margin-top:4px;">' +
            pairs.map(p => '<a href="' + _esc(p.url) + '" target="_blank" class="req-photo-link"' + _captionAttr(p.cap) + ' style="flex:1;min-width:0;"><img src="' + _esc(p.url) + '" alt="Evidence photo" loading="lazy" style="width:100%;height:72px;object-fit:cover;border-radius:4px;display:block;"></a>').join('') +
            '</div>';
        }}
        if (typeof rewirePhotoLinks === 'function') rewirePhotoLinks(photoContainer);
      }}
      row.dataset.resolved = '';
      const chip = row.querySelector('.resolved-chip');
      if (chip) chip.remove();
      const resolveBtn = row.querySelector('[data-role="resolve-btn"]');
      if (resolveBtn) resolveBtn.textContent = 'Mark resolved';
      if (typeof _updateTabCounts === 'function') _updateTabCounts();
    }}

    // Close picker on Escape
    document.addEventListener('keydown', function(e) {{
      if (e.key === 'Escape' && document.getElementById('photoPickerOverlay').style.display !== 'none') {{
        closePhotoPicker();
      }}
    }});

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
          _replaceNotesThread(row, data.notes || [], reqCode);
          editor.remove();
        }} catch (e) {{
          alert('Could not post note: ' + e.message);
          saveBtn.disabled = false;
        }}
      }};
    }}

    function _replaceNotesThread(row, notes, reqCode) {{
      reqCode = reqCode || (row ? row.dataset.id : '');
      let thread = row.querySelector('.req-notes-thread');
      if (!thread) {{
        thread = document.createElement('div');
        thread.className = 'req-notes-thread';
        const actions = row.querySelector('.req-actions');
        row.insertBefore(thread, actions);
      }}
      // Group replies under their parents
      const topLevel = notes.filter(n => !n.parent_note_id);
      const repliesByParent = {{}};
      notes.filter(n => n.parent_note_id).forEach(n => {{
        (repliesByParent[n.parent_note_id] = repliesByParent[n.parent_note_id] || []).push(n);
      }});
      const parts = [];
      topLevel.forEach(n => {{
        parts.push(_renderNoteEl(n, reqCode));
        (repliesByParent[n.id] || []).forEach(r => parts.push(_renderNoteEl(r, reqCode)));
      }});
      thread.innerHTML = parts.join('');
      localizeTimestamps(thread);
      // Re-apply role visibility so reply buttons show for reviewer+
      if (typeof _me !== 'undefined' && _me) {{
        const role = _me.role;
        if (['superadmin','admin','reviewer'].includes(role)) {{
          thread.querySelectorAll('.reviewer-plus').forEach(el => {{ el.style.display = ''; }});
        }}
      }}
      if (!notes.length) thread.remove();
    }}

    function _renderNoteEl(n, reqCode) {{
      const author = _esc(n.author_name || n.author_email || 'Unknown author');
      const iso = n.created_at || '';
      const timeHtml = iso
        ? '<time class="ts-relative req-note-time" datetime="' + _esc(iso) + '">' + _esc(formatTimestamp(iso)) + '</time>'
        : '';
      const body = _esc(n.body || '');
      const isDev = n.visibility === 'dev';
      const isReply = !!n.parent_note_id;
      const visCls = isDev ? 'note-dev' : 'note-public';
      const replyCls = isReply ? ' note-reply' : '';
      let devPill = '';
      if (isDev && !isReply) {{
        const s = (n.dev_status || 'open').toLowerCase();
        devPill = '<span class="note-dev-pill note-dev-' + _esc(s) + '">' + _esc(s.toUpperCase()) + '</span>';
      }}
      // Reply button on top-level dev notes (reviewer+ — hidden by default, revealed by loadMe).
      // Use data-* attributes to avoid quote-nesting issues in onclick.
      let replyBtn = '';
      if (isDev && !isReply && reqCode) {{
        replyBtn = '<button class="btn-note-reply reviewer-plus" style="display:none;"' +
          ' data-reply-note-id="' + n.id + '" data-reply-req-code="' + _esc(reqCode) + '"' +
          ' onclick="event.stopPropagation();openReplyEditor(this.dataset.replyNoteId,this.dataset.replyReqCode)">' +
          'Reply</button>';
      }}
      const noteIdLabel = (isDev && !isReply && n.id)
        ? '<span style="font-size:10px;opacity:0.5;margin-left:2px;">#' + n.id + '</span>'
        : '';
      return (
        '<div class="req-note ' + visCls + replyCls + '" data-note-id="' + n.id + '">' +
          '<div class="req-note-meta">' +
            '<span class="req-note-author">' + author + '</span>' +
            noteIdLabel +
            timeHtml +
            devPill +
            replyBtn +
          '</div>' +
          '<div class="req-note-body">' + body + '</div>' +
        '</div>'
      );
    }}

    function openReplyEditor(noteId, reqCode) {{
      if (!IS_INTERACTIVE || !REPORT_ID) return;
      // Remove any existing reply editor first
      const existing = document.querySelector('.note-reply-editor');
      if (existing) existing.remove();
      const parentNote = document.querySelector('.req-note[data-note-id="' + noteId + '"]');
      if (!parentNote) return;
      const editor = document.createElement('div');
      editor.className = 'note-reply-editor';
      editor.innerHTML =
        '<textarea placeholder="Reply to this bug flag…"></textarea>' +
        '<div class="note-reply-editor-actions">' +
          '<button class="btn btn-sm btn-subtle">Cancel</button>' +
          '<button class="btn btn-sm btn-warning">Post reply</button>' +
        '</div>';
      parentNote.after(editor);
      const ta = editor.querySelector('textarea');
      ta.focus();
      const [cancelBtn, saveBtn] = editor.querySelectorAll('button');
      cancelBtn.onclick = () => editor.remove();
      saveBtn.onclick = async () => {{
        if (!ta.value.trim()) {{ ta.focus(); return; }}
        saveBtn.disabled = true;
        try {{
          const r = await fetch('/api/report/' + REPORT_ID + '/item/' + reqCode + '/note', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{note: ta.value, parent_note_id: noteId}})
          }});
          const data = await r.json();
          if (data.error) throw new Error(data.error);
          const row = editor.closest('.requirement');
          _replaceNotesThread(row, data.notes || [], reqCode);
          editor.remove();
        }} catch (e) {{
          alert('Could not post reply: ' + e.message);
          saveBtn.disabled = false;
        }}
      }};
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

    function _linkifyPhotos(text, photoUrls) {{
      if (!text) return '';
      return _esc(text).replace(/\\bPhoto\\s+(\\d+)\\b/gi, function(match, num) {{
        const url = (photoUrls || {{}})[num] || (photoUrls || {{}})[String(num)];
        if (!url) return match;
        return '<a href="' + _esc(url) + '" target="_blank">' + match + '</a>';
      }});
    }}

    function _esc(s) {{
      const div = document.createElement('div');
      div.textContent = s == null ? '' : String(s);
      return div.innerHTML;
    }}

    // ── Spanish translation ───────────────────────────────────────────────────
    let _REPORT_LANG = localStorage.getItem('solclear-lang') || 'en';

    function setReportLang(lang) {{
      _REPORT_LANG = lang;
      localStorage.setItem('solclear-lang', lang);
      _updateReportLangToggle();
      translateReport();
    }}

    function _updateReportLangToggle() {{
      ['reportLangEN','reportLangES'].forEach(function(id) {{
        const btn = document.getElementById(id);
        if (!btn) return;
        const isActive = id === 'reportLangEN' ? _REPORT_LANG === 'en' : _REPORT_LANG === 'es';
        btn.style.opacity = isActive ? '1' : '0.45';
        btn.style.fontWeight = isActive ? '800' : '600';
      }});
    }}

    _updateReportLangToggle();
    function _translateCacheKey() {{ return 'translations-report-' + REPORT_ID + '-' + _REPORT_LANG; }}

    // Static badge/label translations for the report page
    const _REPORT_ES = {{
      'PASS': 'APROBADO', 'FAIL': 'FALLIDO', 'MISSING': 'FALTANTE',
      'NEEDS REVIEW': 'REQUIERE REVISIÓN', 'ERROR': 'ERROR',
      'Needs attention': 'Requiere atención', 'Passed': 'Aprobados', 'All': 'Todos',
      'ACTION REQUIRED': 'SE REQUIERE ACCIÓN', 'READY FOR SUBMISSION': 'LISTO PARA ENVIAR',
      'CANCELLED — PARTIAL RESULTS': 'CANCELADO — RESULTADOS PARCIALES',
      'Open in CompanyCam ↗': 'Abrir en CompanyCam ↗',
      'Mark resolved': 'Marcar como resuelto', 'Undo resolve': 'Deshacer resolución',
      'Add note': 'Agregar nota', 'Flag bug': 'Reportar error',
      'Select photo': 'Seleccionar foto', 'Re-check': 'Revisar de nuevo',
      'Reply': 'Responder', 'See Palmetto reference': 'Ver referencia de Palmetto',
      'Resolved': 'Resuelto', 'Manual': 'Manual', 'Back to Solclear': 'Volver a Solclear',
    }};

    async function translateReport() {{
      // Static label swap (both directions)
      document.querySelectorAll(
        '.report-tab, .btn, .badge, .done-label, .report-topbar a, .req-actions button, .req-actions a'
      ).forEach(function(el) {{
        const orig = el.dataset.enText;
        if (_REPORT_LANG === 'en' && orig) {{
          el.textContent = orig;
          return;
        }}
        const txt = el.dataset.enText || el.textContent.trim();
        if (!el.dataset.enText) el.dataset.enText = txt; // save original on first pass
        if (_REPORT_LANG === 'es' && _REPORT_ES[txt]) el.textContent = _REPORT_ES[txt];
      }});

      // Dynamic elements (reason text + notes)
      const reasonEls = Array.from(document.querySelectorAll('.reason-expandable'));
      const noteEls   = Array.from(document.querySelectorAll('.req-note-body'));
      const allEls    = [...reasonEls, ...noteEls];

      // Save original English text on first pass
      allEls.forEach(function(el) {{
        if (!el.dataset.enText) el.dataset.enText = el.textContent.trim();
      }});

      // Restore English
      if (_REPORT_LANG === 'en') {{
        allEls.forEach(function(el) {{
          if (el.dataset.enText) {{ el.textContent = el.dataset.enText; delete el.dataset.initialized; }}
        }});
        setTimeout(function() {{
          if (typeof initExpandableReasons === 'function') initExpandableReasons();
        }}, 50);
        return;
      }}

      // Strip "Read more ↩" pill text injected by initExpandableReasons before translating
      const allTexts = allEls.map(function(el) {{
        const raw = el.dataset.enText || el.textContent.trim();
        return raw.replace(/\s*Read more\s*\S*\s*$/i, '').trim();
      }});
      console.log('[translate] elements found:', allEls.length, 'texts:', allTexts.slice(0,2));
      if (!allTexts.length) return;

      // Check session cache first
      let cached = null;
      try {{ cached = JSON.parse(sessionStorage.getItem(_translateCacheKey())); }} catch(e) {{}}
      if (cached && cached.length === allTexts.length) {{
        allEls.forEach(function(el, i) {{
          if (cached[i]) {{ el.textContent = cached[i]; delete el.dataset.initialized; }}
        }});
        setTimeout(function() {{
          if (typeof initExpandableReasons === 'function') initExpandableReasons();
        }}, 50);
        return;
      }}

      // Fetch translations from server (single batched Haiku call)
      try {{
        const r = await fetch('/api/translate', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{texts: allTexts, lang: _REPORT_LANG, report_id: REPORT_ID}})
        }});
        if (!r.ok) {{
          const errText = await r.text();
          console.error('[translate] server error', r.status, errText);
          return;
        }}
        const data = await r.json();
        const translations = data.translations;
        if (!translations || translations.length !== allTexts.length) {{
          console.error('[translate] bad response:', data);
          return;
        }}
        allEls.forEach(function(el, i) {{
          if (translations[i]) {{
            el.textContent = translations[i];
            delete el.dataset.initialized; // allow re-init of expand pill
          }}
        }});
        try {{ sessionStorage.setItem(_translateCacheKey(), JSON.stringify(translations)); }} catch(e) {{}}
        // Re-init expand pills after DOM settles (textContent wipe removed them)
        setTimeout(function() {{
          if (typeof initExpandableReasons === 'function') initExpandableReasons();
        }}, 50);
      }} catch(e) {{
        console.error('[translate] fetch error:', e);
        // Try to read the error body
        try {{ e.response && e.response.text().then(function(t) {{ console.error('[translate] server said:', t); }}); }} catch(_) {{}}
      }}
    }}

    async function translateSingleReason(el, text) {{
      if (_REPORT_LANG === 'en' || !el || !text) return;
      try {{
        const r = await fetch('/api/translate', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{texts: [text], lang: _REPORT_LANG, report_id: REPORT_ID}})
        }});
        const data = await r.json();
        if (data.translations && data.translations[0]) {{
          el.textContent = data.translations[0];
          // Update session cache
          try {{
            const cached = JSON.parse(sessionStorage.getItem(_translateCacheKey()) || '[]');
            sessionStorage.setItem(_translateCacheKey(), JSON.stringify([...cached, data.translations[0]]));
          }} catch(e) {{}}
        }}
      }} catch(e) {{}}
    }}

    document.addEventListener('DOMContentLoaded', function() {{ translateReport(); }});

    // ── Lightbox ──
    // Lightbox state — tracks the sibling photos so arrows can navigate
    let _lbUrls = [];
    let _lbIdx  = 0;

    function openLightbox(url, siblingUrls) {{
      const lb  = document.getElementById('photoLightbox');
      const img = document.getElementById('photoLightboxImg');
      if (!lb || !img) return;
      _lbUrls = siblingUrls && siblingUrls.length > 1 ? siblingUrls : [url];
      _lbIdx  = _lbUrls.indexOf(url);
      if (_lbIdx < 0) _lbIdx = 0;
      img.src = _lbUrls[_lbIdx];
      lb.style.display = 'flex';
      document.body.style.overflow = 'hidden';
      _updateLightboxNav();
    }}

    function _updateLightboxNav() {{
      const prev = document.getElementById('lbPrev');
      const next = document.getElementById('lbNext');
      const ctr  = document.getElementById('lbCounter');
      if (!prev || !next) return;
      const multi = _lbUrls.length > 1;
      prev.style.display = multi ? 'flex' : 'none';
      next.style.display = multi ? 'flex' : 'none';
      if (ctr) ctr.textContent = multi ? (_lbIdx + 1) + ' / ' + _lbUrls.length : '';
      prev.style.opacity = _lbIdx === 0 ? '0.3' : '1';
      next.style.opacity = _lbIdx === _lbUrls.length - 1 ? '0.3' : '1';
    }}

    function lbNavigate(dir) {{
      const img = document.getElementById('photoLightboxImg');
      if (!img) return;
      _lbIdx = Math.max(0, Math.min(_lbUrls.length - 1, _lbIdx + dir));
      img.src = _lbUrls[_lbIdx];
      _updateLightboxNav();
    }}

    function closeLightbox(ev) {{
      if (ev && ev.target === document.getElementById('photoLightboxImg')) return;
      const lb = document.getElementById('photoLightbox');
      if (lb) lb.style.display = 'none';
      document.body.style.overflow = '';
      _lbUrls = []; _lbIdx = 0;
    }}

    document.addEventListener('keydown', function(e) {{
      if (document.getElementById('photoLightbox').style.display === 'none') return;
      if (e.key === 'Escape') closeLightbox();
      else if (e.key === 'ArrowLeft')  lbNavigate(-1);
      else if (e.key === 'ArrowRight') lbNavigate(1);
    }});

    function rewirePhotoLinks(root) {{
      root = root || document;
      root.querySelectorAll('a.req-photo-link, .req-reference-photos a').forEach(function(a) {{
        if (a.dataset.lightboxWired) return;
        a.dataset.lightboxWired = '1';
        a.addEventListener('click', function(e) {{
          e.preventDefault();
          e.stopPropagation();
          // Collect sibling photo links from the same container for navigation
          const container = a.closest('[data-role="photo-container"]') || a.closest('.req-reference-photos') || root;
          const siblings = Array.from(container.querySelectorAll('a.req-photo-link, .req-reference-photos a'))
            .map(function(s) {{ return s.href; }}).filter(Boolean);
          openLightbox(a.href, siblings);
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
        _applyRecheckResult(row, data);
        // Update only THIS row's visibility for the active tab
        const activeTab = document.querySelector('.report-tab.active')?.dataset.tab;
        if (activeTab && activeTab !== 'all') {{
          const newStatus = data.status || '';
          const isAttention = ['FAIL','MISSING','ERROR','NEEDS_REVIEW'].includes(newStatus);
          const show = (activeTab === 'attention') ? isAttention
                     : (activeTab === 'passed')    ? newStatus === 'PASS'
                     : true;
          row.style.display = show ? '' : 'none';
        }}
        if (typeof fetchActiveChecks === 'function') fetchActiveChecks();
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
    <div style="display:flex;align-items:center;gap:8px;">
      <div style="display:flex;border:1px solid rgba(255,255,255,0.3);border-radius:6px;overflow:hidden;font-size:11px;font-weight:700;">
        <button id="reportLangEN" onclick="setReportLang('en')" style="padding:3px 8px;border:none;cursor:pointer;color:#fff;background:transparent;">EN</button>
        <button id="reportLangES" onclick="setReportLang('es')" style="padding:3px 8px;border:none;border-left:1px solid rgba(255,255,255,0.3);cursor:pointer;color:#fff;background:transparent;">ES</button>
      </div>
    <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark mode">
      <svg id="themeIconSun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      <svg id="themeIconMoon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="display:none;"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    </button>
    </div>
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
    <span id="lbCounter" style="position:absolute;top:20px;left:50%;transform:translateX(-50%);color:#fff;font-size:13px;opacity:0.7;pointer-events:none;"></span>
    <button id="lbPrev" onclick="event.stopPropagation();lbNavigate(-1)" aria-label="Previous" style="display:none;position:absolute;left:16px;top:50%;transform:translateY(-50%);background:rgba(0,0,0,0.5);border:none;color:#fff;font-size:28px;cursor:pointer;width:48px;height:48px;border-radius:50%;align-items:center;justify-content:center;">&#8592;</button>
    <button id="lbNext" onclick="event.stopPropagation();lbNavigate(1)" aria-label="Next" style="display:none;position:absolute;right:16px;top:50%;transform:translateY(-50%);background:rgba(0,0,0,0.5);border:none;color:#fff;font-size:28px;cursor:pointer;width:48px;height:48px;border-radius:50%;align-items:center;justify-content:center;">&#8594;</button>
    <img id="photoLightboxImg" src="" alt="" style="max-width:86vw;max-height:88vh;object-fit:contain;border-radius:6px;box-shadow:0 8px 40px rgba(0,0,0,0.6);" onclick="event.stopPropagation()">
  </div>

  <!-- Photo picker modal — reviewer+ only, opened by "Select photo" button -->
  <div id="photoPickerOverlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:1000;align-items:flex-start;justify-content:center;padding-top:40px;">
    <div style="background:var(--bg-card);border-radius:12px;width:min(880px,95vw);max-height:80vh;display:flex;flex-direction:column;box-shadow:0 16px 48px rgba(0,0,0,0.4);overflow:hidden;">
      <div style="padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;flex-shrink:0;">
        <div>
          <div style="font-weight:700;font-size:15px;">Select photos</div>
          <div id="pickerReqTitle" style="font-size:12px;color:var(--text-muted);margin-top:2px;"></div>
        </div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:10px;">
          <span id="pickerSelCount" style="font-size:12px;color:var(--text-muted);"></span>
          <button onclick="closePhotoPicker()" style="background:none;border:none;color:var(--text-secondary);font-size:20px;cursor:pointer;padding:2px 6px;line-height:1;">&#x2715;</button>
        </div>
      </div>
      <div id="pickerGrid" style="overflow-y:auto;padding:16px;flex:1;">
        <div style="color:var(--text-muted);font-size:13px;grid-column:1/-1;padding:24px 0;text-align:center;">Loading photos…</div>
      </div>
      <div style="padding:14px 20px;border-top:1px solid var(--border);display:flex;justify-content:flex-end;gap:10px;flex-shrink:0;">
        <button onclick="closePhotoPicker()" class="btn btn-ghost">Cancel</button>
        <button id="pickerRunBtn" onclick="runCheckWithSelectedPhotos()" class="btn btn-primary" disabled>Run check</button>
      </div>
    </div>
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

    print("Fetching project details...", file=sys.stderr)
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
