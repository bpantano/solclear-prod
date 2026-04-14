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

TMP_DIR = Path(__file__).parent.parent / ".tmp"
API_BASE = "https://api.companycam.com/v2"
CC_TOKEN = os.getenv("COMPANYCAM_API_KEY", "")

# ── Global state ─────────────────────────────────────────────────────────────

_check_lock = threading.Lock()
_check_running = False
_result_queue = queue.Queue()

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

    def log_message(self, fmt, *args):
        pass  # silence request logs

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/":
            self._serve_html()
        elif path == "/api/projects":
            self._api_projects(qs)
        elif path.startswith("/api/projects/") and path.endswith("/checklists"):
            pid = path.split("/")[3]
            self._api_checklists(pid)
        elif path == "/api/reports":
            self._api_reports()
        elif path == "/api/organizations":
            self._api_orgs_list()
        elif path.startswith("/api/users/"):
            uid = path.split("/")[3]
            self._api_user_detail(uid)
        elif path.startswith("/api/organizations/") and path.endswith("/users"):
            oid = path.split("/")[3]
            self._api_org_users(oid)
        elif path.startswith("/api/organizations/"):
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

        if path == "/api/organizations":
            self._api_org_create(body)
        elif path.startswith("/api/organizations/") and path.endswith("/users/csv"):
            oid = path.split("/")[3]
            self._api_org_users_csv(oid, body)
        elif path.startswith("/api/organizations/") and path.endswith("/users"):
            oid = path.split("/")[3]
            self._api_org_user_create(oid, body)
        elif path.startswith("/api/users/") and path.endswith("/toggle"):
            uid = path.split("/")[3]
            self._api_user_toggle(uid)
        elif path.startswith("/api/users/"):
            uid = path.split("/")[3]
            self._api_user_update(uid, body)
        elif path.startswith("/api/organizations/"):
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
            slim = [{
                "id": p["id"],
                "name": p.get("name", ""),
                "address": p.get("address", {}).get("street_address_1", ""),
                "city": p.get("address", {}).get("city", ""),
                "state": p.get("address", {}).get("state", ""),
            } for p in projects]
            self._send_json(slim)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

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
            # Mask API keys — show last 4 chars only
            for key_field in ("companycam_api_key", "anthropic_api_key"):
                val = org.get(key_field)
                if val:
                    org[key_field + "_masked"] = "••••" + val[-4:]
                else:
                    org[key_field + "_masked"] = None
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
            for field in ("name", "status", "companycam_api_key", "anthropic_api_key"):
                if field in data:
                    fields.append(f"{field} = %s")
                    values.append(data[field])
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
            if not email or not first_name or not last_name:
                self._send_json({"error": "Email, first name, and last name are required"}, 400)
                return
            user = execute_returning(
                "INSERT INTO users (organization_id, email, first_name, last_name, phone, role) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
                (org_id, email, first_name, last_name, phone, role)
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
            created = []
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
                # Skip header row
                if email.lower() == "email":
                    continue
                if not email or not first_name or not last_name:
                    errors.append(f"Row {i+1}: missing email, first_name, or last_name")
                    continue
                if role not in ("admin", "reviewer", "crew"):
                    role = "crew"
                try:
                    user = execute_returning(
                        "INSERT INTO users (organization_id, email, first_name, last_name, phone, role) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, email, first_name, last_name, role",
                        (org_id, email, first_name, last_name, phone, role)
                    )
                    created.append(user)
                except Exception as e:
                    if "unique" in str(e).lower():
                        errors.append(f"Row {i+1}: {email} already exists")
                    else:
                        errors.append(f"Row {i+1}: {str(e)}")
            self._send_json({"created": created, "errors": errors, "total": len(created)})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

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
                # Get project name from CompanyCam
                name = pid
                try:
                    r = http_requests.get(f"{API_BASE}/projects/{pid}",
                                          headers=cc_headers(), timeout=5)
                    if r.status_code == 200:
                        name = r.json().get("name", pid)
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
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── Embedded HTML ─────────────────────────────────────────────────────────────

EMBEDDED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Solclear Compliance</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8f9fb; color: #1a1a2e; font-size: 14px; line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      min-height: 100dvh;
    }

    /* ── Header ── */
    .top-bar {
      background: #111827; color: #fff; padding: 12px 20px;
      display: grid; grid-template-columns: 44px 1fr 44px; align-items: center;
    }
    .top-bar .sub { font-size: 11px; color: #6b7280; }
    .hamburger {
      background: none; border: none; color: #fff; cursor: pointer;
      width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
      padding: 0; -webkit-tap-highlight-color: transparent;
    }
    .hamburger svg { width: 24px; height: 24px; }
    .logo-center { display: flex; justify-content: center; }
    .header-spacer { width: 44px; }

    /* ── Nav drawer ── */
    .nav-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 200;
      display: none; opacity: 0; transition: opacity 0.2s ease;
    }
    .nav-overlay.open { display: block; opacity: 1; }
    .nav-drawer {
      position: fixed; top: 0; left: -280px; width: 280px; height: 100%;
      background: #111827; z-index: 201; transition: left 0.25s ease;
      padding: 20px; overflow-y: auto;
    }
    .nav-drawer.open { left: 0; }
    .nav-drawer-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #1f2937;
    }
    .nav-close {
      background: none; border: none; color: #9ca3af; cursor: pointer;
      width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
      font-size: 20px;
    }
    .nav-item {
      display: block; width: 100%; padding: 14px 12px; border-radius: 8px;
      color: #d1d5db; text-decoration: none; font-size: 14px; font-weight: 500;
      margin-bottom: 4px; cursor: pointer; border: none; background: none; text-align: left;
    }
    .nav-item:hover, .nav-item:active { background: #1f2937; color: #fff; }

    /* ── Steps ── */
    .step { display: none; padding: 20px; }
    .step.active { display: block; }
    .step-label {
      font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
      color: #9ca3af; font-weight: 600; margin-bottom: 12px;
    }

    /* ── Search ── */
    .search-input {
      width: 100%; padding: 12px 14px; font-size: 16px; border: 2px solid #e5e7eb;
      border-radius: 8px; outline: none; -webkit-appearance: none;
    }
    .search-input:focus { border-color: #3b82f6; }

    /* ── List items ── */
    .list-item {
      background: #fff; border-radius: 8px; padding: 14px 16px; margin-top: 8px;
      border: 2px solid transparent; cursor: pointer; transition: border-color 0.1s;
      min-height: 44px; display: flex; flex-direction: column; justify-content: center;
    }
    .list-item:hover, .list-item:active { border-color: #3b82f6; }
    .list-item .name { font-weight: 600; font-size: 14px; }
    .list-item .detail { font-size: 12px; color: #6b7280; }

    /* ── Toggles ── */
    .param-group { margin-bottom: 16px; }
    .param-group label {
      display: block; font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.06em; color: #6b7280; margin-bottom: 6px; font-weight: 600;
    }
    .toggle-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .toggle-btn {
      padding: 10px 20px; border-radius: 8px; border: 2px solid #e5e7eb;
      background: #fff; font-size: 14px; font-weight: 500; cursor: pointer;
      min-height: 44px; transition: all 0.1s; flex: 1; text-align: center;
    }
    .toggle-btn.selected { border-color: #3b82f6; background: #eff6ff; color: #1d4ed8; }

    /* ── Run button ── */
    .run-btn {
      width: 100%; padding: 16px; border: none; border-radius: 10px;
      background: #3b82f6; color: #fff; font-size: 16px; font-weight: 600;
      cursor: pointer; min-height: 52px; margin-top: 20px;
    }
    .run-btn:disabled { background: #9ca3af; cursor: not-allowed; }

    /* ── Progress ── */
    .progress-wrap { padding: 20px; }
    .progress-bar-bg {
      width: 100%; height: 8px; background: #e5e7eb; border-radius: 4px;
      overflow: hidden; margin-bottom: 8px;
    }
    .progress-bar-fill {
      height: 100%; background: #3b82f6; border-radius: 4px;
      transition: width 0.3s ease; width: 0%;
    }
    .progress-text { font-size: 12px; color: #6b7280; margin-bottom: 16px; }

    /* ── Status message ── */
    .status-msg {
      background: #eff6ff; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;
      font-size: 13px; color: #1d4ed8; display: none;
    }

    /* ── Result rows ── */
    .result-row {
      background: #fff; border-radius: 6px; padding: 10px 14px; margin-bottom: 6px;
      border-left: 3px solid #e5e7eb; animation: fadeIn 0.2s ease;
    }
    .result-row.pass { border-left-color: #10b981; }
    .result-row.fail { border-left-color: #ef4444; }
    .result-row.missing { border-left-color: #f59e0b; }
    .result-row.error { border-left-color: #8b5cf6; }

    .result-header { display: flex; align-items: center; gap: 8px; }
    .badge {
      font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 3px;
      letter-spacing: 0.04em; text-transform: uppercase; white-space: nowrap;
    }
    .badge-pass { background: #ecfdf5; color: #065f46; }
    .badge-fail { background: #fef2f2; color: #991b1b; }
    .badge-missing { background: #fffbeb; color: #92400e; }
    .badge-error { background: #f5f3ff; color: #5b21b6; }
    .result-id { font-size: 10px; font-weight: 700; color: #9ca3af; }
    .result-title { font-size: 13px; font-weight: 500; flex: 1; }
    .result-reason { font-size: 12px; color: #6b7280; margin-top: 6px; padding-left: 10px; border-left: 2px solid #f3f4f6; }
    .expand-btn {
      margin-top: 4px; background: none; border: none; color: #3b82f6;
      font-size: 11px; font-weight: 500; cursor: pointer; padding: 2px 0;
    }
    .expand-btn:hover { text-decoration: underline; }
    .expand-btn .arrow { font-size: 10px; margin-left: 2px; }

    /* ── Done banner ── */
    .done-banner {
      padding: 16px 20px; display: none; align-items: center; justify-content: space-between;
      flex-wrap: wrap; gap: 10px;
    }
    .done-pass { background: #ecfdf5; border-bottom: 2px solid #10b981; }
    .done-fail { background: #fef2f2; border-bottom: 2px solid #ef4444; }
    .done-label { font-size: 13px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
    .done-pass .done-label { color: #065f46; }
    .done-fail .done-label { color: #991b1b; }
    .done-stats { font-size: 12px; color: #6b7280; }
    .cc-link {
      display: inline-block; margin-top: 8px; padding: 10px 16px; background: #3b82f6;
      color: #fff; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600;
      min-height: 44px; line-height: 24px;
    }

    /* ── Back button ── */
    .back-btn {
      background: none; border: none; color: #3b82f6; font-size: 13px;
      font-weight: 500; cursor: pointer; padding: 4px 0; margin-bottom: 12px;
    }

    /* ── Loader animation ── */
    .loader-anim {
      display: flex; justify-content: center; padding: 20px 0 8px;
    }
    .loader-anim.hidden { display: none; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>

  <!-- Nav drawer -->
  <div class="nav-overlay" id="navOverlay" onclick="closeNav()"></div>
  <div class="nav-drawer" id="navDrawer">
    <div class="nav-drawer-header">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" height="28">
        <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/></g>
        <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#ffffff" letter-spacing="-2.5">solclear</text>
      </svg>
      <button class="nav-close" onclick="closeNav()">&times;</button>
    </div>
    <button class="nav-item" onclick="closeNav();showStep('home')">Recent Reports</button>
    <button class="nav-item" onclick="closeNav();showStep(1)">New Compliance Check</button>
    <div style="border-top:1px solid #1f2937;margin:16px 0 8px;"></div>
    <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.1em;color:#4b5563;padding:0 12px 8px;font-weight:600;">Admin</div>
    <button class="nav-item" onclick="closeNav();showStep('orgs')">Organizations</button>
  </div>

  <div class="top-bar">
    <button class="hamburger" onclick="openNav()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <div class="logo-center">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" height="42" style="flex-shrink:0;">
        <g transform="translate(24,36)"><circle cx="44" cy="40" r="12" fill="#F59E0B"/><path d="M16 76 A 28 28 0 0 1 72 76" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/></g>
        <text x="116" y="104" font-family="Inter,Helvetica,Arial,sans-serif" font-weight="600" font-size="80" fill="#ffffff" letter-spacing="-2.5">solclear</text>
      </svg>
    </div>
    <div class="header-spacer"></div>
  </div>

  <!-- Recent reports -->
  <div id="recentReports" class="step active" style="display:block;">
    <div id="recentList"></div>
    <div style="margin-top:16px;">
      <button class="run-btn" onclick="showStep(1)" style="background:#111827;">New Compliance Check</button>
    </div>
  </div>

  <!-- Step 1: Select project -->
  <div id="step1" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to reports</button>
    <div class="step-label">Step 1 — Select Project</div>
    <input class="search-input" id="projectSearch" type="text" placeholder="Search by name or address..." autocomplete="off">
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
      <div id="resultsList"></div>
    </div>
  </div>

  <!-- Organizations list -->
  <div id="adminOrgs" class="step">
    <button class="back-btn" onclick="showStep('home')">&larr; Back to home</button>
    <div class="step-label">Organizations</div>
    <button class="run-btn" onclick="showCreateOrg()" style="margin-bottom:16px;background:#3b82f6;">+ Create Organization</button>
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
    <div style="background:#fff;border-radius:8px;padding:16px;margin-bottom:16px;">
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
      <div class="param-group">
        <label>CompanyCam API Key</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="search-input" id="orgCcKey" type="password" style="font-size:13px;font-family:monospace;flex:1;" placeholder="Not set">
          <button onclick="toggleKeyVis('orgCcKey')" style="background:#f3f4f6;border:none;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:12px;min-height:44px;">Show</button>
        </div>
      </div>
      <div class="param-group">
        <label>Anthropic API Key</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input class="search-input" id="orgAnthKey" type="password" style="font-size:13px;font-family:monospace;flex:1;" placeholder="Not set">
          <button onclick="toggleKeyVis('orgAnthKey')" style="background:#f3f4f6;border:none;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:12px;min-height:44px;">Show</button>
        </div>
      </div>
      <button class="run-btn" onclick="saveOrg()" style="background:#10b981;">Save Changes</button>
    </div>

    <!-- Users -->
    <div style="background:#fff;border-radius:8px;padding:16px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <label style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;font-weight:600;margin:0;">Users</label>
        <span id="orgUserCount" style="font-size:11px;color:#9ca3af;"></span>
      </div>
      <div id="orgUsersList"></div>

      <!-- Add user form -->
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid #f3f4f6;">
        <div style="font-size:11px;color:#6b7280;font-weight:600;margin-bottom:8px;">ADD USER</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input class="search-input" id="addUserFirst" type="text" placeholder="First Name" style="flex:1;min-width:100px;font-size:13px;">
          <input class="search-input" id="addUserLast" type="text" placeholder="Last Name" style="flex:1;min-width:100px;font-size:13px;">
          <input class="search-input" id="addUserEmail" type="email" placeholder="Email" style="flex:1;min-width:160px;font-size:13px;">
          <input class="search-input" id="addUserPhone" type="tel" placeholder="Phone (optional)" style="flex:1;min-width:120px;font-size:13px;">
          <select id="addUserRole" style="padding:8px;border:2px solid #e5e7eb;border-radius:8px;font-size:13px;min-height:44px;">
            <option value="crew">Crew</option>
            <option value="reviewer">Reviewer</option>
            <option value="admin">Admin</option>
          </select>
          <button onclick="addUser()" style="background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;min-height:44px;">Add</button>
        </div>
      </div>

      <!-- CSV upload -->
      <div style="margin-top:12px;padding-top:12px;border-top:1px solid #f3f4f6;">
        <div style="font-size:11px;color:#6b7280;font-weight:600;margin-bottom:8px;">BULK IMPORT (CSV)</div>
        <div style="font-size:11px;color:#9ca3af;margin-bottom:8px;">Format: email, first_name, last_name, role, phone (one per line)</div>
        <input type="file" id="csvUpload" accept=".csv" onchange="uploadCsv()" style="font-size:12px;">
        <div id="csvResult" style="margin-top:8px;font-size:12px;"></div>
      </div>
    </div>
  </div>

  <!-- User detail/edit -->
  <div id="adminUserDetail" class="step">
    <button class="back-btn" id="userDetailBack">&larr; Back to organization</button>
    <div class="step-label" id="userDetailLabel">Edit User</div>

    <div style="background:#fff;border-radius:8px;padding:16px;margin-bottom:16px;">
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
      <button class="run-btn" onclick="saveUser()" style="background:#10b981;">Save Changes</button>
    </div>

    <div id="userStatusInfo" style="background:#fff;border-radius:8px;padding:16px;font-size:12px;color:#6b7280;"></div>
  </div>

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

    // ── Nav drawer ──
    function openNav() {
      document.getElementById('navDrawer').classList.add('open');
      document.getElementById('navOverlay').classList.add('open');
    }
    function closeNav() {
      document.getElementById('navDrawer').classList.remove('open');
      document.getElementById('navOverlay').classList.remove('open');
    }

    // ── Step navigation ──
    function showStep(n) {
      document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
      document.getElementById('recentReports').style.display = 'none';
      if (n === 'home') {
        document.getElementById('recentReports').style.display = 'block';
        loadRecentReports();
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
      document.getElementById('step' + n).classList.add('active');
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
      const colors = {active:'#10b981',demo:'#3b82f6',inactive:'#9ca3af',onboarding:'#f59e0b'};
      const bg = {active:'#ecfdf5',demo:'#eff6ff',inactive:'#f3f4f6',onboarding:'#fffbeb'};
      return '<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:'+
        (bg[status]||'#f3f4f6')+';color:'+(colors[status]||'#6b7280')+';">'+status.toUpperCase()+'</span>';
    }

    function roleBadgeHtml(role) {
      const colors = {superadmin:'#7c3aed',admin:'#2563eb',reviewer:'#0891b2',crew:'#059669'};
      const bg = {superadmin:'#f5f3ff',admin:'#eff6ff',reviewer:'#ecfeff',crew:'#ecfdf5'};
      return '<span style="font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;background:'+
        (bg[role]||'#f3f4f6')+';color:'+(colors[role]||'#6b7280')+';">'+role+'</span>';
    }

    // ── Organizations ──
    async function loadOrgs() {
      const list = document.getElementById('orgsList');
      list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">Loading...</div>';
      try {
        const r = await fetch('/api/organizations');
        const orgs = await r.json();
        if (!orgs.length) {
          list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">No organizations yet.</div>';
          return;
        }
        list.innerHTML = orgs.map(o => `
          <div class="list-item" onclick="openOrg(${o.id})" style="border-left:3px solid ${
            {active:'#10b981',demo:'#3b82f6',inactive:'#9ca3af',onboarding:'#f59e0b'}[o.status] || '#e5e7eb'
          };">
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="name">${esc(o.name)}</span>
              ${statusBadgeHtml(o.status)}
            </div>
            <div class="detail">${o.user_count} user${o.user_count!==1?'s':''} · ${o.report_count} report${o.report_count!==1?'s':''}</div>
          </div>
        `).join('');
      } catch (e) { list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading organizations</div>'; }
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
      const detail = document.getElementById('adminOrgDetail');
      try {
        const r = await fetch('/api/organizations/' + orgId);
        const org = await r.json();
        document.getElementById('orgDetailLabel').textContent = org.name;
        document.getElementById('orgEditName').value = org.name || '';
        document.getElementById('orgCcKey').value = org.companycam_api_key || '';
        document.getElementById('orgAnthKey').value = org.anthropic_api_key || '';
        // Set status toggle
        document.querySelectorAll('[data-param="org-edit-status"]').forEach(b => {
          b.classList.toggle('selected', b.dataset.value === org.status);
        });
        // Render users
        renderOrgUsers(org.users || []);
      } catch (e) { alert('Error loading org: ' + e.message); }
    }

    function renderOrgUsers(users) {
      document.getElementById('orgUserCount').textContent = users.length + ' user' + (users.length !== 1 ? 's' : '');
      const list = document.getElementById('orgUsersList');
      if (!users.length) { list.innerHTML = '<div style="color:#9ca3af;font-size:12px;">No users yet.</div>'; return; }
      list.innerHTML = users.map(u => `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f3f4f6;${u.is_active ? '' : 'opacity:0.5;'}">
          <div style="flex:1;cursor:pointer;" onclick="openUser(${u.id})">
            <div style="font-weight:500;font-size:13px;color:#3b82f6;">${esc(u.full_name || (u.first_name + ' ' + u.last_name))}${u.is_active ? '' : ' <span style="font-size:10px;color:#ef4444;font-weight:700;">INACTIVE</span>'}</div>
            <div style="font-size:11px;color:#9ca3af;">${esc(u.email)}${u.phone ? ' · ' + esc(u.phone) : ''}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            ${roleBadgeHtml(u.role)}
            <button onclick="toggleUser(${u.id})" style="background:none;border:1px solid ${u.is_active ? '#ef4444' : '#10b981'};color:${u.is_active ? '#ef4444' : '#10b981'};border-radius:6px;padding:4px 10px;font-size:10px;font-weight:600;cursor:pointer;min-height:28px;">
              ${u.is_active ? 'Deactivate' : 'Activate'}
            </button>
          </div>
        </div>
      `).join('');
    }

    async function saveOrg() {
      const statusBtn = document.querySelector('[data-param="org-edit-status"].selected');
      const data = {
        name: document.getElementById('orgEditName').value.trim(),
        status: statusBtn ? statusBtn.dataset.value : 'onboarding',
        companycam_api_key: document.getElementById('orgCcKey').value.trim() || null,
        anthropic_api_key: document.getElementById('orgAnthKey').value.trim() || null,
      };
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
        if (u.deactivated_at) statusHtml += ' · Deactivated: ' + new Date(u.deactivated_at).toLocaleDateString();
        if (u.created_at) statusHtml += ' · Created: ' + new Date(u.created_at).toLocaleDateString();
        info.innerHTML = statusHtml;
      } catch (e) { alert('Error loading user: ' + e.message); }
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
    async function loadRecentReports() {
      const list = document.getElementById('recentList');
      list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">Loading reports...</div>';
      try {
        const r = await fetch('/api/reports');
        const reports = await r.json();
        if (!reports.length) {
          list.innerHTML = '<div class="step-label">No reports yet</div><div style="color:#9ca3af;font-size:13px;padding:4px 0;">Run your first compliance check to see results here.</div>';
          return;
        }
        list.innerHTML = '<div class="step-label">Recent Reports</div>' + reports.map(rpt => {
          const isPass = rpt.failed === 0;
          const date = new Date(rpt.timestamp * 1000).toLocaleDateString('en-US', {month:'short', day:'numeric', hour:'numeric', minute:'2-digit'});
          return `
            <a href="/report/${rpt.project_id}" class="list-item" style="text-decoration:none;color:inherit;border-left:3px solid ${isPass ? '#10b981' : '#ef4444'};">
              <div class="name">${esc(rpt.name)}</div>
              <div class="detail">${rpt.passed}/${rpt.total} passed · ${date}</div>
            </a>`;
        }).join('');
      } catch (e) {
        list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading reports</div>';
      }
    }

    // Check for rerun parameter, otherwise load recent reports
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
          listenSSE(data.total);
        }).catch(e => { alert('Failed: ' + e.message); showStep('home'); });

        // Clean up URL
        window.history.replaceState({}, '', '/');
        return;
      }
      loadRecentReports();
    })();

    // ── Step 1: Project search ──
    const searchInput = document.getElementById('projectSearch');
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => searchProjects(searchInput.value), 300);
    });

    // Load initial list when step 1 is shown
    searchInput.addEventListener('focus', () => {
      if (!document.getElementById('projectList').children.length) searchProjects('');
    });

    async function searchProjects(query) {
      const list = document.getElementById('projectList');
      list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">Searching...</div>';
      try {
        const r = await fetch('/api/projects?query=' + encodeURIComponent(query));
        const projects = await r.json();
        if (!projects.length) { list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">No projects found</div>'; return; }
        list.innerHTML = projects.map(p => `
          <div class="list-item" onclick="selectProject('${p.id}', '${esc(p.name)}', '${esc(p.state)}')">
            <div class="name">${esc(p.name)}</div>
            <div class="detail">${esc([p.address, p.city, p.state].filter(Boolean).join(', '))}</div>
          </div>
        `).join('');
      } catch (e) { list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading projects</div>'; }
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
      list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">Loading checklists...</div>';
      try {
        const r = await fetch('/api/projects/' + projectId + '/checklists');
        const cls = await r.json();
        if (!cls.length) { list.innerHTML = '<div style="color:#9ca3af;padding:12px;font-size:13px;">No checklists on this project</div>'; return; }
        list.innerHTML = cls.map(c => `
          <div class="list-item" onclick="selectChecklist('${c.id}', '${esc(c.name)}')">
            <div class="name">${esc(c.name)}</div>
            <div class="detail">${c.completed_at ? 'Completed' : 'In progress'}</div>
          </div>
        `).join('');
      } catch (e) { list.innerHTML = '<div style="color:#ef4444;padding:12px;">Error loading checklists</div>'; }
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

        listenSSE(data.total);
      } catch (e) {
        alert('Failed to start: ' + e.message);
        btn.disabled = false;
        btn.textContent = 'Run Compliance Check';
      }
    }

    function listenSSE(total) {
      const es = new EventSource('/stream');
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
          appendResult(data.requirement);
          return;
        }

        if (data.type === 'done') {
          es.close();
          document.getElementById('loaderAnim').classList.add('hidden');
          const s = data.summary;
          const pct = Math.round((s.passed / s.total) * 100);
          document.getElementById('progressFill').style.width = '100%';
          document.getElementById('progressText').textContent = `Complete — ${s.passed}/${s.total} passed`;

          const banner = document.getElementById('doneBanner');
          const isPass = s.failed === 0 && s.missing === 0;
          banner.className = 'done-banner ' + (isPass ? 'done-pass' : 'done-fail');
          let ccLink = '';
          if (s.checklist_ids && s.checklist_ids.length) {
            ccLink = `<a class="cc-link" href="https://app.companycam.com/projects/${s.project_id}/todos/${s.checklist_ids[0]}" target="_blank">Open in CompanyCam</a>`;
          }
          const reportLink = `<a class="cc-link" href="/report/${s.project_id}" style="background:#111827;">View Full Report</a>`;
          banner.innerHTML = `
            <div>
              <div class="done-label">${isPass ? 'READY FOR SUBMISSION' : 'ACTION REQUIRED'}</div>
              <div class="done-stats">${s.passed} passed · ${s.failed} failed · ${s.missing} missing · ${s.total} required</div>
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
      let reason = '';
      if (status !== 'pass' && req.reason) {
        let full = esc(req.reason);
        // Replace "Photo(s) N", "Photos N and M", "Photos N, M, and O" with clickable links
        const urls = req.photo_urls || {};
        function linkPhoto(num) {
          const url = urls[num];
          return url ? `<a href="${url}" target="_blank" style="color:#3b82f6;font-weight:500;">${num}</a>` : num;
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

      list.insertAdjacentHTML('beforeend', `
        <div class="result-row ${status}">
          <div class="result-header">
            <span class="badge ${badgeCls}">${req.status}</span>
            <span class="result-id">${req.id}</span>
            <span class="result-title">${esc(req.title)}</span>
          </div>
          ${reason}
        </div>
      `);

      // scroll to bottom
      list.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }

    function toggleResultReason(btn) {
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

    function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
  </script>

</body>
</html>"""


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
