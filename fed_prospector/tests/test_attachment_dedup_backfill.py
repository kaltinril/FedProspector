"""Unit tests for etl.attachment_dedup_backfill (Phase 124, Tasks 10/11).

Uses mocks/fixtures only — never touches the live DB or real filesystem
beyond a tempfile-managed area for the file-deletion test.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from etl.attachment_dedup_backfill import AttachmentDedupBackfill


# ---------------------------------------------------------------------------
# Helpers — synthetic data for a 3-row duplicate group
# ---------------------------------------------------------------------------

def _make_row(attachment_id, document_id, resource_guid, file_path,
              content_hash="hash_abc", text_hash="text_xyz",
              evidence_count=0, summary_count=0, keyword_count=0, ai_count=0,
              file_size_bytes=1024, has_keyword=False, has_ai=False):
    """Build a row dict matching what _fetch_group_rows() returns."""
    return {
        "attachment_id": attachment_id,
        "document_id": document_id,
        "resource_guid": resource_guid,
        "file_path": file_path,
        "file_size_bytes": file_size_bytes,
        "content_hash": content_hash,
        "text_hash": text_hash,
        "evidence_count": evidence_count,
        "summary_count": summary_count,
        "keyword_count": keyword_count,
        "ai_count": ai_count,
        "has_keyword": has_keyword,
        "has_ai": has_ai,
        "keyword_analyzed_at": None,
        "ai_analyzed_at": None,
    }


# ---------------------------------------------------------------------------
# Test 1: Pick canonical correctly
# ---------------------------------------------------------------------------

class TestPickCanonical:

    def test_picks_row_with_highest_intel_count(self):
        rows = [
            _make_row(10, 100, "guid_a", "a/f.pdf", summary_count=1, evidence_count=2),
            _make_row(11, 101, "guid_b", "b/f.pdf",
                      summary_count=4, evidence_count=10, has_ai=True, has_keyword=True),
            _make_row(12, 102, "guid_c", "c/f.pdf", summary_count=0, evidence_count=0),
        ]
        canonical, non_canonicals = AttachmentDedupBackfill._pick_canonical(rows)
        assert canonical["attachment_id"] == 11
        assert {nc["attachment_id"] for nc in non_canonicals} == {10, 12}

    def test_tiebreak_prefers_lowest_attachment_id(self):
        rows = [
            _make_row(20, 200, "guid_a", "a/f.pdf"),
            _make_row(15, 199, "guid_b", "b/f.pdf"),
            _make_row(30, 300, "guid_c", "c/f.pdf"),
        ]
        canonical, non_canonicals = AttachmentDedupBackfill._pick_canonical(rows)
        assert canonical["attachment_id"] == 15
        assert len(non_canonicals) == 2

    def test_ai_beats_keyword_only(self):
        rows = [
            _make_row(1, 1, "g1", "p1", has_keyword=True),
            _make_row(2, 2, "g2", "p2", has_ai=True),
        ]
        canonical, _ = AttachmentDedupBackfill._pick_canonical(rows)
        # Both have summary_count=0+evidence_count=0 → fall to AI tiebreak
        assert canonical["attachment_id"] == 2

    def test_keyword_beats_neither(self):
        rows = [
            _make_row(1, 1, "g1", "p1"),
            _make_row(2, 2, "g2", "p2", has_keyword=True),
        ]
        canonical, _ = AttachmentDedupBackfill._pick_canonical(rows)
        assert canonical["attachment_id"] == 2


# ---------------------------------------------------------------------------
# Test 2: _is_already_deduped
# ---------------------------------------------------------------------------

class TestIsAlreadyDeduped:

    def test_returns_true_when_row_present(self):
        backfill = AttachmentDedupBackfill(db_connection=MagicMock())
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        assert backfill._is_already_deduped(cursor, "abc123") is True

    def test_returns_false_when_no_row(self):
        backfill = AttachmentDedupBackfill(db_connection=MagicMock())
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        assert backfill._is_already_deduped(cursor, "abc123") is False


# ---------------------------------------------------------------------------
# Test 3: Full backfill on a synthetic 3-row group
# ---------------------------------------------------------------------------

class TestProcessGroupSyntheticThreeRows:

    def _build_conn(self, group_rows, opportunity_attachment_rows_by_id,
                    duplicate_groups_content_hash=None,
                    duplicate_groups_text_hash=None,
                    already_deduped_guids=None):
        """Build a mock conn whose cursor responds to known query patterns."""
        already_deduped_guids = already_deduped_guids or set()
        duplicate_groups_content_hash = duplicate_groups_content_hash or []
        duplicate_groups_text_hash = duplicate_groups_text_hash or []

        # Track DB writes for assertions
        log = {
            "inserts_oa": [],          # opportunity_attachment INSERTs
            "deletes_oa": [],          # opportunity_attachment DELETEs
            "inserts_dedup_map": [],   # attachment_dedup_map INSERTs
            "deletes_evidence": [],    # document_intel_evidence DELETEs by doc_id
            "deletes_summary": [],     # document_intel_summary DELETEs by doc_id
            "deletes_doc": [],         # attachment_document DELETEs by doc_id
            "updates_clear_path": [],  # sam_attachment SET file_path = NULL
            "commits": 0,
            "rollbacks": 0,
        }

        def make_cursor(dictionary=False):
            cur = MagicMock()
            state = {"last_query": None, "last_params": None,
                     "last_rowcount": 0, "last_rows": []}

            def execute(query, params=None):
                q = " ".join(query.split())  # collapse whitespace
                state["last_query"] = q
                state["last_params"] = params or ()
                state["last_rowcount"] = 0
                state["last_rows"] = []

                # Fetch duplicate-group hashes
                if "FROM sam_attachment sa" in q and "GROUP BY sa.content_hash" in q:
                    state["last_rows"] = [(h,) for h in duplicate_groups_content_hash]
                    return
                if "FROM attachment_document ad" in q and "GROUP BY ad.text_hash" in q:
                    state["last_rows"] = [(h,) for h in duplicate_groups_text_hash]
                    return

                # Fetch group rows (the fat SELECT with subqueries)
                if "FROM sam_attachment sa JOIN attachment_document ad" in q and \
                   "evidence_count" in q.lower() or "evidence_count" in q:
                    state["last_rows"] = list(group_rows)
                    return

                # Already-deduped lookup
                if "FROM attachment_dedup_map WHERE resource_guid" in q:
                    guid = params[0] if params else None
                    state["last_rows"] = [(1,)] if guid in already_deduped_guids else []
                    return

                # opportunity_attachment lookup
                if q.startswith("SELECT notice_id, url FROM opportunity_attachment"):
                    nc_id = params[0]
                    state["last_rows"] = list(
                        opportunity_attachment_rows_by_id.get(nc_id, [])
                    )
                    return

                # INSERT IGNORE INTO opportunity_attachment
                if q.startswith("INSERT IGNORE INTO opportunity_attachment"):
                    log["inserts_oa"].append(params)
                    return
                if q.startswith("DELETE FROM opportunity_attachment"):
                    log["deletes_oa"].append(params)
                    return

                # INSERT INTO attachment_dedup_map
                if q.startswith("INSERT INTO attachment_dedup_map"):
                    log["inserts_dedup_map"].append(params)
                    return

                # DELETE evidence/summary/document
                if q.startswith("DELETE FROM document_intel_evidence"):
                    log["deletes_evidence"].append(params[0])
                    state["last_rowcount"] = 3  # synthetic count
                    return
                if q.startswith("DELETE FROM document_intel_summary"):
                    log["deletes_summary"].append(params[0])
                    state["last_rowcount"] = 1
                    return
                if q.startswith("DELETE FROM attachment_document"):
                    log["deletes_doc"].append(params[0])
                    state["last_rowcount"] = 1
                    return

                # UPDATE sam_attachment
                if q.startswith("UPDATE sam_attachment SET file_path = NULL"):
                    log["updates_clear_path"].append(params[0])
                    return

                # Dry-run COUNT(*) variants
                if q.startswith("SELECT COUNT(*) FROM document_intel_evidence"):
                    state["last_rows"] = [(3,)]
                    return
                if q.startswith("SELECT COUNT(*) FROM document_intel_summary"):
                    state["last_rows"] = [(1,)]
                    return

            def fetchall():
                return state["last_rows"]

            def fetchone():
                if state["last_rows"]:
                    return state["last_rows"][0]
                return None

            cur.execute.side_effect = execute
            cur.fetchall.side_effect = fetchall
            cur.fetchone.side_effect = fetchone
            type(cur).rowcount = property(lambda self: state["last_rowcount"])
            return cur

        conn = MagicMock()
        conn.cursor.side_effect = lambda dictionary=False: make_cursor(dictionary)

        def commit():
            log["commits"] += 1
        def rollback():
            log["rollbacks"] += 1
        conn.commit.side_effect = commit
        conn.rollback.side_effect = rollback

        return conn, log

    def test_canonical_chosen_non_canonicals_remapped_and_deleted(self, tmp_path):
        # Build: 3-row content_hash group; row 11 has the most intel.
        rows = [
            _make_row(10, 100, "guid_a", "guid_a/file.pdf",
                      content_hash="HHH", text_hash="TTT"),
            _make_row(11, 101, "guid_b", "guid_b/file.pdf",
                      content_hash="HHH", text_hash="TTT",
                      summary_count=4, evidence_count=10,
                      has_ai=True, has_keyword=True),
            _make_row(12, 102, "guid_c", "guid_c/file.pdf",
                      content_hash="HHH", text_hash="TTT"),
        ]
        oa_rows = {
            10: [("notice-1", "https://example/g_a")],
            11: [("notice-2", "https://example/g_b")],
            12: [("notice-3", "https://example/g_c")],
        }
        conn, log = self._build_conn(
            group_rows=rows,
            opportunity_attachment_rows_by_id=oa_rows,
            duplicate_groups_content_hash=["HHH"],
            duplicate_groups_text_hash=[],  # already collapsed by content_hash dedup
        )

        # Create real files for the non-canonicals so file deletion exercises
        attachment_dir = tmp_path
        for row in rows:
            full = attachment_dir / row["file_path"]
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(b"x" * 1024)

        backfill = AttachmentDedupBackfill(
            db_connection=conn,
            attachment_dir=str(attachment_dir),
        )
        stats = backfill.run(dry_run=False)

        # Canonical was attachment_id=11 → dedup map should have guid_a and guid_c
        deduped_guids = {p[0] for p in log["inserts_dedup_map"]}
        canonical_ids = {p[1] for p in log["inserts_dedup_map"]}
        methods = {p[2] for p in log["inserts_dedup_map"]}

        assert deduped_guids == {"guid_a", "guid_c"}
        assert canonical_ids == {11}
        assert methods == {"content_hash"}

        # opportunity_attachment remapping: 2 INSERTs (one per non-canonical's mapping)
        assert len(log["inserts_oa"]) == 2
        # Each INSERT should reference canonical_id=11
        for params in log["inserts_oa"]:
            notice_id, attachment_id, url = params
            assert attachment_id == 11

        # 2 DELETEs from opportunity_attachment for the non-canonicals
        assert len(log["deletes_oa"]) == 2

        # 2 evidence + 2 summary + 2 document deletes
        assert log["deletes_evidence"] == [100, 102]
        assert log["deletes_summary"] == [100, 102]
        assert log["deletes_doc"] == [100, 102]

        # 2 file_path NULLs
        assert log["updates_clear_path"] == [10, 12]

        # Files for non-canonicals should be gone
        assert not (attachment_dir / "guid_a/file.pdf").exists()
        assert not (attachment_dir / "guid_c/file.pdf").exists()
        # Canonical's file is preserved
        assert (attachment_dir / "guid_b/file.pdf").exists()

        # Stats: 1 group, 2 rows deduped, 2 files deleted
        assert stats["groups_processed"] == 1
        assert stats["rows_deleted"] == 2
        assert stats["files_deleted"] == 2
        assert stats["rows_remapped"] == 2
        assert stats["dry_run"] is False
        # Should have committed at least once (per group)
        assert log["commits"] >= 1


# ---------------------------------------------------------------------------
# Test 4: Resume — re-running on already-deduped data is a no-op
# ---------------------------------------------------------------------------

class TestResume:

    def test_already_deduped_rows_are_skipped(self, tmp_path):
        rows = [
            _make_row(10, 100, "guid_a", "guid_a/f.pdf",
                      content_hash="HHH", text_hash="TTT"),
            _make_row(11, 101, "guid_b", "guid_b/f.pdf",
                      content_hash="HHH", text_hash="TTT",
                      has_ai=True, summary_count=2, evidence_count=5),
        ]
        # Pretend guid_a is already in attachment_dedup_map
        builder = TestProcessGroupSyntheticThreeRows()
        conn, log = builder._build_conn(
            group_rows=rows,
            opportunity_attachment_rows_by_id={10: [], 11: []},
            duplicate_groups_content_hash=["HHH"],
            duplicate_groups_text_hash=[],
            already_deduped_guids={"guid_a"},
        )

        backfill = AttachmentDedupBackfill(
            db_connection=conn,
            attachment_dir=str(tmp_path),
        )
        stats = backfill.run(dry_run=False)

        # No dedup_map inserts (the only non-canonical was already done)
        assert log["inserts_dedup_map"] == []
        # No deletes
        assert log["deletes_doc"] == []
        # Resumed-skip count incremented
        assert stats["rows_skipped_resumed"] == 1
        assert stats["rows_deleted"] == 0


# ---------------------------------------------------------------------------
# Test 5: Dry-run produces report and writes nothing
# ---------------------------------------------------------------------------

class TestDryRun:

    def test_dry_run_does_not_write(self, tmp_path):
        rows = [
            _make_row(10, 100, "guid_a", "guid_a/f.pdf",
                      content_hash="HHH", text_hash="TTT"),
            _make_row(11, 101, "guid_b", "guid_b/f.pdf",
                      content_hash="HHH", text_hash="TTT",
                      has_ai=True, summary_count=2, evidence_count=5),
            _make_row(12, 102, "guid_c", "guid_c/f.pdf",
                      content_hash="HHH", text_hash="TTT"),
        ]
        builder = TestProcessGroupSyntheticThreeRows()
        conn, log = builder._build_conn(
            group_rows=rows,
            opportunity_attachment_rows_by_id={
                10: [("n1", "u1")], 11: [], 12: [("n3", "u3")],
            },
            duplicate_groups_content_hash=["HHH"],
            duplicate_groups_text_hash=[],
        )

        # Real files so dry-run can see filesystem sizes
        for row in rows:
            full = tmp_path / row["file_path"]
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_bytes(b"y" * 2048)

        backfill = AttachmentDedupBackfill(
            db_connection=conn,
            attachment_dir=str(tmp_path),
        )
        stats = backfill.run(dry_run=True)

        # NO writes should have happened
        assert log["inserts_dedup_map"] == []
        assert log["inserts_oa"] == []
        assert log["deletes_oa"] == []
        assert log["deletes_evidence"] == []
        assert log["deletes_summary"] == []
        assert log["deletes_doc"] == []
        assert log["updates_clear_path"] == []
        # Should have rolled back at end of group (dry-run path)
        assert log["rollbacks"] >= 1
        assert log["commits"] == 0

        # Files should all still exist
        for row in rows:
            assert (tmp_path / row["file_path"]).exists(), row["file_path"]

        # But stats should reflect what *would* happen
        assert stats["dry_run"] is True
        assert stats["groups_processed"] == 1
        assert stats["rows_deleted"] == 2  # would-be deletes still counted
        assert stats["files_deleted"] == 2
        # bytes_freed > 0 since files exist
        assert stats["bytes_freed"] >= 2 * 2048

    def test_dry_run_handles_empty_groups(self, tmp_path):
        builder = TestProcessGroupSyntheticThreeRows()
        conn, log = builder._build_conn(
            group_rows=[],
            opportunity_attachment_rows_by_id={},
            duplicate_groups_content_hash=[],
            duplicate_groups_text_hash=[],
        )
        backfill = AttachmentDedupBackfill(
            db_connection=conn,
            attachment_dir=str(tmp_path),
        )
        stats = backfill.run(dry_run=True)
        assert stats["groups_processed"] == 0
        assert stats["rows_deleted"] == 0
        assert log["inserts_dedup_map"] == []


# ---------------------------------------------------------------------------
# Test 6: Group with only 1 row (after partial run) is skipped
# ---------------------------------------------------------------------------

class TestEmptyOrSingletonGroup:

    def test_singleton_group_skipped_with_log(self, tmp_path):
        rows = [_make_row(10, 100, "guid_a", "guid_a/f.pdf",
                          content_hash="HHH", text_hash="TTT")]
        builder = TestProcessGroupSyntheticThreeRows()
        conn, log = builder._build_conn(
            group_rows=rows,
            opportunity_attachment_rows_by_id={},
            duplicate_groups_content_hash=["HHH"],
            duplicate_groups_text_hash=[],
        )
        backfill = AttachmentDedupBackfill(
            db_connection=conn,
            attachment_dir=str(tmp_path),
        )
        stats = backfill.run(dry_run=False)
        assert stats["groups_skipped_empty"] == 1
        assert stats["groups_processed"] == 0
        assert log["inserts_dedup_map"] == []
