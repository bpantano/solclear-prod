"""
Tool: monitor_requirements.py
Purpose: Fetch the Palmetto M1 requirements page and compare against a saved snapshot.
         Flags any changes so the knowledgebase can be updated.

Usage:
  python tools/monitor_requirements.py              # Check for changes
  python tools/monitor_requirements.py --save       # Save current page as the baseline snapshot
  python tools/monitor_requirements.py --summarize  # Use Haiku to summarize what changed (~$0.001)
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TMP_DIR = Path(__file__).parent.parent / ".tmp"
SNAPSHOT_PATH = TMP_DIR / "palmetto_requirements_snapshot.txt"
SNAPSHOT_META_PATH = TMP_DIR / "palmetto_requirements_meta.json"

PALMETTO_URL = "https://help.palmetto.finance/en/articles/8306274-solar-energy-plan-install-m1-photo-documentation"


def fetch_page() -> str:
    """Fetch the Palmetto requirements page and extract text content."""
    resp = requests.get(PALMETTO_URL, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SolclearBot/1.0)"
    })
    resp.raise_for_status()
    html = resp.text

    # Strip scripts, styles, and HTML tags — keep only article content
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove dynamic values that change on every page load
    text = re.sub(r'"nonce":"[^"]*"', '"nonce":"***"', text)
    text = re.sub(r'"userId":"[^"]*"', '"userId":"***"', text)
    text = re.sub(r'"_sentryTraceData":"[^"]*"', '"_sentryTraceData":"***"', text)
    text = re.sub(r'"_sentryBaggage":"[^"]*"', '"_sentryBaggage":"***"', text)
    text = re.sub(r'sentry-trace_id=[^,&"]+', 'sentry-trace_id=***', text)
    text = re.sub(r'sentry-sample_rand=[^,&"]+', 'sentry-sample_rand=***', text)

    # Normalize whitespace per line for cleaner diffs
    lines = [line.strip() for line in text.split('.') if line.strip()]
    return '\n'.join(lines)


def _use_db():
    """Check if database is available."""
    try:
        from tools.db import fetch_one
        return True
    except Exception:
        return False


def save_snapshot(text: str):
    """Save current page text as the baseline snapshot."""
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    if _use_db():
        from tools.db import execute
        # Clear old snapshots and insert new one
        execute("DELETE FROM requirement_snapshots WHERE url = %s", (PALMETTO_URL,))
        execute(
            "INSERT INTO requirement_snapshots (url, content_hash, content_text) VALUES (%s, %s, %s)",
            (PALMETTO_URL, content_hash, text)
        )
        print(f"Snapshot saved to database ({len(text)} chars)")
        print(f"Hash: {content_hash[:16]}...")
        return

    # Fallback to local file
    TMP_DIR.mkdir(exist_ok=True)
    with open(SNAPSHOT_PATH, 'w') as f:
        f.write(text)

    meta = {
        "url": PALMETTO_URL,
        "saved_at": datetime.now().isoformat(),
        "hash": content_hash,
        "length": len(text),
    }
    with open(SNAPSHOT_META_PATH, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"Snapshot saved to file ({len(text)} chars)")
    print(f"Hash: {content_hash[:16]}...")


def load_snapshot() -> str:
    """Load the previously saved snapshot."""
    if _use_db():
        from tools.db import fetch_one
        row = fetch_one(
            "SELECT content_text FROM requirement_snapshots WHERE url = %s ORDER BY checked_at DESC LIMIT 1",
            (PALMETTO_URL,)
        )
        return row["content_text"] if row else ""

    # Fallback to local file
    if not SNAPSHOT_PATH.exists():
        return ""
    with open(SNAPSHOT_PATH) as f:
        return f.read()


def compare(old: str, new: str) -> list:
    """Return a list of diff lines between old and new text."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm='',
                                      fromfile='previous', tofile='current', n=2))
    return diff


def summarize_changes(diff_text: str) -> str:
    """Use Haiku to summarize what changed in the requirements. Cost: ~$0.001."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "(ANTHROPIC_API_KEY not set — cannot summarize)"

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{
                "role": "user",
                "content": (
                    "This is a diff of the Palmetto Finance solar installation M1 photo documentation requirements page. "
                    "Summarize what changed in plain language — focus on any new requirements added, requirements removed, "
                    "or wording changes that affect what photos are needed. Be specific about photo IDs if visible.\n\n"
                    f"```\n{diff_text[:3000]}\n```"
                ),
            }],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def analyze_changes_structured(diff_text: str) -> dict:
    """Use Haiku to return structured JSON about what changed. Cost: ~$0.001.
    Returns: {"summary": "...", "new_ids": [{"id": "PS7", "section": "...", "title": "..."}], "changed_ids": ["PS1", "R3"], "removed_ids": ["E8"]}
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"summary": "Cannot analyze — API key not set", "new_ids": [], "changed_ids": [], "removed_ids": []}

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": (
                    "This is a diff of the Palmetto Finance solar installation M1 photo documentation requirements page. "
                    "Analyze the changes and respond with ONLY valid JSON (no markdown, no backticks) in this format:\n"
                    '{"summary": "Plain English summary of changes", '
                    '"material": true, '
                    '"new_ids": [{"id": "PS7", "section": "Project Site", "title": "Short description of new requirement"}], '
                    '"changed_ids": ["PS1", "R3"], '
                    '"removed_ids": ["E8"]}\n\n'
                    "Rules:\n"
                    "- material: true if any actual photo documentation requirements changed (new/modified/removed photo IDs, "
                    "changed validation criteria, new sections). false if only metadata changed (timestamps like 'Updated yesterday' to "
                    "'Updated today', backend feature flags, session tokens, page layout, navigation elements).\n"
                    "- new_ids: requirements that were added (didn't exist before). Include the photo ID, section, and title.\n"
                    "- changed_ids: existing requirements whose wording, conditions, or details changed.\n"
                    "- removed_ids: requirements that were deleted.\n"
                    "- If no changes to a category, use an empty array.\n"
                    "- Photo IDs follow patterns like PS1-PS6, R1-R6, E1-E9, S1-S6, SC1-SC2, SI1-SI2, AMS1-AMS2.\n\n"
                    f"Diff:\n```\n{diff_text[:3000]}\n```"
                ),
            }],
        },
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    # Strip markdown code blocks if Haiku wraps the JSON
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"summary": text, "new_ids": [], "changed_ids": [], "removed_ids": []}


def main():
    parser = argparse.ArgumentParser(description="Monitor Palmetto requirements for changes")
    parser.add_argument("--save", action="store_true", help="Save current page as baseline snapshot")
    parser.add_argument("--summarize", action="store_true", help="Use Haiku to summarize changes (~$0.001)")
    args = parser.parse_args()

    print(f"Fetching {PALMETTO_URL}...", file=sys.stderr)
    current = fetch_page()
    current_hash = hashlib.sha256(current.encode()).hexdigest()

    if args.save:
        save_snapshot(current)
        return

    previous = load_snapshot()
    if not previous:
        print("No baseline snapshot found. Run with --save first to create one.")
        print(f"  python tools/monitor_requirements.py --save")
        return

    prev_hash = hashlib.sha256(previous.encode()).hexdigest()

    if current_hash == prev_hash:
        print(f"\nNo changes detected.")
        if SNAPSHOT_META_PATH.exists():
            with open(SNAPSHOT_META_PATH) as f:
                meta = json.load(f)
            print(f"Baseline from: {meta.get('saved_at', 'unknown')}")
        print(f"Current hash:  {current_hash[:16]}...")
        return

    # Changes detected
    diff = compare(previous, current)
    diff_text = '\n'.join(diff)

    added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))

    print(f"\n{'='*50}")
    print(f"  CHANGES DETECTED")
    print(f"{'='*50}")
    print(f"  Lines added:   {added}")
    print(f"  Lines removed: {removed}")
    print()

    # Show the diff
    for line in diff[:80]:
        if line.startswith('+'):
            print(f"  \033[32m{line}\033[0m")
        elif line.startswith('-'):
            print(f"  \033[31m{line}\033[0m")
        else:
            print(f"  {line}")

    if len(diff) > 80:
        print(f"\n  ... ({len(diff) - 80} more lines)")

    if args.summarize:
        print(f"\n{'─'*50}")
        print("  AI SUMMARY (Haiku)")
        print(f"{'─'*50}")
        summary = summarize_changes(diff_text)
        print(f"  {summary}")

    print(f"\n{'─'*50}")
    print("  To update the baseline after reviewing:")
    print("    python tools/monitor_requirements.py --save")
    print(f"{'─'*50}")


if __name__ == "__main__":
    main()
