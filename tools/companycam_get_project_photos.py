"""
Tool: companycam_get_project_photos.py
Purpose: Retrieve all photos for a CompanyCam project. Handles pagination automatically.
         Saves results to .tmp/photos_{project_id}.json and prints to stdout.

Usage:
  python tools/companycam_get_project_photos.py --project_id <id>
  python tools/companycam_get_project_photos.py --project_id <id> --save_only
"""

import argparse
import json
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.companycam.com/v2"
TMP_DIR = os.path.join(os.path.dirname(__file__), "..", ".tmp")


def get_headers():
    token = os.getenv("COMPANYCAM_API_KEY")
    if not token:
        print("ERROR: COMPANYCAM_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_all_photos(project_id, per_page=100):
    """Fetch all photos across all pages."""
    all_photos = []
    page = 1

    while True:
        params = {"page": page, "per_page": per_page}
        resp = requests.get(
            f"{API_BASE}/projects/{project_id}/photos",
            headers=get_headers(),
            params=params
        )

        if resp.status_code == 429:
            print("Rate limited — waiting 30 seconds...", file=sys.stderr)
            time.sleep(30)
            continue

        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break

        all_photos.extend(batch)

        if len(batch) < per_page:
            break

        page += 1

    return all_photos


def main():
    parser = argparse.ArgumentParser(description="Get all photos for a CompanyCam project")
    parser.add_argument("--project_id", required=True, help="CompanyCam project ID")
    parser.add_argument("--save_only", action="store_true", help="Save to .tmp without printing")
    args = parser.parse_args()

    photos = get_all_photos(args.project_id)

    os.makedirs(TMP_DIR, exist_ok=True)
    output_path = os.path.join(TMP_DIR, f"photos_{args.project_id}.json")
    with open(output_path, "w") as f:
        json.dump(photos, f, indent=2)

    print(f"Saved {len(photos)} photos to {output_path}", file=sys.stderr)

    if not args.save_only:
        print(json.dumps(photos, indent=2))


if __name__ == "__main__":
    main()
