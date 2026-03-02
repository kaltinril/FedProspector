"""Tests for etl.change_detector -- hashing, classification, field diff."""

import pytest
from unittest.mock import MagicMock, patch

from etl.change_detector import ChangeDetector
from utils.hashing import compute_record_hash


# ===================================================================
# compute_record_hash tests (utils.hashing)
# ===================================================================

class TestComputeRecordHash:

    def test_deterministic(self):
        record = {"a": "1", "b": "2"}
        h1 = compute_record_hash(record, ["a", "b"])
        h2 = compute_record_hash(record, ["a", "b"])
        assert h1 == h2

    def test_returns_64_char_hex(self):
        result = compute_record_hash({"x": "y"}, ["x"])
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_none_values_treated_as_empty(self):
        r1 = compute_record_hash({"a": None}, ["a"])
        r2 = compute_record_hash({}, ["a"])  # missing key also yields empty
        assert r1 == r2

    def test_field_order_does_not_matter(self):
        record = {"b": "2", "a": "1"}
        h1 = compute_record_hash(record, ["a", "b"])
        h2 = compute_record_hash(record, ["b", "a"])
        assert h1 == h2  # fields are sorted alphabetically

    def test_different_values_produce_different_hashes(self):
        r1 = compute_record_hash({"a": "1"}, ["a"])
        r2 = compute_record_hash({"a": "2"}, ["a"])
        assert r1 != r2

    def test_extra_fields_ignored(self):
        r1 = compute_record_hash({"a": "1", "b": "2"}, ["a"])
        r2 = compute_record_hash({"a": "1", "c": "3"}, ["a"])
        assert r1 == r2


# ===================================================================
# ChangeDetector.compute_hash tests
# ===================================================================

class TestChangeDetectorComputeHash:

    def test_delegates_to_compute_record_hash(self):
        cd = ChangeDetector()
        record = {"name": "test", "value": "123"}
        result = cd.compute_hash(record, ["name", "value"])
        expected = compute_record_hash(record, ["name", "value"])
        assert result == expected


# ===================================================================
# ChangeDetector.classify_records tests
# ===================================================================

class TestClassifyRecords:

    def test_new_record_classified_as_insert(self):
        cd = ChangeDetector()
        records = [{"key": "A", "value": "1"}]
        existing = {}

        result = cd.classify_records(records, existing, "key", ["key", "value"])

        assert len(result["inserts"]) == 1
        assert len(result["updates"]) == 0
        assert len(result["unchanged"]) == 0

    def test_unchanged_record_classified(self):
        cd = ChangeDetector()
        record = {"key": "A", "value": "1"}
        existing_hash = cd.compute_hash(record, ["key", "value"])
        records = [record]
        existing = {"A": existing_hash}

        result = cd.classify_records(records, existing, "key", ["key", "value"])

        assert len(result["unchanged"]) == 1
        assert len(result["inserts"]) == 0
        assert len(result["updates"]) == 0

    def test_changed_record_classified_as_update(self):
        cd = ChangeDetector()
        old_record = {"key": "A", "value": "1"}
        old_hash = cd.compute_hash(old_record, ["key", "value"])

        new_record = {"key": "A", "value": "2"}
        records = [new_record]
        existing = {"A": old_hash}

        result = cd.classify_records(records, existing, "key", ["key", "value"])

        assert len(result["updates"]) == 1
        assert len(result["inserts"]) == 0
        assert len(result["unchanged"]) == 0

    def test_mixed_classification(self):
        cd = ChangeDetector()
        existing_record = {"key": "A", "value": "1"}
        existing_hash = cd.compute_hash(existing_record, ["key", "value"])

        records = [
            {"key": "A", "value": "1"},  # unchanged
            {"key": "A2", "value": "2"},  # new (insert)
            {"key": "A", "value": "999"},  # would be update but key A already seen
        ]
        existing = {"A": existing_hash}

        result = cd.classify_records(records, existing, "key", ["key", "value"])

        total = len(result["inserts"]) + len(result["updates"]) + len(result["unchanged"])
        assert total == 3

    def test_computed_hash_added_to_records(self):
        cd = ChangeDetector()
        records = [{"key": "A", "value": "1"}]

        cd.classify_records(records, {}, "key", ["key", "value"])

        assert "_computed_hash" in records[0]


# ===================================================================
# ChangeDetector.compute_field_diff tests
# ===================================================================

class TestComputeFieldDiff:

    def test_no_changes(self):
        cd = ChangeDetector()
        old = {"a": "1", "b": "2"}
        new = {"a": "1", "b": "2"}
        assert cd.compute_field_diff(old, new, ["a", "b"]) == []

    def test_single_field_changed(self):
        cd = ChangeDetector()
        old = {"a": "1", "b": "2"}
        new = {"a": "1", "b": "3"}
        diffs = cd.compute_field_diff(old, new, ["a", "b"])

        assert len(diffs) == 1
        assert diffs[0] == ("b", "2", "3")

    def test_multiple_fields_changed(self):
        cd = ChangeDetector()
        old = {"a": "1", "b": "2"}
        new = {"a": "X", "b": "Y"}
        diffs = cd.compute_field_diff(old, new, ["a", "b"])

        assert len(diffs) == 2

    def test_none_to_value(self):
        cd = ChangeDetector()
        old = {"a": None}
        new = {"a": "1"}
        diffs = cd.compute_field_diff(old, new, ["a"])

        assert len(diffs) == 1
        assert diffs[0] == ("a", None, "1")

    def test_value_to_none(self):
        cd = ChangeDetector()
        old = {"a": "1"}
        new = {"a": None}
        diffs = cd.compute_field_diff(old, new, ["a"])

        assert len(diffs) == 1
        assert diffs[0] == ("a", "1", None)

    def test_both_none_no_diff(self):
        cd = ChangeDetector()
        old = {"a": None}
        new = {"a": None}
        assert cd.compute_field_diff(old, new, ["a"]) == []

    def test_numeric_comparison_as_strings(self):
        cd = ChangeDetector()
        old = {"amount": 100}
        new = {"amount": "100"}
        # Both convert to str "100" so should match
        assert cd.compute_field_diff(old, new, ["amount"]) == []
