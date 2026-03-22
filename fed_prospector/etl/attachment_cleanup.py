"""Post-analysis cleanup of attachment files from disk (Phase 110B).

Removes physical files for attachments that have completed the FULL
analysis pipeline — all 4 stages of the state machine:

    downloaded -> text extracted -> keyword intel -> AI analyzed -> [cleanup eligible]

Only files that reached the final stage (AI analysis) can be deleted.
Preserves all database records including extracted text and intel.

Usage:
    from etl.attachment_cleanup import AttachmentFileCleanup
    cleanup = AttachmentFileCleanup()
    stats = cleanup.cleanup_files(dry_run=True)
"""

import logging
import os
from pathlib import Path

from db.connection import get_connection

_DEFAULT_ATTACHMENT_DIR = Path(os.environ.get("ATTACHMENT_DIR", r"E:\fedprospector\attachments"))

logger = logging.getLogger("fed_prospector.etl.attachment_cleanup")


class AttachmentFileCleanup:
    """Removes attachment files that have completed full analysis."""

    def __init__(self, db_connection=None, attachment_dir=None):
        self.db_connection = db_connection
        self.attachment_dir = Path(attachment_dir) if attachment_dir else _DEFAULT_ATTACHMENT_DIR

    def cleanup_files(self, notice_id=None, batch_size=1000, dry_run=False):
        """Delete files for fully-analyzed attachments.

        Args:
            notice_id: If set, only clean up files for this notice.
            batch_size: Max files to process per run.
            dry_run: If True, report what would be deleted without deleting.

        Returns:
            dict with keys: eligible, deleted, already_missing, failed, bytes_reclaimed
        """
        stats = {
            "eligible": 0,
            "deleted": 0,
            "already_missing": 0,
            "failed": 0,
            "bytes_reclaimed": 0,
            "dry_run": dry_run,
        }

        rows = self._fetch_eligible(notice_id, batch_size)
        stats["eligible"] = len(rows)

        if not rows:
            logger.info("No fully-analyzed attachment files to clean up")
            return stats

        logger.info(
            "%s %d fully-analyzed attachment files",
            "Would delete" if dry_run else "Cleaning up",
            len(rows),
        )

        conn = self.db_connection or get_connection()
        try:
            for row in rows:
                try:
                    file_path = row["file_path"]
                    full_path = self.attachment_dir / file_path

                    if not full_path.is_file():
                        # File already gone — just clear file_path in DB
                        if not dry_run:
                            self._clear_file_path(conn, row["attachment_id"])
                        stats["already_missing"] += 1
                        continue

                    file_size = full_path.stat().st_size
                    stats["bytes_reclaimed"] += file_size

                    if dry_run:
                        logger.debug(
                            "Would delete: %s (%.1f KB)",
                            file_path, file_size / 1024,
                        )
                        stats["deleted"] += 1
                        continue

                    # Delete the file
                    full_path.unlink()
                    # Clear file_path in DB to indicate file removed
                    self._clear_file_path(conn, row["attachment_id"])
                    stats["deleted"] += 1

                    # Try to remove empty parent directory (notice_id folder)
                    try:
                        parent = full_path.parent
                        if parent != self.attachment_dir and not any(parent.iterdir()):
                            parent.rmdir()
                    except OSError:
                        pass  # Directory not empty or other issue — fine

                except Exception as e:
                    stats["failed"] += 1
                    logger.error(
                        "Failed to clean up attachment %s (%s): %s",
                        row["attachment_id"], row.get("file_path"), e,
                    )
        finally:
            if not self.db_connection:
                conn.close()

        logger.info(
            "Cleanup %s: %d files %s, %.1f MB %s, %d already missing, %d failed",
            "preview" if dry_run else "complete",
            stats["deleted"],
            "would be deleted" if dry_run else "deleted",
            stats["bytes_reclaimed"] / (1024 * 1024),
            "would be reclaimed" if dry_run else "reclaimed",
            stats["already_missing"],
            stats["failed"],
        )

        return stats

    def _fetch_eligible(self, notice_id, batch_size):
        """Fetch attachments eligible for cleanup.

        Eligible = all 4 pipeline stages complete:
          1. download_status = 'downloaded'
          2. extraction_status = 'extracted'
          3. Has keyword/heuristic intel record
          4. Has AI analysis record (ai_haiku or ai_sonnet)
        AND file_path is not NULL (file still on disk).
        """
        conn = self.db_connection or get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT oa.attachment_id, oa.file_path, oa.file_size_bytes
                FROM opportunity_attachment oa
                WHERE oa.download_status = 'downloaded'
                  AND oa.extraction_status = 'extracted'
                  AND oa.file_path IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM opportunity_attachment_intel oai
                      WHERE oai.attachment_id = oa.attachment_id
                        AND oai.extraction_method IN ('keyword', 'heuristic')
                  )
                  AND EXISTS (
                      SELECT 1 FROM opportunity_attachment_intel oai
                      WHERE oai.attachment_id = oa.attachment_id
                        AND oai.extraction_method IN ('ai_haiku', 'ai_sonnet')
                  )
            """
            params = []

            if notice_id:
                sql += " AND oa.notice_id = %s"
                params.append(notice_id)

            sql += " ORDER BY oa.attachment_id LIMIT %s"
            params.append(batch_size)

            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            if not self.db_connection:
                conn.close()

    def _clear_file_path(self, conn, attachment_id):
        """Set file_path to NULL to indicate the file has been removed."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE opportunity_attachment SET file_path = NULL WHERE attachment_id = %s",
                (attachment_id,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
