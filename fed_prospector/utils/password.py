"""Password hashing compatible with BCrypt.Net-Next EnhancedHashPassword.

The C# API uses BCrypt.Net.BCrypt.EnhancedHashPassword which:
1. SHA-384 hashes the password
2. Base64-encodes the SHA-384 digest
3. Feeds that into standard BCrypt (cost factor 11)

This module replicates that algorithm in Python so that hashes
generated here are verifiable by the C# API and vice versa.
"""

import base64
import hashlib

import bcrypt

BCRYPT_ROUNDS = 11


def hash_password(password: str) -> str:
    """Hash a password using the BCrypt Enhanced algorithm.

    Args:
        password: Plain-text password.

    Returns:
        BCrypt hash string (e.g. '$2b$11$...').
    """
    sha384_digest = hashlib.sha384(password.encode("utf-8")).digest()
    b64 = base64.b64encode(sha384_digest).decode("utf-8")
    return bcrypt.hashpw(
        b64.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a BCrypt Enhanced hash.

    Args:
        password: Plain-text password to check.
        hashed: BCrypt hash from the database.

    Returns:
        True if the password matches.
    """
    try:
        sha384_digest = hashlib.sha384(password.encode("utf-8")).digest()
        b64 = base64.b64encode(sha384_digest).decode("utf-8")
        return bcrypt.checkpw(b64.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
