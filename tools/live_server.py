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

import argparse
import csv
import io
import json
import os
import queue
import socket
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# Add project root to path so we can import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

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

# ── Global state ─────────────────────────────────────────────────────────────

_check_lock = threading.Lock()
_check_running = False
_result_queue = queue.Queue()

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


def cc_headers():
    return {"Authorization": f"Bearer {CC_TOKEN}", "Content-Type": "application/json"}


def derive_params_from_checklist(project_id, checklist_id, manufacturer, project_state=""):
    """Auto-derive job parameters from checklist data and project address."""
    headers = cc_headers()
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

def run_check_thread(project_id, params, rerun_ids=None):
    global _check_running
    try:
        # Ensure photos are cached
        photos_path = TMP_DIR / f"photos_{project_id}.json"
        if not photos_path.exists():
            _result_queue.put(json.dumps({"type": "status", "message": "Fetching photos from CompanyCam..."}))
            photos = get_all_photos(project_id)
            TMP_DIR.mkdir(exist_ok=True)
            with open(photos_path, "w") as f:
                json.dump(photos, f, indent=2)
            _result_queue.put(json.dumps({"type": "status", "message": f"Fetched {len(photos)} photos. Starting check..."}))

        if rerun_ids:
            # Rerun failed only — load previous report, re-check only failed IDs
            _result_queue.put(json.dumps({"type": "status", "message": f"Re-checking {len(rerun_ids)} failed requirements..."}))
            prev_path = TMP_DIR / f"compliance_{project_id}.json"
            prev_report = {}
            if prev_path.exists():
                with open(prev_path) as f:
                    prev_report = json.load(f)
            prev_results = {r["id"]: r for r in prev_report.get("requirements", [])}

            def on_progress(result, index, total):
                _result_queue.put(json.dumps({
                    "type": "progress",
                    "index": index,
                    "total": total,
                    "requirement": result,
                }))

            report = run_compliance_check(project_id, params, run_vision=True,
                                          progress_callback=on_progress, only_ids=rerun_ids)

            # Merge: use new results for rerun IDs, keep old results for the rest
            new_results = {r["id"]: r for r in report.get("requirements", [])}
            merged = []
            for r in prev_report.get("requirements", []):
                if r["id"] in new_results:
                    merged.append(new_results[r["id"]])
                else:
                    merged.append(r)
            # Add any new IDs not in previous (unlikely but safe)
            for r in report.get("requirements", []):
                if r["id"] not in {m["id"] for m in merged}:
                    merged.append(r)

            report["requirements"] = merged
        else:
            def on_progress(result, index, total):
                _result_queue.put(json.dumps({
                    "type": "progress",
                    "index": index,
                    "total": total,
                    "requirement": result,
                }))

            report = run_compliance_check(project_id, params, run_vision=True, progress_callback=on_progress)

        # Save report JSON
        TMP_DIR.mkdir(exist_ok=True)
        with open(TMP_DIR / f"compliance_{project_id}.json", "w") as f:
            json.dump(report, f, indent=2)

        # Summary
        reqs = report["requirements"]
        required = [r for r in reqs if r["status"] != "N/A" and not r.get("optional")]
        _result_queue.put(json.dumps({
            "type": "done",
            "summary": {
                "passed": sum(1 for r in required if r["status"] == "PASS"),
                "failed": sum(1 for r in required if r["status"] == "FAIL"),
                "missing": sum(1 for r in required if r["status"] == "MISSING"),
                "total": len(required),
                "project_id": project_id,
                "checklist_ids": report.get("checklist_ids", []),
            }
        }))
    except Exception as e:
        _result_queue.put(json.dumps({"type": "error", "message": str(e)}))
    finally:
        with _check_lock:
            _check_running = False


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
        if path == "/login":
            self._serve_login_page()
            return
        if path == "/forgot-password":
            self._serve_forgot_password_page()
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

        # All other routes require auth
        session = self._require_auth()
        if not session:
            return

        if path == "/":
            self._serve_html()
        elif path == "/change-password":
            self._serve_change_password_page()
        elif path == "/api/projects":
            self._api_projects(qs)
        elif path.startswith("/api/projects/") and path.endswith("/thumbnail"):
            pid = path.split("/")[3]
            self._api_project_thumbnail(pid)
        elif path.startswith("/api/projects/") and path.endswith("/checklists"):
            pid = path.split("/")[3]
            self._api_checklists(pid)
        elif path == "/api/reports":
            self._api_reports()
        # ── Admin routes (superadmin/admin only) ──
        elif path == "/api/requirements":
            if not self._require_role(session, ("superadmin", "admin")):
                return
            self._api_requirements_list()
        elif path == "/api/requirements/monitor/status":
            if not self._require_role(session, ("superadmin", "admin")):
                return
            self._api_requirements_monitor()
        elif path.startswith("/api/requirements/") and len(path.split("/")) == 4:
            if not self._require_role(session, ("superadmin", "admin")):
                return
            req_id = path.split("/")[3]
            self._api_requirement_detail(req_id)
        elif path == "/api/organizations":
            if not self._require_role(session, ("superadmin", "admin")):
                return
            self._api_orgs_list()
        elif path.startswith("/api/users/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            self._api_user_detail(uid)
        elif path.startswith("/api/organizations/") and path.endswith("/users"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            self._api_org_users(oid)
        elif path.startswith("/api/organizations/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            self._api_org_detail(oid)
        elif path.startswith("/report/"):
            pid = path.split("/")[2]
            self._serve_report(pid)
        elif path == "/start":
            self._start_check(qs)
        elif path == "/stream":
            self._stream_sse()
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

        # All other POSTs require auth
        session = self._require_auth()
        if not session:
            return

        if path == "/api/change-password":
            self._api_change_password(body, session)
        # ── Admin POST routes (superadmin/admin only) ──
        elif path == "/api/organizations":
            if not self._require_role(session, ("superadmin", "admin")):
                return
            self._api_org_create(body)
        elif path.startswith("/api/organizations/") and path.endswith("/users/csv"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            self._api_org_users_csv(oid, body)
        elif path.startswith("/api/organizations/") and path.endswith("/users"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            self._api_org_user_create(oid, body)
        elif path.startswith("/api/users/") and path.endswith("/toggle"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            self._api_user_toggle(uid)
        elif path.startswith("/api/users/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            uid = path.split("/")[3]
            self._api_user_update(uid, body)
        elif path == "/api/requirements/check":
            if not self._require_role(session, ("superadmin", "admin")):
                return
            self._api_requirements_check_now()
        elif path.startswith("/api/requirements/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            req_id = path.split("/")[3]
            self._api_requirement_update(req_id, body)
        elif path.startswith("/api/organizations/"):
            if not self._require_role(session, ("superadmin", "admin")):
                return
            oid = path.split("/")[3]
            self._api_org_update(oid, body)
        else:
            self.send_error(404)

    def _api_projects(self, qs):
        query = qs.get("query", [""])[0]
        api_params = {"per_page": 25}
        if query:
            api_params["query"] = query
        try:
            r = http_requests.get(f"{API_BASE}/projects", headers=cc_headers(), params=api_params, timeout=10)
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
                headers=cc_headers(), params={"per_page": 1}, timeout=10
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
            r = http_requests.get(f"{API_BASE}/projects/{project_id}/checklists", headers=cc_headers(), timeout=10)
            r.raise_for_status()
            checklists = r.json()
            slim = [{
                "id": cl.get("id"),
                "name": cl.get("name", "Unknown"),
                "completed_at": cl.get("completed_at"),
                "template_id": cl.get("checklist_template_id"),
            } for cl in checklists]
            self._send_json(slim)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _start_check(self, qs):
        global _check_running

        with _check_lock:
            if _check_running:
                self._send_json({"ok": False, "error": "A check is already running"}, 409)
                return
            _check_running = True

        # Drain any old events
        while not _result_queue.empty():
            try:
                _result_queue.get_nowait()
            except queue.Empty:
                break

        project_id = qs.get("project_id", [""])[0]
        checklist_id = qs.get("checklist_id", [""])[0]
        manufacturer = qs.get("manufacturer", ["SolarEdge"])[0]
        project_state = qs.get("project_state", [""])[0]
        rerun_ids_raw = qs.get("rerun_ids", [""])[0]
        rerun_ids = set(rerun_ids_raw.split(",")) if rerun_ids_raw else None

        if not project_id or not checklist_id:
            with _check_lock:
                _check_running = False
            self._send_json({"ok": False, "error": "project_id and checklist_id required"}, 400)
            return

        # Auto-derive params from checklist data + project address
        _result_queue.put(json.dumps({"type": "status", "message": "Reading checklist and deriving job parameters..."}))
        params = derive_params_from_checklist(project_id, checklist_id, manufacturer, project_state)

        if rerun_ids:
            total = len(rerun_ids)
        else:
            total = sum(1 for r in REQUIREMENTS if r["condition"](params))

        t = threading.Thread(target=run_check_thread, args=(project_id, params, rerun_ids), daemon=True)
        t.start()

        self._send_json({"ok": True, "total": total, "project_id": project_id, "derived_params": params})

    def _stream_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            while True:
                try:
                    data = _result_queue.get(timeout=15)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    parsed = json.loads(data)
                    if parsed.get("type") in ("done", "error"):
                        break
                except queue.Empty:
                    # keepalive
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
            if not user or not user.get("password_hash"):
                self._send_json({"error": "Invalid email or password"}, 401)
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

    # ── Organization API handlers ──────────────────────────────────────────────

    def _api_orgs_list(self):
        """List all organizations with user and report counts."""
        try:
            orgs = fetch_all("""
                SELECT o.*,
                    (SELECT COUNT(*) FROM users u WHERE u.organization_id = o.id) AS user_count,
                    (SELECT COUNT(*) FROM reports r
                        JOIN projects p ON p.id = r.project_id
                        WHERE p.organization_id = o.id) AS report_count
                FROM organizations o
                ORDER BY o.created_at DESC
            """)
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

    def _api_org_update(self, org_id, body):
        """Update an organization's name, status, API keys, or settings."""
        try:
            data = json.loads(body)
            fields = []
            values = []
            for field in ("name", "status"):
                if field in data:
                    fields.append(f"{field} = %s")
                    values.append(data[field])
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
            password = (data.get("password") or "").strip()
            if not email or not first_name or not last_name:
                self._send_json({"error": "Email, first name, and last name are required"}, 400)
                return
            pw_hash = hash_password(password) if password else None
            user = execute_returning(
                "INSERT INTO users (organization_id, email, first_name, last_name, phone, role, password_hash) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (org_id, email, first_name, last_name, phone, role, pw_hash)
            )
            user["created_at"] = user["created_at"].isoformat() if user.get("created_at") else None
            user["updated_at"] = user["updated_at"].isoformat() if user.get("updated_at") else None
            self._send_json(user, 201)
        except Exception as e:
            if "unique" in str(e).lower():
                self._send_json({"error": f"User with email {email} already exists"}, 409)
            else:
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
                "SELECT id, email, first_name, last_name, full_name, phone, role, is_active, deactivated_at, created_at, updated_at FROM users WHERE id = %s",
                (user_id,)
            )
            if not user:
                self._send_json({"error": "User not found"}, 404)
                return
            for ts in ("created_at", "updated_at", "deactivated_at"):
                if user.get(ts):
                    user[ts] = user[ts].isoformat()
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

    # ── Report handlers ──────────────────────────────────────────────────────

    def _api_reports(self):
        """Return a list of previously generated compliance reports."""
        import glob
        reports = []
        for f in sorted(glob.glob(str(TMP_DIR / "compliance_*.json")), reverse=True):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                pid = data.get("project_id", "")
                reqs = data.get("requirements", [])
                required = [r for r in reqs if r.get("status") != "N/A" and not r.get("optional")]
                passed = sum(1 for r in required if r["status"] == "PASS")
                failed = sum(1 for r in required if r["status"] in ("FAIL", "MISSING", "ERROR"))
                # Get project name and image from CompanyCam
                name = pid
                thumb_url = None
                try:
                    r = http_requests.get(f"{API_BASE}/projects/{pid}",
                                          headers=cc_headers(), timeout=5)
                    if r.status_code == 200:
                        proj = r.json()
                        name = proj.get("name", pid)
                        for fi in (proj.get("feature_image") or []):
                            if fi.get("type") == "thumbnail":
                                thumb_url = fi.get("uri")
                                break
                        if not thumb_url:
                            for fi in (proj.get("feature_image") or []):
                                thumb_url = fi.get("uri")
                                break
                except Exception:
                    pass
                mtime = os.path.getmtime(f)
                reports.append({
                    "project_id": pid,
                    "name": name,
                    "passed": passed,
                    "failed": failed,
                    "total": len(required),
                    "timestamp": int(mtime),
                    "featured_image": thumb_url,
                })
            except Exception:
                continue
        self._send_json(reports)

    def _serve_report(self, project_id):
        """Generate and serve a static HTML report from saved compliance JSON."""
        report_path = TMP_DIR / f"compliance_{project_id}.json"
        if not report_path.exists():
            self.send_error(404, f"No report found for project {project_id}")
            return
        try:
            with open(report_path) as f:
                report = json.load(f)
            # Fetch project details for the report header
            project = {}
            try:
                r = http_requests.get(f"{API_BASE}/projects/{project_id}",
                                      headers=cc_headers(), timeout=5)
                if r.status_code == 200:
                    project = r.json()
            except Exception:
                pass
            from tools.generate_report_html import generate_html
            html = generate_html(report, project)

            # Count failed requirements for the rerun button
            reqs = report.get("requirements", [])
            failed_ids = [r["id"] for r in reqs if r.get("status") in ("FAIL", "MISSING", "ERROR") and r.get("status") != "N/A"]
            n_failed = len(failed_ids)
            params = report.get("params", {})
            checklist_ids = report.get("checklist_ids", [])

            # Inject back link at the top (after <body>)
            back_bar = '''
<div style="background:#111827;padding:10px 20px;">
  <a href="/" style="color:#9ca3af;text-decoration:none;font-size:13px;font-weight:500;">&larr; Back to Solclear</a>
</div>'''
            html = html.replace("<body>", "<body>" + back_bar, 1)

            # Inject rerun button right after the overall banner
            if n_failed > 0:
                rerun_btn = f'''
<div style="padding:12px 32px;background:#fff;border-bottom:1px solid #e5e7eb;">
  <button onclick="rerunFailed()" style="background:#ef4444;color:#fff;border:none;border-radius:8px;padding:12px 20px;font-size:14px;font-weight:600;cursor:pointer;min-height:44px;width:100%;">
    Rerun {n_failed} Failed Item{"s" if n_failed != 1 else ""}
  </button>
</div>
<script>
function rerunFailed() {{
  const qs = new URLSearchParams({{
    project_id: "{project_id}",
    checklist_id: "{checklist_ids[0] if checklist_ids else ""}",
    manufacturer: "{params.get("manufacturer", "SolarEdge")}",
    project_state: "",
    rerun_ids: "{",".join(failed_ids)}",
  }});
  window.location.href = "/?rerun=" + encodeURIComponent(qs.toString());
}}
</script>'''
                # Insert after the params-bar div
                html = html.replace('class="body">', 'class="body">' + rerun_btn, 1)

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


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── HTML templates (extracted to html_pages.py) ──────────────────────────────
from tools.html_pages import (
    LOGIN_HTML, FORGOT_PASSWORD_HTML, RESET_PASSWORD_HTML,
    CHANGE_PASSWORD_HTML, EMBEDDED_HTML,
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


def main():
    parser = argparse.ArgumentParser(description="Live compliance check server")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    local_ip = get_local_ip()
    server = ThreadedHTTPServer(("0.0.0.0", args.port), LiveHandler)

    print(f"\n  Solclear Live Compliance Server")
    print(f"  ────────────────────────────────")
    print(f"  Local:   http://localhost:{args.port}")
    print(f"  Network: http://{local_ip}:{args.port}")
    print(f"\n  Share the network URL with field crews.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
