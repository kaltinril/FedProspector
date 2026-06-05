"""Tests for the identifier cross-reference matcher (Phase 137 additive changes).

Covers:
- Existing fpds_contract / entity / opportunity match targets still fire
  (regression guard — proves the Phase 137 changes removed nothing).
- Phase 137 CHANGE #2: usaspending_award fallback for PIID (.piid) and
  UEI (.recipient_uei), used ONLY for rows still unmatched after the existing
  priority checks.
- Existing targets take priority over the usaspending_award fallback.
- Phase 137 CHANGE #1: the selection ORDER BY puts never-attempted
  (NULL last_xref_attempt_at) rows first, and the WHERE never filters on the
  fairness marker (no row is permanently excluded).
- Phase 137 CHANGE #1: after processing, every batched ref_id is stamped with
  last_xref_attempt_at = NOW() (round-robin rotation).

The matcher issues a sequence of SELECT ... fetchall() calls. We drive a single
MagicMock cursor's fetchall via side_effect, supplying results in the exact order
the method calls them, and inspect cursor.execute.call_args_list for the UPDATEs
and the selection SQL.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.attachment_identifier_extractor import AttachmentIdentifierExtractor


def _make_extractor():
    # db_connection=None so cross_reference() falls through to the patched
    # get_connection() in _run_cross_reference (matching how the method picks its
    # connection: `self.db_connection or get_connection()`).
    return AttachmentIdentifierExtractor(
        db_connection=None, load_manager=MagicMock(),
    )


def _run_cross_reference(extractor, cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    with patch("etl.attachment_identifier_extractor.get_connection",
               return_value=conn):
        return extractor.cross_reference(batch_size=5000)


def _updates(cursor):
    """Return list of (sql, params) for every UPDATE document_identifier_ref call."""
    out = []
    for call in cursor.execute.call_args_list:
        sql = call[0][0]
        params = call[0][1] if len(call[0]) > 1 else None
        if "UPDATE document_identifier_ref" in sql and "matched_table" in sql:
            out.append((sql, params))
    return out


def _selection_sql(cursor):
    """The first execute call is the unmatched-rows selection SELECT."""
    return cursor.execute.call_args_list[0][0][0]


def _stamp_call(cursor):
    """Return (sql, params) for the round-robin stamping UPDATE, or None."""
    for call in cursor.execute.call_args_list:
        sql = call[0][0]
        params = call[0][1] if len(call[0]) > 1 else None
        if "UPDATE document_identifier_ref" in sql and "last_xref_attempt_at = NOW()" in sql:
            return (sql, params)
    return None


# ======================================================================
# CHANGE #1 — selection ordering & fairness
# ======================================================================

class TestSelectionOrdering:

    def test_order_by_puts_null_attempt_first_and_where_unchanged(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []  # no unmatched rows -> no further selects
        extractor = _make_extractor()
        _run_cross_reference(extractor, cursor)

        sql = _selection_sql(cursor)
        # WHERE must still be the only filter — never a give-up filter on the marker.
        assert "WHERE matched_table IS NULL" in sql
        assert "last_xref_attempt_at IS NOT NULL" in sql  # NULLs sort first
        assert "last_xref_attempt_at ASC" in sql
        assert "ref_id ASC" in sql
        # The fairness marker must NOT appear as a WHERE predicate.
        where_part = sql.split("ORDER BY")[0]
        assert "last_xref_attempt_at" not in where_part

    def test_batch_ref_ids_are_stamped_after_processing(self):
        cursor = MagicMock()
        # One CAGE row that won't match anything (entity returns nothing).
        cursor.fetchall.side_effect = [
            [(11, "CAGE", "1ABC2", "1ABC2")],  # selection
            [],                                  # entity.cage_code lookup -> no match
        ]
        extractor = _make_extractor()
        _run_cross_reference(extractor, cursor)

        stamp = _stamp_call(cursor)
        assert stamp is not None, "round-robin stamping UPDATE must run"
        sql, params = stamp
        assert "last_xref_attempt_at = NOW()" in sql
        assert "ref_id IN" in sql
        assert params == [11]  # the unmatched row is still stamped (rotated, not excluded)


# ======================================================================
# Regression — existing match targets still fire
# ======================================================================

class TestExistingTargetsStillMatch:

    def test_piid_matches_fpds_contract_id(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(1, "PIID", "70LGLY21CGLB00003", "70LGLY21CGLB00003")],  # selection
            [("70LGLY21CGLB00003",)],  # fpds_contract.contract_id -> MATCH
            [],                          # fpds_contract.solicitation_number_normalized
            [],                          # opportunity.solicitation_number_normalized
            # no unmatched_piid -> no usaspending select
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)

        ups = _updates(cursor)
        assert ("fpds_contract", "contract_id", "70LGLY21CGLB00003", 1) in [
            (p[1][0], p[1][1], p[1][2], p[1][3]) for p in ups
        ]
        assert stats["matches_found"] == 1

    def test_solicitation_matches_fpds_normalized(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(2, "SOLICITATION", "70LGLY21RGLB00003", "70LGLY21RGLB00003")],
            [],                          # contract_id -> no match
            [("70LGLY21RGLB00003",)],  # fpds solicitation_number_normalized -> MATCH
            [],                          # opportunity solicitation_number_normalized
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)
        ups = _updates(cursor)
        assert any(
            p[1] == ("fpds_contract", "solicitation_number", "70LGLY21RGLB00003", 2)
            for p in ups
        )
        assert stats["matches_found"] == 1

    def test_solicitation_matches_opportunity_normalized(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(3, "SOLICITATION", "ABCD21R0001", "ABCD21R0001")],
            [],                    # contract_id
            [],                    # fpds solicitation_number_normalized
            [("ABCD21R0001",)],  # opportunity solicitation_number_normalized -> MATCH
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)
        ups = _updates(cursor)
        assert any(
            p[1] == ("opportunity", "solicitation_number", "ABCD21R0001", 3)
            for p in ups
        )
        assert stats["matches_found"] == 1

    def test_uei_matches_entity(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(4, "UEI", "ABC123DEF456", "ABC123DEF456")],  # selection
            [("ABC123DEF456",)],  # entity.uei_sam -> MATCH
            [],                     # fpds_contract.vendor_uei
            # no unmatched_uei -> no usaspending select
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)
        ups = _updates(cursor)
        assert any(
            p[0].count("uei_sam") and p[1] == ("ABC123DEF456", 4) for p in ups
        )
        assert stats["matches_found"] == 1

    def test_uei_matches_fpds_vendor_uei(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(5, "UEI", "XYZ789GHI012", "XYZ789GHI012")],
            [],                     # entity.uei_sam -> no match
            [("XYZ789GHI012",)],  # fpds_contract.vendor_uei -> MATCH
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)
        ups = _updates(cursor)
        assert any(
            "vendor_uei" in p[0] and p[1] == ("XYZ789GHI012", 5) for p in ups
        )
        assert stats["matches_found"] == 1

    def test_cage_matches_entity(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(6, "CAGE", "1ABC2", "1ABC2")],
            [("1ABC2",)],  # entity.cage_code -> MATCH
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)
        ups = _updates(cursor)
        assert any("cage_code" in p[0] and p[1] == ("1ABC2", 6) for p in ups)
        assert stats["matches_found"] == 1

    def test_gsa_schedule_matches_idv_piid(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(7, "GSA_SCHEDULE", "GS02F1234A", "GS-02F-1234A")],
            [("GS02F1234A",)],  # fpds_contract.idv_piid -> MATCH (dashless)
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)
        ups = _updates(cursor)
        assert any("idv_piid" in p[0] and p[1] == ("GS02F1234A", 7) for p in ups)
        assert stats["matches_found"] == 1


# ======================================================================
# CHANGE #2 — usaspending_award fallback
# ======================================================================

class TestUsaspendingFallback:

    def test_piid_only_in_usaspending_award_matches(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(10, "PIID", "47QTCA20D00AB", "47QTCA20D00AB")],  # selection
            [],  # fpds_contract.contract_id -> no match
            [],  # fpds solicitation_number_normalized -> no match
            [],  # opportunity solicitation_number_normalized -> no match
            [("47QTCA20D00AB",)],  # usaspending_award.piid -> MATCH (fallback)
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)

        ups = _updates(cursor)
        assert any(
            "usaspending_award" in p[0]
            and "piid" in p[0]
            and p[1] == ("47QTCA20D00AB", 10)
            for p in ups
        ), "PIID present only in usaspending_award.piid should match via fallback"
        assert stats["matches_found"] == 1

        # The fallback query must hit usaspending_award.piid.
        usa_selects = [
            c[0][0] for c in cursor.execute.call_args_list
            if "usaspending_award" in c[0][0] and "SELECT" in c[0][0].upper()
        ]
        assert any("piid" in s for s in usa_selects)

    def test_uei_only_in_usaspending_award_matches(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(20, "UEI", "MNO345PQR678", "MNO345PQR678")],  # selection
            [],  # entity.uei_sam -> no match
            [],  # fpds_contract.vendor_uei -> no match
            [("MNO345PQR678",)],  # usaspending_award.recipient_uei -> MATCH (fallback)
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)

        ups = _updates(cursor)
        assert any(
            "usaspending_award" in p[0]
            and "recipient_uei" in p[0]
            and p[1] == ("MNO345PQR678", 20)
            for p in ups
        ), "UEI present only in usaspending_award.recipient_uei should match via fallback"
        assert stats["matches_found"] == 1

    def test_existing_target_wins_over_usaspending_fallback(self):
        """When a PIID exists in BOTH fpds_contract and usaspending_award, the
        existing fpds_contract target must win and no usaspending fallback query
        should even be issued for it (it never enters unmatched_piid)."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(30, "PIID", "70LGLY21CGLB00003", "70LGLY21CGLB00003")],  # selection
            [("70LGLY21CGLB00003",)],  # fpds_contract.contract_id -> MATCH
            [],  # fpds solicitation_number_normalized
            [],  # opportunity solicitation_number_normalized
            # no usaspending select expected
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)

        ups = _updates(cursor)
        # Exactly one match, against fpds_contract.contract_id.
        assert len(ups) == 1
        assert ups[0][1] == ("fpds_contract", "contract_id", "70LGLY21CGLB00003", 30)
        assert stats["matches_found"] == 1

        # No usaspending_award SELECT should have been issued.
        usa_selects = [
            c[0][0] for c in cursor.execute.call_args_list
            if "usaspending_award" in c[0][0]
        ]
        assert usa_selects == []

    def test_unmatched_everywhere_still_stamped_not_excluded(self):
        """A PIID found in neither fpds nor usaspending stays unmatched but is
        still stamped (rotated), proving no permanent exclusion."""
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(40, "PIID", "99ZZZZ99Z99999", "99ZZZZ99Z99999")],  # selection
            [],  # fpds_contract.contract_id
            [],  # fpds solicitation_number_normalized
            [],  # opportunity solicitation_number_normalized
            [],  # usaspending_award.piid -> still no match
        ]
        extractor = _make_extractor()
        stats = _run_cross_reference(extractor, cursor)

        assert stats["matches_found"] == 0
        assert _updates(cursor) == []  # no match UPDATEs
        stamp = _stamp_call(cursor)
        assert stamp is not None and stamp[1] == [40]  # rotated, not excluded
