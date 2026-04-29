"""Tests for Phase 125 document-level keyword filter in attachment_intel_extractor.

Covers:
- _fetch_eligible_notices selecting on document-level keyword_analyzed_at
- _count_eligible_notices mirroring the same filter (counter/fetcher invariant)
- _filter_unanalyzed_sources skipping already-analyzed sibling docs in mixed-state notices
- --force overriding both eligibility and the per-doc skip
- description-only path retaining the prior notice-level "skip if any summary exists" filter
- attachment-path NO LONGER unioning in description-only-no-attachment notices
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.attachment_intel_extractor import AttachmentIntelExtractor


def _build_cursor(rows=None, scalar=None):
    """Cursor whose fetchall returns `rows` and fetchone returns (scalar,)."""
    cursor = MagicMock()
    cursor.fetchall.return_value = list(rows or [])
    cursor.fetchone.return_value = (scalar,) if scalar is not None else None
    return cursor


def _build_conn(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def _make_extractor(description_only=False):
    extractor = AttachmentIntelExtractor(
        db_connection=MagicMock(), load_manager=MagicMock(),
    )
    extractor._description_only = description_only
    return extractor


# ===================================================================
# _fetch_eligible_notices — attachment path (description_only=False)
# ===================================================================

class TestFetchEligibleNoticesAttachmentPath:

    def test_all_docs_already_analyzed_notice_not_selected(self):
        cursor = _build_cursor(rows=[])  # filter excludes the notice
        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            result = extractor._fetch_eligible_notices(
                notice_id=None, batch_size=100, method="keyword", force=False,
            )
        assert result == []

        sql, params = cursor.execute.call_args[0]
        assert "ad.keyword_analyzed_at IS NULL" in sql
        assert "ad.extraction_status = 'extracted'" in sql
        assert "opportunity_attachment_summary" not in sql
        assert params == [100]

    def test_unanalyzed_or_mixed_notice_selected(self):
        cursor = _build_cursor(rows=[("notice-A",), ("notice-B",)])
        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            result = extractor._fetch_eligible_notices(
                notice_id=None, batch_size=100, method="keyword", force=False,
            )
        assert result == ["notice-A", "notice-B"]
        sql, _ = cursor.execute.call_args[0]
        assert "ad.keyword_analyzed_at IS NULL" in sql

    def test_force_drops_keyword_analyzed_predicate(self):
        cursor = _build_cursor(rows=[("notice-X",)])
        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            result = extractor._fetch_eligible_notices(
                notice_id=None, batch_size=100, method="keyword", force=True,
            )
        assert result == ["notice-X"]
        sql, params = cursor.execute.call_args[0]
        assert "keyword_analyzed_at" not in sql
        assert "opportunity_attachment_summary" not in sql
        assert params == [100]

    def test_description_only_no_attachment_notice_dropped_from_attachment_path(self):
        """Regression check for the deliberate Phase 125 deviation.

        Pre-Phase-125 the attachment-path query UNIONed in opportunity rows that
        had description_text but no attachment. Post-Phase-125 those notices are
        the exclusive domain of description_only=True. Verify the SQL no longer
        references the opportunity table on the attachment branch.
        """
        cursor = _build_cursor(rows=[])
        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            extractor._fetch_eligible_notices(
                notice_id=None, batch_size=100, method="keyword", force=False,
            )
        sql, _ = cursor.execute.call_args[0]
        assert "FROM opportunity " not in sql
        assert "UNION" not in sql.upper()
        assert "description_text" not in sql


# ===================================================================
# _fetch_eligible_notices — description-only path (regression check)
# ===================================================================

class TestFetchEligibleNoticesDescriptionOnly:

    def test_existing_summary_excludes_notice(self):
        cursor = _build_cursor(rows=[])
        extractor = _make_extractor(description_only=True)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            result = extractor._fetch_eligible_notices(
                notice_id=None, batch_size=100, method="description", force=False,
            )
        assert result == []
        sql, params = cursor.execute.call_args[0]
        assert "opportunity_attachment_summary" in sql
        assert "s.summary_id IS NULL" in sql
        assert "description_text" in sql
        assert params == ["description", 100]

    def test_force_skips_summary_filter(self):
        cursor = _build_cursor(rows=[("notice-D",)])
        extractor = _make_extractor(description_only=True)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            result = extractor._fetch_eligible_notices(
                notice_id=None, batch_size=100, method="description", force=True,
            )
        assert result == ["notice-D"]
        sql, _ = cursor.execute.call_args[0]
        assert "opportunity_attachment_summary" not in sql


# ===================================================================
# _count_eligible_notices — must mirror _fetch_eligible_notices
# ===================================================================

class TestCountEligibleNotices:

    def test_attachment_path_uses_doc_level_filter(self):
        cursor = _build_cursor(scalar=42)
        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            count = extractor._count_eligible_notices(
                notice_id=None, method="keyword", force=False,
            )
        assert count == 42
        sql = cursor.execute.call_args[0][0]
        assert "ad.keyword_analyzed_at IS NULL" in sql
        assert "COUNT(DISTINCT m.notice_id)" in sql

    def test_attachment_path_force_drops_doc_level_filter(self):
        cursor = _build_cursor(scalar=99)
        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            count = extractor._count_eligible_notices(
                notice_id=None, method="keyword", force=True,
            )
        assert count == 99
        sql = cursor.execute.call_args[0][0]
        assert "keyword_analyzed_at" not in sql

    def test_description_only_path_keeps_summary_filter(self):
        cursor = _build_cursor(scalar=7)
        extractor = _make_extractor(description_only=True)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            count = extractor._count_eligible_notices(
                notice_id=None, method="description", force=False,
            )
        assert count == 7
        sql = cursor.execute.call_args[0][0]
        assert "opportunity_attachment_summary" in sql
        assert "s.summary_id IS NULL" in sql

    def test_notice_id_short_circuits_to_one(self):
        extractor = _make_extractor(description_only=False)
        # Should not even open a connection.
        with patch("etl.attachment_intel_extractor.get_connection") as gc:
            count = extractor._count_eligible_notices(
                notice_id="solo-notice", method="keyword", force=False,
            )
            gc.assert_not_called()
        assert count == 1


# ===================================================================
# Counter/fetcher pair-call invariant
# ===================================================================

class TestCounterFetcherAgreement:
    """The pair _count_eligible_notices / _fetch_eligible_notices must agree.

    They are called back-to-back from extract_intel (lines 496-497). If they
    diverge, the progress bar lies. We can't compare the live numbers without a
    real DB, but we CAN assert they emit structurally-equivalent WHERE clauses
    on the same hand-built fixture.
    """

    @pytest.mark.parametrize("description_only,force", [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ])
    def test_filter_predicates_match(self, description_only, force):
        fetch_cursor = _build_cursor(rows=[])
        count_cursor = _build_cursor(scalar=0)

        extractor = _make_extractor(description_only=description_only)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(fetch_cursor)):
            extractor._fetch_eligible_notices(
                notice_id=None, batch_size=10_000, method="keyword", force=force,
            )
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(count_cursor)):
            extractor._count_eligible_notices(
                notice_id=None, method="keyword", force=force,
            )

        fetch_sql = fetch_cursor.execute.call_args[0][0]
        count_sql = count_cursor.execute.call_args[0][0]

        for predicate in (
            "keyword_analyzed_at IS NULL",
            "extraction_status = 'extracted'",
            "extracted_text IS NOT NULL",
            "description_text IS NOT NULL",
            "s.summary_id IS NULL",
            "opportunity_attachment_summary",
        ):
            assert (predicate in fetch_sql) == (predicate in count_sql), (
                f"fetch and count disagree on predicate {predicate!r} "
                f"with description_only={description_only}, force={force}"
            )

    def test_returns_same_count_as_fetch_len_on_shared_fixture(self):
        """When the underlying state is the same, count == len(fetch)."""
        notice_rows = [("n1",), ("n2",), ("n3",)]
        fetch_cursor = _build_cursor(rows=notice_rows)
        count_cursor = _build_cursor(scalar=len(notice_rows))

        extractor = _make_extractor(description_only=False)
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(fetch_cursor)):
            fetched = extractor._fetch_eligible_notices(
                notice_id=None, batch_size=10_000, method="keyword", force=False,
            )
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(count_cursor)):
            counted = extractor._count_eligible_notices(
                notice_id=None, method="keyword", force=False,
            )
        assert counted == len(fetched) == 3


# ===================================================================
# _filter_unanalyzed_sources — per-document skip used by _process_notice
# ===================================================================

class TestFilterUnanalyzedSources:

    def test_drops_already_analyzed_docs(self):
        cursor = _build_cursor(rows=[(101,), (103,)])
        extractor = _make_extractor()
        sources = [
            (101, "old.pdf", "text 1"),
            (102, "new.pdf", "text 2"),
            (103, "another_old.pdf", "text 3"),
            (104, "new2.pdf", "text 4"),
        ]
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            kept = extractor._filter_unanalyzed_sources(sources)

        kept_ids = [s[0] for s in kept]
        assert kept_ids == [102, 104]

    def test_keeps_all_when_none_analyzed(self):
        cursor = _build_cursor(rows=[])
        extractor = _make_extractor()
        sources = [
            (201, "a.pdf", "text"),
            (202, "b.pdf", "text"),
        ]
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            kept = extractor._filter_unanalyzed_sources(sources)
        assert [s[0] for s in kept] == [201, 202]

    def test_drops_all_when_all_analyzed(self):
        cursor = _build_cursor(rows=[(301,), (302,)])
        extractor = _make_extractor()
        sources = [
            (301, "a.pdf", "text"),
            (302, "b.pdf", "text"),
        ]
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            kept = extractor._filter_unanalyzed_sources(sources)
        assert kept == []

    def test_description_text_source_always_passes(self):
        """document_id=None marks description_text — it has no per-doc analyzed flag."""
        cursor = _build_cursor(rows=[(401,)])
        extractor = _make_extractor()
        sources = [
            (None, "description_text", "desc"),
            (401, "a.pdf", "text"),
            (402, "b.pdf", "text"),
        ]
        with patch("etl.attachment_intel_extractor.get_connection",
                   return_value=_build_conn(cursor)):
            kept = extractor._filter_unanalyzed_sources(sources)
        assert (None, "description_text", "desc") in kept
        assert 402 in [s[0] for s in kept]
        assert 401 not in [s[0] for s in kept]

    def test_only_description_source_skips_db(self):
        """No real document_ids → no SELECT issued."""
        extractor = _make_extractor()
        sources = [(None, "description_text", "only desc")]
        with patch("etl.attachment_intel_extractor.get_connection") as gc:
            kept = extractor._filter_unanalyzed_sources(sources)
            gc.assert_not_called()
        assert kept == sources


# ===================================================================
# --force in _process_notice bypasses _filter_unanalyzed_sources
# ===================================================================

class TestProcessNoticeForceBypassesPerDocSkip:

    def test_force_skips_filter_call(self):
        extractor = _make_extractor()
        extractor._cleanup_stale_intel_rows = MagicMock()
        extractor._gather_text_sources = MagicMock(return_value=[
            (1, "a.pdf", "text"),
            (2, "b.pdf", "text"),
        ])
        extractor._filter_unanalyzed_sources = MagicMock(
            side_effect=AssertionError(
                "_filter_unanalyzed_sources must not be called when force=True"
            )
        )
        extractor._run_patterns = MagicMock(return_value=[])
        extractor._consolidate_matches = MagicMock(return_value={})
        extractor._compute_combined_hash = MagicMock(return_value="h")
        extractor._stamp_keyword_analyzed_by_doc = MagicMock()
        extractor._upsert_summary_row = MagicMock()

        result = extractor._process_notice(
            notice_id="N1", method="keyword", load_id=1, force=True,
        )

        extractor._filter_unanalyzed_sources.assert_not_called()
        extractor._cleanup_stale_intel_rows.assert_called_once_with("N1")
        assert result == {"intel_upserted": 0, "sources_inserted": 0}

    def test_no_force_calls_filter(self):
        extractor = _make_extractor()
        extractor._gather_text_sources = MagicMock(return_value=[
            (1, "a.pdf", "text"),
            (2, "b.pdf", "text"),
        ])
        extractor._filter_unanalyzed_sources = MagicMock(return_value=[
            (2, "b.pdf", "text"),
        ])
        extractor._run_patterns = MagicMock(return_value=[])
        extractor._consolidate_matches = MagicMock(return_value={})
        extractor._compute_combined_hash = MagicMock(return_value="h")
        extractor._stamp_keyword_analyzed_by_doc = MagicMock()
        extractor._upsert_summary_row = MagicMock()

        extractor._process_notice(
            notice_id="N2", method="keyword", load_id=1, force=False,
        )

        extractor._filter_unanalyzed_sources.assert_called_once()
        passed = extractor._filter_unanalyzed_sources.call_args[0][0]
        assert len(passed) == 2
        # Only the un-filtered doc reaches the pattern extractor.
        run_calls = extractor._run_patterns.call_args_list
        assert len(run_calls) == 1
        assert run_calls[0][0][1] == 2  # attachment_id arg

    def test_no_force_short_circuits_when_filter_returns_empty(self):
        extractor = _make_extractor()
        extractor._gather_text_sources = MagicMock(return_value=[
            (1, "a.pdf", "text"),
        ])
        extractor._filter_unanalyzed_sources = MagicMock(return_value=[])
        extractor._run_patterns = MagicMock(side_effect=AssertionError(
            "_run_patterns must not run when all docs already analyzed"
        ))
        extractor._upsert_summary_row = MagicMock(side_effect=AssertionError(
            "summary upsert must not run when all docs already analyzed"
        ))

        result = extractor._process_notice(
            notice_id="N3", method="keyword", load_id=1, force=False,
        )

        assert result == {"intel_upserted": 0, "sources_inserted": 0}
        extractor._run_patterns.assert_not_called()
        extractor._upsert_summary_row.assert_not_called()


# ===================================================================
# Phase 125B Task 6 — new pattern categories
# ===================================================================
#
# These tests exercise _run_patterns directly. The method is pure
# (text in -> matches out) so no DB mocking is required beyond the
# existing pattern of passing MagicMock() into the constructor.

def _matches_for(extractor, text, *, category=None, pattern_name=None,
                 attachment_id=1, filename="doc.pdf"):
    """Run patterns and filter by category and/or pattern_name."""
    raw = extractor._run_patterns(text, attachment_id, filename)
    out = []
    for cat, info in raw:
        if category is not None and cat != category:
            continue
        if pattern_name is not None and info["pattern_name"] != pattern_name:
            continue
        out.append((cat, info))
    return out


class TestContractCeilingPattern:

    def test_shall_not_exceed_dollar_amount(self):
        extractor = _make_extractor()
        text = "The total contract value shall not exceed $5,000,000 over the period."
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "ceiling_amount"
        assert "$5,000,000" in matches[0][1]["matched_text"]

    def test_ceiling_of_dollar_amount(self):
        extractor = _make_extractor()
        text = "Awarded with a ceiling of $10 million across all CLINs."
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert len(matches) == 1
        assert "$10" in matches[0][1]["matched_text"]

    def test_nte_dollar_amount(self):
        extractor = _make_extractor()
        text = "Issued NTE $2,500,000 for this task."
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "ceiling_amount"
        assert "$2,500,000" in matches[0][1]["matched_text"]


class TestNoBidBondContextCheck:
    """The no_bid_bond context check suppresses ceiling matches when a
    bid-bond / proposal-price phrase appears within 120 chars BEFORE the
    match. The filter must be targeted enough that legitimate contract
    ceilings still match.
    """

    def test_bid_price_within_120_chars_suppresses_match(self):
        extractor = _make_extractor()
        text = (
            "The bidder shall furnish a bid bond equal to 20 percent of the bid price "
            "but not to exceed $500,000 of the contract."
        )
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert matches == []

    def test_proposal_price_within_120_chars_suppresses_match(self):
        extractor = _make_extractor()
        text = (
            "The proposal price submitted shall not exceed $1,000,000 in the offer."
        )
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert matches == []

    def test_bid_guarantee_within_120_chars_suppresses_match(self):
        extractor = _make_extractor()
        text = (
            "A bid guarantee equal to twenty percent of the price, "
            "not to exceed $50,000."
        )
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert matches == []

    def test_twenty_percent_within_120_chars_suppresses_match(self):
        extractor = _make_extractor()
        text = (
            "The bidder shall furnish twenty percent of the price not to exceed "
            "$25,000."
        )
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert matches == []

    def test_real_macc_ceiling_still_matches(self):
        extractor = _make_extractor()
        text = "The MACC shall not exceed $175 Million over five years."
        matches = _matches_for(extractor, text, category="contract_ceiling")
        assert len(matches) == 1
        assert "$175" in matches[0][1]["matched_text"]


class TestClinStructurePattern:

    def test_clin_with_four_digit_id_matches(self):
        extractor = _make_extractor()
        text = "CLIN 0001 - Base Year Services"
        matches = _matches_for(extractor, text, category="clin_structure")
        assert len(matches) == 1
        assert matches[0][1]["matched_text"] == "CLIN 0001"

    def test_clin_with_other_four_digit_id_matches(self):
        extractor = _make_extractor()
        text = "See CLIN 1234 in the schedule."
        matches = _matches_for(extractor, text, category="clin_structure")
        assert len(matches) == 1
        assert matches[0][1]["matched_text"] == "CLIN 1234"

    def test_clin_with_non_digit_suffix_does_not_match(self):
        extractor = _make_extractor()
        text = "Notes show clin abc test."
        matches = _matches_for(extractor, text, category="clin_structure")
        assert matches == []

    def test_nclins_substring_does_not_match(self):
        extractor = _make_extractor()
        text = "NCLINS will be issued separately."
        matches = _matches_for(extractor, text, category="clin_structure")
        assert matches == []


class TestTechSpecsPattern:

    def test_mil_std_matches(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "See MIL-STD-2073 for packaging.",
            category="tech_specs",
        )
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "techspec_mil_std"
        assert "MIL-STD-2073" in matches[0][1]["matched_text"]

    def test_mil_spec_matches(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "Apply MIL-SPEC-12345 coating.",
            category="tech_specs",
        )
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "techspec_mil_spec"
        assert "MIL-SPEC-12345" in matches[0][1]["matched_text"]

    def test_mil_hdbk_with_letter_suffix_matches(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "Per MIL-HDBK-516C airworthiness.",
            category="tech_specs",
        )
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "techspec_mil_hdbk"
        assert "MIL-HDBK-516C" in matches[0][1]["matched_text"]

    def test_mil_prf_with_letter_suffix_matches(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "Component meets MIL-PRF-19500F qualification.",
            category="tech_specs",
        )
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "techspec_mil_prf"
        assert "MIL-PRF-19500F" in matches[0][1]["matched_text"]

    def test_astm_with_letter_dash_digits_matches(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "Per ASTM D3951-18 standard.",
            category="tech_specs",
        )
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "techspec_astm"
        assert "ASTM D3951-18" in matches[0][1]["matched_text"]

    def test_astm_without_revision_suffix_matches(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "Reference ASTM E814 in section.",
            category="tech_specs",
        )
        assert len(matches) == 1
        assert matches[0][1]["pattern_name"] == "techspec_astm"
        assert "ASTM E814" in matches[0][1]["matched_text"]

    def test_invalid_mil_prefix_does_not_match(self):
        extractor = _make_extractor()
        matches = _matches_for(
            extractor, "MIL-XYZ-9999 not real.",
            category="tech_specs",
        )
        assert matches == []


class TestNaicsSizeStandardEnhancement:
    """Phase 125B added a capture group for the dollar amount. Pattern still
    has value=None, so the dollar amount surfaces via matched_text (and the
    consolidator's `tag_value if value else matched_text` fallback)."""

    def test_size_standard_is_dollar_million(self):
        extractor = _make_extractor()
        text = "NAICS 541330 size standard is $34 million for this code."
        matches = _matches_for(extractor, text, pattern_name="naics_size_standard")
        assert len(matches) == 1
        assert "$34" in matches[0][1]["matched_text"]
        assert "million" in matches[0][1]["matched_text"].lower()

    def test_size_standard_of_dollar_with_commas(self):
        extractor = _make_extractor()
        text = "Size standard of $45,000,000 applies."
        matches = _matches_for(extractor, text, pattern_name="naics_size_standard")
        assert len(matches) == 1
        assert "$45,000,000" in matches[0][1]["matched_text"]

    def test_size_standard_of_dollar_compact_M(self):
        extractor = _make_extractor()
        text = "Small business with size standard of $12.5M revenue."
        matches = _matches_for(extractor, text, pattern_name="naics_size_standard")
        assert len(matches) == 1
        assert "$12.5M" in matches[0][1]["matched_text"]

    def test_size_standard_no_preposition_dollar_million(self):
        extractor = _make_extractor()
        text = "Size standard $16.5 Million for the NAICS code."
        matches = _matches_for(extractor, text, pattern_name="naics_size_standard")
        assert len(matches) == 1
        assert "$16.5" in matches[0][1]["matched_text"]
        assert "Million" in matches[0][1]["matched_text"]


class TestWageWdNumberEnhancement:
    """Phase 125B added a capture group for the WD identifier. Pattern still
    has value=None, so the WD number surfaces via matched_text."""

    def test_wage_determination_no_colon_format(self):
        extractor = _make_extractor()
        text = "Wage Determination No.: 2015-5237 applies to this contract."
        matches = _matches_for(extractor, text, pattern_name="wage_wd_number")
        assert len(matches) == 1
        assert "2015-5237" in matches[0][1]["matched_text"]

    def test_wage_determination_bare_number_format(self):
        extractor = _make_extractor()
        text = "See Wage Determination 2015-4217 for rates."
        matches = _matches_for(extractor, text, pattern_name="wage_wd_number")
        assert len(matches) == 1
        assert "2015-4217" in matches[0][1]["matched_text"]
