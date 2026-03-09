"""Bulk CSV loader for USASpending.gov award data.

Loads fiscal-year bulk download ZIPs (containing CSV files) into the
usaspending_award table using LOAD DATA INFILE for performance.
"""

import csv
import glob
import hashlib
import logging
import os
import tempfile
import time
import zipfile

from db.connection import get_connection
from etl.etl_utils import escape_tsv_value, parse_date, parse_decimal
from etl.load_manager import LoadManager


# Column mapping: CSV column name -> usaspending_award table column
CSV_COLUMN_MAP = {
    "contract_award_unique_key": "generated_unique_award_id",
    "award_id_piid": "piid",
    "award_id_fain": "fain",
    "uri": "uri",
    "award_type": "award_type",
    "award_description": "award_description",
    "recipient_name": "recipient_name",
    "recipient_uei": "recipient_uei",
    "recipient_parent_name": "recipient_parent_name",
    "recipient_parent_uei": "recipient_parent_uei",
    "current_total_value_of_award": "base_and_all_options_value",
    "total_dollars_obligated": "total_obligation",
    "period_of_performance_start_date": "start_date",
    "period_of_performance_current_end_date": "end_date",
    "last_modified_date": "last_modified_date",
    "awarding_agency_name": "awarding_agency_name",
    "awarding_sub_agency_name": "awarding_sub_agency_name",
    "funding_agency_name": "funding_agency_name",
    "naics_code": "naics_code",
    "naics_description": "naics_description",
    "product_or_service_code": "psc_code",
    "type_of_set_aside": "type_of_set_aside",
    "type_of_set_aside_description": "type_of_set_aside_description",
    "primary_place_of_performance_state_code": "pop_state",
    "primary_place_of_performance_country_code": "pop_country",
    "primary_place_of_performance_zip_4": "pop_zip",
    "primary_place_of_performance_city_name": "pop_city",
    "solicitation_identifier": "solicitation_identifier",
}

# Date columns that need parse_date()
_DATE_COLUMNS = {"start_date", "end_date", "last_modified_date"}

# Money columns that need parse_decimal()
_MONEY_COLUMNS = {"total_obligation", "base_and_all_options_value"}

# Columns written to TSV / loaded into temp table (excludes first_loaded_at)
LOAD_COLUMNS = [
    "generated_unique_award_id", "piid", "fain", "uri", "award_type",
    "award_description", "recipient_name", "recipient_uei",
    "recipient_parent_name", "recipient_parent_uei",
    "total_obligation", "base_and_all_options_value",
    "start_date", "end_date", "last_modified_date",
    "awarding_agency_name", "awarding_sub_agency_name", "funding_agency_name",
    "naics_code", "naics_description", "psc_code",
    "type_of_set_aside", "type_of_set_aside_description",
    "pop_state", "pop_country", "pop_zip", "pop_city",
    "solicitation_identifier", "fiscal_year", "fpds_enriched_at",
    "record_hash", "last_load_id",
]

# Non-PK columns for the ON DUPLICATE KEY UPDATE clause
_UPDATE_COLUMNS = [c for c in LOAD_COLUMNS if c != "generated_unique_award_id"]

BATCH_SIZE = 50_000


class USASpendingBulkLoader:
    """Loads USASpending bulk CSV downloads into usaspending_award."""

    # Secondary indexes on usaspending_award (excludes PRIMARY KEY).
    # Used by --fast mode to drop indexes before bulk loading and recreate after.
    SECONDARY_INDEXES = [
        ("idx_usa_naics",
         "CREATE INDEX idx_usa_naics ON usaspending_award (naics_code)"),
        ("idx_usa_recipient",
         "CREATE INDEX idx_usa_recipient ON usaspending_award (recipient_uei)"),
        ("idx_usa_agency",
         "CREATE INDEX idx_usa_agency ON usaspending_award (awarding_agency_name(50))"),
        ("idx_usa_setaside",
         "CREATE INDEX idx_usa_setaside ON usaspending_award (type_of_set_aside)"),
        ("idx_usa_dates",
         "CREATE INDEX idx_usa_dates ON usaspending_award (start_date, end_date)"),
        ("idx_usa_modified",
         "CREATE INDEX idx_usa_modified ON usaspending_award (last_modified_date)"),
        ("idx_usa_solicitation",
         "CREATE INDEX idx_usa_solicitation ON usaspending_award (solicitation_identifier)"),
        ("idx_usa_piid",
         "CREATE INDEX idx_usa_piid ON usaspending_award (piid)"),
        ("idx_usa_fy",
         "CREATE INDEX idx_usa_fy ON usaspending_award (fiscal_year)"),
        ("idx_usa_enrich",
         "CREATE INDEX idx_usa_enrich ON usaspending_award (fpds_enriched_at)"),
    ]

    def __init__(self, fast_mode=False):
        self.logger = logging.getLogger("fed_prospector.etl.usaspending_bulk_loader")
        self.load_manager = LoadManager()
        self.fast_mode = fast_mode

    # ------------------------------------------------------------------
    # Pre-load checks
    # ------------------------------------------------------------------

    def _check_buffer_pool_size(self):
        """Check InnoDB buffer pool size and warn if below 1 GB.

        A small buffer pool causes PK lookups to spill to disk during
        large upsert loads, making batch times grow as the table fills.
        """
        ONE_GB = 1024 * 1024 * 1024
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW VARIABLES LIKE 'innodb_buffer_pool_size'")
            row = cursor.fetchone()
            if row is None:
                self.logger.debug("Could not read innodb_buffer_pool_size")
                return
            pool_bytes = int(row[1])
            pool_mb = pool_bytes / (1024 * 1024)
            if pool_bytes < ONE_GB:
                self.logger.warning(
                    "innodb_buffer_pool_size is %.0f MB (%.2f GB). "
                    "For bulk loads, 1 GB+ is recommended to keep PK lookups "
                    "in memory. Increase with: SET GLOBAL "
                    "innodb_buffer_pool_size = 1073741824;",
                    pool_mb, pool_bytes / ONE_GB,
                )
            else:
                self.logger.info(
                    "innodb_buffer_pool_size: %.0f MB (%.2f GB) — OK",
                    pool_mb, pool_bytes / ONE_GB,
                )
        except Exception as exc:
            self.logger.debug("Could not check buffer pool size: %s", exc)
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_fiscal_year(self, zip_path, fiscal_year, load_id):
        """Load all contract CSVs from a bulk download ZIP.

        Args:
            zip_path: Path to the downloaded ZIP file.
            fiscal_year: Federal fiscal year (e.g. 2025).
            load_id: ETL load log ID.

        Returns:
            dict with aggregate stats.
        """
        self.logger.info(
            "Loading FY%d from %s (load_id=%d)", fiscal_year, zip_path, load_id
        )

        # Check if this FY archive was already fully loaded
        archive_hash = self._compute_archive_hash(zip_path)
        if self._is_fy_already_loaded(fiscal_year, archive_hash):
            self.logger.info("FY%d: archive already fully loaded, skipping", fiscal_year)
            return {"records_read": 0, "records_inserted": 0, "records_errored": 0, "csv_files": 0, "skipped": True}

        aggregate = {
            "records_read": 0,
            "records_inserted": 0,
            "records_errored": 0,
            "csv_files": 0,
        }

        # Extract ZIP to temp directory
        extract_dir = tempfile.mkdtemp(prefix=f"usa_fy{fiscal_year}_")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            self.logger.info("Extracted ZIP to %s", extract_dir)

            # Find contract CSV files
            csv_files = glob.glob(
                os.path.join(extract_dir, "**", "*Contracts*.csv"), recursive=True
            )
            if not csv_files:
                # Fallback: try all CSVs
                csv_files = glob.glob(
                    os.path.join(extract_dir, "**", "*.csv"), recursive=True
                )

            self.logger.info("Found %d CSV files to process", len(csv_files))

            total_csvs = len(csv_files)
            fy_start_time = time.time()

            for csv_idx, csv_path in enumerate(csv_files, 1):
                csv_name = os.path.basename(csv_path)

                # Check for existing checkpoint (CSV-level skip)
                checkpoint = self._get_or_create_checkpoint(
                    load_id, fiscal_year, csv_name, archive_hash,
                )
                if checkpoint["status"] == "COMPLETE":
                    self.logger.info("Skipping %s (already loaded)", csv_name)
                    aggregate["csv_files"] += 1
                    aggregate["records_read"] += checkpoint["total_rows_loaded"]
                    aggregate["records_inserted"] += checkpoint["total_rows_loaded"]
                    continue

                self.logger.info(
                    "Processing %s (%d/%d)",
                    csv_name, csv_idx, total_csvs,
                )
                csv_start_time = time.time()
                stats = self._load_csv(
                    csv_path, fiscal_year, load_id,
                    csv_index=csv_idx, total_csvs=total_csvs,
                    checkpoint=checkpoint,
                )
                csv_elapsed = time.time() - csv_start_time

                aggregate["records_read"] += stats["records_read"]
                aggregate["records_inserted"] += stats["records_inserted"]
                aggregate["records_errored"] += stats["records_errored"]
                aggregate["csv_files"] += 1

                # Per-CSV timing summary
                rows = stats["records_read"]
                rows_per_sec = rows / csv_elapsed if csv_elapsed > 0 else 0
                self.logger.info(
                    'CSV "%s" complete: %s rows in %s (%s rows/sec)',
                    os.path.basename(csv_path),
                    f"{rows:,}",
                    self._format_duration(csv_elapsed),
                    f"{rows_per_sec:,.0f}",
                )

        finally:
            # Clean up extracted files
            import shutil
            shutil.rmtree(extract_dir, ignore_errors=True)

        # FY summary with timing
        fy_elapsed = time.time() - fy_start_time
        self.logger.info(
            "FY%d complete: %d CSVs, %s total rows in %s",
            fiscal_year,
            aggregate["csv_files"],
            f"{aggregate['records_read']:,}",
            self._format_duration(fy_elapsed),
        )
        self.logger.info(
            "FY%d details: %s upserted, %s errors",
            fiscal_year,
            f"{aggregate['records_inserted']:,}",
            f"{aggregate['records_errored']:,}",
        )
        return aggregate

    # ------------------------------------------------------------------
    # Index management (--fast mode)
    # ------------------------------------------------------------------

    def _check_and_rebuild_indexes(self):
        """Check for missing secondary indexes and rebuild them.

        Detects indexes left dropped by a previous crashed --fast load
        and recreates them before proceeding.

        Returns:
            int: Number of indexes that were rebuilt (0 if all present).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'usaspending_award' "
                "AND INDEX_NAME != 'PRIMARY'"
            )
            existing = {row[0] for row in cursor.fetchall()}
        except Exception as exc:
            self.logger.warning(
                "Could not check indexes on usaspending_award (table may not "
                "exist yet): %s", exc,
            )
            return 0
        finally:
            cursor.close()
            conn.close()

        missing = [
            (name, ddl) for name, ddl in self.SECONDARY_INDEXES
            if name not in existing
        ]

        if not missing:
            self.logger.debug(
                "All secondary indexes present on usaspending_award"
            )
            return 0

        self.logger.warning(
            "Detected %d missing secondary indexes on usaspending_award "
            "(likely from a previous crashed --fast load). Rebuilding...",
            len(missing),
        )

        total_start = time.monotonic()
        rebuilt = 0
        conn = get_connection()
        cursor = conn.cursor()
        try:
            for index_name, create_sql in missing:
                try:
                    t0 = time.monotonic()
                    cursor.execute(create_sql)
                    conn.commit()
                    elapsed = time.monotonic() - t0
                    self.logger.info(
                        "Rebuilt index %s in %.1fs", index_name, elapsed
                    )
                    rebuilt += 1
                except Exception as exc:
                    conn.rollback()
                    self.logger.warning(
                        "Failed to rebuild index %s: %s", index_name, exc
                    )
        finally:
            cursor.close()
            conn.close()

        total_elapsed = time.monotonic() - total_start
        self.logger.info(
            "Index rebuild complete: %d indexes rebuilt in %.1fs",
            rebuilt, total_elapsed,
        )
        return rebuilt

    def _drop_secondary_indexes(self):
        """Drop all secondary indexes on usaspending_award for faster bulk loading."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            for index_name, _ in self.SECONDARY_INDEXES:
                try:
                    cursor.execute(
                        f"DROP INDEX {index_name} ON usaspending_award"
                    )
                    conn.commit()
                    self.logger.info("Dropped index %s", index_name)
                except Exception:
                    conn.rollback()
                    self.logger.debug(
                        "Index %s does not exist, skipping drop", index_name
                    )
        finally:
            cursor.close()
            conn.close()

    def _recreate_secondary_indexes(self):
        """Recreate all secondary indexes on usaspending_award after bulk loading."""
        total_start = time.monotonic()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            for index_name, create_sql in self.SECONDARY_INDEXES:
                t0 = time.monotonic()
                cursor.execute(create_sql)
                conn.commit()
                elapsed = time.monotonic() - t0
                self.logger.info(
                    "Created index %s in %.1fs", index_name, elapsed
                )
        finally:
            cursor.close()
            conn.close()
        total_elapsed = time.monotonic() - total_start
        self.logger.info(
            "All %d secondary indexes rebuilt in %.1fs",
            len(self.SECONDARY_INDEXES), total_elapsed,
        )

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _load_csv(self, csv_path, fiscal_year, load_id,
                  csv_index=None, total_csvs=None, checkpoint=None):
        """Process one CSV file: normalize, write batched TSVs, LOAD DATA INFILE, upsert.

        Rows are written to TSV files in batches of BATCH_SIZE.  Each batch
        gets its own temp-table lifecycle (create -> load -> upsert -> commit
        -> drop) so InnoDB never has to handle a million-row upsert at once.

        Args:
            csv_path: Path to the CSV file.
            fiscal_year: Federal fiscal year.
            load_id: ETL load log ID.
            csv_index: 1-based index of this CSV within the FY (for progress).
            total_csvs: Total number of CSVs for this FY (for progress).
            checkpoint: Optional checkpoint dict for resume support.

        Returns:
            dict with stats.
        """
        import shutil

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_errored": 0,
        }

        tsv_dir = None
        logged_unmapped = False

        try:
            tsv_dir = tempfile.mkdtemp(prefix="usa_bulk_tsv_")
            batch_num = 0
            batch_rows = 0
            tsv_file = None
            tsv_paths = []

            csv_read_start = time.monotonic()

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)

                for row in reader:
                    stats["records_read"] += 1

                    if stats["records_read"] % 100_000 == 0:
                        self.logger.info(
                            "Reading CSV: %s rows processed...",
                            f"{stats['records_read']:,}",
                        )

                    # Log unmapped columns on first row
                    if not logged_unmapped and reader.fieldnames:
                        unmapped = [
                            c for c in reader.fieldnames
                            if c not in CSV_COLUMN_MAP
                        ]
                        if unmapped:
                            self.logger.debug(
                                "Unmapped CSV columns (%d): %s",
                                len(unmapped),
                                ", ".join(unmapped[:20]),
                            )
                        logged_unmapped = True

                    try:
                        normalized = self._normalize_csv_row(row, fiscal_year)
                        if normalized is None:
                            stats["records_errored"] += 1
                            continue
                        normalized["last_load_id"] = load_id

                        # Start new batch file when needed
                        if tsv_file is None or batch_rows >= BATCH_SIZE:
                            if tsv_file is not None:
                                tsv_file.close()
                            batch_num += 1
                            tsv_path = os.path.join(tsv_dir, f"batch_{batch_num}.tsv")
                            tsv_paths.append(tsv_path)
                            tsv_file = open(tsv_path, "w", encoding="utf-8", newline="")
                            batch_rows = 0

                        values = [
                            escape_tsv_value(normalized.get(col))
                            for col in LOAD_COLUMNS
                        ]
                        tsv_file.write("\t".join(values) + "\n")
                        batch_rows += 1

                    except Exception as exc:
                        stats["records_errored"] += 1
                        if stats["records_errored"] <= 10:
                            self.logger.warning(
                                "Error normalizing row #%d: %s",
                                stats["records_read"], exc,
                            )

            if tsv_file is not None:
                tsv_file.close()

            if stats["records_read"] == 0:
                self.logger.warning("CSV file was empty: %s", csv_path)
                return stats

            # Process each batch
            total_batches = len(tsv_paths)
            self.logger.info(
                "Processing %d rows in %d batches of %d",
                stats["records_read"] - stats["records_errored"],
                total_batches, BATCH_SIZE,
            )

            # Determine how many batches to skip for resume
            skip_batches = 0
            if checkpoint and checkpoint["completed_batches"] > 0:
                skip_batches = checkpoint["completed_batches"]
                self.logger.info(
                    "Resuming from batch %d (skipping %d completed batches)",
                    skip_batches + 1, skip_batches,
                )
                # Count previously loaded rows toward stats
                stats["records_inserted"] += checkpoint["total_rows_loaded"]

            conn = get_connection()
            cursor = conn.cursor()
            batch_wall_start = time.monotonic()
            try:
                for i, batch_tsv in enumerate(tsv_paths, 1):
                    # Skip already-completed batches (resume support)
                    if i <= skip_batches:
                        try:
                            os.unlink(batch_tsv)
                        except OSError:
                            pass
                        continue

                    t_start = time.monotonic()

                    self._create_temp_table(cursor)

                    mysql_path = batch_tsv.replace("\\", "/")
                    col_list = ", ".join(LOAD_COLUMNS)

                    sql = (
                        f"LOAD DATA INFILE '{mysql_path}' "
                        f"INTO TABLE tmp_usaspending_bulk "
                        f"FIELDS TERMINATED BY '\\t' "
                        f"LINES TERMINATED BY '\\n' "
                        f"({col_list})"
                    )
                    cursor.execute(sql)
                    loaded = cursor.rowcount

                    self._upsert_from_temp(cursor)
                    upserted = cursor.rowcount
                    conn.commit()

                    cursor.execute("DROP TEMPORARY TABLE IF EXISTS tmp_usaspending_bulk")

                    elapsed = time.monotonic() - t_start
                    stats["records_inserted"] += loaded

                    # Update checkpoint after each successful batch
                    if checkpoint:
                        self._update_checkpoint_batch(
                            checkpoint["checkpoint_id"], i,
                            stats["records_inserted"],
                        )

                    # Calculate ETA based on wall time and batches completed
                    batches_done = i - skip_batches
                    wall_elapsed = time.monotonic() - batch_wall_start
                    batches_remaining = total_batches - i
                    if batches_done > 0 and batches_remaining > 0:
                        avg_per_batch = wall_elapsed / batches_done
                        eta_seconds = avg_per_batch * batches_remaining
                        eta_min = int(eta_seconds) // 60
                        eta_sec = int(eta_seconds) % 60
                        eta_str = f" (ETA: ~{eta_min}m {eta_sec:02d}s remaining)"
                    else:
                        eta_str = ""

                    # Build overall FY progress prefix if we have CSV context
                    progress_str = ""
                    if (csv_index is not None and total_csvs is not None
                            and total_csvs > 0):
                        completed_csvs = csv_index - 1
                        overall_pct = (
                            (completed_csvs * total_batches + i)
                            / (total_csvs * total_batches)
                            * 100
                        )
                        progress_str = (
                            f" | CSV {csv_index}/{total_csvs}, "
                            f"overall: {overall_pct:.0f}%"
                        )

                    self.logger.info(
                        "Batch %d/%d: %d loaded, %d upserted in %.1fs%s%s",
                        i, total_batches, loaded, upserted, elapsed,
                        eta_str, progress_str,
                    )

                    # Free disk space immediately
                    try:
                        os.unlink(batch_tsv)
                    except OSError:
                        pass

                # All batches complete — mark checkpoint done
                if checkpoint:
                    self._complete_checkpoint(checkpoint["checkpoint_id"])

            except Exception:
                conn.rollback()
                if checkpoint:
                    self._fail_checkpoint(checkpoint["checkpoint_id"])
                raise
            finally:
                cursor.close()
                conn.close()

        finally:
            if tsv_dir and os.path.exists(tsv_dir):
                shutil.rmtree(tsv_dir, ignore_errors=True)

        return stats

    @staticmethod
    def _format_duration(seconds):
        """Format a duration in seconds as 'Xm Ys' or 'Xs'."""
        seconds = int(seconds)
        if seconds >= 60:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs:02d}s"
        return f"{seconds}s"

    def _normalize_csv_row(self, row, fiscal_year):
        """Map a CSV row to usaspending_award column values.

        Args:
            row: dict from csv.DictReader.
            fiscal_year: Federal fiscal year.

        Returns:
            dict keyed by table column names, or None if row should be skipped.
        """
        result = {}

        for csv_col, db_col in CSV_COLUMN_MAP.items():
            value = row.get(csv_col, "")
            if value == "":
                value = None

            # Apply type-specific parsing
            if db_col in _DATE_COLUMNS and value is not None:
                value = parse_date(value)
            elif db_col in _MONEY_COLUMNS and value is not None:
                value = parse_decimal(value)

            result[db_col] = value

        # Skip rows without a primary key
        if not result.get("generated_unique_award_id"):
            return None

        # Set bulk-load-specific fields
        result["fiscal_year"] = fiscal_year
        result["fpds_enriched_at"] = None
        result["record_hash"] = None

        return result

    def _create_temp_table(self, cursor):
        """Create a temporary table matching usaspending_award structure.

        Drops the primary key so LOAD DATA INFILE can load CSVs with
        multiple rows per generated_unique_award_id (contract modifications).
        """
        cursor.execute(
            "CREATE TEMPORARY TABLE IF NOT EXISTS tmp_usaspending_bulk "
            "LIKE usaspending_award"
        )
        cursor.execute("ALTER TABLE tmp_usaspending_bulk DROP PRIMARY KEY")

    def _upsert_from_temp(self, cursor):
        """Upsert rows from temp table into usaspending_award.

        Deduplicates the temp table first: for each generated_unique_award_id,
        keeps only the row with the latest last_modified_date.  This handles
        bulk CSVs that contain multiple rows per award (contract modifications).
        """
        col_list = ", ".join(LOAD_COLUMNS)
        prefixed_col_list = ", ".join(f"t.{c}" for c in LOAD_COLUMNS)
        update_parts = [
            f"{c} = VALUES({c})" for c in _UPDATE_COLUMNS
        ]
        update_parts.append("last_loaded_at = NOW()")

        sql = (
            f"INSERT INTO usaspending_award ({col_list}) "
            f"SELECT {prefixed_col_list} FROM ("
            f"  SELECT *, ROW_NUMBER() OVER ("
            f"    PARTITION BY generated_unique_award_id "
            f"    ORDER BY last_modified_date DESC"
            f"  ) AS rn FROM tmp_usaspending_bulk"
            f") t WHERE t.rn = 1 "
            f"ON DUPLICATE KEY UPDATE "
            + ", ".join(update_parts)
        )
        cursor.execute(sql)

    # ------------------------------------------------------------------
    # Checkpoint / resume methods
    # ------------------------------------------------------------------

    def _get_or_create_checkpoint(self, load_id, fiscal_year, csv_file_name,
                                  archive_hash=None):
        """Get an existing checkpoint or create a new one.

        Args:
            load_id: ETL load log ID.
            fiscal_year: Federal fiscal year.
            csv_file_name: Name of the CSV file being loaded.
            archive_hash: Optional hash string for FY dedup.

        Returns:
            dict with checkpoint_id, status, completed_batches,
            total_rows_loaded.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Check across ALL loads for this FY + CSV (not just current load_id)
            # so that re-running without --resume still skips completed CSVs
            cursor.execute(
                "SELECT checkpoint_id, status, completed_batches, "
                "total_rows_loaded "
                "FROM usaspending_load_checkpoint "
                "WHERE fiscal_year = %s AND csv_file_name = %s "
                "AND archive_hash = %s AND status = 'COMPLETE' "
                "ORDER BY checkpoint_id DESC LIMIT 1",
                (fiscal_year, csv_file_name, archive_hash),
            )
            row = cursor.fetchone()

            if row is not None:
                self.logger.info(
                    "Found COMPLETE checkpoint %d for %s from a previous load",
                    row["checkpoint_id"], csv_file_name,
                )
                return row

            # Check current load_id for in-progress resume
            cursor.execute(
                "SELECT checkpoint_id, status, completed_batches, "
                "total_rows_loaded "
                "FROM usaspending_load_checkpoint "
                "WHERE load_id = %s AND csv_file_name = %s",
                (load_id, csv_file_name),
            )
            row = cursor.fetchone()

            if row is not None:
                self.logger.info(
                    "Found existing checkpoint %d for %s (status=%s, "
                    "batches=%d)",
                    row["checkpoint_id"], csv_file_name, row["status"],
                    row["completed_batches"],
                )
                return row

            # Create new checkpoint
            cursor.execute(
                "INSERT INTO usaspending_load_checkpoint "
                "(load_id, fiscal_year, csv_file_name, status, archive_hash) "
                "VALUES (%s, %s, %s, 'IN_PROGRESS', %s)",
                (load_id, fiscal_year, csv_file_name, archive_hash),
            )
            conn.commit()
            checkpoint_id = cursor.lastrowid
            self.logger.info(
                "Created checkpoint %d for %s", checkpoint_id, csv_file_name,
            )
            return {
                "checkpoint_id": checkpoint_id,
                "status": "IN_PROGRESS",
                "completed_batches": 0,
                "total_rows_loaded": 0,
            }
        finally:
            cursor.close()
            conn.close()

    def _update_checkpoint_batch(self, checkpoint_id, completed_batches,
                                 rows_loaded):
        """Update batch progress for a checkpoint.

        Args:
            checkpoint_id: The checkpoint row ID.
            completed_batches: Number of batches completed so far.
            rows_loaded: Total rows loaded so far.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE usaspending_load_checkpoint "
                "SET completed_batches = %s, total_rows_loaded = %s "
                "WHERE checkpoint_id = %s",
                (completed_batches, rows_loaded, checkpoint_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def _complete_checkpoint(self, checkpoint_id):
        """Mark a checkpoint as COMPLETE.

        Args:
            checkpoint_id: The checkpoint row ID.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE usaspending_load_checkpoint "
                "SET status = 'COMPLETE', completed_at = NOW() "
                "WHERE checkpoint_id = %s",
                (checkpoint_id,),
            )
            conn.commit()
            self.logger.info("Checkpoint %d marked COMPLETE", checkpoint_id)
        finally:
            cursor.close()
            conn.close()

    def _fail_checkpoint(self, checkpoint_id):
        """Mark a checkpoint as FAILED.

        Args:
            checkpoint_id: The checkpoint row ID.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE usaspending_load_checkpoint "
                "SET status = 'FAILED' "
                "WHERE checkpoint_id = %s",
                (checkpoint_id,),
            )
            conn.commit()
            self.logger.warning("Checkpoint %d marked FAILED", checkpoint_id)
        finally:
            cursor.close()
            conn.close()

    def _compute_archive_hash(self, archive_path):
        """Compute a hash of the first 1MB of a file plus its size.

        Args:
            archive_path: Path to the archive file.

        Returns:
            String in format "{sha256_hex}:{file_size}".
        """
        hasher = hashlib.sha256()
        with open(archive_path, "rb") as f:
            data = f.read(1024 * 1024)  # First 1MB
            hasher.update(data)
        file_size = os.path.getsize(archive_path)
        return f"{hasher.hexdigest()}:{file_size}"

    def _is_fy_already_loaded(self, fiscal_year, archive_hash):
        """Check if a fiscal year archive has already been fully loaded.

        Looks for a load_id where every checkpoint row for that load has
        status='COMPLETE' and at least one row matches the given fiscal_year
        and archive_hash.

        Args:
            fiscal_year: Federal fiscal year.
            archive_hash: Hash string from _compute_archive_hash.

        Returns:
            True if the FY archive was already fully loaded, False otherwise.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT c1.load_id "
                "FROM usaspending_load_checkpoint c1 "
                "WHERE c1.fiscal_year = %s AND c1.archive_hash = %s "
                "  AND c1.status = 'COMPLETE' "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM usaspending_load_checkpoint c2 "
                "    WHERE c2.load_id = c1.load_id "
                "      AND c2.status != 'COMPLETE'"
                "  ) "
                "LIMIT 1",
                (fiscal_year, archive_hash),
            )
            row = cursor.fetchone()
            if row:
                self.logger.info(
                    "FY%d archive already fully loaded (load_id=%d)",
                    fiscal_year, row[0],
                )
                return True
            return False
        finally:
            cursor.close()
            conn.close()
