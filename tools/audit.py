"""
tools/audit.py — Audit log helpers.

Records significant user-initiated actions to the audit_log table.
Callers use the action-specific wrappers; direct use of log_action()
is discouraged so action strings stay consistent.

Design: best-effort only. Every wrapper wraps the DB write in
try/except so an audit failure NEVER breaks the underlying action.
Log rows that fail to insert are printed to stderr for ops visibility.
"""
from __future__ import annotations

import json
import sys
from typing import Optional


def log_action(
    action: str,
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Insert one audit_log row. Never raises."""
    try:
        from tools.db import execute
        execute(
            """INSERT INTO audit_log (action, user_id, org_id, target_type, target_id, metadata)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (action, user_id, org_id, target_type, target_id,
             json.dumps(metadata or {})),
        )
    except Exception as e:
        print(f"[audit] failed to log '{action}': {e}", file=sys.stderr)


# ── Action-specific wrappers ─────────────────────────────────────────────────

def log_login(user_id: int, org_id: Optional[int], email: str) -> None:
    log_action("login", user_id=user_id, org_id=org_id,
                target_type="user", target_id=user_id,
                metadata={"email": email})


def log_report_run(user_id: int, org_id: Optional[int], report_id: int,
                   project_id: Optional[str] = None) -> None:
    log_action("report_run", user_id=user_id, org_id=org_id,
                target_type="report", target_id=report_id,
                metadata={"project_id": project_id})


def log_report_cancel(user_id: int, org_id: Optional[int], report_id: int) -> None:
    log_action("report_cancel", user_id=user_id, org_id=org_id,
                target_type="report", target_id=report_id)


def log_requirement_recheck(user_id: int, org_id: Optional[int],
                             report_id: int, req_code: str) -> None:
    log_action("requirement_recheck", user_id=user_id, org_id=org_id,
                target_type="report", target_id=report_id,
                metadata={"requirement_code": req_code})


def log_note_add(user_id: int, org_id: Optional[int],
                 note_id: int, visibility: str, req_code: Optional[str] = None) -> None:
    log_action("note_add", user_id=user_id, org_id=org_id,
                target_type="note", target_id=note_id,
                metadata={"visibility": visibility, "requirement_code": req_code})


def log_dev_note_triage(user_id: int, note_id: int,
                        new_status: str, author_user_id: Optional[int] = None) -> None:
    log_action("dev_note_triage", user_id=user_id,
                target_type="note", target_id=note_id,
                metadata={"new_status": new_status, "author_user_id": author_user_id})


def log_org_settings_change(user_id: int, org_id: int,
                              changed_fields: list[str]) -> None:
    log_action("org_settings_change", user_id=user_id, org_id=org_id,
                target_type="organization", target_id=org_id,
                metadata={"changed_fields": changed_fields})


def log_user_invite(inviter_id: int, org_id: int,
                    invitee_email: str, role: str) -> None:
    log_action("user_invite", user_id=inviter_id, org_id=org_id,
                target_type="user",
                metadata={"invitee_email": invitee_email, "role": role})


def log_user_role_change(actor_id: int, org_id: int,
                          target_user_id: int, new_role: str) -> None:
    log_action("user_role_change", user_id=actor_id, org_id=org_id,
                target_type="user", target_id=target_user_id,
                metadata={"new_role": new_role})


# ── Read API ─────────────────────────────────────────────────────────────────

def list_audit_log(
    org_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> list:
    """Return audit log rows, newest first. Admins pass org_id to see
    their org only; superadmin passes None for all orgs."""
    from tools.db import fetch_all
    conditions = []
    params: list = []
    if org_id is not None:
        conditions.append("a.org_id = %s")
        params.append(org_id)
    if user_id is not None:
        conditions.append("a.user_id = %s")
        params.append(user_id)
    if action:
        conditions.append("a.action = %s")
        params.append(action)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = fetch_all(
        f"""SELECT a.id, a.action, a.target_type, a.target_id, a.metadata,
                   a.created_at,
                   u.full_name AS actor_name, u.email AS actor_email,
                   o.name AS org_name
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            LEFT JOIN organizations o ON o.id = a.org_id
            {where}
            ORDER BY a.created_at DESC
            LIMIT {int(limit)}""",
        tuple(params) if params else None,
    )
    for r in rows:
        if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return rows
