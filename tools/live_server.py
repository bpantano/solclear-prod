"""
Tool: live_server.py
Purpose: Live compliance check server with real-time progress via SSE.
         Serves a mobile-friendly UI where crews select a project,
         pick a checklist, confirm job params, and watch results stream in.

Usage:
  python tools/live_server.py
  python tools/live_server.py --port 9000

Crew connects via phone: http://<your-ip>:8080
"""

import sys
from pathlib import Path

# CRITICAL: must run BEFORE any 'import html' (direct or transitive via
# http.server). When this file is invoked as `python tools/live_server.py`,
# Python sets sys.path[0] = tools/ — and our tools/html/ package then
# shadows stdlib html. Strip the tools/ entry and put project root first
# so `import html` finds Python's stdlib html (and html.escape) cleanly.
# See memory: feedback_tools_html_shadowing.md (2026-04-23 prod outage).
_THIS_DIR = str(Path(__file__).resolve().parent)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path[:] = [p for p in sys.path if p != _THIS_DIR]
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import argparse
import csv
import io
import json
import os
import queue
import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import requests as http_requests
from tools.compliance_check import run_compliance_check, REQUIREMENTS
from tools.companycam_get_project_photos import get_all_photos
from tools.db import fetch_all, fetch_one, execute, execute_returning
from tools.crypto import encrypt, decrypt, is_encrypted
from tools.auth import (
    hash_password, check_password, create_session_token,
    get_session_from_request, set_session_cookie_header,
    clear_session_cookie_header, create_reset_token,
    validate_reset_token, send_reset_email,
)

TMP_DIR = Path(__file__).parent.parent / ".tmp"
API_BASE = "https://api.companycam.com/v2"
CC_TOKEN = os.getenv("COMPANYCAM_API_KEY", "")

# ── Per-run check registry ────────────────────────────────────────────────────
#
# Replaces the old single global (_check_running, _result_queue, _cancel_event)
# which only allowed one check at a time across the entire server.
#
# Each active check owns its own queue + cancel event keyed by run_id
# (== db_report_id). Multiple users / orgs can run checks concurrently;
# the only shared resource is the Anthropic API, which is throttled via
# existing 429-retry logic.
#
# Lifecycle:
#   1. /start creates the entry and spawns run_check_thread.
#   2. /stream?run=<id> streams from that entry's queue.
#   3. /api/cancel {run_id} sets that entry's cancel_event.
#   4. run_check_thread's finally block schedules removal after a 60s
#      grace window so a reconnecting SSE client still gets the done event.

_active_runs: dict = {}          # run_id (int) → {queue, cancel_event, user_id, org_id}
_active_runs_lock = threading.Lock()


def _register_run(run_id: int, user_id, org_id) -> tuple:
    """Create and register the queue + cancel_event for a new check.
    Returns (result_queue, cancel_event)."""
    q = queue.Queue()
    ev = threading.Event()
    with _active_runs_lock:
        _active_runs[run_id] = {
            "queue": q,
            "cancel_event": ev,
            "user_id": user_id,
            "org_id": org_id,
        }
    return q, ev


def _deregister_run(run_id: int, delay: float = 60.0) -> None:
    """Schedule removal of a finished run from the registry. The 60-second
    grace window lets any still-connected SSE client read the final done/
    cancelled event before the queue disappears."""
    def _remove():
        time.sleep(delay)
        with _active_runs_lock:
            _active_runs.pop(run_id, None)
    threading.Thread(target=_remove, daemon=True, name=f"run-cleanup-{run_id}").start()

# Cached Anthropic platform status, refreshed by _poll_anthropic_status().
# Indicator values from Statuspage: "none" (all good), "minor", "major",
# "critical", "maintenance". `last_check` is epoch seconds — the UI can
# show "data as of …" if needed. When we can't reach the status page
# itself, indicator stays "unknown" so we don't falsely claim all clear.
_anthropic_status = {
    "indicator": "unknown",
    "description": "Status unknown — poller has not yet completed its first check.",
    "last_check": 0,
}
_anthropic_status_lock = threading.Lock()


def _poll_anthropic_status():
    """Background thread that fetches status.anthropic.com every 60s and
    caches the result in _anthropic_status. Runs forever until the process
    exits; daemon thread, so it doesn't block shutdown. Failures are
    swallowed and surfaced as indicator=unknown — a transient DNS blip
    on our side shouldn't spam the UI with fake outage banners."""
    import requests as _req
    global _anthropic_status
    while True:
        try:
            r = _req.get(
                "https://status.anthropic.com/api/v2/status.json",
                timeout=10,
            )
            r.raise_for_status()
            body = r.json()
            status = body.get("status", {}) or {}
            with _anthropic_status_lock:
                _anthropic_status = {
                    "indicator": status.get("indicator") or "unknown",
                    "description": status.get("description") or "",
                    "last_check": int(time.time()),
                }
        except Exception as e:
            # Don't overwrite a previously-known status with "unknown" on a
            # single failed poll — only mark unknown if we've never had a
            # successful read. Logs the error for ops visibility.
            with _anthropic_status_lock:
                if _anthropic_status.get("last_check", 0) == 0:
                    _anthropic_status = {
                        "indicator": "unknown",
                        "description": f"Unable to reach status.anthropic.com: {e}",
                        "last_check": 0,
                    }
            print(f"anthropic status poll failed: {e}", file=sys.stderr)
        time.sleep(60)

# Rate limiting for password reset (in-memory)
_reset_attempts = {}  # {email: (count, window_start_timestamp)}
RESET_RATE_LIMIT = 3  # max attempts per window
RESET_RATE_WINDOW = 900  # 15 minutes


def _check_rate_limit(email: str) -> bool:
    """Returns True if allowed, False if rate limited."""
    now = time.time()
    key = email.lower()
    if key in _reset_attempts:
        count, window_start = _reset_attempts[key]
        if now - window_start > RESET_RATE_WINDOW:
            _reset_attempts[key] = (1, now)
            return True
        if count >= RESET_RATE_LIMIT:
            return False
        _reset_attempts[key] = (count + 1, window_start)
        return True
    _reset_attempts[key] = (1, now)
    return True

# Track recently detected requirement changes (auto-expire after 7 days)
_recently_new = {}       # {"PS7": {"section": "...", "title": "...", "ts": timestamp}, ...}
_recently_changed = {}   # {"PS1": timestamp, ...}
_recently_removed = {}   # {"E8": timestamp, ...}
_TRACKING_EXPIRY = 7 * 24 * 60 * 60  # 7 days


def _cleanup_stale_tracking():
    """Remove tracking entries older than 7 days."""
    cutoff = time.time() - _TRACKING_EXPIRY
    for d in (_recently_new, _recently_changed, _recently_removed):
        for key in list(d.keys()):
            val = d[key]
            ts = val.get("ts", 0) if isinstance(val, dict) else val
            if ts < cutoff:
                del d[key]

# Template IDs that indicate battery installs
BATTERY_TEMPLATE_IDS = {"95194", "184407"}  # Install - Battery, LightReach : PV + Battery

# Incentive states (expand as needed)
INCENTIVE_STATES = {"CA", "California", "NY", "New York", "NJ", "New Jersey", "MA", "Massachusetts",
                    "CT", "Connecticut", "IL", "Illinois", "MD", "Maryland", "MN", "Minnesota",
                    "RI", "Rhode Island", "NM", "New Mexico", "CO", "Colorado"}


def _session_org_id(handler):
    """Pull org_id from the cached session on a handler instance. Returns
    None if not set — callers fall back to the env-var CC_TOKEN."""
    s = getattr(handler, "_session", None) or {}
    return s.get("org_id")


def cc_headers(org_id=None):
    """Build CompanyCam auth headers. Prefers the org's stored (encrypted)
    key when org_id is supplied; falls back to the CC_TOKEN env var so
    existing callers that don't yet pass an org_id keep working.

    This enables per-org CompanyCam key isolation: Independent Solar's
    key lives in their org row, not in a shared env var."""
    key = CC_TOKEN  # env-var fallback — used in dev + legacy callers
    if org_id:
        try:
            org = fetch_one(
                "SELECT companycam_api_key FROM organizations WHERE id = %s",
                (org_id,),
            )
            stored = (org or {}).get("companycam_api_key")
            if stored:
                key = decrypt(stored)  # no-op if ENCRYPTION_KEY not set
        except Exception as e:
            print(f"WARNING: could not load org {org_id} CC key, using env fallback: {e}",
                  file=sys.stderr)
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def derive_params_from_checklist(project_id, checklist_id, manufacturer,
                                  project_state="", org_id=None):
    """Auto-derive job parameters from checklist data and project address."""
    headers = cc_headers(org_id)
    has_battery = False
    is_backup = False
    portal_access = False

    try:
        cl = http_requests.get(f"{API_BASE}/projects/{project_id}/checklists/{checklist_id}",
                               headers=headers, timeout=10).json()

        # Battery: derive from template ID
        template_id = str(cl.get("checklist_template_id", ""))
        if template_id in BATTERY_TEMPLATE_IDS:
            has_battery = True

        # Collect all tasks
        all_tasks = list(cl.get("sectionless_tasks", []))
        for s in cl.get("sections", []):
            all_tasks.extend(s.get("tasks", []))

        for task in all_tasks:
            title = task.get("title", "").lower().strip()

            # Backup battery: Transfer Switch Wiring task exists with photos
            if title == "transfer switch wiring" and task.get("photos"):
                is_backup = True

            # Portal access: Monitoring App Screenshots -> "Comms established?" sub_task
            if title == "monitoring app screenshots":
                for sub in task.get("sub_tasks", []):
                    if "comms" in sub.get("label", "").lower():
                        answer = (sub.get("answer_text") or "").lower()
                        if answer in ("yes", "true"):
                            portal_access = True

    except Exception as e:
        print(f"WARNING: Could not derive params from checklist: {e}", file=sys.stderr)

    # Incentive state: derive from project address
    is_incentive = project_state.strip() in INCENTIVE_STATES

    return {
        "manufacturer": manufacturer,
        "lender": "LightReach",
        "has_battery": has_battery,
        "is_backup_battery": is_backup,
        "is_incentive_state": is_incentive,
        "portal_access_granted": portal_access,
    }


# ── Background check thread ──────────────────────────────────────────────────

def _upsert_project(cc_project_id, session):
    """Ensure a project exists in our DB for this CompanyCam project. Returns our internal project ID."""
    org_id = session.get("org_id")
    # Check if exists
    existing = fetch_one("SELECT id FROM projects WHERE companycam_id = %s", (str(cc_project_id),))
    if existing:
        return existing["id"]
    # Fetch project details from CompanyCam
    try:
        r = http_requests.get(f"{API_BASE}/projects/{cc_project_id}", headers=cc_headers(org_id), timeout=10)
        r.raise_for_status()
        p = r.json()
        proj = execute_returning(
            "INSERT INTO projects (organization_id, companycam_id, name, address, city, state) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (org_id, str(cc_project_id), p.get("name", ""), p.get("address", {}).get("street_address_1", ""),
             p.get("address", {}).get("city", ""), p.get("address", {}).get("state", ""))
        )
        return proj["id"]
    except Exception:
        # Fallback — create with minimal info
        proj = execute_returning(
            "INSERT INTO projects (organization_id, companycam_id, name) VALUES (%s, %s, %s) RETURNING id",
            (org_id, str(cc_project_id), f"Project {cc_project_id}")
        )
        return proj["id"]


def run_check_thread(cc_project_id, params, run_id, result_queue, cancel_event,
                     rerun_ids=None, session=None):
    """Worker thread for a single compliance check run.

    All mutable state (queue, cancel signal) is scoped to this run via
    `run_id`. Multiple calls can execute concurrently — they never share
    queue or cancel_event with each other.

    `run_id` equals the DB report_id so the caller can correlate SSE
    streams with report rows without extra bookkeeping."""
    session = session or {}
    try:
        # Ensure photos are cached
        photos_path = TMP_DIR / f"photos_{cc_project_id}.json"
        if not photos_path.exists():
            result_queue.put(json.dumps({"type": "status", "message": "Fetching photos from CompanyCam..."}))
            photos = get_all_photos(cc_project_id)
            TMP_DIR.mkdir(exist_ok=True)
            with open(photos_path, "w") as f:
                json.dump(photos, f, indent=2)
            result_queue.put(json.dumps({"type": "status", "message": f"Fetched {len(photos)} photos. Starting check..."}))

        # The report row was pre-created by _start_check so the client
        # had a run_id before photos were fetched. Here we fill in the
        # params (manufacturer, battery, etc.) now that derive_params has
        # returned. If the pre-create failed, run_id is None and we fall
        # back to creating a fresh row.
        db_report_id = run_id
        try:
            if db_report_id:
                execute(
                    """UPDATE reports
                       SET manufacturer = %s, has_battery = %s, is_backup_battery = %s,
                           is_incentive_state = %s, portal_access_granted = %s
                       WHERE id = %s""",
                    (params.get("manufacturer"), params.get("has_battery", False),
                     params.get("is_backup_battery", False), params.get("is_incentive_state", False),
                     params.get("portal_access_granted", False), db_report_id),
                )
            else:
                # Fallback if pre-create failed — insert fresh.
                db_project_id = _upsert_project(cc_project_id, session)
                is_test = session.get("role") == "superadmin"
                report_row = execute_returning(
                    """INSERT INTO reports (project_id, run_by, manufacturer, has_battery, is_backup_battery,
                       is_incentive_state, portal_access_granted, is_test, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'running') RETURNING id""",
                    (db_project_id, session.get("user_id"), params.get("manufacturer"),
                     params.get("has_battery", False), params.get("is_backup_battery", False),
                     params.get("is_incentive_state", False), params.get("portal_access_granted", False),
                     is_test),
                )
                db_report_id = report_row["id"] if report_row else None
        except Exception as e:
            print(f"WARNING: Could not update report in DB: {e}", file=sys.stderr)

        def on_progress(result, index, total):
            result_queue.put(json.dumps({
                "type": "progress",
                "index": index,
                "total": total,
                "requirement": result,
            }))
            # Save individual result to DB
            if db_report_id:
                try:
                    execute(
                        """INSERT INTO requirement_results
                           (report_id, requirement_id, status, reason, photo_urls, candidates, total_duration_ms)
                           VALUES (%s, (SELECT id FROM requirements WHERE code = %s AND is_active = TRUE ORDER BY version DESC LIMIT 1),
                                   %s, %s, %s, %s, %s)""",
                        (db_report_id, result.get("id"), result.get("status"), result.get("reason"),
                         json.dumps(result.get("photo_urls", {})), result.get("candidates", 0),
                         result.get("total_duration_ms"))
                    )
                except Exception:
                    pass  # Requirements table may not have matching rows yet

        # Scope every _call_anthropic inside this check to the db_report_id
        # so api_call_log rows can be attributed back to this report. If the
        # DB insert above failed and db_report_id is None, logging is skipped
        # automatically (the check still runs fine).
        # `should_cancel` is polled at each requirement boundary — if
        # POST /api/cancel fires, the current vision call finishes, then
        # the loop breaks out with a partial results array.
        from tools.compliance_check import set_call_context
        cancel_event.clear()
        with set_call_context(report_id=db_report_id, purpose="vision"):
            if rerun_ids:
                result_queue.put(json.dumps({"type": "status", "message": f"Re-checking {len(rerun_ids)} failed requirements..."}))
                report = run_compliance_check(cc_project_id, params, run_vision=True,
                                              progress_callback=on_progress, only_ids=rerun_ids,
                                              should_cancel=cancel_event.is_set)
            else:
                report = run_compliance_check(cc_project_id, params, run_vision=True,
                                              progress_callback=on_progress,
                                              should_cancel=cancel_event.is_set)

        # Also save to .tmp/ for backward compatibility
        TMP_DIR.mkdir(exist_ok=True)
        report["db_report_id"] = db_report_id
        with open(TMP_DIR / f"compliance_{cc_project_id}.json", "w") as f:
            json.dump(report, f, indent=2)

        # Update report summary in DB
        reqs = report["requirements"]
        required = [r for r in reqs if r["status"] != "N/A" and not r.get("optional")]
        n_pass = sum(1 for r in required if r["status"] == "PASS")
        n_fail = sum(1 for r in required if r["status"] == "FAIL")
        n_missing = sum(1 for r in required if r["status"] == "MISSING")
        n_review = sum(1 for r in required if r["status"] == "NEEDS_REVIEW")
        was_cancelled = bool(report.get("cancelled"))

        if db_report_id:
            try:
                # 'cancelled' is a new TEXT status alongside 'complete'/'error'/'running'.
                # Partial totals are recorded so the report detail page can still
                # render the results we did collect before stopping.
                # checklist_ids: persist the array discovered during the run so
                # the report-detail page's rerun button doesn't have to refetch
                # them from CompanyCam (avoids rate limiting under concurrent users).
                final_status = "cancelled" if was_cancelled else "complete"
                execute(
                    """UPDATE reports SET status = %s, completed_at = NOW(),
                       total_required = %s, total_passed = %s, total_failed = %s,
                       total_missing = %s, total_needs_review = %s,
                       checklist_ids = %s
                       WHERE id = %s""",
                    (final_status, len(required), n_pass, n_fail, n_missing, n_review,
                     json.dumps(report.get("checklist_ids", [])), db_report_id)
                )
            except Exception as e:
                print(f"WARNING: Could not update report in DB: {e}", file=sys.stderr)

        summary_payload = {
            "passed": n_pass,
            "failed": n_fail,
            "missing": n_missing,
            "needs_review": n_review,
            "total": len(required),
            "project_id": cc_project_id,
            "db_report_id": db_report_id,
            "checklist_ids": report.get("checklist_ids", []),
            "cancelled": was_cancelled,
        }
        result_queue.put(json.dumps({
            "type": "cancelled" if was_cancelled else "done",
            "summary": summary_payload,
        }))

        # Fire bell notifications. Checks completing with attention items
        # ping the org's reviewers; cancelled checks ping the runner.
        # Wrapped in try/except so notification failures never affect
        # the check itself or the SSE stream the user is watching.
        try:
            from tools.notifications import notify_check_completed, notify_check_cancelled
            # Enrich summary with project name. Use db_report_id (always
            # available) to look up the project — avoids depending on
            # db_project_id which is only defined in the fallback INSERT
            # branch and was causing UnboundLocalError after the Day 4
            # refactor.
            project_name = None
            if db_report_id:
                try:
                    p = fetch_one(
                        "SELECT pr.name FROM reports r JOIN projects pr ON pr.id = r.project_id WHERE r.id = %s",
                        (db_report_id,),
                    )
                    project_name = (p or {}).get("name")
                except Exception:
                    pass
            summary_for_notify = {**summary_payload, "project_name": project_name}
            runner_user_id = (session or {}).get("user_id")
            org_id = (session or {}).get("org_id")
            if was_cancelled:
                notify_check_cancelled(summary_for_notify, runner_user_id)
            elif org_id:
                notify_check_completed(summary_for_notify, runner_user_id, org_id)
        except Exception as e:
            print(f"check-completion notify failed: {e}", file=sys.stderr)
    except Exception as e:
        result_queue.put(json.dumps({"type": "error", "message": str(e)}))
        if db_report_id:
            try:
                execute("UPDATE reports SET status = 'error' WHERE id = %s", (db_report_id,))
            except Exception:
                pass
    finally:
        cancel_event.clear()
        # Schedule removal of this run from the registry after a grace
        # period so any reconnecting SSE client can still drain the queue.
        _deregister_run(run_id)


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class LiveHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # silence request logs

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _get_session(self):
        """Get current session or None."""
        return get_session_from_request(self.headers)

    def _require_auth(self):
        """Check session. Returns session dict or sends redirect/401 and returns None."""
        session = self._get_session()
        if session:
            return session
        # For API requests, return 401
        if self.path.startswith("/api/"):
            self._send_json({"error": "Not authenticated"}, 401)
        else:
            # Redirect to login page
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
        return None

    def _require_role(self, session, allowed_roles):
        """Check if session user has one of the allowed roles. Returns True if authorized, sends 403 and returns False if not."""
        if session.get("role") in allowed_roles:
            return True
        self._send_json({"error": "Insufficient permissions"}, 403)
        return False

    def _require_org_access(self, session, org_id, write=False):
        """Verify the session user may act on the given organization.

        Superadmins: any org.
        Admins: their own org — read or write.
        Reviewers: their own org — READ ONLY (write=False). Writes return 403.
        Any other role: 403.
        """
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return False
        role = session.get("role")
        if role == "superadmin":
            return True
        try:
            same_org = int(org_id) == session.get("org_id")
        except (TypeError, ValueError):
            same_org = False
        if role == "admin" and same_org:
            return True
        if role == "reviewer" and same_org and not write:
            return True
        self._send_json({"error": "Forbidden"}, 403)
        return False

    def _get_user_org(self, user_id):
        """Look up a user's organization_id. Returns None if user not found."""
        try:
            row = fetch_one("SELECT organization_id FROM users WHERE id = %s", (user_id,))
            return row.get("organization_id") if row else None
        except Exception:
            return None

    def _require_user_access(self, session, user_id):
        """Verify the session user may act on the given user (edit/toggle).
        Superadmin: any user. Admin: only users in their org.
        Reviewer + crew cannot manage users."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return False
        role = session.get("role")
        if role == "superadmin":
            return True
        if role == "admin":
            target_org = self._get_user_org(user_id)
            if target_org is not None and target_org == session.get("org_id"):
                return True
        self._send_json({"error": "Forbidden"}, 403)
        return False

    def _serve_logo_svg(self):
        """Serve the Solclear wordmark SVG as an image (public, used in emails)."""
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" width="640" height="160">
  <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#0F172A" stroke-width="7" stroke-linecap="round"/></g>
  <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#0F172A" letter-spacing="-2.5">solclear</text>
</svg>"""
        body = svg.encode()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _serve_og_image(self):
        """Serve an OG preview image for link sharing (iMessage, Slack, etc.)."""
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
<rect width="1200" height="630" fill="#0f172a"/>
<g transform="translate(440,180)">
  <circle cx="60" cy="54" r="22" fill="#F59E0B"/>
  <path d="M14 100 A 46 46 0 0 1 106 100" fill="none" stroke="#e2e8f0" stroke-width="10" stroke-linecap="round"/>
</g>
<text x="600" y="340" text-anchor="middle" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="72" fill="#e2e8f0" letter-spacing="-2">solclear</text>
<text x="600" y="400" text-anchor="middle" font-family="Inter,Helvetica,Arial,sans-serif" font-size="28" fill="#64748b">Solar compliance, simplified.</text>
</svg>"""
        body = svg.encode()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _serve_favicon(self):
        """Serve the Solclear mark as a favicon."""
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
<circle cx="60" cy="54" r="14" fill="#F59E0B"/>
<path d="M24 92 A 36 36 0 0 1 96 92" fill="none" stroke="#0F172A" stroke-width="8" stroke-linecap="round"/>
</svg>"""
        body = svg.encode()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=604800")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _serve_login_page(self):
        body = LOGIN_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # Public routes (no auth required)
        if path == "/logo.svg":
            self._serve_logo_svg()
            return
        if path == "/favicon.svg" or path == "/favicon.ico":
            self._serve_favicon()
            return
        if path == "/og-image.svg":
            self._serve_og_image()
            return
            return
        if path == "/login":
            self._serve_login_page()
            return
        if path == "/forgot-password":
            self._serve_forgot_password_page()
            return
        if path == "/request-demo":
            self._serve_request_demo_page()
            return
        if path == "/reset-password":
            self._serve_reset_password_page(qs)
            return
        if path == "/logout":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Set-Cookie", clear_session_cookie_header())
            self.end_headers()
            return
        if path == "/healthz":
            # Lightweight liveness probe for Railway's healthcheck. Returns
            # 200 as soon as the HTTP server can respond — deliberately does
            # NOT hit the DB or any external API, since those failures
            # shouldn't gate a zero-downtime deploy cutover. Railway polls
            # this during deploys; traffic only shifts to the new container
            # once /healthz returns 200. No auth required.
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        # All other routes require auth
        session = self._require_auth()
        if not session:
            return
        # Cache on self so handler methods can access org_id without
        # needing session threaded through every signature.
        self._session = session

        if path == "/":
            self._serve_html()
        elif path == "/change-password":
            self._serve_change_password_page()
        elif path == "/api/me":
            self._api_me(session)
        elif path == "/api/platform_status":
            self._api_platform_status(session)
        elif path == "/api/my_active_check":
            self._api_my_active_check(session)
        elif path == "/api/notifications":
            self._api_notifications_list(session, qs)
        elif path == "/api/notifications/unread_count":
            self._api_notifications_unread_count(session)
        elif path.startswith("/api/admin/req_timing/"):
            if not self._require_role(session, ("superadmin",)):
                return
            code = path.split("/")[4] if len(path.split("/")) > 4 else ""
            self._api_req_timing_detail(code)
        elif path.startswith("/api/reference_photos/"):
            parts = path.split("/")
            # /api/reference_photos/{req_code}         → list metadata
            # /api/reference_photos/{req_code}/{id}/img → serve bytes
            if len(parts) >= 6 and parts[5] == "img":
                try:
                    photo_id = int(parts[4])
                except ValueError:
                    self.send_error(400, "Invalid photo id")
                    return
                self._serve_reference_photo_bytes(photo_id)
            else:
                req_code = parts[3] if len(parts) > 3 else ""
                self._api_reference_photo(req_code)
        elif path == "/api/dev_notes":
            if not self._require_role(session, ("superadmin",)):
                return
            self._api_dev_notes_list(session, qs)
        elif path == "/api/admin/cost/summary":
            if not self._require_role(session, ("superadmin",)):
                return
            self._api_admin_cost_summary(qs)
        elif path == "/api/admin/cost/filter-options":
            if not self._require_role(session, ("superadmin",)):
                return
            self._api_admin_cost_filter_options()
        elif path == "/api/projects":
            self._api_projects(qs)
        elif path.startswith("/api/projects/") and path.endswith("/thumbnail"):
            pid = path.split("/")[3]
            self._api_project_thumbnail(pid)
        elif path.startswith("/api/projects/") and path.endswith("/checklists"):
            pid = path.split("/")[3]
            self._api_checklists(pid)
        elif path == "/api/reports":
            self._api_reports(session)
        # ── Admin routes ──
        # Requirements: superadmin/admin/reviewer can view AND edit.
        # Crew has no access to the requirements catalog.
        elif path == "/api/requirements":
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            self._api_requirements_list()
        elif path == "/api/requirements/monitor/status":
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            self._api_requirements_monitor()
        elif path.startswith("/api/requirements/") and len(path.split("/")) == 4:
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            req_id = path.split("/")[3]
            self._api_requirement_detail(req_id)
        # Organization GETs: superadmin/admin/reviewer can view; reviewer is
        # scoped to their own org (read-only, enforced by _require_org_access).
        elif path == "/api/organizations":
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            self._api_orgs_list(session)
        # User detail endpoint is management-only (the user edit form); keep
        # it restricted to admin+superadmin so a reviewer can't pull emails
        # and phone numbers out of context.
        elif path.startswith("/api/users/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            if not self._require_user_access(session, uid):
                return
            self._api_user_detail(uid)
        elif path.startswith("/api/organizations/") and path.endswith("/users"):
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            oid = path.split("/")[3]
            if not self._require_org_access(session, oid):  # read — reviewer allowed
                return
            self._api_org_users(oid)
        elif path.startswith("/api/organizations/"):
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            oid = path.split("/")[3]
            if not self._require_org_access(session, oid):  # read — reviewer allowed
                return
            self._api_org_detail(oid)
        elif path.startswith("/report/"):
            pid = path.split("/")[2]
            self._serve_report(pid, session)
        elif path == "/start":
            self._start_check(qs, session)
        elif path == "/stream":
            self._stream_sse(qs)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        # Public POST routes
        if path == "/api/login":
            self._api_login(body)
            return
        if path == "/api/forgot-password":
            self._api_forgot_password(body)
            return
        if path == "/api/reset-password":
            self._api_reset_password(body)
            return
        if path == "/api/request-demo":
            self._api_request_demo(body)
            return

        # All other POSTs require auth
        session = self._require_auth()
        if not session:
            return
        self._session = session

        if path == "/api/change-password":
            self._api_change_password(body, session)
        # Cancel the currently-running compliance check. Any authenticated
        # user can request it — there's only ever one running at a time.
        elif path == "/api/cancel":
            self._api_cancel_check(body)
        elif path == "/api/notifications/read-all":
            self._api_notifications_mark_all_read(session)
        elif path.startswith("/api/notifications/") and path.endswith("/read"):
            # /api/notifications/{id}/read
            try:
                nid = int(path.split("/")[3])
            except (IndexError, ValueError):
                self._send_json({"error": "Invalid notification id"}, 400)
                return
            self._api_notifications_mark_read(nid, session)
        # Dev-notes triage actions — superadmin only.
        # /api/dev_notes/{id}/status   → transition triage state
        # /api/dev_notes/{id}/reply    → append a reply to the thread
        elif path.startswith("/api/dev_notes/"):
            if not self._require_role(session, ("superadmin",)):
                return
            parts = path.split("/")
            try:
                note_id = int(parts[3])
            except (IndexError, ValueError):
                self._send_json({"error": "Invalid note id"}, 400)
                return
            action = parts[4] if len(parts) > 4 else ""
            if action == "status":
                self._api_dev_note_set_status(note_id, body, session)
            elif action == "reply":
                self._api_dev_note_reply(note_id, body, session)
            else:
                self._send_json({"error": "Unknown action"}, 404)
        # ── Impersonation (superadmin starts, any impersonating user stops) ──
        elif path == "/api/admin/impersonate":
            self._api_impersonate(body, session)
        elif path == "/api/admin/stop-impersonate":
            self._api_stop_impersonate(session)
        # ── Admin POST routes (superadmin/admin only) ──
        elif path == "/api/organizations":
            # Creating a new organization is a platform-level operation,
            # reserved for superadmins. Org admins cannot spawn new orgs.
            if not self._require_role(session, ("superadmin",)):
                return
            self._api_org_create(body)
        elif path.startswith("/api/organizations/") and path.endswith("/users/csv"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            if not self._require_org_access(session, oid, write=True):
                return
            self._api_org_users_csv(oid, body)
        elif path.startswith("/api/organizations/") and path.endswith("/users"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            if not self._require_org_access(session, oid, write=True):
                return
            self._api_org_user_create(oid, body)
        elif path.startswith("/api/users/") and path.endswith("/resend-invite"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            if not self._require_user_access(session, uid):
                return
            self._api_user_resend_invite(uid)
        elif path.startswith("/api/users/") and path.endswith("/toggle"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            if not self._require_user_access(session, uid):
                return
            self._api_user_toggle(uid)
        elif path.startswith("/api/users/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            if not self._require_user_access(session, uid):
                return
            self._api_user_update(uid, body)
        # Reviewers can trigger the Palmetto monitor check + edit
        # requirements; crew is excluded.
        elif path == "/api/requirements/check":
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            self._api_requirements_check_now()
        elif path.startswith("/api/requirements/"):
            if not self._require_role(session, ("superadmin", "admin", "reviewer")):
                return
            req_id = path.split("/")[3]
            self._api_requirement_update(req_id, body)
        elif path.startswith("/api/organizations/"):
            # Org updates stay admin+superadmin only. Reviewer cannot edit.
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            if not self._require_org_access(session, oid, write=True):
                return
            self._api_org_update(oid, body, session)
        # ── Interactive report item actions ──
        # /api/report/{report_id}/item/{req_code}/resolve  → toggle resolved
        # /api/report/{report_id}/item/{req_code}/note     → save note
        elif path.startswith("/api/report/") and path.endswith("/resolve"):
            parts = path.split("/")
            if len(parts) == 7:
                self._api_report_item_resolve(parts[3], parts[5], session)
            else:
                self.send_error(404)
        elif path.startswith("/api/report/") and path.endswith("/note"):
            parts = path.split("/")
            if len(parts) == 7:
                self._api_report_item_note(parts[3], parts[5], body, session)
            else:
                self.send_error(404)
        # /api/recheck/{report_id}/{req_code} → re-run one requirement
        elif path.startswith("/api/recheck/"):
            parts = path.split("/")
            if len(parts) == 5:
                self._api_report_item_recheck(parts[3], parts[4], session)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def _api_projects(self, qs):
        query = qs.get("query", [""])[0]
        api_params = {"per_page": 25}
        if query:
            api_params["query"] = query
        try:
            r = http_requests.get(f"{API_BASE}/projects", headers=cc_headers(_session_org_id(self)), params=api_params, timeout=10)
            r.raise_for_status()
            projects = r.json()
            slim = []
            for p in projects:
                # feature_image is an array of {type, uri} — grab thumbnail or first available
                thumb_url = None
                for fi in (p.get("feature_image") or []):
                    if fi.get("type") == "thumbnail":
                        thumb_url = fi.get("uri")
                        break
                if not thumb_url:
                    for fi in (p.get("feature_image") or []):
                        thumb_url = fi.get("uri")
                        break
                slim.append({
                    "id": p["id"],
                    "name": p.get("name", ""),
                    "address": p.get("address", {}).get("street_address_1", ""),
                    "city": p.get("address", {}).get("city", ""),
                    "state": p.get("address", {}).get("state", ""),
                    "featured_image": thumb_url,
                    "created_at": p.get("created_at"),
                    "updated_at": p.get("updated_at"),
                })
            self._send_json(slim)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_project_thumbnail(self, project_id):
        """Return the thumbnail URL from the project's first photo."""
        try:
            r = http_requests.get(
                f"{API_BASE}/projects/{project_id}/photos",
                headers=cc_headers(_session_org_id(self)), params={"per_page": 1}, timeout=10
            )
            r.raise_for_status()
            photos = r.json()
            if photos:
                for uri in photos[0].get("uris", []):
                    if uri.get("type") == "thumbnail":
                        self._send_json({"url": uri["url"]})
                        return
            self._send_json({"url": None})
        except Exception as e:
            print(f"WARNING: Failed to fetch thumbnail for project {project_id}: {e}", file=sys.stderr)
            self._send_json({"url": None})

    def _api_checklists(self, project_id):
        try:
            r = http_requests.get(f"{API_BASE}/projects/{project_id}/checklists", headers=cc_headers(_session_org_id(self)), timeout=10)
            r.raise_for_status()
            checklists = r.json()
            slim = []
            for cl in checklists:
                total_tasks = 0
                completed_tasks = 0
                # Tasks live either outside any section, or nested inside sections[].tasks[]
                for task in cl.get("sectionless_tasks", []) or []:
                    total_tasks += 1
                    if task.get("completed_at"):
                        completed_tasks += 1
                for section in cl.get("sections", []) or []:
                    for task in section.get("tasks", []) or []:
                        total_tasks += 1
                        if task.get("completed_at"):
                            completed_tasks += 1
                slim.append({
                    "id": cl.get("id"),
                    "name": cl.get("name", "Unknown"),
                    "completed_at": cl.get("completed_at"),
                    "template_id": cl.get("checklist_template_id"),
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                })
            self._send_json(slim)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _start_check(self, qs, session=None):
        """Start a compliance check. No longer limited to one per server —
        each run gets its own queue + cancel_event keyed by db_report_id.
        Returns run_id so the client can connect the right SSE stream.

        Order: derive params first (blocking, ~200ms) so we have all
        column values for a clean INSERT. Insert the report row to get
        run_id. Register the run. Spawn thread. Return run_id to client.
        The thread skips re-inserting since the row already exists."""
        session = session or {}
        project_id = qs.get("project_id", [""])[0]
        checklist_id = qs.get("checklist_id", [""])[0]
        manufacturer = qs.get("manufacturer", ["SolarEdge"])[0]
        project_state = qs.get("project_state", [""])[0]
        rerun_ids_raw = qs.get("rerun_ids", [""])[0]
        rerun_ids = set(rerun_ids_raw.split(",")) if rerun_ids_raw else None

        if not project_id or not checklist_id:
            self._send_json({"ok": False, "error": "project_id and checklist_id required"}, 400)
            return

        # 1. Derive params (fast ~200ms checklist fetch + address lookup).
        #    Must happen before the INSERT so we have all non-null columns.
        params = derive_params_from_checklist(project_id, checklist_id, manufacturer, project_state,
                                              org_id=session.get("org_id"))

        # 2. Insert the report row with full params → get run_id.
        run_id = None
        try:
            db_project_id = _upsert_project(project_id, session)
            is_test = session.get("role") == "superadmin"
            report_row = execute_returning(
                """INSERT INTO reports (project_id, run_by, manufacturer, has_battery,
                   is_backup_battery, is_incentive_state, portal_access_granted, is_test, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'running') RETURNING id""",
                (db_project_id, session.get("user_id"), params.get("manufacturer"),
                 params.get("has_battery", False), params.get("is_backup_battery", False),
                 params.get("is_incentive_state", False), params.get("portal_access_granted", False),
                 is_test),
            )
            run_id = report_row["id"] if report_row else None
        except Exception as e:
            print(f"WARNING: Could not create report row in DB: {e}", file=sys.stderr)

        # 3. Register this run. Use a fallback queue if DB insert failed —
        #    check still runs, just won't persist to the DB.
        if run_id:
            result_queue, cancel_event = _register_run(
                run_id, session.get("user_id"), session.get("org_id")
            )
        else:
            result_queue, cancel_event = queue.Queue(), threading.Event()

        result_queue.put(json.dumps({"type": "status", "message": "Starting check..."}))

        if rerun_ids:
            total = len(rerun_ids)
        else:
            total = sum(1 for r in REQUIREMENTS if r["condition"](params))

        # 4. Spawn thread. Thread skips the INSERT since the row was created
        #    above — it only needs to UPDATE when run finishes.
        t = threading.Thread(
            target=run_check_thread,
            args=(project_id, params, run_id, result_queue, cancel_event),
            kwargs={"rerun_ids": rerun_ids, "session": session},
            daemon=True,
            name=f"check-{run_id}",
        )
        t.start()

        self._send_json({
            "ok": True,
            "total": total,
            "project_id": project_id,
            "run_id": run_id,
            "derived_params": params,
        })

    def _api_cancel_check(self, body=None):
        """Request cancellation of a specific check by run_id.
        Body: {run_id: <int>}. Cooperative — the in-flight vision call
        finishes (~5-15s), then the loop exits and emits 'cancelled'."""
        try:
            data = json.loads(body) if body else {}
            run_id = data.get("run_id")
        except Exception:
            run_id = None
        if not run_id:
            self._send_json({"ok": False, "error": "run_id required"}, 400)
            return
        with _active_runs_lock:
            run = _active_runs.get(int(run_id))
        if not run:
            self._send_json({"ok": False, "error": "No active check with that run_id"}, 404)
            return
        run["cancel_event"].set()
        self._send_json({"ok": True})

    def _stream_sse(self, qs=None):
        """SSE stream for a specific check run. Client connects with
        /stream?run=<run_id> and receives progress/done/cancelled events.
        Sends keepalive comments every 15s so proxies don't drop the
        connection.

        If the run_id is not found (run finished before client connected,
        or invalid id) we emit a single 'not_found' event so the client
        can fall back to polling the report page."""
        run_id_raw = (qs or {}).get("run", [""])[0]
        try:
            run_id = int(run_id_raw) if run_id_raw else None
        except ValueError:
            run_id = None

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if not run_id:
            self.wfile.write(b'data: {"type":"error","message":"run_id required"}\n\n')
            self.wfile.flush()
            return

        with _active_runs_lock:
            run = _active_runs.get(run_id)
        if not run:
            # Run already finished or never existed — client should
            # navigate to the report page directly.
            self.wfile.write(b'data: {"type":"not_found"}\n\n')
            self.wfile.flush()
            return

        result_queue = run["queue"]
        try:
            while True:
                try:
                    data = result_queue.get(timeout=15)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    parsed = json.loads(data)
                    if parsed.get("type") in ("done", "cancelled", "error"):
                        break
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── Auth handlers ─────────────────────────────────────────────────────────

    def _api_login(self, body):
        """Authenticate with email + password. Returns session cookie."""
        try:
            data = json.loads(body)
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            if not email or not password:
                self._send_json({"error": "Email and password required"}, 400)
                return
            user = fetch_one(
                "SELECT id, email, first_name, last_name, full_name, role, organization_id, password_hash, is_active FROM users WHERE LOWER(email) = %s",
                (email,)
            )
            if not user:
                self._send_json({"error": "Invalid email or password"}, 401)
                return
            if not user.get("password_hash"):
                self._send_json({"error": "Check your email for an invitation link to set your password before logging in."}, 401)
                return
            if not user.get("is_active"):
                self._send_json({"error": "Account is deactivated"}, 403)
                return
            if not check_password(password, user["password_hash"]):
                self._send_json({"error": "Invalid email or password"}, 401)
                return
            token = create_session_token(user["id"], user["role"], user.get("organization_id"))
            # Send response with session cookie
            resp_body = json.dumps({
                "ok": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user.get("full_name") or f"{user['first_name']} {user['last_name']}",
                    "role": user["role"],
                }
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.send_header("Set-Cookie", set_session_cookie_header(token))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_forgot_password(self, body):
        """Send a password reset email."""
        try:
            data = json.loads(body)
            email = (data.get("email") or "").strip().lower()
            if not email:
                self._send_json({"error": "Email is required"}, 400)
                return
            # Rate limit: max 3 attempts per 15 minutes per email
            if not _check_rate_limit(email):
                self._send_json({"ok": True, "message": "If an account exists with that email, a reset link has been sent."})
                return  # Silently reject — don't reveal rate limiting to prevent enumeration
            # Always return success to prevent email enumeration
            user = fetch_one("SELECT id, email, is_active FROM users WHERE LOWER(email) = %s", (email,))
            if user and user.get("is_active"):
                token = create_reset_token(user["id"], user["email"])
                # Build reset URL — use Host header to get the right domain
                host = self.headers.get("Host", "localhost:8080")
                scheme = "https" if "railway" in host or "." in host else "http"
                reset_url = f"{scheme}://{host}/reset-password?token={token}"
                send_reset_email(user["email"], reset_url)
            self._send_json({"ok": True, "message": "If an account exists with that email, a reset link has been sent."})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_reset_password(self, body):
        """Reset password using a valid reset token."""
        try:
            data = json.loads(body)
            token = (data.get("token") or "").strip()
            new_password = (data.get("password") or "").strip()
            if not token or not new_password:
                self._send_json({"error": "Token and new password are required"}, 400)
                return
            if len(new_password) < 8:
                self._send_json({"error": "Password must be at least 8 characters"}, 400)
                return
            payload = validate_reset_token(token)
            if not payload:
                self._send_json({"error": "Invalid or expired reset link. Please request a new one."}, 400)
                return
            pw_hash = hash_password(new_password)
            execute("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s", (pw_hash, payload["user_id"]))
            self._send_json({"ok": True, "message": "Password updated. You can now sign in."})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_change_password(self, body, session):
        """Change password for the logged-in user (requires current password)."""
        try:
            data = json.loads(body)
            current_password = (data.get("current_password") or "").strip()
            new_password = (data.get("new_password") or "").strip()
            if not current_password or not new_password:
                self._send_json({"error": "Current and new password are required"}, 400)
                return
            if len(new_password) < 8:
                self._send_json({"error": "New password must be at least 8 characters"}, 400)
                return
            user = fetch_one("SELECT id, password_hash FROM users WHERE id = %s", (session["user_id"],))
            if not user or not check_password(current_password, user["password_hash"]):
                self._send_json({"error": "Current password is incorrect"}, 401)
                return
            pw_hash = hash_password(new_password)
            execute("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s", (pw_hash, session["user_id"]))
            self._send_json({"ok": True, "message": "Password changed successfully."})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _serve_forgot_password_page(self):
        body = FORGOT_PASSWORD_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _serve_reset_password_page(self, qs):
        token = qs.get("token", [""])[0]
        html = RESET_PASSWORD_HTML.replace("{{TOKEN}}", token)
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _serve_change_password_page(self):
        body = CHANGE_PASSWORD_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _api_request_demo(self, body):
        """Handle demo request form submission — save to DB and send notification email."""
        try:
            data = json.loads(body)
            name = (data.get("name") or "").strip()
            email = (data.get("email") or "").strip()
            phone = (data.get("phone") or "").strip()
            company = (data.get("company") or "").strip()
            message = (data.get("message") or "").strip()
            if not name:
                self._send_json({"error": "Name is required"}, 400)
                return
            if not email and not phone:
                self._send_json({"error": "Please provide either an email or phone number"}, 400)
                return
            # Save to DB
            execute(
                "INSERT INTO leads (name, email, phone, company, message) VALUES (%s, %s, %s, %s, %s)",
                (name, email or None, phone or None, company or None, message or None)
            )
            # Send notification email via Resend
            try:
                resend_key = os.getenv("RESEND_API_KEY")
                if resend_key:
                    import requests as req_lib
                    req_lib.post(
                        "https://api.resend.com/emails",
                        headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                        json={
                            "from": "inquiries@solclear.co",
                            "to": [os.getenv("DEMO_NOTIFY_EMAIL", "bap.builds@gmail.com")],
                            **({"reply_to": email} if email else {}),
                            "subject": f"Demo Request: {company or name}",
                            "html": (
                                '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;padding:24px;">'
                                f'<h2 style="font-size:18px;color:#1a1a2e;">New Demo Request</h2>'
                                f'<p><strong>Name:</strong> {name}</p>'
                                f'<p><strong>Email:</strong> {("<a href=mailto:" + email + ">" + email + "</a>") if email else "Not provided"}</p>'
                                f'<p><strong>Phone:</strong> {phone or "Not provided"}</p>'
                                f'<p><strong>Company:</strong> {company or "Not provided"}</p>'
                                f'<p><strong>Message:</strong> {message or "No message"}</p>'
                                '</div>'
                            ),
                        },
                        timeout=10,
                    )
            except Exception as e:
                print(f"WARNING: Could not send demo request notification: {e}", file=sys.stderr)
            self._send_json({"ok": True, "message": "Thank you! We'll be in touch shortly."})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _serve_request_demo_page(self):
        body = REQUEST_DEMO_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    # ── Organization API handlers ──────────────────────────────────────────────

    def _api_orgs_list(self, session=None):
        """List organizations with user + report counts.
        Superadmin sees all; admin sees only their own organization."""
        try:
            session = session or {}
            role = session.get("role")
            base_sql = """
                SELECT o.*,
                    (SELECT COUNT(*) FROM users u WHERE u.organization_id = o.id) AS user_count,
                    (SELECT COUNT(*) FROM reports r
                        JOIN projects p ON p.id = r.project_id
                        WHERE p.organization_id = o.id) AS report_count
                FROM organizations o
            """
            if role == "admin":
                orgs = fetch_all(base_sql + " WHERE o.id = %s ORDER BY o.created_at DESC",
                                 (session.get("org_id"),))
            else:
                orgs = fetch_all(base_sql + " ORDER BY o.created_at DESC")
            for o in orgs:
                o["created_at"] = o["created_at"].isoformat() if o.get("created_at") else None
                o["updated_at"] = o["updated_at"].isoformat() if o.get("updated_at") else None
            self._send_json(orgs)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_org_detail(self, org_id):
        """Get a single organization with its users."""
        try:
            org = fetch_one("SELECT * FROM organizations WHERE id = %s", (org_id,))
            if not org:
                self._send_json({"error": "Organization not found"}, 404)
                return
            org["created_at"] = org["created_at"].isoformat() if org.get("created_at") else None
            org["updated_at"] = org["updated_at"].isoformat() if org.get("updated_at") else None
            # Never return API key values — only indicate if they're set
            for key_field in ("companycam_api_key", "anthropic_api_key"):
                org[key_field + "_set"] = bool(org.get(key_field))
                org.pop(key_field, None)
            users = fetch_all("""
                SELECT id, email, first_name, last_name, full_name, phone, role, is_active, created_at
                FROM users WHERE organization_id = %s ORDER BY is_active DESC, created_at
            """, (org_id,))
            for u in users:
                u["created_at"] = u["created_at"].isoformat() if u.get("created_at") else None
            org["users"] = users
            self._send_json(org)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_org_users(self, org_id):
        """List users for an organization."""
        try:
            users = fetch_all("""
                SELECT id, email, first_name, last_name, full_name, phone, role, is_active, created_at
                FROM users WHERE organization_id = %s ORDER BY is_active DESC, created_at
            """, (org_id,))
            for u in users:
                u["created_at"] = u["created_at"].isoformat() if u.get("created_at") else None
            self._send_json(users)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_org_create(self, body):
        """Create a new organization."""
        try:
            data = json.loads(body)
            name = data.get("name", "").strip()
            if not name:
                self._send_json({"error": "Name is required"}, 400)
                return
            status = data.get("status", "onboarding")
            org = execute_returning(
                "INSERT INTO organizations (name, status) VALUES (%s, %s) RETURNING *",
                (name, status)
            )
            org["created_at"] = org["created_at"].isoformat() if org.get("created_at") else None
            org["updated_at"] = org["updated_at"].isoformat() if org.get("updated_at") else None
            self._send_json(org, 201)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_org_update(self, org_id, body, session=None):
        """Update an organization's name, status, API keys, or settings.
        Admins can edit their own org's name/API keys/settings. Status is
        a platform-level billing field reserved for superadmins."""
        try:
            data = json.loads(body)
            role = (session or {}).get("role")
            fields = []
            values = []
            if "name" in data:
                fields.append("name = %s")
                values.append(data["name"])
            if "status" in data:
                # Only superadmin can change status
                if role == "superadmin":
                    fields.append("status = %s")
                    values.append(data["status"])
                elif data["status"] is not None:
                    self._send_json({"error": "Only superadmin can change organization status"}, 403)
                    return
            # Encrypt API keys before storing
            for key_field in ("companycam_api_key", "anthropic_api_key"):
                if key_field in data and data[key_field]:
                    fields.append(f"{key_field} = %s")
                    values.append(encrypt(data[key_field]))
            if "settings" in data:
                fields.append("settings = %s")
                values.append(json.dumps(data["settings"]))
            if not fields:
                self._send_json({"error": "No fields to update"}, 400)
                return
            fields.append("updated_at = NOW()")
            values.append(org_id)
            org = execute_returning(
                f"UPDATE organizations SET {', '.join(fields)} WHERE id = %s RETURNING *",
                tuple(values)
            )
            if not org:
                self._send_json({"error": "Organization not found"}, 404)
                return
            org["created_at"] = org["created_at"].isoformat() if org.get("created_at") else None
            org["updated_at"] = org["updated_at"].isoformat() if org.get("updated_at") else None
            self._send_json(org)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_org_user_create(self, org_id, body):
        """Add a single user to an organization."""
        try:
            data = json.loads(body)
            email = data.get("email", "").strip()
            first_name = data.get("first_name", "").strip()
            last_name = data.get("last_name", "").strip()
            phone = (data.get("phone") or "").strip() or None
            role = data.get("role", "crew")
            VALID_ROLES = ("crew", "reviewer", "admin")
            if role not in VALID_ROLES:
                self._send_json({"error": f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}"}, 400)
                return
            if not email or not first_name or not last_name:
                self._send_json({"error": "Email, first name, and last name are required"}, 400)
                return
            # Password is no longer required on creation — if omitted, an
            # invite email is sent automatically so the user sets their own.
            password = (data.get("password") or "").strip()
            pw_hash = hash_password(password) if password else None
            user = execute_returning(
                "INSERT INTO users (organization_id, email, first_name, last_name, phone, role, password_hash) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (org_id, email, first_name, last_name, phone, role, pw_hash)
            )
            user["created_at"] = user["created_at"].isoformat() if user.get("created_at") else None
            user["updated_at"] = user["updated_at"].isoformat() if user.get("updated_at") else None

            # Auto-send invite when no password was provided
            invite_sent = False
            if not password and user.get("id"):
                try:
                    from tools.auth import create_invite_token, send_invite_email
                    token = create_invite_token(user["id"], email)
                    base_url = os.getenv("APP_PUBLIC_URL", "https://app.solclear.co")
                    invite_url = f"{base_url}/reset-password?token={token}"
                    # Get the inviting admin's name for the email copy
                    _s = getattr(self, "_session", {}) or {}
                    inviter = _s.get("full_name") or _s.get("email") or "Your admin"
                    invite_sent = send_invite_email(email, invite_url, invited_by=inviter)
                except Exception as e:
                    print(f"WARNING: invite email failed for {email}: {e}", file=sys.stderr)

            user["invite_sent"] = invite_sent
            self._send_json(user, 201)
        except Exception as e:
            if "unique" in str(e).lower():
                self._send_json({"error": f"User with email {email} already exists"}, 409)
            else:
                self._send_json({"error": str(e)}, 500)

    def _api_user_resend_invite(self, user_id):
        """Re-send the invitation email for a user who hasn't set a password yet.
        Only works when password_hash IS NULL — if the user already has a
        password they should use the forgot-password flow instead."""
        try:
            user = fetch_one("SELECT id, email, password_hash, is_active FROM users WHERE id = %s", (user_id,))
            if not user:
                self._send_json({"error": "User not found"}, 404)
                return
            if user.get("password_hash"):
                self._send_json({"error": "This user already has a password set. Direct them to Forgot Password instead."}, 400)
                return
            from tools.auth import create_invite_token, send_invite_email
            token = create_invite_token(user["id"], user["email"])
            base_url = os.getenv("APP_PUBLIC_URL", "https://app.solclear.co")
            invite_url = f"{base_url}/reset-password?token={token}"
            _s = getattr(self, "_session", {}) or {}
            inviter = _s.get("full_name") or _s.get("email") or "Your admin"
            sent = send_invite_email(user["email"], invite_url, invited_by=inviter)
            if sent:
                self._send_json({"ok": True, "message": f"Invitation email resent to {user['email']}"})
            else:
                self._send_json({"ok": False, "error": "Failed to send email — check Resend configuration"}, 500)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_user_toggle(self, user_id):
        """Toggle a user's is_active status and set/clear deactivated_at."""
        try:
            user = execute_returning(
                """UPDATE users SET
                    is_active = NOT is_active,
                    deactivated_at = CASE WHEN is_active THEN NOW() ELSE NULL END,
                    updated_at = NOW()
                WHERE id = %s RETURNING id, is_active, deactivated_at""",
                (user_id,)
            )
            if not user:
                self._send_json({"error": "User not found"}, 404)
                return
            if user.get("deactivated_at"):
                user["deactivated_at"] = user["deactivated_at"].isoformat()
            self._send_json(user)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_user_detail(self, user_id):
        """Get a single user."""
        try:
            user = fetch_one(
                "SELECT id, email, first_name, last_name, full_name, phone, role, is_active, deactivated_at, created_at, updated_at, password_hash FROM users WHERE id = %s",
                (user_id,)
            )
            if not user:
                self._send_json({"error": "User not found"}, 404)
                return
            for ts in ("created_at", "updated_at", "deactivated_at"):
                if user.get(ts):
                    user[ts] = user[ts].isoformat()
            # Expose whether a password has been set without exposing the hash
            user["has_password"] = bool(user.pop("password_hash", None))
            self._send_json(user)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_user_update(self, user_id, body):
        """Update a user's first_name, last_name, email, phone, or role."""
        try:
            data = json.loads(body)
            # Validate role if being changed
            if "role" in data:
                VALID_ROLES = ("crew", "reviewer", "admin")
                if data["role"] not in VALID_ROLES:
                    self._send_json({"error": f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}"}, 400)
                    return
            fields = []
            values = []
            for field in ("first_name", "last_name", "email", "phone", "role"):
                if field in data:
                    fields.append(f"{field} = %s")
                    values.append(data[field] if data[field] else None)
            if not fields:
                self._send_json({"error": "No fields to update"}, 400)
                return
            fields.append("updated_at = NOW()")
            values.append(user_id)
            user = execute_returning(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s RETURNING id, email, first_name, last_name, full_name, phone, role, is_active",
                tuple(values)
            )
            if not user:
                self._send_json({"error": "User not found"}, 404)
                return
            self._send_json(user)
        except Exception as e:
            if "unique" in str(e).lower():
                self._send_json({"error": "Email already in use"}, 409)
            else:
                self._send_json({"error": str(e)}, 500)

    def _api_org_users_csv(self, org_id, body):
        """Bulk create users from CSV. Format: email,first_name,last_name,role,phone (header optional)."""
        try:
            text = body.decode("utf-8")
            reader = csv.reader(io.StringIO(text))
            valid_rows = []
            errors = []
            for i, row in enumerate(reader):
                if len(row) < 3:
                    if len(row) >= 1 and row[0].strip().lower() == "email":
                        continue
                    errors.append(f"Row {i+1}: need at least email, first_name, last_name")
                    continue
                email = row[0].strip()
                first_name = row[1].strip()
                last_name = row[2].strip()
                role = row[3].strip() if len(row) > 3 else "crew"
                phone = row[4].strip() if len(row) > 4 else None
                if email.lower() == "email":
                    continue
                if not email or not first_name or not last_name:
                    errors.append(f"Row {i+1}: missing email, first_name, or last_name")
                    continue
                if role not in ("admin", "reviewer", "crew"):
                    role = "crew"
                valid_rows.append((org_id, email, first_name, last_name, phone, role))

            # Batch insert all valid rows in one query
            created = []
            if valid_rows:
                conn = get_conn()
                try:
                    import psycopg2.extras as pg_extras
                    cur = conn.cursor(cursor_factory=pg_extras.RealDictCursor)
                    pg_extras.execute_values(
                        cur,
                        "INSERT INTO users (organization_id, email, first_name, last_name, phone, role) VALUES %s RETURNING id, email, first_name, last_name, role",
                        valid_rows,
                        template="(%s, %s, %s, %s, %s, %s)"
                    )
                    created = [dict(row) for row in cur.fetchall()]
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    err_str = str(e).lower()
                    if "unique" in err_str:
                        errors.append("One or more emails already exist. No users were created from this batch.")
                    else:
                        errors.append(f"Batch insert failed: {e}")
                finally:
                    from tools.db import _return_conn
                    _return_conn(conn)

            self._send_json({"created": created, "errors": errors, "total": len(created)})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── Requirements handlers ────────────────────────────────────────────────

    def _api_requirements_list(self):
        """Return all requirements from compliance_check.py, grouped by section."""
        try:
            reqs = []
            for i, r in enumerate(REQUIREMENTS):
                req_id = r["id"]
                change_status = None
                if req_id in _recently_new:
                    change_status = "new"
                elif req_id in _recently_changed:
                    change_status = "changed"
                elif req_id in _recently_removed:
                    change_status = "removed"
                reqs.append({
                    "index": i,
                    "id": req_id,
                    "section": r["section"],
                    "title": r["title"],
                    "task_titles": r.get("task_titles", []),
                    "keywords": r.get("keywords", []),
                    "validation_prompt": r.get("validation_prompt", ""),
                    "optional": r.get("optional", False),
                    "is_stub": r.get("_stub", False),
                    "change_status": change_status,
                })
            self._send_json(reqs)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_requirement_detail(self, req_id):
        """Return a single requirement by its ID (e.g., 'PS1', 'R3')."""
        for i, r in enumerate(REQUIREMENTS):
            if r["id"] == req_id:
                self._send_json({
                    "index": i,
                    "id": r["id"],
                    "section": r["section"],
                    "title": r["title"],
                    "task_titles": r.get("task_titles", []),
                    "keywords": r.get("keywords", []),
                    "validation_prompt": r.get("validation_prompt", ""),
                    "optional": r.get("optional", False),
                })
                return
        self._send_json({"error": "Requirement not found"}, 404)

    def _api_requirement_update(self, req_id, body):
        """Update a requirement's editable fields in-memory. Note: does not persist across restarts yet."""
        try:
            data = json.loads(body)
            for r in REQUIREMENTS:
                if r["id"] == req_id:
                    if "validation_prompt" in data:
                        r["validation_prompt"] = data["validation_prompt"]
                    if "task_titles" in data:
                        r["task_titles"] = data["task_titles"]
                    if "keywords" in data:
                        r["keywords"] = data["keywords"]
                    if "title" in data:
                        r["title"] = data["title"]
                    self._send_json({"ok": True, "id": req_id, "message": "Updated in memory. Will reset on server restart until DB migration."})
                    return
            self._send_json({"error": "Requirement not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_requirements_monitor(self):
        """Return the current monitor status — last check time, hash, and whether changes were detected."""
        try:
            # Try database first
            row = fetch_one(
                "SELECT url, content_hash, checked_at, LENGTH(content_text) as length FROM requirement_snapshots WHERE url = %s ORDER BY checked_at DESC LIMIT 1",
                ("https://help.palmetto.finance/en/articles/8306274-solar-energy-plan-install-m1-photo-documentation",)
            )
            if row:
                self._send_json({
                    "status": "ok",
                    "url": row["url"],
                    "saved_at": row["checked_at"].isoformat() if row["checked_at"] else "",
                    "hash": row["content_hash"][:16] if row["content_hash"] else "",
                    "length": row["length"] or 0,
                    "has_snapshot": True,
                })
                return

            # Fallback to local file
            meta_path = TMP_DIR / "palmetto_requirements_meta.json"
            if not meta_path.exists():
                self._send_json({"status": "no_baseline", "message": "No baseline snapshot saved yet. Click 'Check Now' to create one."})
                return
            with open(meta_path) as f:
                meta = json.load(f)
            self._send_json({
                "status": "ok",
                "url": meta.get("url", ""),
                "saved_at": meta.get("saved_at", ""),
                "hash": meta.get("hash", "")[:16],
                "length": meta.get("length", 0),
                "has_snapshot": True,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_requirements_check_now(self):
        """Run the requirements monitor check and return results."""
        try:
            from tools.monitor_requirements import fetch_page, load_snapshot, save_snapshot, compare
            import re as re_mod
            import hashlib
            current = fetch_page()
            current_hash = hashlib.sha256(current.encode()).hexdigest()

            # Coverage check: find requirement IDs on Palmetto page vs what we have
            page_ids = set(re_mod.findall(r'\b(PS\d+|R\d+|E\d+|S\d+|SC\d+|SI\d+|AMS\d+)\b', current))
            our_ids = set(r["id"] for r in REQUIREMENTS)
            missing_from_us = sorted(page_ids - our_ids)
            extra_in_us = sorted(our_ids - page_ids)

            previous = load_snapshot()
            if not previous:
                # First run — save current as baseline
                save_snapshot(current)
                result = {"status": "baseline_created", "message": "Baseline created. Next check will compare against this version.", "hash": current_hash[:16]}
                if missing_from_us:
                    result["missing_ids"] = missing_from_us
                    result["message"] += f" Found {len(missing_from_us)} requirement(s) on Palmetto's page not in our system."
                self._send_json(result)
                return
            prev_hash = hashlib.sha256(previous.encode()).hexdigest()
            if current_hash == prev_hash:
                result = {"status": "no_changes", "hash": current_hash[:16]}
                if missing_from_us:
                    result["missing_ids"] = missing_from_us
                self._send_json(result)
            else:
                diff = compare(previous, current)
                diff_text = '\n'.join(diff[:100])
                added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
                removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
                # Get structured AI analysis (~$0.001)
                analysis = {"summary": "", "new_ids": [], "changed_ids": [], "removed_ids": []}
                try:
                    from tools.monitor_requirements import analyze_changes_structured
                    analysis = analyze_changes_structured(diff_text)
                except Exception as ex:
                    analysis["summary"] = f"{added} lines added, {removed} lines removed. Review the diff for details."

                # Update tracking sets
                global _recently_new, _recently_changed, _recently_removed
                for new_req in analysis.get("new_ids", []):
                    req_id = new_req.get("id", "")
                    if req_id and not any(r["id"] == req_id for r in REQUIREMENTS):
                        # Generate a suggested validation prompt for the new requirement
                        suggested_prompt = f"NEW: This requirement ({req_id}) was recently added by Palmetto. Configure the validation prompt before running checks."
                        try:
                            suggested_prompt = self._generate_validation_prompt(
                                req_id, new_req.get("title", ""), new_req.get("section", ""), diff_text
                            )
                        except Exception:
                            pass
                        # Create stub requirement
                        REQUIREMENTS.append({
                            "id": req_id,
                            "section": new_req.get("section", "Unknown"),
                            "title": new_req.get("title", f"New requirement {req_id} — needs configuration"),
                            "condition": lambda params: True,
                            "task_titles": [],
                            "keywords": [],
                            "validation_prompt": suggested_prompt,
                            "optional": True,
                            "_stub": True,
                        })
                    _recently_new[req_id] = {"section": new_req.get("section", ""), "title": new_req.get("title", ""), "ts": time.time()}

                for cid in analysis.get("changed_ids", []):
                    _recently_changed[cid] = time.time()

                for rid in analysis.get("removed_ids", []):
                    _recently_removed[rid] = time.time()

                _cleanup_stale_tracking()

                is_material = analysis.get("material", True)

                # Only notify for material changes — actual requirement
                # additions, modifications, or removals. Cosmetic diffs
                # (timestamps, layout, metadata) don't require action.
                if is_material:
                    try:
                        from tools.notifications import notify
                        from tools.db import fetch_all as _fa
                        body_notif = analysis.get("summary", f"{added} lines added, {removed} lines removed.")
                        superadmins = _fa("SELECT id FROM users WHERE role = 'superadmin' AND is_active = TRUE")
                        for u in superadmins:
                            notify(
                                u["id"], "palmetto_change", "⚠ Palmetto M1 spec changed", body_notif,
                                "https://help.palmetto.finance/en/articles/8306274-solar-energy-plan-install-m1-photo-documentation",
                                metadata={"added": added, "removed": removed},
                                send_email=True,
                            )
                        print(f"[palmetto] notified {len(superadmins)} superadmin(s)", file=sys.stderr)
                    except Exception as notify_err:
                        print(f"[palmetto] notification failed: {notify_err}", file=sys.stderr)
                else:
                    print("[palmetto] non-material change — skipping notification", file=sys.stderr)

                self._send_json({
                    "status": "changes_detected",
                    "material": is_material,
                    "added": added,
                    "removed": removed,
                    "summary": analysis.get("summary", ""),
                    "new_ids": analysis.get("new_ids", []),
                    "changed_ids": analysis.get("changed_ids", []),
                    "removed_ids": analysis.get("removed_ids", []),
                    "missing_ids": missing_from_us,
                    "diff_preview": diff_text,
                    "hash": current_hash[:16],
                })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _generate_validation_prompt(self, req_id, title, section, diff_text):
        """Generate a suggested validation prompt for a new requirement. Cost: ~$0.001."""
        import requests as req_lib
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return f"Verify this photo meets the {req_id} ({title}) requirement. Respond: PASS or FAIL, then one sentence explaining why."

        resp = req_lib.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"A new solar installation photo requirement was added by Palmetto Finance:\n"
                        f"- ID: {req_id}\n"
                        f"- Section: {section}\n"
                        f"- Title: {title}\n\n"
                        f"Context from the page diff:\n```\n{diff_text[:1500]}\n```\n\n"
                        f"Write a concise validation prompt for an AI vision model that will check a photo against this requirement. "
                        f"The prompt should:\n"
                        f"1. Describe what the photo should show\n"
                        f"2. List 2-3 specific things to verify\n"
                        f"3. End with: 'Respond: PASS or FAIL, then one sentence explaining why.'\n\n"
                        f"Return ONLY the prompt text, nothing else."
                    ),
                }],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()

    # ── Me / session info ────────────────────────────────────────────────────

    def _api_me(self, session):
        """Return the current user's session info so the SPA can render
        role-aware UI.

        The session token only carries user_id/role/org_id — look up email
        and full_name from the users table for display convenience.

        When impersonation is active, the active user_id/role/org_id are
        the impersonated values. is_impersonating + real_full_name/email
        let the UI render a "Stop impersonating [name]" banner."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        out = {
            "user_id": session.get("user_id"),
            "role": session.get("role"),
            "org_id": session.get("org_id"),
            "email": None,
            "full_name": None,
            "is_impersonating": bool(session.get("real_user_id")),
            "real_user_id": session.get("real_user_id"),
            "real_role": session.get("real_role"),
            "real_email": None,
            "real_full_name": None,
        }
        def _lookup(uid):
            if not uid:
                return None
            try:
                return fetch_one(
                    "SELECT email, full_name FROM users WHERE id = %s",
                    (uid,),
                )
            except Exception:
                return None
        u = _lookup(session.get("user_id"))
        if u:
            out["email"] = u.get("email")
            out["full_name"] = u.get("full_name")
        if out["is_impersonating"]:
            ru = _lookup(session.get("real_user_id"))
            if ru:
                out["real_email"] = ru.get("email")
                out["real_full_name"] = ru.get("full_name")
        # Piggy-back the cached Anthropic platform status so the SPA can
        # render a degraded-service banner without a second round trip.
        # Fresh polls happen in the background every 60s — /api/me is
        # called on first load (via loadMe); the SPA also polls
        # /api/platform_status directly on a 60s interval for refresh.
        with _anthropic_status_lock:
            out["platform_status"] = dict(_anthropic_status)
        self._send_json(out)

    def _api_req_timing_detail(self, req_code):
        """Per-run timing breakdown for one requirement. Powers the
        drill-down when a row in the Performance tab is clicked."""
        if not req_code:
            self._send_json({"error": "req_code required"}, 400)
            return
        try:
            rows = fetch_all("""
                SELECT r.id AS report_id,
                       p.name AS project_name,
                       rr.total_duration_ms,
                       rr.status,
                       rr.created_at,
                       COALESCE(acl.api_ms, 0)::INTEGER AS api_ms
                FROM requirement_results rr
                JOIN requirements req ON req.id = rr.requirement_id
                JOIN reports r ON r.id = rr.report_id
                JOIN projects p ON p.id = r.project_id
                LEFT JOIN (
                    SELECT report_id, requirement_code,
                           SUM(duration_ms) AS api_ms
                    FROM api_call_log
                    WHERE requirement_code = %s
                    GROUP BY report_id, requirement_code
                ) acl ON acl.report_id = rr.report_id
                WHERE req.code = %s
                  AND rr.total_duration_ms IS NOT NULL
                ORDER BY rr.created_at DESC
                LIMIT 50
            """, (req_code.upper(), req_code.upper()))
            for r in rows:
                if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                    r["created_at"] = r["created_at"].isoformat()
                if r.get("total_duration_ms"):
                    r["total_duration_ms"] = int(r["total_duration_ms"])
            self._send_json({"runs": rows, "req_code": req_code.upper()})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _serve_reference_photo_bytes(self, photo_id):
        """Serve the raw image bytes for a reference photo. Cached for 1 hour
        (photos only change when the Palmetto spec changes). No auth required."""
        try:
            row = fetch_one(
                "SELECT image_bytes, mime_type FROM requirement_reference_photos WHERE id = %s",
                (photo_id,),
            )
            if not row or not row.get("image_bytes"):
                self.send_error(404, "Photo not found")
                return
            data = bytes(row["image_bytes"])
            self.send_response(200)
            self.send_header("Content-Type", row.get("mime_type") or "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, str(e))

    def _api_reference_photo(self, req_code):
        """Return reference photo metadata for a requirement code.
        No auth required — reference photos are public Palmetto content.
        Returns a list of {id, alt_text, url} where url points to
        /api/reference_photos/{req_code}/{id}/img for the bytes."""
        if not req_code:
            self._send_json({"error": "req_code required"}, 400)
            return
        try:
            rows = fetch_all(
                "SELECT id, alt_text, display_order FROM requirement_reference_photos "
                "WHERE requirement_code = %s ORDER BY display_order ASC",
                (req_code.upper(),),
            )
            photos = [
                {
                    "id": r["id"],
                    "alt_text": r.get("alt_text") or "",
                    "url": f"/api/reference_photos/{req_code}/{r['id']}/img",
                }
                for r in rows
            ]
            self._send_json({"photos": photos})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_platform_status(self, session):
        """Lightweight endpoint for the SPA to poll every 60s. Returns
        just the cached Anthropic status — no DB hits, no auth beyond
        requiring a signed-in session. Kept separate from /api/me so a
        repeated 60s poll doesn't spam the users table."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        with _anthropic_status_lock:
            self._send_json(dict(_anthropic_status))

    def _api_my_active_check(self, session):
        """Return the logged-in user's active check state so the home
        page can show a 'your check is still running / just completed'
        banner even after they disconnected and came back later.

        Returns:
          - running: most recent report for this user with status='running',
            or null if none. Lets us show 'view progress →' on home.
          - recently_completed: most recent report with status in
            ('complete', 'cancelled') whose completed_at is within the
            last 30 min, or null. Gives us the 'view report →' banner
            for checks that finished while they were offline. Frontend
            stores dismissed report_ids in localStorage so the banner
            doesn't re-nag after the user has seen it once.

        No-op for unauthenticated; returns 401. Designed to be cheap
        enough to call on every home page load."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        user_id = session.get("user_id")
        if not user_id:
            self._send_json({"running": None, "recently_completed": None})
            return
        try:
            running = fetch_one("""
                SELECT r.id AS db_report_id,
                       p.companycam_id AS project_id,
                       p.name AS project_name,
                       r.started_at,
                       r.total_required
                FROM reports r
                JOIN projects p ON p.id = r.project_id
                WHERE r.run_by = %s AND r.status = 'running'
                ORDER BY r.started_at DESC
                LIMIT 1
            """, (user_id,))

            recent = fetch_one("""
                SELECT r.id AS db_report_id,
                       p.companycam_id AS project_id,
                       p.name AS project_name,
                       r.status,
                       r.completed_at,
                       r.total_passed, r.total_failed,
                       r.total_missing, r.total_needs_review, r.total_required
                FROM reports r
                JOIN projects p ON p.id = r.project_id
                WHERE r.run_by = %s
                  AND r.status IN ('complete', 'cancelled')
                  AND r.completed_at > NOW() - INTERVAL '30 minutes'
                ORDER BY r.completed_at DESC
                LIMIT 1
            """, (user_id,))

            def _iso(row, *keys):
                if not row:
                    return row
                for k in keys:
                    if row.get(k) and hasattr(row[k], "isoformat"):
                        row[k] = row[k].isoformat()
                return row

            self._send_json({
                "running": _iso(running, "started_at"),
                "recently_completed": _iso(recent, "completed_at"),
            })
        except Exception as e:
            # Non-critical endpoint — on any DB hiccup return empty
            # state rather than a 500. The banner is just nice-to-have.
            print(f"my_active_check failed: {e}", file=sys.stderr)
            self._send_json({"running": None, "recently_completed": None})

    # ── Notifications (top-bar bell) ─────────────────────────────────────────

    def _api_notifications_list(self, session, qs):
        """List notifications for the logged-in user. Newest first.
        Optional ?unread_only=1. Capped at 50 — the bell dropdown
        only shows recent activity, not the full history."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        try:
            from tools.notifications import list_for_user, unread_count
            unread_only = (qs.get("unread_only", [""])[0] == "1")
            rows = list_for_user(session.get("user_id"), unread_only=unread_only, limit=50)
            for r in rows:
                for k in ("created_at", "read_at"):
                    if r.get(k) and hasattr(r[k], "isoformat"):
                        r[k] = r[k].isoformat()
            self._send_json({
                "notifications": rows,
                "unread_count": unread_count(session.get("user_id")),
            })
        except Exception as e:
            print(f"notifications_list failed: {e}", file=sys.stderr)
            self._send_json({"notifications": [], "unread_count": 0})

    def _api_notifications_unread_count(self, session):
        """Lightweight badge endpoint — polled every 60s by the bell.
        Just the int count, no row data, so the poll is cheap."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        try:
            from tools.notifications import unread_count
            self._send_json({"unread_count": unread_count(session.get("user_id"))})
        except Exception as e:
            print(f"unread_count failed: {e}", file=sys.stderr)
            self._send_json({"unread_count": 0})

    def _api_notifications_mark_read(self, notification_id, session):
        """Mark one notification as read. Scoped by user_id in the
        helper so users can't flip each other's state."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        try:
            from tools.notifications import mark_read, unread_count
            mark_read(notification_id, session.get("user_id"))
            self._send_json({"ok": True, "unread_count": unread_count(session.get("user_id"))})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_notifications_mark_all_read(self, session):
        """Bulk-mark every unread notification for the user."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        try:
            from tools.notifications import mark_all_read
            n = mark_all_read(session.get("user_id"))
            self._send_json({"ok": True, "marked": n, "unread_count": 0})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── Dev Notes triage (superadmin only) ──────────────────────────────────

    def _api_dev_notes_list(self, session, qs):
        """List top-level dev notes for the triage tab. Each row includes
        author + project + requirement context + the inline reply
        thread. Optional ?status=open|acknowledged|corrected filter.

        Auth: caller must be superadmin (gated upstream in the route
        dispatcher). No org scoping — superadmin sees all orgs."""
        try:
            from tools.notes_db import list_dev_notes, list_replies_for_note, dev_notes_counts_by_status
            status_filter = (qs.get("status", [""])[0] or None) if qs else None
            if status_filter not in (None, "open", "acknowledged", "corrected"):
                self._send_json({"error": "Invalid status filter"}, 400)
                return
            notes = list_dev_notes(status_filter=status_filter, limit=200)
            # Attach reply thread for each. N+1 query pattern, fine for
            # the triage volume we expect (dozens of open notes max);
            # revisit if list grows.
            for n in notes:
                replies = list_replies_for_note(n["id"])
                for r in replies:
                    if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
                        r["created_at"] = r["created_at"].isoformat()
                n["replies"] = replies
                for k in ("created_at", "resolved_at"):
                    if n.get(k) and hasattr(n[k], "isoformat"):
                        n[k] = n[k].isoformat()
            self._send_json({
                "notes": notes,
                "counts": dev_notes_counts_by_status(),
            })
        except Exception as e:
            print(f"dev_notes_list failed: {e}", file=sys.stderr)
            self._send_json({"error": str(e)}, 500)

    def _api_dev_note_set_status(self, note_id, body, session):
        """Transition a dev note's triage state (open → acknowledged →
        corrected, or back to open). Notifies the original author."""
        try:
            from tools.notes_db import get_note, set_dev_note_status
            from tools.notifications import notify_dev_note_status_changed
            data = json.loads(body) if body else {}
            new_status = data.get("status")
            if new_status not in ("open", "acknowledged", "corrected"):
                self._send_json({"error": "Invalid status"}, 400)
                return
            note = get_note(note_id)
            if not note or note.get("visibility") != "dev" or note.get("parent_note_id"):
                # Refuse to triage replies or non-dev notes
                self._send_json({"error": "Note not found"}, 404)
                return
            updated = set_dev_note_status(note_id, new_status, session.get("user_id"))
            # Fire notification to original author (handler swallows
            # any errors — never fails the status transition)
            try:
                actor = fetch_one(
                    "SELECT full_name, email FROM users WHERE id = %s",
                    (session.get("user_id"),),
                ) or {}
                notify_dev_note_status_changed(
                    note,
                    new_status,
                    by_user_name=actor.get("full_name") or actor.get("email"),
                )
            except Exception as e:
                print(f"notify_dev_note_status_changed failed: {e}", file=sys.stderr)
            # Serialize timestamps
            for k in ("created_at", "resolved_at"):
                if updated and updated.get(k) and hasattr(updated[k], "isoformat"):
                    updated[k] = updated[k].isoformat()
            self._send_json({"ok": True, "note": updated})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_dev_note_reply(self, note_id, body, session):
        """Post a reply to a top-level dev note. Reply inherits visibility
        from the parent. Notifies everyone in the thread except the
        replier."""
        try:
            from tools.notes_db import get_note, add_note
            from tools.notifications import notify_dev_note_reply
            data = json.loads(body) if body else {}
            reply_body = (data.get("body") or "").strip()
            if not reply_body:
                self._send_json({"error": "Reply body is empty"}, 400)
                return
            parent = get_note(note_id)
            if not parent or parent.get("visibility") != "dev" or parent.get("parent_note_id"):
                # Only allow replies on top-level dev notes
                self._send_json({"error": "Note not found"}, 404)
                return
            reply = add_note(
                report_id=parent["report_id"],
                requirement_result_id=parent.get("requirement_result_id"),
                author_user_id=session.get("user_id"),
                visibility="dev",
                body=reply_body,
                parent_note_id=note_id,
            )
            # Fire bell notifications to thread participants
            try:
                actor = fetch_one(
                    "SELECT full_name, email FROM users WHERE id = %s",
                    (session.get("user_id"),),
                ) or {}
                notify_dev_note_reply(
                    parent,
                    reply,
                    replier_name=actor.get("full_name") or actor.get("email"),
                )
            except Exception as e:
                print(f"notify_dev_note_reply failed: {e}", file=sys.stderr)
            # Serialize timestamps
            if reply.get("created_at") and hasattr(reply["created_at"], "isoformat"):
                reply["created_at"] = reply["created_at"].isoformat()
            self._send_json({"ok": True, "reply": dict(reply)})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── Impersonation ────────────────────────────────────────────────────────

    def _api_impersonate(self, body, session):
        """Start (or re-target) impersonation. Requires the *real* role to be
        superadmin — once impersonating, the session.role field will be the
        impersonated role, so we check real_role first and fall back to role."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        # The requester's real role is the authoritative check — once
        # impersonating as e.g. admin, we still need superadmin powers to
        # re-target or stop.
        real_role = session.get("real_role") or session.get("role")
        real_user_id = session.get("real_user_id") or session.get("user_id")
        if real_role != "superadmin":
            self._send_json({"error": "Forbidden"}, 403)
            return
        try:
            data = json.loads(body) if body else {}
            target_id = int(data.get("user_id", 0) or 0)
            reason = (data.get("reason") or "").strip() or None
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid request"}, 400)
            return
        if target_id <= 0:
            self._send_json({"error": "user_id is required"}, 400)
            return
        if target_id == real_user_id:
            self._send_json({"error": "You cannot impersonate yourself"}, 400)
            return
        try:
            target = fetch_one(
                "SELECT id, role, organization_id, is_active, full_name FROM users WHERE id = %s",
                (target_id,),
            )
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
            return
        if not target:
            self._send_json({"error": "User not found"}, 404)
            return
        if not target.get("is_active"):
            self._send_json({"error": "Cannot impersonate an inactive user"}, 403)
            return
        # Close any currently-open impersonation log row for this superadmin
        try:
            execute(
                """UPDATE impersonation_log SET ended_at = NOW()
                   WHERE superadmin_id = %s AND ended_at IS NULL""",
                (real_user_id,),
            )
            execute(
                """INSERT INTO impersonation_log
                   (superadmin_id, impersonated_user_id, reason)
                   VALUES (%s, %s, %s)""",
                (real_user_id, target["id"], reason),
            )
        except Exception as e:
            print(f"WARNING: impersonation_log write failed: {e}", file=sys.stderr)
        # Mint the new session cookie
        token = create_session_token(
            user_id=target["id"],
            role=target["role"],
            org_id=target.get("organization_id"),
            real_user_id=real_user_id,
            real_role="superadmin",
            real_org_id=None,
        )
        body_out = json.dumps({
            "ok": True,
            "impersonating": {
                "user_id": target["id"],
                "full_name": target.get("full_name"),
                "role": target["role"],
            },
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", set_session_cookie_header(token))
        self.send_header("Content-Length", str(len(body_out)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body_out)

    def _api_stop_impersonate(self, session):
        """End an active impersonation and restore the superadmin session.
        No-op 200 if there's no active impersonation — safe to call anytime."""
        if not session:
            self._send_json({"error": "Not authenticated"}, 401)
            return
        real_user_id = session.get("real_user_id")
        if not real_user_id:
            self._send_json({"ok": True, "impersonating": False})
            return
        # Close the open log row
        try:
            execute(
                """UPDATE impersonation_log SET ended_at = NOW()
                   WHERE superadmin_id = %s AND ended_at IS NULL""",
                (real_user_id,),
            )
        except Exception as e:
            print(f"WARNING: impersonation_log close failed: {e}", file=sys.stderr)
        # Restore the superadmin session
        token = create_session_token(
            user_id=real_user_id,
            role=session.get("real_role") or "superadmin",
            org_id=session.get("real_org_id"),
        )
        body_out = json.dumps({"ok": True, "impersonating": False}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", set_session_cookie_header(token))
        self.send_header("Content-Length", str(len(body_out)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body_out)

    # ── Admin: cost dashboard ────────────────────────────────────────────────

    def _api_admin_cost_summary(self, qs=None):
        """Return per-report / per-requirement / per-day cost stats for the
        superadmin cost dashboard. Accepts optional filters via query string:
          org_id=<int>   — only cost from this org's projects
          user_id=<int>  — only cost from runs this user triggered (reports.run_by)
          from=YYYY-MM-DD — lower bound on called_at (inclusive)
          to=YYYY-MM-DD   — upper bound on called_at (inclusive, end-of-day)"""
        qs = qs or {}
        try:
            # Build a shared WHERE clause + params list. Every query joins
            # reports + projects LEFT so unattributed rows still count when
            # no report-based filter is set, and get filtered out naturally
            # when one is.
            filters = []
            params_list = []

            org_id = qs.get("org_id", [""])[0]
            user_id = qs.get("user_id", [""])[0]
            date_from = qs.get("from", [""])[0]
            date_to = qs.get("to", [""])[0]

            if org_id:
                filters.append("p.organization_id = %s")
                params_list.append(int(org_id))
            if user_id:
                filters.append("r.run_by = %s")
                params_list.append(int(user_id))
            if date_from:
                filters.append("a.called_at >= %s::timestamptz")
                params_list.append(date_from)
            if date_to:
                # End-of-day inclusive
                filters.append("a.called_at <= (%s::date + INTERVAL '1 day')::timestamptz")
                params_list.append(date_to)

            where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""
            params_t = tuple(params_list)

            # Totals — joins to reports/projects so org/user filters apply;
            # today and this_month are scoped to the same filter.
            totals = fetch_one(f"""
                SELECT
                  COALESCE(SUM(a.cost_usd), 0) AS all_time,
                  COALESCE(SUM(a.cost_usd) FILTER (WHERE a.called_at >= DATE_TRUNC('month', NOW())), 0) AS this_month,
                  COALESCE(SUM(a.cost_usd) FILTER (WHERE a.called_at >= DATE_TRUNC('day', NOW())), 0) AS today,
                  COUNT(*) AS call_count
                FROM api_call_log a
                LEFT JOIN reports r ON r.id = a.report_id
                LEFT JOIN projects p ON p.id = r.project_id
                {where_clause}
            """, params_t)

            # Per-purpose breakdown so superadmin can see what fraction of
            # spend is full vision runs vs cheap Haiku prefilter calls vs
            # single-item rechecks. NULL purpose (legacy rows) lumped as
            # 'unknown' so they're still surfaced.
            by_purpose = fetch_all(f"""
                SELECT COALESCE(a.purpose, 'unknown') AS purpose,
                       COUNT(*) AS call_count,
                       COALESCE(SUM(a.cost_usd), 0) AS total_cost,
                       COALESCE(AVG(a.cost_usd), 0) AS avg_cost
                FROM api_call_log a
                LEFT JOIN reports r ON r.id = a.report_id
                LEFT JOIN projects p ON p.id = r.project_id
                {where_clause}
                GROUP BY COALESCE(a.purpose, 'unknown')
                ORDER BY total_cost DESC
            """, params_t)

            top_reports = fetch_all(f"""
                SELECT r.id AS report_id,
                       p.name AS project_name,
                       p.companycam_id,
                       r.is_test,
                       r.completed_at,
                       COUNT(a.id) AS call_count,
                       COALESCE(SUM(a.cost_usd), 0) AS cost_usd
                FROM api_call_log a
                JOIN reports r ON r.id = a.report_id
                JOIN projects p ON p.id = r.project_id
                {where_clause}
                GROUP BY r.id, p.name, p.companycam_id, r.is_test, r.completed_at
                ORDER BY cost_usd DESC
                LIMIT 10
            """, params_t)

            # requirement_code filter needs to be AND'd with other filters
            req_where = "WHERE a.requirement_code IS NOT NULL"
            if filters:
                req_where += " AND " + " AND ".join(filters)
            top_reqs = fetch_all(f"""
                SELECT a.requirement_code,
                       COUNT(*) AS call_count,
                       COALESCE(AVG(a.cost_usd), 0) AS avg_cost,
                       COALESCE(MAX(a.cost_usd), 0) AS max_cost,
                       COALESCE(SUM(a.cost_usd), 0) AS total_cost
                FROM api_call_log a
                LEFT JOIN reports r ON r.id = a.report_id
                LEFT JOIN projects p ON p.id = r.project_id
                {req_where}
                GROUP BY a.requirement_code
                ORDER BY total_cost DESC
                LIMIT 10
            """, params_t)

            # Daily trend: always last 30 days regardless of date filter
            # (otherwise the chart becomes useless when a single-day filter is
            # set). Keep org/user filters, ignore date filter for this chart.
            daily_filters = [f for f in filters if not f.startswith("a.called_at")]
            daily_params = params_list[:len(daily_filters)]
            daily_where = "WHERE a.called_at >= NOW() - INTERVAL '30 days'"
            if daily_filters:
                daily_where += " AND " + " AND ".join(daily_filters)
            daily = fetch_all(f"""
                SELECT DATE_TRUNC('day', a.called_at)::date AS day,
                       COUNT(*) AS call_count,
                       COALESCE(SUM(a.cost_usd), 0) AS cost_usd
                FROM api_call_log a
                LEFT JOIN reports r ON r.id = a.report_id
                LEFT JOIN projects p ON p.id = r.project_id
                {daily_where}
                GROUP BY day
                ORDER BY day
            """, tuple(daily_params))

            recent = fetch_all(f"""
                SELECT a.id, a.report_id, p.name AS project_name,
                       a.requirement_code, a.purpose, a.model,
                       a.input_tokens, a.output_tokens,
                       a.cost_usd, a.duration_ms, a.called_at
                FROM api_call_log a
                LEFT JOIN reports r ON r.id = a.report_id
                LEFT JOIN projects p ON p.id = r.project_id
                {where_clause}
                ORDER BY a.id DESC
                LIMIT 20
            """, params_t)

            # Normalize datetime / numeric for JSON
            def _iso(row, *keys):
                for k in keys:
                    if row.get(k) and hasattr(row[k], "isoformat"):
                        row[k] = row[k].isoformat()
                # Decimals need to be floats
                for k in ("cost_usd", "avg_cost", "max_cost", "total_cost", "all_time", "this_month", "today"):
                    if k in row and row[k] is not None:
                        row[k] = float(row[k])
                return row

            # Per-requirement timing: lifetime averages — intentionally
            # unfiltered so the Performance tab always reflects inherent
            # speed characteristics of each requirement, not a filtered
            # window that would produce noisy averages on small samples.
            # Cast to INTEGER so these come back as Python int, not Decimal.
            # ROUND(AVG(...)) returns Postgres NUMERIC which Python's json.dumps
            # can't serialize — that was silently crashing the whole endpoint.
            req_timing = fetch_all("""
                SELECT req.code AS requirement_code,
                       COUNT(*) AS run_count,
                       ROUND(AVG(rr.total_duration_ms))::INTEGER AS avg_total_ms,
                       MIN(rr.total_duration_ms)::INTEGER AS min_total_ms,
                       MAX(rr.total_duration_ms)::INTEGER AS max_total_ms,
                       ROUND(COALESCE(AVG(acl.api_ms), 0))::INTEGER AS avg_api_ms
                FROM requirement_results rr
                JOIN requirements req ON req.id = rr.requirement_id
                LEFT JOIN (
                    SELECT report_id, requirement_code,
                           SUM(duration_ms) AS api_ms
                    FROM api_call_log
                    GROUP BY report_id, requirement_code
                ) acl ON acl.report_id = rr.report_id
                      AND acl.requirement_code = req.code
                WHERE rr.total_duration_ms IS NOT NULL
                GROUP BY req.code
                ORDER BY avg_total_ms DESC
                LIMIT 20
            """)

            totals = _iso(totals or {})
            top_reports = [_iso(r, "completed_at") for r in top_reports]
            top_reqs = [_iso(r) for r in top_reqs]
            daily = [_iso(r, "day") for r in daily]
            recent = [_iso(r, "called_at") for r in recent]
            by_purpose = [_iso(r) for r in by_purpose]
            req_timing = [_iso(r) for r in req_timing]

            self._send_json({
                "totals": totals,
                "by_purpose": by_purpose,
                "top_reports": top_reports,
                "top_requirements": top_reqs,
                "requirement_timing": req_timing,
                "daily_last_30": daily,
                "recent_calls": recent,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_admin_cost_filter_options(self):
        """Populate the Costs dashboard filter dropdowns with only the orgs
        and users that actually have cost rows — less noise than dumping
        every org/user in the system."""
        try:
            orgs = fetch_all("""
                SELECT DISTINCT o.id, o.name
                FROM api_call_log a
                JOIN reports r ON r.id = a.report_id
                JOIN projects p ON p.id = r.project_id
                JOIN organizations o ON o.id = p.organization_id
                ORDER BY o.name
            """)
            users = fetch_all("""
                SELECT DISTINCT u.id, u.full_name, u.email
                FROM api_call_log a
                JOIN reports r ON r.id = a.report_id
                JOIN users u ON u.id = r.run_by
                ORDER BY u.full_name
            """)
            self._send_json({"orgs": orgs, "users": users})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── Report handlers ──────────────────────────────────────────────────────

    def _api_reports(self, session=None):
        """Return a list of compliance reports from Postgres, scoped by org."""
        try:
            session = session or {}
            role = session.get("role", "")
            org_id = session.get("org_id")

            # Superadmins see all non-test reports + their own test reports
            # Org users see only their org's non-test reports
            # Include both 'complete' and 'cancelled' so users can get back
            # to a partially-completed report they cancelled mid-run; the
            # UI flags cancelled ones with a badge so it's clear the data
            # is partial.
            if role == "superadmin":
                rows = fetch_all("""
                    SELECT r.id, r.project_id, p.companycam_id, p.name, r.total_passed, r.total_failed,
                           r.total_missing, r.total_needs_review, r.total_required, r.is_test, r.status, r.created_at
                    FROM reports r
                    JOIN projects p ON p.id = r.project_id
                    WHERE r.status IN ('complete', 'cancelled')
                    ORDER BY r.created_at DESC
                    LIMIT 100
                """)
            else:
                rows = fetch_all("""
                    SELECT r.id, r.project_id, p.companycam_id, p.name, r.total_passed, r.total_failed,
                           r.total_missing, r.total_needs_review, r.total_required, r.is_test, r.status, r.created_at
                    FROM reports r
                    JOIN projects p ON p.id = r.project_id
                    WHERE r.status IN ('complete', 'cancelled') AND r.is_test = FALSE
                      AND p.organization_id = %s
                    ORDER BY r.created_at DESC
                    LIMIT 100
                """, (org_id,))

            reports = []
            for row in rows:
                # Fetch thumbnail from CompanyCam
                thumb_url = None
                try:
                    resp = http_requests.get(f"{API_BASE}/projects/{row['companycam_id']}",
                                             headers=cc_headers(_session_org_id(self)), timeout=5)
                    if resp.status_code == 200:
                        proj = resp.json()
                        for fi in (proj.get("feature_image") or []):
                            thumb_url = fi.get("uri")
                            break
                except Exception:
                    pass

                reports.append({
                    "db_report_id": row["id"],
                    "project_id": row["companycam_id"],
                    "name": row["name"],
                    "passed": row["total_passed"],
                    "failed": row["total_failed"],
                    "missing": row["total_missing"],
                    "needs_review": row.get("total_needs_review", 0) or 0,
                    "total": row["total_required"],
                    "is_test": row["is_test"],
                    "status": row["status"],
                    "timestamp": int(row["created_at"].timestamp()) if row.get("created_at") else 0,
                    "featured_image": thumb_url,
                })
            self._send_json(reports)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _serve_report(self, report_id, session=None):
        """Generate and serve a static HTML report from Postgres or .tmp/ fallback.

        `session` is needed to filter dev notes — reviewers and above see
        the whole thread; crew only sees public notes. When falling back
        to the .tmp/ legacy path (no DB), notes aren't available anyway."""
        report = None
        project = {}
        project_id = report_id  # May be DB report ID or CC project ID
        viewer_role = (session or {}).get("role") or "crew"

        # Try loading from Postgres first (report_id could be a DB ID)
        try:
            db_report = fetch_one("""
                SELECT r.*, p.companycam_id, p.name as project_name, p.address, p.city, p.state
                FROM reports r JOIN projects p ON p.id = r.project_id
                WHERE r.id = %s""", (report_id,))
            if db_report:
                # Load requirement results (including interactive fields).
                # LEFT JOIN on users so resolver name comes along when present.
                results = fetch_all("""
                    SELECT rr.id AS req_result_id,
                           rr.status, rr.reason, rr.photo_urls, rr.candidates,
                           rr.resolved_at, rr.resolved_by, rr.notes,
                           u.full_name AS resolved_by_name,
                           req.code as id, req.title, req.section, req.is_optional as optional
                    FROM requirement_results rr
                    JOIN requirements req ON req.id = rr.requirement_id
                    LEFT JOIN users u ON u.id = rr.resolved_by
                    WHERE rr.report_id = %s
                    ORDER BY req.id""", (report_id,))
                # ISO-format timestamps for JSON-serialization in the template
                for r in results:
                    if r.get("resolved_at"):
                        r["resolved_at"] = r["resolved_at"].isoformat()
                # Attach the notes thread for each requirement result.
                # list_notes_for_req_result filters dev notes by viewer role
                # (so crew never sees them), returns oldest-first.
                from tools.notes_db import list_notes_for_req_result
                for r in results:
                    rr_id = r.get("req_result_id")
                    if rr_id:
                        thread = list_notes_for_req_result(rr_id, viewer_role)
                        for n in thread:
                            for k in ("created_at", "resolved_at"):
                                if n.get(k) and hasattr(n[k], "isoformat"):
                                    n[k] = n[k].isoformat()
                        r["notes_thread"] = thread
                    else:
                        r["notes_thread"] = []
                report = {
                    "project_id": db_report["companycam_id"],
                    "params": {
                        "manufacturer": db_report.get("manufacturer"),
                        "lender": "LightReach",
                        "has_battery": db_report.get("has_battery"),
                        "is_backup_battery": db_report.get("is_backup_battery"),
                        "is_incentive_state": db_report.get("is_incentive_state"),
                        "portal_access_granted": db_report.get("portal_access_granted"),
                    },
                    "requirements": [dict(r) for r in results],
                    # checklist_ids is a JSONB array on the reports row
                    # (migration 004). Pre-migration / pre-fix rows return [].
                    "checklist_ids": db_report.get("checklist_ids") or [],
                    # status: 'complete' | 'cancelled' (from reports.status).
                    # Used by the report renderer to show a "Run full check
                    # again" CTA only on cancelled reports — completed ones
                    # don't need it (Re-run failed items is the right UX).
                    "status": db_report.get("status"),
                    "db_report_id": int(report_id),
                }
                project_id = db_report["companycam_id"]
                project = {"name": db_report.get("project_name", ""),
                           "address": {"street_address_1": db_report.get("address", ""),
                                       "city": db_report.get("city", ""),
                                       "state": db_report.get("state", "")}}
        except Exception:
            pass

        # Fallback to .tmp/ file (legacy or if DB load failed)
        if not report:
            report_path = TMP_DIR / f"compliance_{report_id}.json"
            if not report_path.exists():
                self.send_error(404, f"No report found for ID {report_id}")
                return
            try:
                with open(report_path) as f:
                    report = json.load(f)
            except Exception:
                self.send_error(500, "Failed to load report")
                return

        # Fetch project details from CompanyCam if not already loaded
        if not project.get("name"):
            try:
                r = http_requests.get(f"{API_BASE}/projects/{project_id}",
                                      headers=cc_headers(_session_org_id(self)), timeout=5)
                if r.status_code == 200:
                    project = r.json()
            except Exception:
                pass

        try:
            from tools.generate_report_html import generate_html
            # The template now renders its own top bar, summary card, tabs,
            # and rerun button — no post-hoc injections needed.
            html = generate_html(report, project)
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, str(e))

    def _serve_html(self):
        body = EMBEDDED_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    # ── Interactive report item actions ───────────────────────────────────────

    def _load_report_item(self, report_id, req_code, session):
        """Fetch a single requirement_results row, enforcing org scoping.
        Returns (row_dict, err_msg). If err_msg is set, respond & stop."""
        try:
            row = fetch_one(
                """SELECT rr.*, p.organization_id, p.companycam_id,
                          r.manufacturer, r.has_battery, r.is_backup_battery,
                          r.is_incentive_state, r.portal_access_granted
                   FROM requirement_results rr
                   JOIN requirements req ON req.id = rr.requirement_id
                   JOIN reports r ON r.id = rr.report_id
                   JOIN projects p ON p.id = r.project_id
                   WHERE rr.report_id = %s AND req.code = %s""",
                (report_id, req_code),
            )
            if not row:
                return None, "Report item not found"
            # Org scoping: non-superadmins must match the project's org
            if session.get("role") != "superadmin":
                if row.get("organization_id") != session.get("org_id"):
                    return None, "Forbidden"
            return row, None
        except Exception as e:
            return None, str(e)

    def _api_report_item_resolve(self, report_id, req_code, session):
        """Toggle an item's resolved state."""
        row, err = self._load_report_item(report_id, req_code, session)
        if err:
            status = 404 if err == "Report item not found" else (403 if err == "Forbidden" else 500)
            self._send_json({"error": err}, status)
            return
        try:
            now_null = row.get("resolved_at") is not None  # currently resolved → will un-resolve
            if now_null:
                updated = execute_returning(
                    "UPDATE requirement_results SET resolved_at = NULL, resolved_by = NULL WHERE id = %s RETURNING resolved_at, resolved_by",
                    (row["id"],),
                )
            else:
                updated = execute_returning(
                    "UPDATE requirement_results SET resolved_at = NOW(), resolved_by = %s WHERE id = %s RETURNING resolved_at, resolved_by",
                    (session.get("user_id"), row["id"]),
                )
            if updated and updated.get("resolved_at"):
                updated["resolved_at"] = updated["resolved_at"].isoformat()
            # Enrich with resolver name for the UI chip
            if updated and updated.get("resolved_by"):
                u = fetch_one("SELECT full_name FROM users WHERE id = %s", (updated["resolved_by"],))
                updated["resolved_by_name"] = u.get("full_name") if u else None
            self._send_json(updated or {})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_report_item_note(self, report_id, req_code, body, session):
        """Append a note to a report item's comment thread.

        Notes are immutable once posted (comment-thread style, not edit-
        in-place). Callers POST {note: "text", visibility: "public"|"dev"}.
        Visibility defaults to 'public'. Dev notes require the caller's
        role to be reviewer/admin/superadmin (can_file_dev_note).

        Returns the created note + the full refreshed thread so the UI
        can re-render without a second fetch."""
        row, err = self._load_report_item(report_id, req_code, session)
        if err:
            status = 404 if err == "Report item not found" else (403 if err == "Forbidden" else 500)
            self._send_json({"error": err}, status)
            return
        try:
            from tools.notes_db import (
                add_note, list_notes_for_req_result,
                can_file_dev_note,
            )
            data = json.loads(body) if body else {}
            note_body = (data.get("note") or "").strip()
            if not note_body:
                self._send_json({"error": "Note body is empty"}, 400)
                return
            visibility = data.get("visibility") or "public"
            if visibility not in ("public", "dev"):
                self._send_json({"error": "Invalid visibility"}, 400)
                return
            role = session.get("role") or ""
            if visibility == "dev" and not can_file_dev_note(role):
                self._send_json({"error": "Forbidden"}, 403)
                return

            created = add_note(
                report_id=int(report_id),
                requirement_result_id=row["id"],
                author_user_id=session.get("user_id"),
                visibility=visibility,
                body=note_body,
            )
            # Notify superadmins on dev-note filings (in-app + email).
            # Public notes don't fire notifications today — they're already
            # visible inline on the report; pinging on every crew comment
            # would be too noisy. May add per-user opt-in later.
            if visibility == "dev":
                try:
                    from tools.notifications import notify_dev_note_filed
                    # Session only carries user_id; look up name for the
                    # "From: Javier" line in Brandon's email.
                    filer = fetch_one(
                        "SELECT full_name, email FROM users WHERE id = %s",
                        (session.get("user_id"),),
                    ) or {}
                    note_for_notification = dict(created)
                    note_for_notification["req_code"] = req_code
                    notify_dev_note_filed(
                        note_for_notification,
                        filer_name=filer.get("full_name") or filer.get("email"),
                    )
                except Exception as e:
                    # Notification failure must NEVER break note creation
                    print(f"notify_dev_note_filed failed: {e}", file=sys.stderr)

            thread = list_notes_for_req_result(row["id"], role)
            # Serialize timestamps for JSON
            def _iso(n):
                for k in ("created_at", "resolved_at"):
                    if n.get(k) and hasattr(n[k], "isoformat"):
                        n[k] = n[k].isoformat()
                return n
            self._send_json({
                "ok": True,
                "created": _iso(dict(created)),
                "notes": [_iso(dict(n)) for n in thread],
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_report_item_recheck(self, report_id, req_code, session):
        """Re-run compliance for a single requirement on an existing report.
        Updates the requirement_results row in place and returns the new result."""
        row, err = self._load_report_item(report_id, req_code, session)
        if err:
            status = 404 if err == "Report item not found" else (403 if err == "Forbidden" else 500)
            self._send_json({"error": err}, status)
            return
        try:
            params = {
                "manufacturer": row.get("manufacturer"),
                "has_battery": row.get("has_battery", False),
                "is_backup_battery": row.get("is_backup_battery", False),
                "is_incentive_state": row.get("is_incentive_state", False),
                "portal_access_granted": row.get("portal_access_granted", False),
            }
            # Ensure the photos cache exists. Railway redeploys wipe
            # /app/.tmp/, so any recheck on a report from a prior deploy
            # would otherwise hit FileNotFoundError. Refetch on miss —
            # full check path does the same. (Longer-term fix: move the
            # cache out of ephemeral disk; see project_multi_user_readiness.md)
            cc_project_id = row["companycam_id"]
            photos_path = TMP_DIR / f"photos_{cc_project_id}.json"
            if not photos_path.exists():
                photos = get_all_photos(cc_project_id)
                TMP_DIR.mkdir(exist_ok=True)
                with open(photos_path, "w") as f:
                    json.dump(photos, f, indent=2)
            # Scope API-call logging to this report + requirement so the
            # recheck cost gets attributed correctly in api_call_log.
            from tools.compliance_check import set_call_context
            with set_call_context(report_id=int(report_id), purpose="recheck"):
                # Single-item rechecks don't benefit from a thread pool —
                # there's only one task to run. Force sequential to avoid
                # spinning up a worker thread for nothing.
                report = run_compliance_check(
                    cc_project_id, params,
                    run_vision=True, only_ids={req_code},
                    max_workers=1,
                )
            # Find the matching requirement result
            new_result = next(
                (r for r in report.get("requirements", []) if r.get("id") == req_code),
                None,
            )
            if not new_result:
                self._send_json({"error": "Recheck returned no result"}, 500)
                return
            # Update the existing row (not a new row — patches the current report)
            updated = execute_returning(
                """UPDATE requirement_results
                   SET status = %s, reason = %s, photo_urls = %s, candidates = %s,
                       resolved_at = NULL, resolved_by = NULL,
                       total_duration_ms = %s
                   WHERE id = %s
                   RETURNING status, reason, photo_urls, candidates""",
                (
                    new_result.get("status"),
                    new_result.get("reason"),
                    json.dumps(new_result.get("photo_urls", {})),
                    new_result.get("candidates", 0),
                    new_result.get("total_duration_ms"),
                    row["id"],
                ),
            )
            # Clear public notes — they were written about the prior
            # verdict and may no longer apply. Dev notes (bug reports
            # about Solclear itself) persist across rechecks.
            from tools.notes_db import clear_public_notes_for_req_result
            clear_public_notes_for_req_result(row["id"])
            # Recompute the report summary so totals stay correct
            self._recompute_report_summary(report_id)
            self._send_json(updated or {})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _recompute_report_summary(self, report_id):
        """Recount status buckets across requirement_results and write back to reports.

        Totals exclude optional requirements and N/A rows, matching the aggregation
        done at initial save time in run_check_thread.
        """
        try:
            counts = fetch_one(
                """SELECT
                     COUNT(*) FILTER (WHERE rr.status != 'N/A') AS total,
                     COUNT(*) FILTER (WHERE rr.status = 'PASS') AS passed,
                     COUNT(*) FILTER (WHERE rr.status = 'FAIL') AS failed,
                     COUNT(*) FILTER (WHERE rr.status = 'MISSING') AS missing,
                     COUNT(*) FILTER (WHERE rr.status = 'NEEDS_REVIEW') AS needs_review
                   FROM requirement_results rr
                   JOIN requirements req ON req.id = rr.requirement_id
                   WHERE rr.report_id = %s AND req.is_optional = FALSE""",
                (report_id,),
            )
            if counts:
                execute(
                    """UPDATE reports SET total_required = %s, total_passed = %s,
                       total_failed = %s, total_missing = %s, total_needs_review = %s
                       WHERE id = %s""",
                    (counts["total"], counts["passed"], counts["failed"],
                     counts["missing"], counts["needs_review"], report_id),
                )
        except Exception as e:
            print(f"WARNING: Failed to recompute report summary: {e}", file=sys.stderr)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── HTML templates (extracted to html_pages.py) ──────────────────────────────
from tools.html_pages import (
    LOGIN_HTML, FORGOT_PASSWORD_HTML, RESET_PASSWORD_HTML,
    CHANGE_PASSWORD_HTML, REQUEST_DEMO_HTML, EMBEDDED_HTML,
)


# ── Main ─────────────────────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def _mark_running_checks_cancelled_on_shutdown():
    """Best-effort: mark every report stuck in status='running' as
    'cancelled' before this process exits, and recompute totals from
    requirement_results so the partial report shows useful counts.

    Without this, a Railway redeploy (SIGTERM) leaves the report
    zombified — the worker thread is killed mid-call, never updates
    status, and the user sees a permanently 'still running' banner.

    Runs from the SIGTERM handler with ~10s of grace before SIGKILL.
    Wrapped in try/except since the DB might be unreachable during
    shutdown — we'd rather exit cleanly than block."""
    try:
        from tools.db import execute, fetch_all
        rows = fetch_all("SELECT id FROM reports WHERE status = 'running'")
        if not rows:
            return
        for r in rows:
            counts = fetch_all(
                """SELECT
                     COUNT(*) FILTER (WHERE rr.status != 'N/A') AS total,
                     COUNT(*) FILTER (WHERE rr.status = 'PASS') AS passed,
                     COUNT(*) FILTER (WHERE rr.status = 'FAIL') AS failed,
                     COUNT(*) FILTER (WHERE rr.status = 'MISSING') AS missing,
                     COUNT(*) FILTER (WHERE rr.status = 'NEEDS_REVIEW') AS needs_review
                   FROM requirement_results rr
                   JOIN requirements req ON req.id = rr.requirement_id
                   WHERE rr.report_id = %s AND req.is_optional = FALSE""",
                (r["id"],),
            )
            c = counts[0] if counts else {}
            execute(
                """UPDATE reports
                   SET status = 'cancelled', completed_at = NOW(),
                       total_required = %s, total_passed = %s, total_failed = %s,
                       total_missing = %s, total_needs_review = %s
                   WHERE id = %s AND status = 'running'""",
                (c.get("total", 0), c.get("passed", 0), c.get("failed", 0),
                 c.get("missing", 0), c.get("needs_review", 0), r["id"]),
            )
        print(f"[shutdown] marked {len(rows)} running report(s) as cancelled", file=sys.stderr)
    except Exception as e:
        print(f"[shutdown] cleanup failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Live compliance check server")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    local_ip = get_local_ip()
    server = ThreadedHTTPServer(("0.0.0.0", args.port), LiveHandler)

    # Kick off the Anthropic platform-status poller as a daemon thread so
    # the UI can surface "API is degraded" banners without having to wait
    # for a compliance check to fail first. See _poll_anthropic_status.
    threading.Thread(target=_poll_anthropic_status, daemon=True,
                     name="anthropic-status-poller").start()

    # Graceful shutdown: when Railway redeploys (or any platform sends
    # SIGTERM), mark in-flight reports as cancelled before exit so the
    # UI doesn't show them as eternally "still running". Railway gives
    # ~10s between SIGTERM and SIGKILL — plenty for this small DB write.
    # Server-restart durability (resuming the actual check) is a bigger
    # change tracked in project_multi_user_readiness.md; this just stops
    # the zombie-report symptom.
    import signal
    def _on_term(signum, frame):
        print(f"[shutdown] signal {signum} received, cleaning up…", file=sys.stderr)
        _mark_running_checks_cancelled_on_shutdown()
        try:
            server.shutdown()
        except Exception:
            pass
        sys.exit(0)
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)

    print(f"\n  Solclear Live Compliance Server")
    print(f"  ────────────────────────────────")
    print(f"  Local:   http://localhost:{args.port}")
    print(f"  Network: http://{local_ip}:{args.port}")
    print(f"\n  Share the network URL with field crews.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # SIGINT is also handled above, but keep this fallback in case
        # a non-default handler is somehow active during shutdown.
        _mark_running_checks_cancelled_on_shutdown()
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
