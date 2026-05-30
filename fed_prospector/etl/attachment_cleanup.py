"""Post-extraction cleanup of attachment files from disk (Phase 110B, Phase 130).

Removes physical files for attachments once everything we need from the raw
file has been safely captured in the database. A file is cleanup-eligible
once it has been:

    downloaded -> content-hashed -> file details captured -> text extracted
        -> [cleanup eligible]

Keyword and AI intel work from `extracted_text` in the DB, not the raw file,
so they are NOT required for cleanup. If the raw bytes are ever needed again,
re-download (Phase 131) is the recovery path. Preserves all database records
including extracted text, hashes, and intel.

Usage:
    from etl.attachment_cleanup import AttachmentFileCleanup
    cleanup = AttachmentFileCleanup()
    stats = cleanup.cleanup_files(dry_run=True)
"""

import logging
from pathlib import Path

from config.settings import ATTACHMENT_DIR as _DEFAULT_ATTACHMENT_DIR
from db.connection import get_connection

logger = logging.getLogger("fed_prospector.etl.attachment_cleanup")


class AttachmentFileCleanup:
    """Removes attachment files whose text and hashes are safely captured."""

    def __init__(self, db_connection=None, attachment_dir=None):
        self.db_connection = db_connection
        self.attachment_dir = Path(attachment_dir) if attachment_dir else _DEFAULT_ATTACHMENT_DIR

    def cleanup_files(self, notice_id=None, batch_size=1000, dry_run=False):
        """Delete files for fully-extracted attachments.

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
            logger.info("No fully-extracted attachment files to clean up")
            return stats

        logger.info(
            "%s %d fully-extracted attachment files",
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

                    # Try to remove empty parent directory (resource_guid folder)
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

        Eligible = everything we need from the raw file is captured in the DB:
          1. File downloaded: download_status = 'downloaded' AND file_path IS NOT NULL
          2. File hashed: content_hash IS NOT NULL
          3. File details captured: file_size_bytes IS NOT NULL
          4. Text extracted: extraction_status = 'extracted' AND text_hash IS NOT NULL

        Keyword/AI intel is NOT required — it reads extracted_text from the DB,
        not the raw file. Re-download (Phase 131) is the recovery path.
        """
        conn = self.db_connection or get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT sa.attachment_id, sa.file_path, sa.file_size_bytes
                FROM sam_attachment sa
                JOIN attachment_document ad ON ad.attachment_id = sa.attachment_id
                WHERE sa.download_status = 'downloaded'
                  AND sa.file_path IS NOT NULL
                  AND sa.content_hash IS NOT NULL
                  AND sa.file_size_bytes IS NOT NULL
                  AND ad.extraction_status = 'extracted'
                  AND ad.text_hash IS NOT NULL
            """
            params = []

            if notice_id:
                sql += (
                    " AND EXISTS ("
                    "   SELECT 1 FROM opportunity_attachment m"
                    "   WHERE m.attachment_id = sa.attachment_id AND m.notice_id = %s"
                    " )"
                )
                params.append(notice_id)

            sql += " ORDER BY sa.attachment_id LIMIT %s"
            params.append(batch_size)

            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            if not self.db_connection:
                conn.close()

    def _clear_file_path(self, conn, attachment_id):
        """Set file_path to NULL on sam_attachment to indicate the file has been removed."""
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sam_attachment SET file_path = NULL WHERE attachment_id = %s",
                (attachment_id,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
