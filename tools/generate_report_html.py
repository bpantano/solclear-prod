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


def render_requirement(req: dict) -> str:
    status = req.get("status", "")
    optional_tag = '<span class="optional-tag">optional</span>' if req.get("optional") else ""
    candidates = req.get("candidates")
    candidates_note = f'<span class="candidates-note">{candidates} photo{"s" if candidates != 1 else ""} reviewed</span>' if candidates else ""

    reason_html = ""
    if status not in ("PASS", "N/A") and req.get("reason"):
        reason_html = f'<p class="reason">{req["reason"]}</p>'

    photo_html = ""
    if req.get("photo_url"):
        photo_html = f'<a class="photo-link" href="{req["photo_url"]}" target="_blank">View photo →</a>'

    return f"""
    <div class="requirement req-{status.lower()}">
      <div class="req-header">
        {status_badge(status)}
        <span class="req-id">{req["id"]}</span>
        <span class="req-title">{req["title"]}</span>
        {optional_tag}
        {candidates_note}
      </div>
      {reason_html}
      {photo_html}
    </div>"""


def render_section(section_name: str, reqs: list) -> str:
    applicable = [r for r in reqs if r.get("status") != "N/A"]
    if not applicable:
        return ""

    rows = "".join(render_requirement(r) for r in applicable)
    passed = sum(1 for r in applicable if r["status"] == "PASS")
    total = len(applicable)

    return f"""
  <div class="section">
    <div class="section-header">
      <h2>{section_name}</h2>
      <span class="section-score">{passed}/{total}</span>
    </div>
    {rows}
  </div>"""


def generate_html(report: dict, project: dict) -> str:
    reqs = report.get("requirements", [])
    params = report.get("params", {})
    project_id = report.get("project_id", "")

    # Header info
    name = project.get("name") or f"Project {project_id}"
    address = project.get("address", {})
    addr_str = ", ".join(filter(None, [
        address.get("street_address_1"),
        address.get("city"),
        address.get("state"),
    ]))
    generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Summary counts
    required = [r for r in reqs if r["status"] != "N/A" and not r.get("optional")]
    n_pass    = sum(1 for r in required if r["status"] == "PASS")
    n_fail    = sum(1 for r in required if r["status"] == "FAIL")
    n_missing = sum(1 for r in required if r["status"] == "MISSING")
    n_error   = sum(1 for r in required if r["status"] == "ERROR")
    n_total   = len(required)

    overall_class = "overall-pass" if (n_fail + n_missing + n_error) == 0 else "overall-fail"
    overall_label = "READY FOR SUBMISSION" if (n_fail + n_missing + n_error) == 0 else "ACTION REQUIRED"

    # Job params
    manufacturer = params.get("manufacturer", "—")
    lender = params.get("lender", "—")
    has_battery = "Yes" if params.get("has_battery") else "No"
    backup = "Yes" if params.get("is_backup_battery") else "No"
    incentive = "Yes" if params.get("is_incentive_state") else "No"
    portal = "Yes" if params.get("portal_access_granted") else "No"

    # Group by section
    sections: dict = {}
    for r in reqs:
        sections.setdefault(r["section"], []).append(r)

    sections_html = "".join(render_section(sec, reqs) for sec, reqs in sections.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>M1 Compliance Report — {name}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f4f5f7;
      color: #1a1a2e;
      font-size: 14px;
      line-height: 1.5;
    }}

    /* ── Header ── */
    .header {{
      background: #1a1a2e;
      color: #fff;
      padding: 28px 40px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }}
    .header-left h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; }}
    .header-left .address {{ font-size: 13px; color: #9ca3af; }}
    .header-right {{ text-align: right; font-size: 12px; color: #9ca3af; }}

    /* ── Overall status banner ── */
    .overall-banner {{
      padding: 16px 40px;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.05em;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .overall-pass {{ background: #d1fae5; color: #065f46; }}
    .overall-fail {{ background: #fee2e2; color: #991b1b; }}
    .overall-banner .score {{
      font-size: 13px;
      font-weight: 400;
      letter-spacing: 0;
      opacity: 0.8;
    }}

    /* ── Job params ── */
    .params-bar {{
      background: #fff;
      border-bottom: 1px solid #e5e7eb;
      padding: 12px 40px;
      display: flex;
      gap: 32px;
      flex-wrap: wrap;
    }}
    .param {{ display: flex; flex-direction: column; gap: 2px; }}
    .param-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: #6b7280; }}
    .param-value {{ font-size: 13px; font-weight: 500; }}

    /* ── Body ── */
    .body {{ max-width: 860px; margin: 32px auto; padding: 0 20px; }}

    /* ── Section ── */
    .section {{ margin-bottom: 28px; }}
    .section-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 2px solid #1a1a2e;
      margin-bottom: 12px;
    }}
    .section-header h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }}
    .section-score {{ font-size: 12px; font-weight: 600; color: #6b7280; }}

    /* ── Requirement row ── */
    .requirement {{
      background: #fff;
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 8px;
      border-left: 4px solid #e5e7eb;
    }}
    .req-pass    {{ border-left-color: #10b981; }}
    .req-fail    {{ border-left-color: #ef4444; }}
    .req-missing {{ border-left-color: #f59e0b; }}
    .req-error   {{ border-left-color: #8b5cf6; }}
    .req-n\/a    {{ border-left-color: #e5e7eb; opacity: 0.5; }}

    .req-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .req-id {{ font-size: 11px; font-weight: 700; color: #6b7280; min-width: 32px; }}
    .req-title {{ font-size: 14px; font-weight: 500; flex: 1; }}

    .optional-tag {{
      font-size: 10px;
      background: #f3f4f6;
      color: #6b7280;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 500;
    }}
    .candidates-note {{
      font-size: 11px;
      color: #9ca3af;
    }}

    /* ── Badges ── */
    .badge {{
      font-size: 10px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 4px;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }}
    .badge-pass    {{ background: #d1fae5; color: #065f46; }}
    .badge-fail    {{ background: #fee2e2; color: #991b1b; }}
    .badge-missing {{ background: #fef3c7; color: #92400e; }}
    .badge-error   {{ background: #ede9fe; color: #5b21b6; }}
    .badge-skip    {{ background: #f3f4f6; color: #6b7280; }}
    .badge-na      {{ background: #f3f4f6; color: #9ca3af; }}

    /* ── Reason & photo ── */
    .reason {{
      margin-top: 10px;
      font-size: 13px;
      color: #374151;
      padding-left: 12px;
      border-left: 2px solid #e5e7eb;
      white-space: pre-wrap;
    }}
    .photo-link {{
      display: inline-block;
      margin-top: 8px;
      font-size: 12px;
      color: #3b82f6;
      text-decoration: none;
      font-weight: 500;
    }}
    .photo-link:hover {{ text-decoration: underline; }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 32px;
      font-size: 11px;
      color: #9ca3af;
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
      <div>Palmetto M1 Compliance Report</div>
      <div>{generated}</div>
      <div>Project ID: {project_id}</div>
    </div>
  </div>

  <div class="overall-banner {overall_class}">
    {overall_label}
    <span class="score">{n_pass} passed &nbsp;·&nbsp; {n_fail} failed &nbsp;·&nbsp; {n_missing} missing &nbsp;·&nbsp; {n_total} required</span>
  </div>

  <div class="params-bar">
    <div class="param"><span class="param-label">Lender</span><span class="param-value">{lender}</span></div>
    <div class="param"><span class="param-label">Manufacturer</span><span class="param-value">{manufacturer}</span></div>
    <div class="param"><span class="param-label">Battery</span><span class="param-value">{has_battery}</span></div>
    <div class="param"><span class="param-label">Backup</span><span class="param-value">{backup}</span></div>
    <div class="param"><span class="param-label">Incentive State</span><span class="param-value">{incentive}</span></div>
    <div class="param"><span class="param-label">Portal Access</span><span class="param-value">{portal}</span></div>
  </div>

  <div class="body">
    {sections_html}
  </div>

  <div class="footer">
    Generated by Solclear Compliance &nbsp;·&nbsp; Palmetto LightReach M1 Requirements
  </div>

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
