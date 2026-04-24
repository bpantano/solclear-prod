"""
tools/notes_db.py — DB helpers for the unified notes system.

Backing table: `notes` (migration 005). Supports two visibility scopes:
  - 'public' — crew/reviewer/admin/superadmin comments, comment-thread style.
               Visible to anyone with access to the parent report.
  - 'dev'    — reviewer/admin bug tickets filed against Solclear itself.
               Visible ONLY to reviewer / admin / superadmin. Goes through
               open → acknowledged → corrected triage.

Notes are immutable once posted — post follow-ups instead of editing. This
keeps the audit trail honest and simplifies the schema (no edit tracking).
Dev-note triage state transitions (dev_status, resolved_at/_by) are not
edits — they're separate metadata.

Callers:
  - live_server.py handlers for the /api/report/{report_id}/item/{req_code}/note
    endpoint and friends
  - generate_report_html.py when rendering the thread beneath each requirement
"""
from __future__ import annotations

from typing import Optional

from tools.db import execute_returning, fetch_all, fetch_one, execute


# Roles that can read dev notes. Crew never sees the dev scope exists.
_DEV_NOTE_VIEWER_ROLES = {"reviewer", "admin", "superadmin"}
# Roles that can file dev notes. Same set today.
_DEV_NOTE_AUTHOR_ROLES = {"reviewer", "admin", "superadmin"}
# Roles that can transition dev-note status (acknowledge / mark corrected).
_DEV_NOTE_TRIAGE_ROLES = {"superadmin"}


def can_view_dev_notes(role: str) -> bool:
    return role in _DEV_NOTE_VIEWER_ROLES


def can_file_dev_note(role: str) -> bool:
    return role in _DEV_NOTE_AUTHOR_ROLES


def can_triage_dev_note(role: str) -> bool:
    return role in _DEV_NOTE_TRIAGE_ROLES


def add_note(
    report_id: int,
    requirement_result_id: Optional[int],
    author_user_id: Optional[int],
    visibility: str,
    body: str,
    parent_note_id: Optional[int] = None,
) -> dict:
    """Insert a new note. Returns the full row as a dict (including the
    server-assigned id + created_at).

    For top-level dev notes, auto-initializes dev_status='open'. Replies
    (parent_note_id != None) never get a dev_status — only the top-level
    note carries triage state.

    Visibility on a reply should match its parent (caller is responsible
    — usually fetched + passed in)."""
    if visibility not in ("public", "dev"):
        raise ValueError(f"invalid visibility: {visibility!r}")
    body = (body or "").strip()
    if not body:
        raise ValueError("note body cannot be empty")

    # Replies inherit triage scope from their parent — they don't get
    # their own dev_status. Top-level dev notes start as 'open'.
    dev_status = None if parent_note_id else ("open" if visibility == "dev" else None)
    row = execute_returning(
        """
        INSERT INTO notes (
            report_id, requirement_result_id, author_user_id,
            visibility, body, dev_status, parent_note_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, report_id, requirement_result_id, author_user_id,
                  visibility, body, dev_status, resolved_at, resolved_by_user_id,
                  parent_note_id, created_at
        """,
        (report_id, requirement_result_id, author_user_id, visibility,
         body, dev_status, parent_note_id),
    )
    return row or {}


def get_note(note_id: int) -> Optional[dict]:
    """Single note fetch by id. Used by endpoints that need the
    parent record to validate operations (e.g. reply, status
    transition)."""
    return fetch_one(
        """SELECT id, report_id, requirement_result_id, author_user_id,
                  visibility, body, dev_status, resolved_at, resolved_by_user_id,
                  parent_note_id, created_at
           FROM notes WHERE id = %s""",
        (note_id,),
    )


def list_replies_for_note(parent_note_id: int) -> list:
    """Reply thread for a top-level note, oldest-first. Includes author
    info for display. Used by the dev-notes triage tab to render an
    expandable reply thread under each top-level dev note."""
    return fetch_all(
        """
        SELECT n.id, n.body, n.author_user_id, n.created_at,
               u.full_name AS author_name, u.email AS author_email
        FROM notes n
        LEFT JOIN users u ON u.id = n.author_user_id
        WHERE n.parent_note_id = %s
        ORDER BY n.created_at ASC
        """,
        (parent_note_id,),
    )


def list_thread_participant_user_ids(parent_note_id: int, exclude_user_id: Optional[int] = None) -> list:
    """All distinct user_ids who have authored either the parent note
    or any reply in its thread. Used to fan out reply notifications.
    Excludes the user who just replied so they don't ping themselves."""
    rows = fetch_all(
        """
        SELECT DISTINCT author_user_id
        FROM notes
        WHERE (id = %s OR parent_note_id = %s)
          AND author_user_id IS NOT NULL
        """,
        (parent_note_id, parent_note_id),
    )
    ids = [r["author_user_id"] for r in rows if r.get("author_user_id")]
    if exclude_user_id is not None:
        ids = [i for i in ids if i != exclude_user_id]
    return list(set(ids))


def list_notes_for_req_result(
    req_result_id: int,
    viewer_role: str,
) -> list:
    """Return all notes on a requirement result, ordered oldest-first
    (comment-thread narrative order). Dev notes are filtered out for
    viewers whose role doesn't include dev-note access.

    Each note includes the author's full_name and email for display —
    legacy/backfilled notes will have NULL author fields, which the UI
    should render as "Unknown author"."""
    if can_view_dev_notes(viewer_role):
        visibility_filter = "n.visibility IN ('public', 'dev')"
    else:
        visibility_filter = "n.visibility = 'public'"
    return fetch_all(
        f"""
        SELECT n.id, n.report_id, n.requirement_result_id, n.author_user_id,
               n.visibility, n.body, n.dev_status, n.resolved_at,
               n.resolved_by_user_id, n.created_at,
               u.full_name AS author_name, u.email AS author_email,
               ru.full_name AS resolver_name
        FROM notes n
        LEFT JOIN users u ON u.id = n.author_user_id
        LEFT JOIN users ru ON ru.id = n.resolved_by_user_id
        WHERE n.requirement_result_id = %s
          AND {visibility_filter}
        ORDER BY n.created_at ASC
        """,
        (req_result_id,),
    )


def list_notes_for_report(report_id: int, viewer_role: str) -> list:
    """All notes across all requirements on a report — useful for the
    report-level thread view (future) or for bulk operations like
    clearing notes when a requirement is recheck'd."""
    if can_view_dev_notes(viewer_role):
        visibility_filter = "n.visibility IN ('public', 'dev')"
    else:
        visibility_filter = "n.visibility = 'public'"
    return fetch_all(
        f"""
        SELECT n.id, n.requirement_result_id, n.author_user_id,
               n.visibility, n.body, n.dev_status, n.created_at,
               u.full_name AS author_name
        FROM notes n
        LEFT JOIN users u ON u.id = n.author_user_id
        WHERE n.report_id = %s AND {visibility_filter}
        ORDER BY n.created_at ASC
        """,
        (report_id,),
    )


def clear_public_notes_for_req_result(req_result_id: int) -> None:
    """Delete all public notes attached to a requirement result.

    Invoked when a single-item recheck runs — the old notes reflected
    the prior verdict and may no longer apply to the new one. Dev
    notes are PRESERVED (bug reports persist across rechecks — they're
    about Solclear's behavior, not about this specific verdict)."""
    execute(
        "DELETE FROM notes WHERE requirement_result_id = %s AND visibility = 'public'",
        (req_result_id,),
    )


def set_dev_note_status(
    note_id: int,
    new_status: str,
    by_user_id: int,
) -> dict:
    """Transition a dev note's triage state (open → acknowledged →
    corrected). resolved_at/resolved_by_user_id are set when the new
    status is 'acknowledged' or 'corrected'; cleared when reverting
    to 'open'."""
    if new_status not in ("open", "acknowledged", "corrected"):
        raise ValueError(f"invalid dev_status: {new_status!r}")
    if new_status == "open":
        return execute_returning(
            """
            UPDATE notes
            SET dev_status = 'open',
                resolved_at = NULL,
                resolved_by_user_id = NULL
            WHERE id = %s AND visibility = 'dev'
            RETURNING *
            """,
            (note_id,),
        ) or {}
    return execute_returning(
        """
        UPDATE notes
        SET dev_status = %s,
            resolved_at = NOW(),
            resolved_by_user_id = %s
        WHERE id = %s AND visibility = 'dev'
        RETURNING *
        """,
        (new_status, by_user_id, note_id),
    ) or {}


def list_dev_notes(
    status_filter: Optional[str] = None,
    limit: int = 200,
) -> list:
    """Superadmin triage view. Returns dev notes with author + report +
    requirement context, newest-first within each status group.

    `status_filter` narrows to one of 'open' | 'acknowledged' |
    'corrected'; None returns all. `limit` caps each query; the triage
    UI paginates the 'corrected' (archived) panel separately.

    Only TOP-LEVEL dev notes are returned (parent_note_id IS NULL).
    Replies are loaded inline per-note via list_replies_for_note() —
    they don't have triage state of their own."""
    where = "n.visibility = 'dev' AND n.parent_note_id IS NULL"
    params: tuple = ()
    if status_filter:
        where += " AND n.dev_status = %s"
        params = (status_filter,)
    return fetch_all(
        f"""
        SELECT n.id, n.report_id, n.requirement_result_id, n.body,
               n.dev_status, n.created_at, n.resolved_at,
               u.full_name AS author_name, u.email AS author_email,
               ru.full_name AS resolver_name,
               req.code AS requirement_code, req.title AS requirement_title,
               rr.status AS requirement_status,
               p.name AS project_name, p.companycam_id AS project_cc_id,
               o.id AS org_id, o.name AS org_name
        FROM notes n
        LEFT JOIN users u ON u.id = n.author_user_id
        LEFT JOIN users ru ON ru.id = n.resolved_by_user_id
        LEFT JOIN requirement_results rr ON rr.id = n.requirement_result_id
        LEFT JOIN requirements req ON req.id = rr.requirement_id
        LEFT JOIN reports r ON r.id = n.report_id
        LEFT JOIN projects p ON p.id = r.project_id
        LEFT JOIN organizations o ON o.id = p.organization_id
        WHERE {where}
        ORDER BY n.created_at DESC
        LIMIT {int(limit)}
        """,
        params,
    )


def dev_notes_counts_by_status() -> dict:
    """Returns counts per dev-note status (top-level only). Powers
    badge counts on the superadmin Dev Notes nav item and tab
    headers. Replies are excluded — they're conversational, not
    triage units."""
    rows = fetch_all(
        """
        SELECT COALESCE(dev_status, 'unknown') AS status, COUNT(*) AS n
        FROM notes
        WHERE visibility = 'dev' AND parent_note_id IS NULL
        GROUP BY COALESCE(dev_status, 'unknown')
        """
    )
    return {r["status"]: r["n"] for r in rows}
