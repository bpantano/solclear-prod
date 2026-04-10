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

def run_check_thread(project_id, params):
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
        elif path == "/start":
            self._start_check(qs)
        elif path == "/stream":
            self._stream_sse()
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

        if not project_id or not checklist_id:
            with _check_lock:
                _check_running = False
            self._send_json({"ok": False, "error": "project_id and checklist_id required"}, 400)
            return

        # Auto-derive params from checklist data + project address
        _result_queue.put(json.dumps({"type": "status", "message": "Reading checklist and deriving job parameters..."}))
        params = derive_params_from_checklist(project_id, checklist_id, manufacturer, project_state)

        total = sum(1 for r in REQUIREMENTS if r["condition"](params))

        t = threading.Thread(target=run_check_thread, args=(project_id, params), daemon=True)
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
      background: #111827; color: #fff; padding: 16px 20px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .top-bar h1 { font-size: 16px; font-weight: 600; }
    .top-bar .sub { font-size: 11px; color: #6b7280; }

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

    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>

  <div class="top-bar">
    <div>
      <h1>Solclear</h1>
      <div class="sub">Palmetto M1 Compliance</div>
    </div>
  </div>

  <!-- Step 1: Select project -->
  <div id="step1" class="step active">
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
      <div class="status-msg" id="statusMsg"></div>
      <div class="progress-bar-bg"><div class="progress-bar-fill" id="progressFill"></div></div>
      <div class="progress-text" id="progressText">Preparing...</div>
      <div id="resultsList"></div>
    </div>
  </div>

  <script>
    let selectedProjectId = null;
    let selectedProjectName = '';
    let selectedProjectState = '';
    let selectedChecklistId = null;
    let selectedChecklistName = '';
    let selectedManufacturer = null;
    let searchTimer = null;

    // ── Step navigation ──
    function showStep(n) {
      document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
      document.getElementById('step' + n).classList.add('active');
    }

    // ── Step 1: Project search ──
    const searchInput = document.getElementById('projectSearch');
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => searchProjects(searchInput.value), 300);
    });

    // Load initial list on page load
    searchProjects('');

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
          banner.innerHTML = `
            <div>
              <div class="done-label">${isPass ? 'READY FOR SUBMISSION' : 'ACTION REQUIRED'}</div>
              <div class="done-stats">${s.passed} passed · ${s.failed} failed · ${s.missing} missing · ${s.total} required</div>
              ${ccLink}
            </div>
          `;
          banner.style.display = 'flex';

          document.getElementById('runBtn').disabled = false;
          document.getElementById('runBtn').textContent = 'Run Compliance Check';
          return;
        }

        if (data.type === 'error') {
          es.close();
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
