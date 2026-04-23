"""
Tool: design/generate.py
Purpose: Render every Solclear HTML surface to a static file in this folder
         so it can be shared with a design tool (Claude Design, Figma
         screenshots, etc.) without pulling in the whole codebase / .env.

Usage (from repo root):
    python -m design.generate

Produces:
    design/app.html              — main SPA shell (EMBEDDED_HTML)
    design/login.html            — sign-in
    design/forgot-password.html
    design/reset-password.html
    design/change-password.html
    design/request-demo.html
    design/report-sample.html    — sample compliance report (report id=1 if
                                   available, otherwise a stub with fake data)

Nothing in this folder reads from .env, touches CompanyCam, or hits the DB
except the optional fetch of one sample report for report-sample.html. It's
safe to zip and share with a design tool.
"""
import json
import sys
from pathlib import Path

# Allow running as `python -m design.generate` from the repo root.
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools.html.embedded import EMBEDDED_HTML
from tools.html.auth_pages import (
    LOGIN_HTML,
    FORGOT_PASSWORD_HTML,
    RESET_PASSWORD_HTML,
    CHANGE_PASSWORD_HTML,
    REQUEST_DEMO_HTML,
)
from tools.generate_report_html import generate_html as generate_report

OUT = Path(__file__).parent


def _write(name: str, html: str) -> None:
    path = OUT / name
    path.write_text(html)
    print(f"  {path.relative_to(ROOT)}  ({len(html):,} bytes)")


def _sample_report_html() -> str:
    """Try to pull report id=1 from the DB for a realistic render. Falls back
    to a hand-rolled stub if the DB isn't reachable (e.g. when running on a
    laptop without .env)."""
    try:
        from tools.db import fetch_one, fetch_all  # noqa: E402
        db_report = fetch_one("""
            SELECT r.*, p.companycam_id, p.name as project_name,
                   p.address, p.city, p.state
            FROM reports r JOIN projects p ON p.id = r.project_id
            WHERE r.id = 1
        """)
        if not db_report:
            raise RuntimeError("no report id=1 in DB")
        results = fetch_all("""
            SELECT rr.status, rr.reason, rr.photo_urls, rr.candidates,
                   rr.resolved_at, rr.resolved_by, rr.notes,
                   u.full_name AS resolved_by_name,
                   req.code AS id, req.title, req.section,
                   req.is_optional AS optional
            FROM requirement_results rr
            JOIN requirements req ON req.id = rr.requirement_id
            LEFT JOIN users u ON u.id = rr.resolved_by
            WHERE rr.report_id = 1
            ORDER BY req.id
        """)
        for r in results:
            if r.get("resolved_at"):
                r["resolved_at"] = r["resolved_at"].isoformat()
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
            "checklist_ids": [],
            "db_report_id": 1,
        }
        project = {
            "name": db_report.get("project_name", ""),
            "address": {
                "street_address_1": db_report.get("address", ""),
                "city": db_report.get("city", ""),
                "state": db_report.get("state", ""),
            },
        }
        return generate_report(report, project)
    except Exception as e:
        print(f"  (no DB available — falling back to stub report: {e})")
        stub_report = {
            "project_id": "SAMPLE-0001",
            "params": {
                "manufacturer": "Tesla", "lender": "LightReach",
                "has_battery": True, "is_backup_battery": True,
                "is_incentive_state": False, "portal_access_granted": False,
            },
            "checklist_ids": [],
            "db_report_id": None,
            "requirements": [
                {"id": "PS3", "title": "MCI Location & Photo (Tesla only)", "section": "Project Site",
                 "status": "PASS", "reason": "Hand-drawn stringing map visible with MCI positions marked.",
                 "photo_urls": {}, "candidates": 1, "optional": False},
                {"id": "PS5", "title": "Module Serial Number", "section": "Project Site",
                 "status": "PASS", "reason": "Module back-label with serial number clearly legible.",
                 "photo_urls": {}, "candidates": 4, "optional": False},
                {"id": "R4", "title": "Under-Array Wire Management (per array)", "section": "Roof",
                 "status": "NEEDS_REVIEW",
                 "reason": "Camera angle makes clip attachment unclear; please verify in person.",
                 "photo_urls": {}, "candidates": 4, "optional": False},
                {"id": "R6", "title": "Rooftop Junction Box (per junction box)", "section": "Roof",
                 "status": "FAIL",
                 "reason": "Junction box cover is sealed; internal terminations not visible.",
                 "photo_urls": {}, "candidates": 2, "optional": False},
                {"id": "E1", "title": "Main Breaker Rating", "section": "Electrical",
                 "status": "PASS", "reason": "200A main breaker visible and readable.",
                 "photo_urls": {}, "candidates": 3, "optional": False},
            ],
        }
        project = {"name": "Sample Project", "address": {
            "street_address_1": "123 Demo St", "city": "Phoenix", "state": "AZ"}}
        return generate_report(stub_report, project)


def main() -> None:
    print("Rendering design surfaces to", OUT.relative_to(ROOT))
    _write("app.html", EMBEDDED_HTML)
    _write("login.html", LOGIN_HTML)
    _write("forgot-password.html", FORGOT_PASSWORD_HTML)
    _write("reset-password.html", RESET_PASSWORD_HTML)
    _write("change-password.html", CHANGE_PASSWORD_HTML)
    _write("request-demo.html", REQUEST_DEMO_HTML)
    _write("report-sample.html", _sample_report_html())
    print("\nDone. Open any .html file directly in a browser to preview.")


if __name__ == "__main__":
    main()
