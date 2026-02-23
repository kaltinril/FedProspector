"""SHA-256 record hashing for change detection."""

import hashlib


def compute_record_hash(record: dict, fields: list) -> str:
    """Compute SHA-256 hash of specified fields from a record.

    Fields are sorted alphabetically and joined with pipes.
    None values become empty strings.

    Args:
        record: Dictionary of field values
        fields: List of field names to include in hash

    Returns:
        64-character hex SHA-256 hash string
    """
    parts = []
    for field in sorted(fields):
        val = record.get(field)
        parts.append(str(val) if val is not None else "")
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
