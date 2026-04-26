"""
tools/run_palmetto_check.py
Daily cron entry-point for Palmetto M1 requirements change detection.

This is the script Railway's cron service runs. It reuses the logic from
tools/monitor_requirements.py and fires bell + email notifications to
superadmins when changes are detected, so they don't have to manually
click "Check Now" in the Requirements admin page.

Railway cron setup:
  - Service: add a new service in the same Railway project
  - Start command: python -m tools.run_palmetto_check
  - Cron Schedule: 0 6 * * *  (6am UTC daily)
  - Same environment variables as the web service

Cost per run: ~$0.001 (one Haiku call for diff analysis, only when changes detected).
"""
import hashlib
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


def main():
    print(f"[palmetto-cron] {datetime.now(timezone.utc).isoformat()} — checking Palmetto M1 spec")

    from tools.monitor_requirements import fetch_page, load_snapshot, save_snapshot, compare, analyze_changes_structured

    # 1. Fetch current page text
    try:
        current = fetch_page()
    except Exception as e:
        print(f"[palmetto-cron] FETCH FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    current_hash = hashlib.sha256(current.encode()).hexdigest()
    print(f"[palmetto-cron] fetched {len(current)} chars, hash={current_hash[:16]}...")

    # 2. Compare to stored baseline
    previous = load_snapshot()
    if not previous:
        # First ever run — save baseline, no notification
        save_snapshot(current)
        print("[palmetto-cron] no baseline found — saved current page as baseline. Will alert on future changes.")
        return

    prev_hash = hashlib.sha256(previous.encode()).hexdigest()
    if current_hash == prev_hash:
        print("[palmetto-cron] no changes detected. Nothing to do.")
        return

    # 3. Changes detected — analyse and notify
    diff = compare(previous, current)
    diff_text = "\n".join(diff[:100])
    added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    print(f"[palmetto-cron] CHANGE DETECTED — +{added} lines / -{removed} lines")

    analysis = {"summary": "", "material": True, "new_ids": [], "changed_ids": [], "removed_ids": []}
    try:
        analysis = analyze_changes_structured(diff_text)
        print(f"[palmetto-cron] AI analysis: material={analysis.get('material')} — {analysis.get('summary', '')[:120]}")
    except Exception as e:
        analysis["summary"] = f"{added} lines added, {removed} lines removed — review the Palmetto page manually."
        print(f"[palmetto-cron] AI analysis failed: {e}", file=sys.stderr)

    is_material = analysis.get("material", True)

    # Only notify for material changes — actual requirement additions,
    # modifications, or removals. Non-material diffs (timestamps, layout,
    # metadata) are logged but don't require superadmin action.
    if is_material:
        try:
            from tools.notifications import notify
            from tools.db import fetch_all
            body = analysis.get("summary") or f"{added} lines added, {removed} lines removed."
            link = "https://help.palmetto.finance/en/articles/8306274-solar-energy-plan-install-m1-photo-documentation"
            superadmins = fetch_all("SELECT id FROM users WHERE role = 'superadmin' AND is_active = TRUE")
            for u in superadmins:
                notify(u["id"], "palmetto_change", "⚠ Palmetto M1 spec changed", body, link,
                       metadata={"added": added, "removed": removed}, send_email=True)
            print(f"[palmetto-cron] notified {len(superadmins)} superadmin(s)")
        except Exception as e:
            print(f"[palmetto-cron] notification failed: {e}", file=sys.stderr)
    else:
        print("[palmetto-cron] non-material change — no notification sent")

    # 4. Save the new content as the updated baseline
    save_snapshot(current)
    print("[palmetto-cron] baseline updated.")


if __name__ == "__main__":
    main()
