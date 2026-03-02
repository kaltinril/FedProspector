"""Unit tests for utils/parsing.py.

Tests cover:
- fix_pipe_escapes: escaped pipe normalization
- parse_pipe_delimited: pipe-delimited line parsing
- split_tilde_values: tilde-delimited multi-value splitting
"""

import pytest

from utils.parsing import fix_pipe_escapes, parse_pipe_delimited, split_tilde_values


# =========================================================================
# fix_pipe_escapes
# =========================================================================

class TestFixPipeEscapes:
    def test_replaces_escaped_pipes(self):
        assert fix_pipe_escapes("|\\|") == "||"

    def test_replaces_multiple_escaped_pipes(self):
        assert fix_pipe_escapes("A|\\|B|\\|C") == "A||B||C"

    def test_no_escaped_pipes_unchanged(self):
        assert fix_pipe_escapes("A|B|C") == "A|B|C"

    def test_empty_string(self):
        assert fix_pipe_escapes("") == ""


# =========================================================================
# parse_pipe_delimited
# =========================================================================

class TestParsePipeDelimited:
    def test_basic_parsing(self):
        result = parse_pipe_delimited("A|B|C")
        assert result == ["A", "B", "C"]

    def test_empty_fields_become_none(self):
        result = parse_pipe_delimited("A||C")
        assert result == ["A", None, "C"]

    def test_strips_whitespace(self):
        result = parse_pipe_delimited("  A  | B |  C  ")
        assert result == ["A", "B", "C"]

    def test_whitespace_only_field_becomes_none(self):
        result = parse_pipe_delimited("A|   |C")
        assert result == ["A", None, "C"]

    def test_fixes_escaped_pipes_first(self):
        result = parse_pipe_delimited("A|\\|B")
        # After fix: "A||B" -> ["A", None, "B"]
        assert result == ["A", None, "B"]

    def test_strips_trailing_newline(self):
        result = parse_pipe_delimited("A|B|C\n")
        assert result == ["A", "B", "C"]

    def test_strips_trailing_crlf(self):
        result = parse_pipe_delimited("A|B|C\r\n")
        assert result == ["A", "B", "C"]


# =========================================================================
# split_tilde_values
# =========================================================================

class TestSplitTildeValues:
    def test_basic_splitting(self):
        result = split_tilde_values("code1~code2~code3")
        assert result == ["code1", "code2", "code3"]

    def test_single_value(self):
        result = split_tilde_values("code1")
        assert result == ["code1"]

    def test_strips_whitespace(self):
        result = split_tilde_values(" code1 ~ code2 ~ code3 ")
        assert result == ["code1", "code2", "code3"]

    def test_empty_segments_ignored(self):
        result = split_tilde_values("code1~~code3")
        assert result == ["code1", "code3"]

    def test_none_returns_empty_list(self):
        assert split_tilde_values(None) == []

    def test_empty_string_returns_empty_list(self):
        assert split_tilde_values("") == []
