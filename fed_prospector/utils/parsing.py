"""Parsing utilities for federal data files."""

import re


def fix_pipe_escapes(line):
    """Fix escaped pipe characters in DAT extract files.

    SAM.gov DAT files use |\\| to represent empty fields.
    This should become || (two pipes = empty field).
    """
    return line.replace("|\\|", "||")


def parse_pipe_delimited(line, expected_fields=None):
    """Parse a pipe-delimited line into a list of values.

    Empty fields (between consecutive pipes) become None.
    Strips whitespace from values.

    Args:
        line: Raw pipe-delimited string
        expected_fields: If set, validates field count

    Returns:
        List of string values (or None for empty fields)
    """
    cleaned = fix_pipe_escapes(line.rstrip("\n\r"))
    parts = cleaned.split("|")
    result = []
    for p in parts:
        stripped = p.strip()
        result.append(stripped if stripped else None)
    return result


def split_tilde_values(value):
    """Split tilde-delimited multi-value fields.

    SAM.gov uses ~ to separate multiple values in a single field.
    Example: 'code1~code2~code3' -> ['code1', 'code2', 'code3']

    Returns:
        List of strings, or empty list if value is None/empty
    """
    if not value:
        return []
    return [v.strip() for v in value.split("~") if v.strip()]
