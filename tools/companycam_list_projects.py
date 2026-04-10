"""
Tool: companycam_list_projects.py
Purpose: List CompanyCam projects, optionally filtered by name/address query.
Output: JSON array of project objects to stdout.

Usage:
  python tools/companycam_list_projects.py
  python tools/companycam_list_projects.py --query "Smith residence"
  python tools/companycam_list_projects.py --query "123 Main" --per_page 20
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


def list_projects(query=None, per_page=25, page=1):
    params = {"page": page, "per_page": per_page}
    if query:
        params["query"] = query

    resp = requests.get(f"{API_BASE}/projects", headers=get_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="List CompanyCam projects")
    parser.add_argument("--query", help="Filter by project name or address")
    parser.add_argument("--per_page", type=int, default=25)
    parser.add_argument("--page", type=int, default=1)
    args = parser.parse_args()

    projects = list_projects(query=args.query, per_page=args.per_page, page=args.page)
    print(json.dumps(projects, indent=2))


if __name__ == "__main__":
    main()
