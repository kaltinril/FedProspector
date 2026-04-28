"""Tests for Phase 124 Layer 4 text-hash dedup in attachment_text_extractor.

Exercises `AttachmentTextExtractor._handle_text_hash_dedup` end-to-end with a
mock DB connection so we can verify the exact SQL the method emits without
touching any real database. Per project memory: "Never modify live DB data
for testing."
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure fed_prospector/ is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.attachment_text_extractor import AttachmentTextExtractor


# ---------------------------------------------------------------------------
# Helper: a scriptable mock cursor that returns canned rows in order.
# ---------------------------------------------------------------------------
class ScriptedCursor:
    """A cursor that returns pre-scripted rows for sequential SELECTs.

    Each entry in `responses` is a (fetchone | fetchall, value) tuple consumed
    in order. `executed` records every SQL string executed for assertions.
    """

    def __init__(self, responses, dictionary=False):
        self.responses = list(responses)
        self.executed = []
        self.dictionary = dictionary
        self._last_kind = None
        self._last_value = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        # Pop the next scripted response so the *next* fetchone/fetchall sees it.
        if self.responses:
            self._last_kind, self._last_value = self.responses.pop(0)
        else:
            self._last_kind, self._last_value = None, None

    def fetchone(self):
        if self._last_kind == "fetchone":
            value = self._last_value
            self._last_kind, self._last_value = None, None
            return value
        return None

    def fetchall(self):
        if self._last_kind == "fetchall":
            value = self._last_value
            self._last_kind, self._last_value = None, None
            return value or []
        return []

    def close(self):
        pass


def _build_extractor(read_responses, write_responses=None, attachment_dir=None):
    """Wire an extractor to two scripted cursors (one dict, one tuple).

    The method opens cursor() twice: once with dictionary=True for SELECTs,
    and a plain second cursor() for writes.
    """
    read_cursor = ScriptedCursor(read_responses, dictionary=True)
    write_cursor = ScriptedCursor(write_responses or [], dictionary=False)

    conn = MagicMock()
    # First cursor() call returns the dict cursor; subsequent calls return write.
    cursors = [read_cursor, write_cursor]
    conn.cursor.side_effect = lambda *a, **kw: cursors.pop(0) if cursors else MagicMock()

    extractor = AttachmentTextExtractor(
        db_connection=conn,
        load_manager=MagicMock(),
        attachment_dir=attachment_dir or "/tmp/test_attachments",
    )
    return extractor, conn, read_cursor, write_cursor


# ===================================================================
# Layer 4 hits an existing fully-processed canonical
# ===================================================================
class TestLayer4Hit:

    def test_layer4_hit_remaps_records_dedup_and_deletes(self, tmp_path):
        """A canonical with intel exists → remap, dedup_map insert, delete row."""
        # Layout:
        #   current document_id=200, attachment_id=100, resource_guid='guid-cur'
        #   canonical attachment_id=99, resource_guid='guid-canon'
        text_hash = "a" * 64
        content_hash = "b" * 64

        # Set up a real on-disk file we can verify gets deleted.
        attach_dir = tmp_path / "attachments"
        sub_dir = attach_dir / "guid-cur"
        sub_dir.mkdir(parents=True)
        file_path_rel = "guid-cur/file.pdf"
        (attach_dir / file_path_rel).write_bytes(b"x")

        read_responses = [
            # 1. SELECT current document's sam_attachment + resource_guid + content_hash + file_path
            ("fetchone", {
                "sam_attachment_id": 100,
                "resource_guid": "guid-cur",
                "content_hash": content_hash,
                "file_path": file_path_rel,
            }),
            # 2. SELECT canonical (matching text_hash, intel exists)
            ("fetchone", {"attachment_id": 99}),
            # 3. SELECT canonical resource_guid
            ("fetchone", {"resource_guid": "guid-canon"}),
        ]
        write_responses = [
            # 4. SELECT opportunity_attachment rows for current
            ("fetchall", [("notice-A", "https://example.com/a")]),
            # 5. INSERT canonical opportunity_attachment (no fetch)
            ("fetchone", None),
            # 6. DELETE original opportunity_attachment
            ("fetchone", None),
            # 7. INSERT IGNORE attachment_dedup_map
            ("fetchone", None),
            # 8. DELETE attachment_document
            ("fetchone", None),
            # 9. UPDATE sam_attachment SET file_path = NULL
            ("fetchone", None),
        ]

        extractor, conn, read_cursor, write_cursor = _build_extractor(
            read_responses, write_responses, attachment_dir=str(attach_dir),
        )
        # Initialize per-run state as extract_text would.
        extractor._seen_text_hashes = {}
        import threading
        extractor._seen_lock = threading.Lock()
        extractor._layer4_dedup_count = 0
        extractor._in_batch_dedup_count = 0

        result = extractor._handle_text_hash_dedup(
            document_id=200, text_hash=text_hash,
        )

        assert result is True
        assert extractor._layer4_dedup_count == 1
        assert extractor._in_batch_dedup_count == 0

        # Verify the dedup_map insert happened with the expected columns.
        sql_blob = " | ".join(s for s, _ in write_cursor.executed)
        assert "INSERT IGNORE INTO attachment_dedup_map" in sql_blob
        assert "DELETE FROM attachment_document" in sql_blob
        assert "UPDATE sam_attachment SET file_path = NULL" in sql_blob
        assert "INSERT IGNORE INTO opportunity_attachment" in sql_blob
        assert "DELETE FROM opportunity_attachment" in sql_blob

        # Find the dedup_map insert and verify the params.
        for sql, params in write_cursor.executed:
            if "attachment_dedup_map" in sql:
                # (resource_guid, canonical_attachment_id, content_hash, text_hash)
                assert params[0] == "guid-cur"
                assert params[1] == 99
                assert params[2] == content_hash
                assert params[3] == text_hash
                break
        else:
            pytest.fail("attachment_dedup_map INSERT not executed")

        # Find the opportunity_attachment INSERT-then-DELETE pair.
        op_inserts = [(s, p) for s, p in write_cursor.executed
                      if "INSERT IGNORE INTO opportunity_attachment" in s]
        op_deletes = [(s, p) for s, p in write_cursor.executed
                      if "DELETE FROM opportunity_attachment" in s]
        assert len(op_inserts) == 1
        assert len(op_deletes) == 1
        assert op_inserts[0][1] == ("notice-A", 99, "https://example.com/a")
        assert op_deletes[0][1] == ("notice-A", 100)

        # Insert must come before delete.
        ins_idx = next(i for i, (s, _) in enumerate(write_cursor.executed)
                       if "INSERT IGNORE INTO opportunity_attachment" in s)
        del_idx = next(i for i, (s, _) in enumerate(write_cursor.executed)
                       if "DELETE FROM opportunity_attachment" in s)
        assert ins_idx < del_idx, "INSERT must precede DELETE to preserve reference"

        # Physical file should be gone.
        assert not (attach_dir / file_path_rel).exists()

        # Commit was called.
        conn.commit.assert_called()

        # In-batch tracker now points to the canonical.
        assert extractor._seen_text_hashes[text_hash] == 99


# ===================================================================
# Layer 4 misses (no canonical) → returns False, no writes
# ===================================================================
class TestLayer4Miss:

    def test_no_match_means_no_writes(self):
        """No canonical exists → nothing remapped, returns False."""
        text_hash = "c" * 64

        read_responses = [
            # 1. SELECT current
            ("fetchone", {
                "sam_attachment_id": 50,
                "resource_guid": "guid-only",
                "content_hash": "d" * 64,
                "file_path": "guid-only/f.pdf",
            }),
            # 2. SELECT canonical → no row
            ("fetchone", None),
        ]

        extractor, conn, read_cursor, write_cursor = _build_extractor(read_responses, [])
        extractor._seen_text_hashes = {}
        import threading
        extractor._seen_lock = threading.Lock()
        extractor._layer4_dedup_count = 0
        extractor._in_batch_dedup_count = 0

        result = extractor._handle_text_hash_dedup(document_id=300, text_hash=text_hash)

        assert result is False
        # No writes occurred (the write_cursor was never even instantiated by
        # the method — nothing in executed list).
        assert write_cursor.executed == []
        assert extractor._layer4_dedup_count == 0
        # The current sam_attachment_id is recorded as the in-batch canonical.
        assert extractor._seen_text_hashes[text_hash] == 50
        # No commit was called (no transactional writes).
        conn.commit.assert_not_called()


# ===================================================================
# Edge case: same text, different filename — sam_attachment.filename preserved
# ===================================================================
class TestFilenamePreserved:

    def test_filename_only_intel_unaffected_by_dedup(self, tmp_path):
        """Layer 4 dedup must not touch sam_attachment.filename.

        sam_attachment.filename is the only piece of identifying metadata
        that survives dedup (since extracted text and file_path are removed).
        Per the phase doc: filename-based intel runs on sam_attachment.filename
        independently, so it must be preserved on the deduped row.
        """
        text_hash = "e" * 64

        attach_dir = tmp_path / "attachments"
        attach_dir.mkdir()

        read_responses = [
            ("fetchone", {
                "sam_attachment_id": 100,
                "resource_guid": "guid-cur",
                "content_hash": "f" * 64,
                "file_path": None,  # already-missing file is fine
            }),
            ("fetchone", {"attachment_id": 99}),
            ("fetchone", {"resource_guid": "guid-canon"}),
        ]
        write_responses = [
            ("fetchall", []),  # no opportunity_attachment rows
            ("fetchone", None),  # dedup_map insert
            ("fetchone", None),  # delete attachment_document
            ("fetchone", None),  # set file_path = NULL
        ]

        extractor, conn, read_cursor, write_cursor = _build_extractor(
            read_responses, write_responses, attachment_dir=str(attach_dir),
        )
        extractor._seen_text_hashes = {}
        import threading
        extractor._seen_lock = threading.Lock()
        extractor._layer4_dedup_count = 0
        extractor._in_batch_dedup_count = 0

        result = extractor._handle_text_hash_dedup(
            document_id=200, text_hash=text_hash,
        )

        assert result is True
        # Confirm: only file_path is touched on sam_attachment, NOT filename.
        sa_writes = [(s, p) for s, p in write_cursor.executed
                     if "UPDATE sam_attachment" in s or "DELETE FROM sam_attachment" in s]
        assert len(sa_writes) == 1
        sql, _ = sa_writes[0]
        assert "file_path = NULL" in sql
        assert "filename" not in sql.lower(), \
            "Layer 4 dedup must NOT modify sam_attachment.filename"


# ===================================================================
# In-batch dedup: two documents with the same text_hash in one run
# ===================================================================
class TestInBatchDedup:

    def test_second_doc_dedups_to_first_in_batch(self, tmp_path):
        """Two new docs in the same batch share a text_hash, no DB canonical.

        First call records the document in _seen_text_hashes and returns False.
        Second call sees the in-batch entry, deduplicates against it, and
        increments the in-batch counter (not the layer4 counter, since the DB
        was not consulted for the canonical).
        """
        text_hash = "1" * 64
        content_hash_1 = "2" * 64
        content_hash_2 = "3" * 64

        attach_dir = tmp_path / "attachments"
        attach_dir.mkdir()

        # ---- First call: fresh document, no DB canonical ----
        first_reads = [
            ("fetchone", {
                "sam_attachment_id": 500,
                "resource_guid": "guid-1",
                "content_hash": content_hash_1,
                "file_path": None,
            }),
            ("fetchone", None),  # no DB canonical
        ]
        ext1, conn1, _, w1 = _build_extractor(
            first_reads, [], attachment_dir=str(attach_dir),
        )
        # Persist per-run state across the two simulated docs by using one extractor.
        ext1._seen_text_hashes = {}
        import threading
        ext1._seen_lock = threading.Lock()
        ext1._layer4_dedup_count = 0
        ext1._in_batch_dedup_count = 0

        result1 = ext1._handle_text_hash_dedup(document_id=600, text_hash=text_hash)
        assert result1 is False
        assert ext1._seen_text_hashes[text_hash] == 500
        assert w1.executed == []

        # ---- Second call on the same extractor: in-batch dedup hits ----
        # We swap in a fresh pair of cursors for the second call.
        second_read = ScriptedCursor([
            # 1. SELECT current
            ("fetchone", {
                "sam_attachment_id": 501,
                "resource_guid": "guid-2",
                "content_hash": content_hash_2,
                "file_path": None,
            }),
            # 2. SELECT canonical resource_guid (in-batch hit means we skip
            #    the DB canonical lookup, but we still resolve the canonical's
            #    resource_guid for logging).
            ("fetchone", {"resource_guid": "guid-1"}),
        ], dictionary=True)
        second_write = ScriptedCursor([
            ("fetchall", []),  # no opportunity_attachment rows
            ("fetchone", None),  # dedup_map insert
            ("fetchone", None),  # delete attachment_document
            ("fetchone", None),  # file_path = NULL
        ], dictionary=False)

        cursors = [second_read, second_write]
        ext1.db_connection.cursor.side_effect = (
            lambda *a, **kw: cursors.pop(0) if cursors else MagicMock()
        )

        result2 = ext1._handle_text_hash_dedup(document_id=601, text_hash=text_hash)
        assert result2 is True
        assert ext1._in_batch_dedup_count == 1
        assert ext1._layer4_dedup_count == 0

        # The dedup_map insert should reference the canonical from the in-batch
        # cache (sam_attachment_id 500), not 501.
        for sql, params in second_write.executed:
            if "attachment_dedup_map" in sql:
                assert params[1] == 500, "in-batch canonical must be sam_attachment 500"
                break
        else:
            pytest.fail("attachment_dedup_map INSERT not executed for in-batch dedup")


# ===================================================================
# Empty / null text_hash short-circuits
# ===================================================================
class TestTextHashEmpty:

    def test_empty_text_hash_returns_false(self):
        extractor, conn, read_cursor, write_cursor = _build_extractor([], [])
        assert extractor._handle_text_hash_dedup(document_id=1, text_hash="") is False
        assert extractor._handle_text_hash_dedup(document_id=1, text_hash=None) is False
        assert read_cursor.executed == []
