"""
Encryption helper for Solclear.
Uses Fernet symmetric encryption to protect sensitive data at rest (API keys, etc.)

The ENCRYPTION_KEY env var must be a valid Fernet key (base64-encoded 32 bytes).
Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Usage:
    from tools.crypto import encrypt, decrypt

    encrypted = encrypt("my-api-key")    # Returns encrypted string or None if key not set
    original  = decrypt(encrypted)       # Returns original string or None if key not set/invalid
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

_fernet = None


def _get_fernet():
    """Get or create the Fernet instance. Returns None if ENCRYPTION_KEY not set."""
    global _fernet
    if _fernet is not None:
        return _fernet
    if not ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(ENCRYPTION_KEY.encode())
        return _fernet
    except Exception as e:
        print(f"WARNING: Invalid ENCRYPTION_KEY: {e}", file=sys.stderr)
        return None


def encrypt(value):
    """Encrypt a string value. Returns encrypted string, or the original value if encryption is not configured."""
    if not value:
        return value
    f = _get_fernet()
    if not f:
        return value  # No encryption key — store as plaintext (dev mode)
    return f.encrypt(value.encode()).decode()


def decrypt(value):
    """Decrypt an encrypted string. Returns original value, or the value as-is if decryption fails (plaintext fallback)."""
    if not value:
        return value
    f = _get_fernet()
    if not f:
        return value  # No encryption key — assume plaintext
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        # Value might be plaintext (pre-encryption migration) — return as-is
        return value


def is_encrypted(value):
    """Check if a value looks like it was encrypted with Fernet (starts with gAAAAA)."""
    return bool(value and value.startswith("gAAAAA"))
