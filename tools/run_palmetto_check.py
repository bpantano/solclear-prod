"""
tools/run_palmetto_check.py
Daily cron entry-point for Palmetto M1 requirements change detection
and reference photo scraping.

This is the script Railway's cron service runs. It:
  1. Fetches the Palmetto M1 spec page and diffs against the baseline
  2. Notifies superadmins if material requirements changed
  3. Scrapes reference photos from the article and stores them in
     requirement_reference_photos so the report detail UI can show
     reviewers/crew what a passing photo looks like for each requirement

Railway cron setup:
  - Service: add a new service in the same Railway project
  - Start command: python -m tools.run_palmetto_check
  - Cron Schedule: 0 6 * * *  (6am UTC daily)
  - Same environment variables as the web service

Cost per run: ~$0.001 (one Haiku call for diff analysis, only when changes detected).
"""
import hashlib
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

PALMETTO_URL = (
    "https://help.palmetto.finance/en/articles/"
    "8306274-solar-energy-plan-install-m1-photo-documentation"
)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Extracts ALL requirement codes mentioned in a heading.
# Handles both individual headings ("R1) Close up...") and shared
# example headings ("PS1 and PS2 Photo Examples:") so photos are
# attributed to every requirement mentioned, not just the first.
_REQ_CODE_ANY = re.compile(r'\b([A-Z]{1,3}\d+)\b', re.IGNORECASE)


def scrape_reference_photos() -> dict:
    """Scrape Palmetto's article and return {req_code: [{src_url, alt_text}]}.
    Associates each image with the nearest preceding requirement heading."""
    resp = requests.get(PALMETTO_URL, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    article = (
        soup.find("div", class_=lambda c: c and "article" in c.lower())
        or soup.find("article")
        or soup
    )

    photos_by_req: dict = {}
    current_reqs: list = []  # may be multiple codes for shared headings

    for el in article.descendants:
        if not hasattr(el, "name") or not el.name:
            continue
        # New heading — extract ALL requirement codes mentioned.
        # "PS1 and PS2 Photo Examples:" → [PS1, PS2]
        # "R1) Close up of attachments..." → [R1]
        if el.name in ("h1", "h2", "h3", "h4", "h5"):
            heading_text = el.get_text(strip=True)
            codes = [m.upper() for m in _REQ_CODE_ANY.findall(heading_text)]
            # Only update current_reqs if we found known-style codes
            # (filter out stray numbers like "1" or "2" in prose)
            valid = [c for c in codes if len(c) >= 2]
            if valid:
                current_reqs = valid
                for code in current_reqs:
                    if code not in photos_by_req:
                        photos_by_req[code] = []
        # Image — assign to ALL currently-active requirement codes so
        # shared example sections populate every relevant requirement.
        elif el.name == "img" and current_reqs:
            src = el.get("src") or el.get("data-src") or ""
            if not src or src.startswith("data:") or len(src) < 20:
                continue
            alt = el.get("alt") or ""
            for code in current_reqs:
                photos_by_req[code].append({"src_url": src, "alt_text": alt})

    return photos_by_req


def save_reference_photos(photos_by_req: dict) -> int:
    """Replace all stored reference photos with the freshly-scraped set.
    Downloads each image and stores bytes in Postgres. Returns total saved."""
    from tools.db import execute, fetch_all
    # Clear old set — we always replace with the freshest scrape
    execute("DELETE FROM requirement_reference_photos")

    total = 0
    for req_code, photos in photos_by_req.items():
        for order, photo in enumerate(photos):
            src = photo["src_url"]
            try:
                r = requests.get(src, headers={"User-Agent": USER_AGENT}, timeout=15)
                r.raise_for_status()
                mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
                execute(
                    """INSERT INTO requirement_reference_photos
                       (requirement_code, image_bytes, mime_type, src_url, alt_text, display_order)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (req_code, r.content, mime, src, photo.get("alt_text") or "", order),
                )
                total += 1
            except Exception as e:
                print(f"  [ref-photos] could not fetch {src[:60]}: {e}", file=sys.stderr)

    return total


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
        # First ever run — save baseline + scrape reference photos
        save_snapshot(current)
        print("[palmetto-cron] no baseline found — saved baseline. Scraping reference photos...")
        try:
            photos_by_req = scrape_reference_photos()
            n = save_reference_photos(photos_by_req)
            reqs_covered = len(photos_by_req)
            print(f"[palmetto-cron] saved {n} reference photos across {reqs_covered} requirements.")
        except Exception as e:
            print(f"[palmetto-cron] reference photo scrape failed: {e}", file=sys.stderr)
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

    # Save to palmetto_change_history for the Requirements tab changelog.
    try:
        from tools.audit import save_palmetto_change
        save_palmetto_change(
            summary=analysis.get("summary", f"{added} lines added, {removed} lines removed."),
            lines_added=added, lines_removed=removed,
            new_ids=[r.get("id", "") if isinstance(r, dict) else r for r in analysis.get("new_ids", [])],
            changed_ids=analysis.get("changed_ids", []),
            removed_ids=analysis.get("removed_ids", []),
        )
        print("[palmetto-cron] change saved to palmetto_change_history")
    except Exception as e:
        print(f"[palmetto-cron] history save failed: {e}", file=sys.stderr)

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

    # 5. Refresh reference photos whenever the spec changes — the photos
    #    may have been updated alongside the text (new examples, removed
    #    examples, etc). Always re-scrape on any change, not just material.
    try:
        print("[palmetto-cron] re-scraping reference photos...")
        photos_by_req = scrape_reference_photos()
        n = save_reference_photos(photos_by_req)
        print(f"[palmetto-cron] saved {n} reference photos across {len(photos_by_req)} requirements.")
    except Exception as e:
        print(f"[palmetto-cron] reference photo refresh failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
