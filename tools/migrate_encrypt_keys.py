"""
One-time migration: encrypt existing plaintext API keys in organizations table.

Run after setting ENCRYPTION_KEY in your environment:
  python tools/migrate_encrypt_keys.py

Safe to run multiple times — skips already-encrypted values.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.db import fetch_all, execute
from tools.crypto import encrypt, is_encrypted


def migrate():
    orgs = fetch_all("SELECT id, name, companycam_api_key, anthropic_api_key FROM organizations")
    updated = 0

    for org in orgs:
        changes = {}
        for field in ("companycam_api_key", "anthropic_api_key"):
            val = org.get(field)
            if val and not is_encrypted(val):
                changes[field] = encrypt(val)

        if changes:
            sets = ", ".join(f"{k} = %s" for k in changes)
            vals = list(changes.values()) + [org["id"]]
            execute(f"UPDATE organizations SET {sets} WHERE id = %s", tuple(vals))
            updated += 1
            print(f"  Encrypted keys for org: {org['name']} (id={org['id']})")

    if updated:
        print(f"\nDone — encrypted keys for {updated} organization(s).")
    else:
        print("No plaintext keys found — nothing to migrate.")


if __name__ == "__main__":
    from tools.crypto import ENCRYPTION_KEY
    if not ENCRYPTION_KEY:
        print("ERROR: ENCRYPTION_KEY not set in environment. Generate one with:")
        print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        print("Then add it to your .env file and try again.")
        sys.exit(1)
    migrate()
