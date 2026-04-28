"""One-time backfill to clean up existing duplicate attachment groups (Phase 124).

Resolves the ~622 content-hash and ~625 text-hash duplicate groups already in
the database. Processes one duplicate group at a time, each in its own
transaction. Resumable: if a group's non-canonical resource_guid already
exists in ``attachment_dedup_map``, that row is skipped.

Strict ordering per non-canonical row in a group:
  1. INSERT IGNORE canonical mapping into ``opportunity_attachment``
  2. DELETE non-canonical ``opportunity_attachment`` row
  3. INSERT into ``attachment_dedup_map`` (resource_guid -> canonical)
  4. DELETE orphaned ``document_intel_evidence`` rows (must precede summaries
     because evidence references intel_id from summary)
  5. DELETE orphaned ``document_intel_summary`` rows
  6. DELETE the non-canonical ``attachment_document`` row
  7. Delete the physical file and set ``sam_attachment.file_path = NULL``

Order of dedup methods: content_hash first, then text_hash. A content_hash
dedup naturally collapses some text_hash groups along the way.

Usage:
    from etl.attachment_dedup_backfill import AttachmentDedupBackfill
    backfill = AttachmentDedupBackfill()
    stats = backfill.run(dry_run=True)
"""

import logging
from pathlib import Path

from config.settings import ATTACHMENT_DIR as _DEFAULT_ATTACHMENT_DIR
from db.connection import get_connection

logger = logging.getLogger("fed_prospector.etl.attachment_dedup_backfill")


class AttachmentDedupBackfill:
    """Clean up pre-existing duplicate attachment groups (Phase 124, Task 10/11)."""

    def __init__(self, db_connection=None, attachment_dir=None):
        self.db_connection = db_connection
        self.attachment_dir = (
            Path(attachment_dir) if attachment_dir else _DEFAULT_ATTACHMENT_DIR
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self, dry_run=False):
        """Run the backfill (or dry-run preview) for both Layer 3 and Layer 4.

        Args:
            dry_run: If True, no DB writes or file deletions; only a report.

        Returns:
            dict with aggregate stats (groups, rows_remapped, rows_deleted,
            evidence_rows_deleted, summary_rows_deleted, files_deleted,
            bytes_freed, skipped_resumed, dry_run).
        """
        stats = self._new_stats(dry_run)

        conn = self.db_connection or get_connection()
        try:
            # Layer 3 first — content_hash dedup naturally collapses some
            # text_hash groups before Layer 4 runs.
            self._run_for_method(conn, "content_hash", stats, dry_run)
            self._run_for_method(conn, "text_hash", stats, dry_run)
        finally:
            if not self.db_connection:
                conn.close()

        self._log_summary(stats)

        if not dry_run and (stats["rows_remapped"] or stats["rows_deleted"]):
            logger.info(
                "REMINDER: Re-run `python main.py backfill opportunity-intel` "
                "to refresh opportunity_attachment_summary and per-opportunity "
                "rollups after the dedup remap."
            )

        return stats

    @staticmethod
    def _new_stats(dry_run):
        return {
            "dry_run": dry_run,
            "groups_processed": 0,
            "groups_skipped_empty": 0,
            "rows_remapped": 0,
            "rows_deleted": 0,
            "rows_skipped_resumed": 0,
            "evidence_rows_deleted": 0,
            "summary_rows_deleted": 0,
            "files_deleted": 0,
            "files_already_missing": 0,
            "bytes_freed": 0,
            "by_method": {
                "content_hash": {"groups": 0, "rows_deduped": 0},
                "text_hash": {"groups": 0, "rows_deduped": 0},
            },
        }

    # ------------------------------------------------------------------
    # Per-method orchestration
    # ------------------------------------------------------------------

    def _run_for_method(self, conn, method, stats, dry_run):
        """Process all duplicate groups for the given dedup_method."""
        groups = self._fetch_duplicate_groups(conn, method)
        logger.info(
            "Layer %s: found %d duplicate group(s) to process (dry_run=%s)",
            "3 (content_hash)" if method == "content_hash" else "4 (text_hash)",
            len(groups),
            dry_run,
        )

        for hash_value in groups:
            rows = self._fetch_group_rows(conn, method, hash_value)
            if len(rows) < 2:
                # Group already collapsed by a prior step (e.g. Layer 3 ran first
                # and removed rows that also shared a text_hash) or partial run.
                stats["groups_skipped_empty"] += 1
                logger.debug(
                    "Skipping %s group %s: only %d row(s) remain",
                    method, hash_value[:12] if hash_value else "<null>", len(rows),
                )
                continue

            canonical, non_canonicals = self._pick_canonical(rows)
            self._process_group(
                conn, method, hash_value, canonical, non_canonicals, stats, dry_run,
            )
            stats["groups_processed"] += 1
            stats["by_method"][method]["groups"] += 1

    def _fetch_duplicate_groups(self, conn, method):
        """Return list of hash values (content_hash or text_hash) with >1 rows."""
        cursor = conn.cursor()
        try:
            if method == "content_hash":
                cursor.execute(
                    """
                    SELECT sa.content_hash
                    FROM sam_attachment sa
                    JOIN attachment_document ad ON ad.attachment_id = sa.attachment_id
                    WHERE sa.content_hash IS NOT NULL
                    GROUP BY sa.content_hash
                    HAVING COUNT(*) > 1
                    """
                )
            else:  # text_hash
                cursor.execute(
                    """
                    SELECT ad.text_hash
                    FROM attachment_document ad
                    WHERE ad.text_hash IS NOT NULL
                    GROUP BY ad.text_hash
                    HAVING COUNT(*) > 1
                    """
                )
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def _fetch_group_rows(self, conn, method, hash_value):
        """Return rows for a duplicate group, with intel-completeness signals.

        Each row dict contains:
          attachment_id, document_id, resource_guid, file_path, file_size_bytes,
          content_hash, text_hash, evidence_count, summary_count,
          has_keyword (bool), has_ai (bool).
        """
        cursor = conn.cursor(dictionary=True)
        try:
            if method == "content_hash":
                where_clause = "sa.content_hash = %s"
            else:
                where_clause = "ad.text_hash = %s"

            cursor.execute(
                f"""
                SELECT
                    sa.attachment_id,
                    ad.document_id,
                    sa.resource_guid,
                    sa.file_path,
                    sa.file_size_bytes,
                    sa.content_hash,
                    ad.text_hash,
                    ad.keyword_analyzed_at,
                    ad.ai_analyzed_at,
                    (SELECT COUNT(*) FROM document_intel_evidence die
                     WHERE die.document_id = ad.document_id) AS evidence_count,
                    (SELECT COUNT(*) FROM document_intel_summary dis
                     WHERE dis.document_id = ad.document_id) AS summary_count,
                    (SELECT COUNT(*) FROM document_intel_summary dis
                     WHERE dis.document_id = ad.document_id
                       AND dis.extraction_method IN ('keyword','heuristic')) AS keyword_count,
                    (SELECT COUNT(*) FROM document_intel_summary dis
                     WHERE dis.document_id = ad.document_id
                       AND dis.extraction_method IN ('ai_haiku','ai_sonnet')) AS ai_count
                FROM sam_attachment sa
                JOIN attachment_document ad ON ad.attachment_id = sa.attachment_id
                WHERE {where_clause}
                ORDER BY sa.attachment_id
                """,
                (hash_value,),
            )
            rows = cursor.fetchall()
            for r in rows:
                r["has_keyword"] = bool(r.get("keyword_count")) or bool(r.get("keyword_analyzed_at"))
                r["has_ai"] = bool(r.get("ai_count")) or bool(r.get("ai_analyzed_at"))
            return rows
        finally:
            cursor.close()

    @staticmethod
    def _pick_canonical(rows):
        """Pick the row with the most complete intel as canonical.

        Ranking (higher is better):
          1. summary_count + evidence_count (intel completeness)
          2. has_ai (AI analysis present)
          3. has_keyword (keyword analysis present)
        Tie-break on lowest attachment_id (oldest row).

        Returns (canonical_row, [non_canonical_rows]).
        """
        def sort_key(r):
            return (
                -(int(r.get("summary_count") or 0) + int(r.get("evidence_count") or 0)),
                0 if r["has_ai"] else 1,
                0 if r["has_keyword"] else 1,
                int(r["attachment_id"]),
            )

        ordered = sorted(rows, key=sort_key)
        return ordered[0], ordered[1:]

    # ------------------------------------------------------------------
    # Per-group processing (one transaction)
    # ------------------------------------------------------------------

    def _process_group(self, conn, method, hash_value, canonical, non_canonicals,
                        stats, dry_run):
        """Process a single duplicate group atomically.

        For each non-canonical row: remap opportunity_attachment, write the
        dedup_map row, delete intel evidence/summaries, delete the document
        row, delete the file, NULL the file_path on sam_attachment.

        On any error, the transaction is rolled back. The next group can
        still be retried on a future run.
        """
        canonical_id = canonical["attachment_id"]
        canonical_doc_id = canonical["document_id"]
        method_label = "content_hash" if method == "content_hash" else "text_hash"

        logger.info(
            "Group %s=%s: canonical attachment_id=%d (doc_id=%s, "
            "summary=%d, evidence=%d, ai=%s, keyword=%s); %d non-canonical row(s)",
            method_label,
            (hash_value[:12] + "...") if hash_value else "<null>",
            canonical_id, canonical_doc_id,
            int(canonical.get("summary_count") or 0),
            int(canonical.get("evidence_count") or 0),
            canonical["has_ai"], canonical["has_keyword"],
            len(non_canonicals),
        )

        cursor = conn.cursor()
        try:
            for nc in non_canonicals:
                if self._is_already_deduped(cursor, nc["resource_guid"]):
                    stats["rows_skipped_resumed"] += 1
                    logger.debug(
                        "  Skipping resource_guid=%s (already in attachment_dedup_map)",
                        nc["resource_guid"],
                    )
                    continue

                self._dedup_one(
                    cursor, method, canonical, nc, stats, dry_run,
                )
                stats["by_method"][method]["rows_deduped"] += 1

            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        except Exception:
            conn.rollback()
            logger.exception(
                "Failed to process %s group hash=%s; rolled back, will retry on next run",
                method_label, (hash_value or "")[:16],
            )
            raise
        finally:
            cursor.close()

    def _is_already_deduped(self, cursor, resource_guid):
        """Return True if this resource_guid already has an entry in attachment_dedup_map."""
        cursor.execute(
            "SELECT 1 FROM attachment_dedup_map WHERE resource_guid = %s LIMIT 1",
            (resource_guid,),
        )
        return cursor.fetchone() is not None

    def _dedup_one(self, cursor, method, canonical, nc, stats, dry_run):
        """Apply the strict-ordered dedup steps for one non-canonical row."""
        canonical_id = canonical["attachment_id"]
        nc_id = nc["attachment_id"]
        nc_doc_id = nc["document_id"]
        nc_guid = nc["resource_guid"]

        logger.info(
            "  -> dedup attachment_id=%d (doc_id=%s, guid=%s) -> canonical %d",
            nc_id, nc_doc_id, nc_guid, canonical_id,
        )

        # (a) Look up opportunity_attachment rows referencing the non-canonical
        cursor.execute(
            "SELECT notice_id, url FROM opportunity_attachment WHERE attachment_id = %s",
            (nc_id,),
        )
        oa_rows = cursor.fetchall()

        # (b) INSERT IGNORE the canonical mapping (preserves notice -> canonical)
        # (c) DELETE the non-canonical opportunity_attachment row
        for notice_id, url in oa_rows:
            if not dry_run:
                cursor.execute(
                    "INSERT IGNORE INTO opportunity_attachment "
                    "(notice_id, attachment_id, url) VALUES (%s, %s, %s)",
                    (notice_id, canonical_id, url),
                )
                cursor.execute(
                    "DELETE FROM opportunity_attachment "
                    "WHERE notice_id = %s AND attachment_id = %s",
                    (notice_id, nc_id),
                )
            stats["rows_remapped"] += 1

        # (d) INSERT INTO attachment_dedup_map
        if not dry_run:
            cursor.execute(
                "INSERT INTO attachment_dedup_map "
                "(resource_guid, canonical_attachment_id, dedup_method, "
                " content_hash, text_hash) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    nc_guid, canonical_id, method,
                    nc.get("content_hash"), nc.get("text_hash"),
                ),
            )

        # (e) DELETE orphaned document_intel_evidence rows
        # MUST precede document_intel_summary deletion: evidence.intel_id
        # references summary's intel_id (logical FK, not enforced).
        if nc_doc_id is not None:
            if dry_run:
                cursor.execute(
                    "SELECT COUNT(*) FROM document_intel_evidence WHERE document_id = %s",
                    (nc_doc_id,),
                )
                evidence_count = cursor.fetchone()[0] or 0
            else:
                cursor.execute(
                    "DELETE FROM document_intel_evidence WHERE document_id = %s",
                    (nc_doc_id,),
                )
                evidence_count = cursor.rowcount or 0
            stats["evidence_rows_deleted"] += evidence_count

        # (f) DELETE orphaned document_intel_summary rows
        if nc_doc_id is not None:
            if dry_run:
                cursor.execute(
                    "SELECT COUNT(*) FROM document_intel_summary WHERE document_id = %s",
                    (nc_doc_id,),
                )
                summary_count = cursor.fetchone()[0] or 0
            else:
                cursor.execute(
                    "DELETE FROM document_intel_summary WHERE document_id = %s",
                    (nc_doc_id,),
                )
                summary_count = cursor.rowcount or 0
            stats["summary_rows_deleted"] += summary_count

        # (g) DELETE the non-canonical attachment_document row
        if nc_doc_id is not None:
            if not dry_run:
                cursor.execute(
                    "DELETE FROM attachment_document WHERE document_id = %s",
                    (nc_doc_id,),
                )
        stats["rows_deleted"] += 1

        # (h) Delete the physical file; NULL file_path on sam_attachment
        self._delete_file_and_clear_path(cursor, nc, stats, dry_run)

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def _delete_file_and_clear_path(self, cursor, nc, stats, dry_run):
        """Delete the non-canonical's file and clear file_path on sam_attachment.

        The sam_attachment row is intentionally NOT deleted — it remains as
        Layer 1's "I've seen this URL" record per phase doc.
        """
        file_path = nc.get("file_path")
        nc_id = nc["attachment_id"]

        if file_path:
            full_path = self.attachment_dir / file_path
            if full_path.is_file():
                try:
                    file_size = full_path.stat().st_size
                except OSError:
                    file_size = int(nc.get("file_size_bytes") or 0)
                stats["bytes_freed"] += file_size

                if not dry_run:
                    try:
                        full_path.unlink()
                        # Best-effort: remove empty parent dir
                        try:
                            parent = full_path.parent
                            if parent != self.attachment_dir and not any(parent.iterdir()):
                                parent.rmdir()
                        except OSError:
                            pass
                    except OSError as e:
                        logger.warning(
                            "Failed to delete file %s for attachment_id=%d: %s",
                            full_path, nc_id, e,
                        )
                stats["files_deleted"] += 1
            else:
                stats["files_already_missing"] += 1

        if not dry_run:
            cursor.execute(
                "UPDATE sam_attachment SET file_path = NULL WHERE attachment_id = %s",
                (nc_id,),
            )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @staticmethod
    def _log_summary(stats):
        prefix = "DRY RUN preview" if stats["dry_run"] else "Backfill complete"
        logger.info(
            "%s: %d group(s) processed, %d skipped (empty), "
            "%d rows remapped, %d rows deleted, %d resumed-skip; "
            "%d evidence rows, %d summary rows, %d files (%.1f MB), "
            "%d files already missing",
            prefix,
            stats["groups_processed"],
            stats["groups_skipped_empty"],
            stats["rows_remapped"],
            stats["rows_deleted"],
            stats["rows_skipped_resumed"],
            stats["evidence_rows_deleted"],
            stats["summary_rows_deleted"],
            stats["files_deleted"],
            stats["bytes_freed"] / (1024 * 1024),
            stats["files_already_missing"],
        )
