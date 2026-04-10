"""
Tool: companycam_get_checklist_templates.py
Purpose: List all checklist templates in the CompanyCam account.
         Use this to discover what templates exist and find the Palmetto checklist template ID.

Output: JSON to stdout.

Usage:
  python tools/companycam_get_checklist_templates.py
"""

import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.companycam.com/v2"


def get_headers():
    token = os.getenv("COMPANYCAM_API_KEY")
    if not token:
        print("ERROR: COMPANYCAM_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_checklist_templates():
    resp = requests.get(f"{API_BASE}/templates/checklists", headers=get_headers())
    resp.raise_for_status()
    return resp.json()


def main():
    templates = get_checklist_templates()
    print(json.dumps(templates, indent=2))
    print(f"\nFound {len(templates)} checklist template(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
