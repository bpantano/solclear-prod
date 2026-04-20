"""
Tool: generate_report_html.py
Purpose: Generate a self-contained HTML compliance report from a compliance check JSON file.
         Opens the report in the default browser automatically.

Usage:
  python tools/generate_report_html.py --project_id <id>
  python tools/generate_report_html.py --project_id <id> --no_open
"""

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
API_BASE = "https://api.companycam.com/v2"


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
    cfg = {
        "PASS":          ("pass",    "PASS"),
        "FAIL":          ("fail",    "FAIL"),
        "MISSING":       ("missing", "MISSING"),
        "ERROR":         ("error",   "ERROR"),
        "FOUND_NO_VISION": ("skip",  "SKIPPED"),
        "N/A":           ("na",      "N/A"),
    }
    cls, label = cfg.get(status, ("na", status))
    return f'<span class="badge badge-{cls}">{label}</span>'


import re


def linkify_photos(text: str, photo_urls: dict) -> str:
    """Replace 'Photo(s) N', 'Photos N and M', 'Photos N, M' with clickable links."""
    if not photo_urls:
        return text
    def link_number(match):
        num = match.group(1)
        url = photo_urls.get(num) or photo_urls.get(int(num))
        if url:
            return f'<a href="{url}" target="_blank" style="color:#3b82f6;font-weight:500;">{num}</a>'
        return num
    def replacer(match):
        return re.sub(r'(\d+)', link_number, match.group(0))
    return re.sub(r'Photos?\s+(\d+(?:\s*(?:,\s*(?:and\s+)?|and\s+|&\s*)\d+)*)', replacer, text, flags=re.IGNORECASE)


def truncate_reason(reason: str, limit: int = 120) -> tuple:
    """Return (short, full) — short is truncated if needed."""
    if not reason:
        return "", ""
    clean = " ".join(reason.split())
    if len(clean) <= limit:
        return clean, ""
    return clean[:limit].rsplit(" ", 1)[0] + "...", clean


def render_requirement(req: dict) -> str:
    status = req.get("status", "")
    optional_tag = '<span class="optional-tag">optional</span>' if req.get("optional") else ""
    candidates = req.get("candidates")
    candidates_note = f'<span class="meta">{candidates} photos</span>' if candidates and candidates > 1 else ""
    photo_urls = req.get("photo_urls", {})

    reason_html = ""
    if status not in ("PASS", "N/A", "FOUND_NO_VISION") and req.get("reason"):
        short, full = truncate_reason(req["reason"])
        if full:
            short_linked = linkify_photos(short, photo_urls)
            full_linked = linkify_photos(full, photo_urls)
            reason_html = f'''
      <p class="reason">{short_linked}</p>
      <div class="reason-full" style="display:none"><p class="reason">{full_linked}</p></div>
      <button class="expand-btn" onclick="toggleReason(this)">Show more <span class="arrow">&#9662;</span></button>'''
        else:
            reason_html = f'<p class="reason">{linkify_photos(short, photo_urls)}</p>'

    collapsed_class = " collapsed" if status == "PASS" else ""
    click_handler = ' onclick="this.classList.toggle(\'collapsed\')"' if status == "PASS" else ""

    # Show the evaluated photo thumbnail (key 1 is the selected winner)
    eval_url = photo_urls.get(1) or photo_urls.get("1")
    photo_html = ""
    if eval_url and status not in ("N/A", "FOUND_NO_VISION"):
        photo_html = f'<a href="{eval_url}" target="_blank" style="display:block;margin-top:8px;"><img src="{eval_url}" style="width:100%;max-width:280px;border-radius:6px;border:2px solid #e5e7eb;" loading="lazy"></a>'

    return f"""
    <div class="requirement req-{status.lower()}{collapsed_class}"{click_handler}>
      <div class="req-header">
        {status_badge(status)}
        <span class="req-id">{req["id"]}</span>
        <span class="req-title">{req["title"]}</span>
        {optional_tag}
        {candidates_note}
      </div>
      {photo_html}
      {reason_html}
    </div>"""


def render_section(section_name: str, reqs: list, companycam_url: str = "") -> str:
    applicable = [r for r in reqs if r.get("status") != "N/A"]
    if not applicable:
        return ""

    passed = sum(1 for r in applicable if r["status"] == "PASS")
    failed = sum(1 for r in applicable if r["status"] in ("FAIL", "MISSING", "ERROR"))
    total = len(applicable)

    # Sort: failures first, then missing, then errors, then pass
    order = {"FAIL": 0, "MISSING": 1, "ERROR": 2, "FOUND_NO_VISION": 3, "PASS": 4}
    sorted_reqs = sorted(applicable, key=lambda r: order.get(r["status"], 5))

    rows = "".join(render_requirement(r) for r in sorted_reqs)

    score_class = "score-clean" if failed == 0 else "score-issues"
    cc_link = f'<a class="cc-link" href="{companycam_url}" target="_blank">Open in CompanyCam &#8599;</a>' if companycam_url else ""

    return f"""
  <div class="section">
    <div class="section-header">
      <h2>{section_name}</h2>
      <div class="section-right">
        {cc_link}
        <span class="section-score {score_class}">{passed}/{total}</span>
      </div>
    </div>
    {rows}
  </div>"""


def generate_html(report: dict, project: dict) -> str:
    reqs = report.get("requirements", [])
    params = report.get("params", {})
    project_id = report.get("project_id", "")

    name = project.get("name") or f"Project {project_id}"
    address = project.get("address", {})
    addr_str = ", ".join(filter(None, [
        address.get("street_address_1"),
        address.get("city"),
        address.get("state"),
    ]))
    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    required = [r for r in reqs if r["status"] != "N/A" and not r.get("optional")]
    n_pass    = sum(1 for r in required if r["status"] == "PASS")
    n_fail    = sum(1 for r in required if r["status"] == "FAIL")
    n_missing = sum(1 for r in required if r["status"] == "MISSING")
    n_error   = sum(1 for r in required if r["status"] == "ERROR")
    n_total   = len(required)

    overall_class = "overall-pass" if (n_fail + n_missing + n_error) == 0 else "overall-fail"
    overall_label = "READY FOR SUBMISSION" if (n_fail + n_missing + n_error) == 0 else "ACTION REQUIRED"

    manufacturer = params.get("manufacturer", "—")
    lender = params.get("lender", "—")
    has_battery = "Yes" if params.get("has_battery") else "No"
    backup = "Yes" if params.get("is_backup_battery") else "No"
    incentive = "Yes" if params.get("is_incentive_state") else "No"
    portal = "Yes" if params.get("portal_access_granted") else "No"

    pct = round((n_pass / n_total) * 100) if n_total else 0

    # CompanyCam checklist URL
    checklist_ids = report.get("checklist_ids", [])
    cc_url = f"https://app.companycam.com/projects/{project_id}/todos/{checklist_ids[0]}" if checklist_ids else ""

    sections: dict = {}
    for r in reqs:
        sections.setdefault(r["section"], []).append(r)

    sections_html = "".join(render_section(sec, reqs, cc_url) for sec, reqs in sections.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>M1 Compliance — {name}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8f9fb;
      color: #1a1a2e;
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }}

    /* ── Header ── */
    .header {{
      background: #111827;
      color: #fff;
      padding: 24px 32px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }}
    .header-left h1 {{ font-size: 18px; font-weight: 600; margin-bottom: 2px; }}
    .header-left .address {{ font-size: 13px; color: #9ca3af; }}
    .header-right {{ text-align: right; font-size: 11px; color: #6b7280; white-space: nowrap; }}

    /* ── Overall banner ── */
    .overall-banner {{
      padding: 14px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .overall-pass {{ background: #ecfdf5; border-bottom: 2px solid #10b981; }}
    .overall-fail {{ background: #fef2f2; border-bottom: 2px solid #ef4444; }}

    .overall-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .overall-label {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .overall-pass .overall-label {{ color: #065f46; }}
    .overall-fail .overall-label {{ color: #991b1b; }}

    .overall-right {{
      display: flex;
      gap: 16px;
      font-size: 12px;
      color: #6b7280;
    }}
    .stat {{ display: flex; align-items: center; gap: 4px; }}
    .stat-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
    .stat-dot-pass {{ background: #10b981; }}
    .stat-dot-fail {{ background: #ef4444; }}
    .stat-dot-missing {{ background: #f59e0b; }}

    /* ── Progress ring ── */
    .progress-ring {{
      width: 40px;
      height: 40px;
      flex-shrink: 0;
    }}
    .progress-ring circle {{
      fill: none;
      stroke-width: 4;
      transform: rotate(-90deg);
      transform-origin: 50% 50%;
    }}
    .ring-bg {{ stroke: #e5e7eb; }}
    .ring-fill {{ stroke-linecap: round; transition: stroke-dashoffset 0.5s ease; }}
    .overall-pass .ring-fill {{ stroke: #10b981; }}
    .overall-fail .ring-fill {{ stroke: #ef4444; }}
    .ring-text {{ font-size: 10px; font-weight: 700; fill: #374151; text-anchor: middle; dominant-baseline: central; }}

    /* ── Params bar ── */
    .params-bar {{
      background: #fff;
      border-bottom: 1px solid #e5e7eb;
      padding: 10px 32px;
      display: flex;
      gap: 24px;
      flex-wrap: wrap;
    }}
    .param {{ display: flex; align-items: center; gap: 6px; }}
    .param-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: #9ca3af; font-weight: 500; }}
    .param-value {{ font-size: 12px; font-weight: 600; color: #374151; }}
    .param-sep {{ color: #e5e7eb; }}

    /* ── Body ── */
    .body {{ max-width: 820px; margin: 24px auto; padding: 0 16px; }}

    /* ── Section ── */
    .section {{ margin-bottom: 24px; }}
    .section-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 2px solid #111827;
      margin-bottom: 8px;
    }}
    .section-header h2 {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; color: #374151; }}
    .section-right {{ display: flex; align-items: center; gap: 12px; }}
    .cc-link {{
      font-size: 11px;
      color: #3b82f6;
      text-decoration: none;
      font-weight: 500;
    }}
    .cc-link:hover {{ text-decoration: underline; }}
    .section-score {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }}
    .score-clean {{ background: #ecfdf5; color: #065f46; }}
    .score-issues {{ background: #fef2f2; color: #991b1b; }}

    /* ── Requirement row ── */
    .requirement {{
      background: #fff;
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 6px;
      border-left: 3px solid #e5e7eb;
      transition: all 0.15s ease;
    }}
    .req-pass    {{ border-left-color: #10b981; }}
    .req-fail    {{ border-left-color: #ef4444; }}
    .req-missing {{ border-left-color: #f59e0b; }}
    .req-error   {{ border-left-color: #8b5cf6; }}

    .requirement.collapsed {{
      padding: 6px 14px;
      opacity: 0.6;
      cursor: pointer;
    }}
    .requirement.collapsed:hover {{ opacity: 0.85; }}
    .requirement.collapsed .reason,
    .requirement.collapsed .reason-full,
    .requirement.collapsed .expand-btn,
    .requirement.collapsed .meta {{ display: none !important; }}

    .req-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .req-id {{ font-size: 10px; font-weight: 700; color: #9ca3af; min-width: 28px; }}
    .req-title {{ font-size: 13px; font-weight: 500; flex: 1; color: #1f2937; }}

    .optional-tag {{
      font-size: 9px;
      background: #f3f4f6;
      color: #9ca3af;
      padding: 1px 5px;
      border-radius: 3px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .meta {{
      font-size: 10px;
      color: #d1d5db;
    }}

    /* ── Badges ── */
    .badge {{
      font-size: 9px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 3px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .badge-pass    {{ background: #ecfdf5; color: #065f46; }}
    .badge-fail    {{ background: #fef2f2; color: #991b1b; }}
    .badge-missing {{ background: #fffbeb; color: #92400e; }}
    .badge-error   {{ background: #f5f3ff; color: #5b21b6; }}
    .badge-skip    {{ background: #f9fafb; color: #9ca3af; }}
    .badge-na      {{ background: #f9fafb; color: #d1d5db; }}

    /* ── Reason text ── */
    .reason {{
      margin-top: 8px;
      font-size: 12px;
      color: #6b7280;
      line-height: 1.6;
      padding-left: 10px;
      border-left: 2px solid #f3f4f6;
    }}

    .expand-btn {{
      margin-top: 4px;
      background: none;
      border: none;
      color: #3b82f6;
      font-size: 11px;
      font-weight: 500;
      cursor: pointer;
      padding: 2px 0;
    }}
    .expand-btn:hover {{ text-decoration: underline; }}
    .expand-btn .arrow {{ font-size: 10px; margin-left: 2px; display: inline-block; transition: transform 0.15s ease; }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 24px;
      font-size: 10px;
      color: #d1d5db;
      letter-spacing: 0.02em;
    }}

    /* ── Mobile ── */
    @media (max-width: 640px) {{
      .header {{
        flex-direction: column;
        padding: 20px 16px;
        gap: 8px;
      }}
      .header-right {{ text-align: left; }}
      .overall-banner {{
        flex-direction: column;
        padding: 12px 16px;
        align-items: flex-start;
        gap: 8px;
      }}
      .overall-right {{ flex-wrap: wrap; gap: 10px; }}
      .params-bar {{
        padding: 10px 16px;
        gap: 12px;
      }}
      .param {{ flex-basis: 45%; }}
      .param-sep {{ display: none; }}
      .body {{ padding: 0 12px; }}
      .requirement {{ padding: 10px 12px; }}
      .req-header {{ gap: 6px; }}
      .req-title {{ font-size: 12px; }}
    }}
  </style>
</head>
<body>

  <div class="header">
    <div class="header-left">
      <h1>{name}</h1>
      <div class="address">{addr_str}</div>
    </div>
    <div class="header-right">
      Palmetto M1 Report<br>
      {generated}<br>
      ID: {project_id}
    </div>
  </div>

  <div class="overall-banner {overall_class}">
    <div class="overall-left">
      <svg class="progress-ring" viewBox="0 0 44 44">
        <circle class="ring-bg" cx="22" cy="22" r="18"/>
        <circle class="ring-fill" cx="22" cy="22" r="18"
          stroke-dasharray="{round(2 * 3.14159 * 18, 1)}"
          stroke-dashoffset="{round(2 * 3.14159 * 18 * (1 - pct / 100), 1)}"/>
        <text class="ring-text" x="22" y="22">{pct}%</text>
      </svg>
      <span class="overall-label">{overall_label}</span>
    </div>
    <div class="overall-right">
      <span class="stat"><span class="stat-dot stat-dot-pass"></span>{n_pass} passed</span>
      <span class="stat"><span class="stat-dot stat-dot-fail"></span>{n_fail} failed</span>
      <span class="stat"><span class="stat-dot stat-dot-missing"></span>{n_missing} missing</span>
      <span class="stat">{n_total} required</span>
    </div>
  </div>

  <div class="params-bar">
    <div class="param"><span class="param-label">Lender</span><span class="param-value">{lender}</span></div>
    <span class="param-sep">|</span>
    <div class="param"><span class="param-label">Manufacturer</span><span class="param-value">{manufacturer}</span></div>
    <span class="param-sep">|</span>
    <div class="param"><span class="param-label">Battery</span><span class="param-value">{has_battery}</span></div>
    <span class="param-sep">|</span>
    <div class="param"><span class="param-label">Backup</span><span class="param-value">{backup}</span></div>
    <span class="param-sep">|</span>
    <div class="param"><span class="param-label">Incentive</span><span class="param-value">{incentive}</span></div>
    <span class="param-sep">|</span>
    <div class="param"><span class="param-label">Portal</span><span class="param-value">{portal}</span></div>
  </div>

  <div class="body">
    {sections_html}
  </div>

  <div class="footer">
    Solclear Compliance &middot; Palmetto LightReach M1
  </div>

  <script>
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
  </script>

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
