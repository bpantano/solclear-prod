"""
Tool: companycam_get_project_checklists.py
Purpose: Retrieve all checklists (with sections and tasks) for a CompanyCam project.
Output: JSON to stdout.

Usage:
  python tools/companycam_get_project_checklists.py --project_id <id>
"""

import argparse
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


def get_project_checklists(project_id):
    resp = requests.get(
        f"{API_BASE}/projects/{project_id}/checklists",
        headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Get checklists for a CompanyCam project")
    parser.add_argument("--project_id", required=True, help="CompanyCam project ID")
    args = parser.parse_args()

    checklists = get_project_checklists(args.project_id)
    print(json.dumps(checklists, indent=2))


if __name__ == "__main__":
    main()
