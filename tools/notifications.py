"""
tools/notifications.py — In-app + email notifications.

Backing table: `notifications` (migration 006). One row per (user, event).

Two delivery channels:
  - In-app: a row in the `notifications` table, surfaced in the top-bar
    bell with unread count badge.
  - Email: optional, fired at write time via Resend (same key used by
    auth.send_reset_email). Per-user opt-in/out is a future feature;
    today the email decision is hardcoded per notification kind.

Public API:
  notify(user_id, kind, title, body, link_url, metadata, send_email)
      Low-level — write a notification row, optionally send email.

Wrappers (always prefer these over notify() at call sites):
  notify_dev_note_filed(note, filer)
  notify_dev_note_status_changed(note, by_user, new_status)
  notify_check_completed(report_summary, runner_user_id, org_id)
  notify_check_cancelled(report_summary, runner_user_id)

All wrappers swallow exceptions (logged to stderr) so a notification
failure never breaks the underlying action that triggered it.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from tools.db import execute, execute_returning, fetch_all, fetch_one


# ── Email (Resend) ──────────────────────────────────────────────────────────
# Same env vars used by auth.py — single Resend account, single from-address.
_RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
_RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@solclear.io")
# Public URL for deep-links in emails. Falls back to the prod domain;
# can be overridden via env for local dev / preview environments.
_APP_URL = os.getenv("APP_PUBLIC_URL", "https://app.solclear.co")


def _send_email(to_email: str, subject: str, html: str) -> bool:
    """POST to Resend. Returns True on success, False (and prints) on
    any failure. Never raises — email is best-effort."""
    if not _RESEND_API_KEY:
        print(f"[notifications] RESEND_API_KEY not set, skipping email to {to_email}", file=sys.stderr)
        return False
    if not to_email:
        return False
    import requests
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {_RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": _RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html},
            timeout=10,
        )
        if resp.status_code >= 400:
            print(f"[notifications] Resend {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"[notifications] email send failed: {e}", file=sys.stderr)
        return False


def _email_html(title: str, body: str, link_url: Optional[str]) -> str:
    """Minimal email template — same visual language as the password
    reset email but trimmed since notifications are higher-volume."""
    cta = ""
    if link_url:
        full_url = link_url if link_url.startswith("http") else _APP_URL.rstrip("/") + link_url
        cta = (
            f'<a href="{full_url}" style="display:inline-block;background:#3b82f6;color:#fff;'
            f'padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600;'
            f'font-size:14px;margin-top:12px;">Open in Solclear</a>'
        )
    body_html = (body or "").replace("\n", "<br>")
    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;'
        'max-width:480px;margin:0 auto;padding:32px 20px;">'
        f'<h2 style="font-size:17px;margin-bottom:8px;color:#1a1a2e;">{title}</h2>'
        f'<div style="font-size:14px;color:#374151;line-height:1.55;">{body_html}</div>'
        f'{cta}'
        '<p style="font-size:11px;color:#9ca3af;margin-top:32px;">'
        'You\'re receiving this because of an event in Solclear. '
        f'Visit <a href="{_APP_URL}" style="color:#9ca3af;">{_APP_URL}</a> for more.'
        '</p></div>'
    )


# ── Core write path ─────────────────────────────────────────────────────────

def notify(
    user_id: int,
    kind: str,
    title: str,
    body: Optional[str] = None,
    link_url: Optional[str] = None,
    metadata: Optional[dict] = None,
    send_email: bool = False,
) -> Optional[int]:
    """Write a notification row. Optionally fire email.

    Always returns the new id, or None if the write failed (caught and
    logged — never raises). Email failure is independent of row write.
    """
    try:
        row = execute_returning(
            """INSERT INTO notifications (user_id, kind, title, body, link_url, metadata)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (user_id, kind, title, body, link_url, json.dumps(metadata or {})),
        )
    except Exception as e:
        print(f"[notifications] insert failed: {e}", file=sys.stderr)
        return None

    if send_email:
        try:
            user = fetch_one("SELECT email FROM users WHERE id = %s", (user_id,))
            if user and user.get("email"):
                _send_email(user["email"], title, _email_html(title, body or "", link_url))
        except Exception as e:
            print(f"[notifications] email lookup/send failed: {e}", file=sys.stderr)

    return (row or {}).get("id")


# ── Recipient helpers ───────────────────────────────────────────────────────

def _superadmin_user_ids() -> list:
    rows = fetch_all(
        "SELECT id FROM users WHERE role = 'superadmin' AND is_active = TRUE"
    )
    return [r["id"] for r in rows]


def _reviewer_user_ids_for_org(org_id: int, exclude_user_id: Optional[int] = None) -> list:
    """All reviewers / admins in an org (admins also do reviewer-style work).
    Optionally excludes a single user — typically the one whose action
    triggered the notification, so they don't ping themselves."""
    rows = fetch_all(
        """SELECT id FROM users
           WHERE organization_id = %s
             AND role IN ('reviewer', 'admin')
             AND is_active = TRUE""",
        (org_id,),
    )
    ids = [r["id"] for r in rows]
    if exclude_user_id is not None:
        ids = [i for i in ids if i != exclude_user_id]
    return ids


# ── Wrappers (use these at call sites) ───────────────────────────────────────

def notify_dev_note_filed(note: dict, filer_name: Optional[str] = None) -> None:
    """A reviewer/admin filed a dev note (bug ticket). Notify all
    superadmins via bell + email. Rare event, high signal."""
    title = "New dev note filed"
    body_lines = []
    if filer_name:
        body_lines.append(f"From: {filer_name}")
    requirement_code = note.get("requirement_code") or note.get("req_code")
    if requirement_code:
        body_lines.append(f"Requirement: {requirement_code}")
    snippet = (note.get("body") or "").strip()
    if snippet:
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        body_lines.append("")
        body_lines.append(snippet)
    body = "\n".join(body_lines)
    link = f"/report/{note['report_id']}" if note.get("report_id") else None
    metadata = {
        "note_id": note.get("id"),
        "report_id": note.get("report_id"),
        "requirement_code": requirement_code,
    }
    for uid in _superadmin_user_ids():
        notify(uid, "dev_note", title, body, link, metadata, send_email=True)


def notify_dev_note_status_changed(note: dict, new_status: str, by_user_name: Optional[str] = None) -> None:
    """A superadmin transitioned a dev note's status. Notify the original
    author so they know it's been seen / fixed. Bell only (no email
    spam)."""
    author_id = note.get("author_user_id")
    if not author_id:
        return  # legacy / system-generated note with no author — nothing to notify
    pretty = {"acknowledged": "acknowledged", "corrected": "marked corrected", "open": "reopened"}.get(new_status, new_status)
    title = f"Your dev note was {pretty}"
    body = f"By: {by_user_name}" if by_user_name else None
    link = f"/report/{note['report_id']}" if note.get("report_id") else None
    notify(
        author_id, "dev_note_status", title, body, link,
        {"note_id": note.get("id"), "new_status": new_status},
        send_email=False,
    )


def notify_dev_note_reply(
    parent_note: dict,
    reply: dict,
    replier_name: Optional[str] = None,
) -> None:
    """A reply was posted on a dev note. Notify everyone in the thread
    (parent author + previous repliers) except the replier themself.
    Bell only — replies fly back and forth during triage and email-per-
    reply would be too much."""
    parent_id = parent_note.get("id")
    if not parent_id:
        return
    from tools.notes_db import list_thread_participant_user_ids
    replier_id = reply.get("author_user_id")
    recipients = list_thread_participant_user_ids(parent_id, exclude_user_id=replier_id)
    if not recipients:
        return
    snippet = (reply.get("body") or "").strip()
    if len(snippet) > 200:
        snippet = snippet[:197] + "..."
    title = f"{replier_name} replied to a dev note" if replier_name else "New reply on your dev note"
    link = f"/report/{parent_note['report_id']}" if parent_note.get("report_id") else None
    metadata = {
        "parent_note_id": parent_id,
        "reply_id": reply.get("id"),
        "report_id": parent_note.get("report_id"),
    }
    for uid in recipients:
        notify(uid, "dev_note_reply", title, snippet, link, metadata, send_email=False)


def notify_check_completed(
    report_summary: dict,
    runner_user_id: Optional[int],
    org_id: int,
) -> None:
    """Compliance check finished. Only fire if there's something needing
    human attention — clean PASS-only checks don't ping anyone (no work
    to do, no signal). Notifies all reviewers + admins in the org
    (excluding the runner — they already saw it on their screen)."""
    n_fail = report_summary.get("failed", 0) or 0
    n_missing = report_summary.get("missing", 0) or 0
    n_review = report_summary.get("needs_review", 0) or 0
    n_attention = n_fail + n_missing + n_review
    if n_attention <= 0:
        return  # clean check → no need to ping reviewers

    project = report_summary.get("project_name") or f"Project {report_summary.get('project_id', '')}"
    title = f"{project} — check ready for review"
    parts = []
    if n_fail: parts.append(f"{n_fail} failed")
    if n_missing: parts.append(f"{n_missing} missing")
    if n_review: parts.append(f"{n_review} to review")
    body = " · ".join(parts)
    link = f"/report/{report_summary['db_report_id']}" if report_summary.get("db_report_id") else None
    metadata = {
        "report_id": report_summary.get("db_report_id"),
        "project_id": report_summary.get("project_id"),
        "n_attention": n_attention,
    }
    for uid in _reviewer_user_ids_for_org(org_id, exclude_user_id=runner_user_id):
        notify(uid, "check_complete", title, body, link, metadata, send_email=False)


def notify_check_cancelled(report_summary: dict, runner_user_id: Optional[int]) -> None:
    """Check was cancelled mid-run. Tell the runner so they know it
    won't appear in the normal complete-checks flow."""
    if not runner_user_id:
        return
    project = report_summary.get("project_name") or f"Project {report_summary.get('project_id', '')}"
    title = f"{project} — check cancelled"
    n_pass = report_summary.get("passed", 0) or 0
    n_total = report_summary.get("total", 0) or 0
    body = f"Partial results: {n_pass}/{n_total} completed before cancel"
    link = f"/report/{report_summary['db_report_id']}" if report_summary.get("db_report_id") else None
    notify(
        runner_user_id, "check_cancelled", title, body, link,
        {"report_id": report_summary.get("db_report_id")},
        send_email=False,
    )


# ── Read API (used by /api/notifications endpoints) ─────────────────────────

def list_for_user(user_id: int, unread_only: bool = False, limit: int = 50) -> list:
    where = "user_id = %s"
    params: tuple = (user_id,)
    if unread_only:
        where += " AND read_at IS NULL"
    return fetch_all(
        f"""SELECT id, kind, title, body, link_url, metadata, read_at, created_at
            FROM notifications
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT {int(limit)}""",
        params,
    )


def unread_count(user_id: int) -> int:
    row = fetch_one(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id = %s AND read_at IS NULL",
        (user_id,),
    )
    return (row or {}).get("n", 0) or 0


def mark_read(notification_id: int, user_id: int) -> bool:
    """Marks one notification read. Scoped by user_id so users can't
    flip each other's notification state. Returns True if a row was
    updated."""
    res = execute(
        """UPDATE notifications
           SET read_at = NOW()
           WHERE id = %s AND user_id = %s AND read_at IS NULL""",
        (notification_id, user_id),
    )
    return getattr(res, "rowcount", 0) > 0


def mark_all_read(user_id: int) -> int:
    """Marks every unread notification for a user as read. Returns the
    number affected."""
    res = execute(
        "UPDATE notifications SET read_at = NOW() WHERE user_id = %s AND read_at IS NULL",
        (user_id,),
    )
    return getattr(res, "rowcount", 0)
