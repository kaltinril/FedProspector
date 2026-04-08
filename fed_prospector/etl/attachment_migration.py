"""Attachment deduplication migration (Phase 110ZZZ).

Migrates the single-table opportunity_attachment model to a normalized
6-table model: sam_attachment, attachment_document, opportunity_attachment
(repurposed as map table), document_intel_summary, document_intel_evidence,
and opportunity_attachment_summary.

Usage:
    python main.py maintain migrate-dedup [--dry-run]
    python main.py maintain migrate-files
"""

import logging
import os
import shutil

from config.settings import ATTACHMENT_DIR
from db.connection import get_connection
from etl.etl_utils import extract_resource_guid

logger = logging.getLogger("fed_prospector.attachment_migration")


class AttachmentDeduplicationMigration:
    """Run the full attachment deduplication database migration."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.logger = logging.getLogger("fed_prospector.attachment_migration")
        self.dry_run_report = []

    def run(self) -> dict:
        """Run the full migration. Returns stats dict."""
        self.logger.info("Starting attachment deduplication migration (dry_run=%s)", self.dry_run)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            self._step1_add_resource_guid(cursor)
            if not self.dry_run:
                conn.commit()

            self._step2_populate_resource_guid(cursor)
            if not self.dry_run:
                conn.commit()

            self._step2b_validate_guids(cursor)

            self._step3_identify_canonical_rows(cursor)
            if not self.dry_run:
                conn.commit()

            self._step4_create_tables_and_migrate(cursor, conn)

            self._step5_drop_old_intel_create_new(cursor)
            if not self.dry_run:
                conn.commit()

            self._step6_swap_tables(cursor)
            if not self.dry_run:
                conn.commit()

            stats = self._step7_verify(cursor)

            self.logger.info("Migration complete. Stats: %s", stats)
            return stats
        except Exception:
            conn.rollback()
            self.logger.exception("Migration failed")
            raise
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Step 1: Add resource_guid column to existing table
    # ------------------------------------------------------------------

    def _step1_add_resource_guid(self, cursor):
        """Add resource_guid column to opportunity_attachment if not present."""
        self.logger.info("Step 1: Adding resource_guid column to opportunity_attachment")

        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'opportunity_attachment'
              AND COLUMN_NAME = 'resource_guid'
        """)
        if cursor.fetchone():
            self.logger.info("  resource_guid column already exists, skipping")
            return

        if self.dry_run:
            self.logger.info("  DRY RUN: Would add resource_guid CHAR(32) column")
            self.dry_run_report.append("Step 1: Would add resource_guid CHAR(32) column")
            return

        cursor.execute("""
            ALTER TABLE opportunity_attachment
                ADD COLUMN resource_guid CHAR(32) AFTER attachment_id
        """)
        self.logger.info("  Added resource_guid column")

    # ------------------------------------------------------------------
    # Step 2: Populate resource_guid from URLs
    # ------------------------------------------------------------------

    def _step2_populate_resource_guid(self, cursor):
        """Populate resource_guid from existing URL values."""
        self.logger.info("Step 2: Populating resource_guid from URLs")

        if self.dry_run:
            # resource_guid column may not exist yet (Step 1 was skipped in dry-run)
            # so just count rows with matching URL patterns
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM opportunity_attachment
                WHERE url LIKE '%%/resources/files/%%/download%%'
            """)
            row = cursor.fetchone()
            self.logger.info("  DRY RUN: Would populate resource_guid for %d rows", row["cnt"])
            self.dry_run_report.append(f"Step 2: Would populate resource_guid for {row['cnt']} rows")
            return

        cursor.execute("""
            UPDATE opportunity_attachment
            SET resource_guid = LOWER(SUBSTRING_INDEX(
                SUBSTRING_INDEX(url, '/resources/files/', -1), '/download', 1))
            WHERE url LIKE '%%/resources/files/%%/download%%'
              AND (resource_guid IS NULL OR resource_guid = '')
        """)
        self.logger.info("  Updated %d rows with resource_guid", cursor.rowcount)

    # ------------------------------------------------------------------
    # Step 2b: Validate no NULL resource_guids remain
    # ------------------------------------------------------------------

    def _step2b_validate_guids(self, cursor):
        """Validate that all rows have resource_guid populated."""
        self.logger.info("Step 2b: Validating resource_guid population")

        if self.dry_run:
            # In dry_run, resource_guid column may not exist, so check URL patterns
            cursor.execute("""
                SELECT COUNT(*) AS null_count FROM opportunity_attachment
                WHERE url NOT LIKE '%%/resources/files/%%/download%%'
            """)
            row = cursor.fetchone()
            if row["null_count"] > 0:
                self.logger.warning(
                    "  DRY RUN: %d rows have URLs that won't produce a resource_guid",
                    row["null_count"]
                )
                self.dry_run_report.append(f"  WARNING: {row['null_count']} rows have URLs that won't produce a resource_guid")
            else:
                self.logger.info("  DRY RUN: All URLs match the resource_guid pattern")
                self.dry_run_report.append("Step 2b: All URLs match the resource_guid pattern")
            return

        cursor.execute("""
            SELECT COUNT(*) AS null_count FROM opportunity_attachment
            WHERE resource_guid IS NULL OR resource_guid = ''
        """)
        row = cursor.fetchone()
        null_count = row["null_count"]

        if null_count > 0:
            # Show sample URLs that didn't match
            cursor.execute("""
                SELECT attachment_id, notice_id, url FROM opportunity_attachment
                WHERE resource_guid IS NULL OR resource_guid = ''
                LIMIT 10
            """)
            samples = cursor.fetchall()
            for s in samples:
                self.logger.warning(
                    "  NULL resource_guid: attachment_id=%s notice_id=%s url=%s",
                    s["attachment_id"], s["notice_id"], s["url"]
                )
            raise ValueError(
                f"{null_count} rows have NULL resource_guid. "
                "These have non-standard URLs that need manual review before migration can proceed."
            )

        self.logger.info("  All rows have resource_guid populated")

    # ------------------------------------------------------------------
    # Step 3: Identify canonical rows (one per resource_guid)
    # ------------------------------------------------------------------

    def _step3_identify_canonical_rows(self, cursor):
        """Create _migration_canonical table with best row per resource_guid."""
        self.logger.info("Step 3: Identifying canonical rows per resource_guid")

        if self.dry_run:
            # In dry_run, resource_guid column may not exist yet, so derive from URL
            cursor.execute("""
                SELECT COUNT(DISTINCT LOWER(SUBSTRING_INDEX(
                    SUBSTRING_INDEX(url, '/resources/files/', -1), '/download', 1))) AS guid_count,
                       COUNT(*) AS total_rows
                FROM opportunity_attachment
                WHERE url LIKE '%%/resources/files/%%/download%%'
            """)
            row = cursor.fetchone()
            self.logger.info(
                "  DRY RUN: Would select %d canonical rows from %d total",
                row["guid_count"], row["total_rows"]
            )
            self.dry_run_report.append(f"Step 3: Would select {row['guid_count']} canonical rows from {row['total_rows']} total")
            return

        # Drop if exists from a previous partial run
        cursor.execute("DROP TABLE IF EXISTS _migration_canonical")

        cursor.execute("""
            CREATE TABLE _migration_canonical AS
            SELECT resource_guid, attachment_id AS canonical_id
            FROM (
                SELECT oa.resource_guid, oa.attachment_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY oa.resource_guid
                           ORDER BY
                               CASE WHEN EXISTS (
                                   SELECT 1 FROM opportunity_attachment_intel ai
                                   WHERE ai.attachment_id = oa.attachment_id
                               ) THEN 0 ELSE 1 END,
                               FIELD(COALESCE(oa.extraction_status, 'pending'), 'extracted', 'failed', 'unsupported', 'pending'),
                               FIELD(COALESCE(oa.download_status, 'pending'), 'downloaded', 'failed', 'skipped', 'pending'),
                               CASE WHEN oa.skip_reason IS NOT NULL THEN 1 ELSE 0 END,
                               oa.created_at ASC
                       ) AS rn
                FROM opportunity_attachment oa
            ) ranked
            WHERE rn = 1
        """)

        # Add indexes for Step 4 joins
        cursor.execute("ALTER TABLE _migration_canonical ADD INDEX idx_guid (resource_guid)")
        cursor.execute("ALTER TABLE _migration_canonical ADD INDEX idx_canonical (canonical_id)")

        cursor.execute("SELECT COUNT(*) AS cnt FROM _migration_canonical")
        row = cursor.fetchone()
        self.logger.info("  Created _migration_canonical with %d canonical rows", row["cnt"])

    # ------------------------------------------------------------------
    # Step 4: Create new tables and migrate data
    # ------------------------------------------------------------------

    def _step4_create_tables_and_migrate(self, cursor, conn):
        """Create sam_attachment, attachment_document, opportunity_attachment_new and populate them."""
        self.logger.info("Step 4: Creating new tables and migrating data")

        if self.dry_run:
            self.logger.info("  DRY RUN: Would create sam_attachment, attachment_document, opportunity_attachment_new")
            self.logger.info("  DRY RUN: Would migrate canonical rows into sam_attachment and attachment_document")
            self.logger.info("  DRY RUN: Would create opportunity_attachment_new map rows for all notice_id/attachment_id pairs")
            self.dry_run_report.append("Step 4: Would create sam_attachment, attachment_document, opportunity_attachment_new and migrate data")
            return

        # 1. Create all tables first (DDL causes implicit commit in MySQL)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sam_attachment (
                attachment_id          INT AUTO_INCREMENT PRIMARY KEY,
                resource_guid          CHAR(32) NOT NULL,
                url                    VARCHAR(500) NOT NULL,
                filename               VARCHAR(500),
                file_size_bytes        BIGINT,
                file_path              VARCHAR(500),
                download_status        ENUM('pending','downloaded','failed','skipped') DEFAULT 'pending',
                content_hash           CHAR(64),
                downloaded_at          DATETIME,
                download_retry_count   INT NOT NULL DEFAULT 0,
                skip_reason            VARCHAR(100),
                last_load_id           INT,
                created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE INDEX idx_resource_guid (resource_guid),
                INDEX idx_status (download_status),
                INDEX idx_content_hash (content_hash),
                INDEX idx_url (url)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachment_document (
                document_id            INT AUTO_INCREMENT PRIMARY KEY,
                attachment_id          INT NOT NULL,
                filename               VARCHAR(500),
                content_type           VARCHAR(100),
                extracted_text         LONGTEXT,
                page_count             INT,
                is_scanned             TINYINT DEFAULT 0,
                ocr_quality            ENUM('good','fair','poor'),
                extraction_status      ENUM('pending','extracted','failed','unsupported') DEFAULT 'pending',
                text_hash              CHAR(64),
                extracted_at           DATETIME,
                extraction_retry_count INT DEFAULT 0,
                last_load_id           INT,
                created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_attachment (attachment_id),
                INDEX idx_status (extraction_status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_attachment_new (
                notice_id              VARCHAR(100) NOT NULL,
                attachment_id          INT NOT NULL,
                url                    VARCHAR(500) NOT NULL,
                last_load_id           INT,
                created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notice_id, attachment_id),
                INDEX idx_attachment (attachment_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 2. Idempotency: if tables have data from a previous partial run, truncate
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'sam_attachment'
        """)
        if cursor.fetchone()["cnt"]:
            cursor.execute("SELECT COUNT(*) AS cnt FROM sam_attachment")
            if cursor.fetchone()["cnt"] > 0:
                self.logger.warning("sam_attachment already has data - truncating for re-run")
                cursor.execute("TRUNCATE TABLE sam_attachment")
                cursor.execute("TRUNCATE TABLE attachment_document")
                cursor.execute("TRUNCATE TABLE opportunity_attachment_new")

        # 3. Wrap all INSERTs in a single transaction
        cursor.execute("START TRANSACTION")

        # Insert canonical rows into sam_attachment
        cursor.execute("""
            INSERT INTO sam_attachment (attachment_id, resource_guid, url, filename, file_size_bytes,
                file_path, download_status, content_hash, downloaded_at, download_retry_count,
                skip_reason, last_load_id, created_at)
            SELECT oa.attachment_id, oa.resource_guid, oa.url, oa.filename, oa.file_size_bytes,
                oa.file_path, oa.download_status, oa.content_hash, oa.downloaded_at,
                oa.download_retry_count, oa.skip_reason, oa.last_load_id, oa.created_at
            FROM opportunity_attachment oa
            JOIN _migration_canonical c ON oa.attachment_id = c.canonical_id
        """)
        sa_count = cursor.rowcount
        self.logger.info("  Inserted %d rows into sam_attachment", sa_count)

        # Insert 1:1 document rows
        cursor.execute("""
            INSERT INTO attachment_document (attachment_id, filename, content_type, extracted_text,
                page_count, is_scanned, ocr_quality, extraction_status, text_hash, extracted_at,
                extraction_retry_count, last_load_id, created_at)
            SELECT oa.attachment_id, oa.filename, oa.content_type, oa.extracted_text,
                oa.page_count, oa.is_scanned, oa.ocr_quality, oa.extraction_status,
                oa.text_hash, oa.extracted_at, oa.extraction_retry_count,
                oa.last_load_id, oa.created_at
            FROM opportunity_attachment oa
            JOIN _migration_canonical c ON oa.attachment_id = c.canonical_id
        """)
        doc_count = cursor.rowcount
        self.logger.info("  Inserted %d rows into attachment_document", doc_count)

        # Insert all (notice_id, canonical_id, url) mappings — IGNORE duplicates
        cursor.execute("""
            INSERT IGNORE INTO opportunity_attachment_new (notice_id, attachment_id, url, last_load_id, created_at)
            SELECT oa.notice_id, c.canonical_id, oa.url, oa.last_load_id, oa.created_at
            FROM opportunity_attachment oa
            JOIN _migration_canonical c ON oa.resource_guid = c.resource_guid
        """)
        map_count = cursor.rowcount
        self.logger.info("  Inserted %d rows into opportunity_attachment_new", map_count)

        conn.commit()
        self.logger.info("  Step 4 transaction committed")

        # Reset AUTO_INCREMENT after explicit ID inserts
        cursor.execute("SELECT COALESCE(MAX(attachment_id), 0) + 1 AS next_id FROM sam_attachment")
        next_id = cursor.fetchone()["next_id"]
        cursor.execute(f"ALTER TABLE sam_attachment AUTO_INCREMENT = {next_id}")
        self.logger.info("  Reset sam_attachment AUTO_INCREMENT to %d", next_id)

    # ------------------------------------------------------------------
    # Step 5: Drop old intel tables, create new (empty) intel tables
    # ------------------------------------------------------------------

    def _step5_drop_old_intel_create_new(self, cursor):
        """Drop old intel/source tables and create new intel tables."""
        self.logger.info("Step 5: Dropping old intel tables, creating new intel tables")

        if self.dry_run:
            cursor.execute("SELECT COUNT(*) AS cnt FROM opportunity_attachment_intel")
            intel_count = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) AS cnt FROM opportunity_intel_source")
            source_count = cursor.fetchone()["cnt"]
            self.logger.info(
                "  DRY RUN: Would drop opportunity_attachment_intel (%d rows) "
                "and opportunity_intel_source (%d rows)",
                intel_count, source_count
            )
            self.logger.info("  DRY RUN: Would create document_intel_summary, document_intel_evidence, opportunity_attachment_summary (empty)")
            self.dry_run_report.append("Step 5: Would drop old intel tables and create new empty ones")
            return

        # Drop old tables (order: sources reference intel)
        cursor.execute("DROP TABLE IF EXISTS opportunity_intel_source")
        cursor.execute("DROP TABLE IF EXISTS opportunity_attachment_intel")
        self.logger.info("  Dropped old intel tables")

        # Create new intel tables (empty)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_intel_summary (
                intel_id               INT AUTO_INCREMENT PRIMARY KEY,
                document_id            INT NOT NULL,
                extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
                source_text_hash       CHAR(64),
                clearance_required     CHAR(1),
                clearance_level        VARCHAR(50),
                clearance_scope        VARCHAR(50),
                clearance_details      TEXT,
                eval_method            VARCHAR(50),
                eval_details           TEXT,
                vehicle_type           VARCHAR(100),
                vehicle_details        TEXT,
                is_recompete           CHAR(1),
                incumbent_name         VARCHAR(200),
                recompete_details      TEXT,
                pricing_structure      VARCHAR(50),
                place_of_performance   VARCHAR(200),
                scope_summary          TEXT,
                period_of_performance  VARCHAR(200),
                labor_categories       JSON,
                key_requirements       JSON,
                overall_confidence     ENUM('high','medium','low') NOT NULL,
                confidence_details     JSON,
                citation_offsets       JSON,
                last_load_id           INT,
                extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE INDEX idx_upsert (document_id, extraction_method),
                INDEX idx_document (document_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_intel_evidence (
                evidence_id            INT AUTO_INCREMENT PRIMARY KEY,
                intel_id               INT NOT NULL,
                field_name             VARCHAR(50) NOT NULL,
                document_id            INT,
                source_filename        VARCHAR(500),
                page_number            INT,
                char_offset_start      INT,
                char_offset_end        INT,
                matched_text           VARCHAR(500),
                surrounding_context    TEXT,
                pattern_name           VARCHAR(100),
                extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
                confidence             ENUM('high','medium','low') NOT NULL,
                created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_intel (intel_id),
                INDEX idx_document (document_id),
                INDEX idx_field (field_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_attachment_summary (
                summary_id             INT AUTO_INCREMENT PRIMARY KEY,
                notice_id              VARCHAR(100) NOT NULL,
                extraction_method      ENUM('keyword','heuristic','ai_haiku','ai_sonnet') NOT NULL,
                clearance_required     CHAR(1),
                clearance_level        VARCHAR(50),
                clearance_scope        VARCHAR(50),
                clearance_details      TEXT,
                eval_method            VARCHAR(50),
                eval_details           TEXT,
                vehicle_type           VARCHAR(100),
                vehicle_details        TEXT,
                is_recompete           CHAR(1),
                incumbent_name         VARCHAR(200),
                recompete_details      TEXT,
                pricing_structure      VARCHAR(50),
                place_of_performance   VARCHAR(200),
                scope_summary          TEXT,
                period_of_performance  VARCHAR(200),
                labor_categories       JSON,
                key_requirements       JSON,
                overall_confidence     ENUM('high','medium','low') NOT NULL,
                confidence_details     JSON,
                citation_offsets       JSON,
                source_text_hash       CHAR(64),
                last_load_id           INT,
                extracted_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE INDEX idx_upsert (notice_id, extraction_method),
                INDEX idx_notice (notice_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        self.logger.info("  Created new intel tables (empty)")

    # ------------------------------------------------------------------
    # Step 6: Swap tables
    # ------------------------------------------------------------------

    def _step6_swap_tables(self, cursor):
        """Drop old opportunity_attachment and rename new table into place."""
        self.logger.info("Step 6: Swapping tables")

        if self.dry_run:
            self.logger.info("  DRY RUN: Would drop old opportunity_attachment and rename opportunity_attachment_new")
            self.dry_run_report.append("Step 6: Would swap opportunity_attachment tables")
            return

        # Verify row counts before dropping
        cursor.execute("SELECT COUNT(*) AS cnt FROM opportunity_attachment")
        old_count = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(*) AS cnt FROM opportunity_attachment_new")
        new_map_count = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(*) AS cnt FROM sam_attachment")
        sa_count = cursor.fetchone()["cnt"]

        self.logger.info(
            "  Pre-swap counts: old opportunity_attachment=%d, "
            "opportunity_attachment_new=%d, sam_attachment=%d",
            old_count, new_map_count, sa_count
        )

        if new_map_count == 0:
            raise ValueError("opportunity_attachment_new has 0 rows — aborting swap")
        if sa_count == 0:
            raise ValueError("sam_attachment has 0 rows — aborting swap")

        # The new map table should have >= old rows (every old row maps to a canonical)
        # It might have exactly old_count rows (one map row per original row)
        if new_map_count < old_count:
            self.logger.warning(
                "  WARNING: new map table (%d rows) has fewer rows than old table (%d rows). "
                "This can happen if duplicate (notice_id, resource_guid) pairs exist. Proceeding.",
                new_map_count, old_count
            )

        # Atomic swap: rename both in a single DDL statement
        cursor.execute("RENAME TABLE opportunity_attachment TO _old_opportunity_attachment, opportunity_attachment_new TO opportunity_attachment")
        self.logger.info("  Atomically swapped opportunity_attachment_new -> opportunity_attachment")

        # Drop the old table now that the swap succeeded
        cursor.execute("DROP TABLE IF EXISTS _old_opportunity_attachment")
        self.logger.info("  Dropped _old_opportunity_attachment")

        # Clean up migration helper
        cursor.execute("DROP TABLE IF EXISTS _migration_canonical")
        self.logger.info("  Dropped _migration_canonical")

    # ------------------------------------------------------------------
    # Step 7: Verify
    # ------------------------------------------------------------------

    def _step7_verify(self, cursor) -> dict:
        """Verify migration results. Returns stats dict."""
        self.logger.info("Step 7: Verifying migration")

        stats = {}

        if self.dry_run:
            self.logger.info("  DRY RUN: Skipping verification")
            return {"dry_run": True, "report": self.dry_run_report}

        for table in [
            "sam_attachment", "attachment_document", "opportunity_attachment",
            "document_intel_summary", "document_intel_evidence", "opportunity_attachment_summary",
        ]:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            count = cursor.fetchone()["cnt"]
            stats[table] = count
            self.logger.info("  %s: %d rows", table, count)

        # Verify old tables are gone
        for old_table in ["opportunity_attachment_intel", "opportunity_intel_source"]:
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """, (old_table,))
            exists = cursor.fetchone()["cnt"] > 0
            if exists:
                self.logger.warning("  WARNING: Old table %s still exists!", old_table)
                stats[f"{old_table}_still_exists"] = True
            else:
                self.logger.info("  Old table %s: dropped", old_table)

        # Verify _migration_canonical is gone
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '_migration_canonical'
        """)
        if cursor.fetchone()["cnt"] > 0:
            self.logger.warning("  WARNING: _migration_canonical still exists")

        return stats

    # ------------------------------------------------------------------
    # Step 8: Migrate files (separate, re-runnable)
    # ------------------------------------------------------------------

    def _step8_migrate_files(self):
        """Move files from {ATTACHMENT_DIR}/{notice_id}/ to {ATTACHMENT_DIR}/{resource_guid}/."""
        attachment_dir = str(ATTACHMENT_DIR)
        self.logger.info("Step 8: Migrating files (attachment_dir=%s, dry_run=%s)", attachment_dir, self.dry_run)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Get all sam_attachment rows that have files on disk
            cursor.execute("""
                SELECT sa.attachment_id, sa.resource_guid, sa.filename, sa.file_path
                FROM sam_attachment sa
                WHERE sa.file_path IS NOT NULL
                  AND sa.download_status = 'downloaded'
            """)
            rows = cursor.fetchall()
            self.logger.info("  Found %d attachments with file_path set", len(rows))

            stats = {"total": len(rows), "moved": 0, "skipped_already_moved": 0,
                     "skipped_missing": 0, "failed": 0, "updated_path": 0}

            for row in rows:
                resource_guid = row["resource_guid"]
                filename = row["filename"]
                old_relative_path = row["file_path"]
                attachment_id = row["attachment_id"]

                if not old_relative_path or not filename:
                    stats["skipped_missing"] += 1
                    continue

                # file_path stores relative paths (e.g. "notice_id/filename")
                # Build full paths for filesystem operations
                full_old_path = os.path.join(attachment_dir, old_relative_path)
                new_relative_path = os.path.join(resource_guid, filename)
                full_new_path = os.path.join(attachment_dir, new_relative_path)
                new_dir = os.path.join(attachment_dir, resource_guid)

                # Already in the new location?
                if os.path.normpath(old_relative_path) == os.path.normpath(new_relative_path):
                    stats["skipped_already_moved"] += 1
                    continue

                # Check if already moved (file exists at new path)
                if os.path.exists(full_new_path):
                    # Update DB path if needed
                    if not self.dry_run:
                        cursor.execute(
                            "UPDATE sam_attachment SET file_path = %s WHERE attachment_id = %s",
                            (new_relative_path, attachment_id)
                        )
                        conn.commit()
                        stats["updated_path"] += 1
                    stats["skipped_already_moved"] += 1
                    continue

                # Check if source exists
                if not os.path.exists(full_old_path):
                    self.logger.debug("  File not found at old path: %s", full_old_path)
                    stats["skipped_missing"] += 1
                    continue

                if self.dry_run:
                    self.logger.debug("  Would move: %s -> %s", full_old_path, full_new_path)
                    stats["moved"] += 1
                    continue

                try:
                    os.makedirs(new_dir, exist_ok=True)
                    shutil.move(full_old_path, full_new_path)

                    # Update DB with relative path
                    cursor.execute(
                        "UPDATE sam_attachment SET file_path = %s WHERE attachment_id = %s",
                        (new_relative_path, attachment_id)
                    )
                    conn.commit()
                    stats["moved"] += 1

                    # Try to remove old directory if empty
                    old_dir = os.path.dirname(full_old_path)
                    try:
                        os.rmdir(old_dir)
                    except OSError:
                        pass  # Not empty, that's fine

                except Exception as e:
                    self.logger.error("  Failed to move %s -> %s: %s", full_old_path, full_new_path, e)
                    stats["failed"] += 1

                # Log progress every 1000 files
                processed = stats["moved"] + stats["skipped_already_moved"] + stats["skipped_missing"] + stats["failed"]
                if processed % 1000 == 0 and processed > 0:
                    self.logger.info("  Progress: %d/%d files processed", processed, stats["total"])

            self.logger.info(
                "  File migration complete: moved=%d, already_moved=%d, "
                "missing=%d, failed=%d, path_updated=%d",
                stats["moved"], stats["skipped_already_moved"],
                stats["skipped_missing"], stats["failed"], stats["updated_path"]
            )
            return stats

        finally:
            cursor.close()
            conn.close()
