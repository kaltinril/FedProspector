"""Bulk CSV loader for USASpending.gov award data.

Loads fiscal-year bulk download ZIPs (containing CSV files) into the
usaspending_award table using LOAD DATA INFILE for performance.
"""

import csv
import glob
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

    def __init__(self):
        self.logger = logging.getLogger("fed_prospector.etl.usaspending_bulk_loader")
        self.load_manager = LoadManager()

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

            for csv_path in csv_files:
                self.logger.info("Processing %s", os.path.basename(csv_path))
                stats = self._load_csv(csv_path, fiscal_year, load_id)
                aggregate["records_read"] += stats["records_read"]
                aggregate["records_inserted"] += stats["records_inserted"]
                aggregate["records_errored"] += stats["records_errored"]
                aggregate["csv_files"] += 1

        finally:
            # Clean up extracted files
            import shutil
            shutil.rmtree(extract_dir, ignore_errors=True)

        self.logger.info(
            "FY%d complete: %d files, %d read, %d upserted, %d errors",
            fiscal_year,
            aggregate["csv_files"],
            aggregate["records_read"],
            aggregate["records_inserted"],
            aggregate["records_errored"],
        )
        return aggregate

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _load_csv(self, csv_path, fiscal_year, load_id):
        """Process one CSV file: normalize, write batched TSVs, LOAD DATA INFILE, upsert.

        Rows are written to TSV files in batches of BATCH_SIZE.  Each batch
        gets its own temp-table lifecycle (create -> load -> upsert -> commit
        -> drop) so InnoDB never has to handle a million-row upsert at once.

        Args:
            csv_path: Path to the CSV file.
            fiscal_year: Federal fiscal year.
            load_id: ETL load log ID.

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

            conn = get_connection()
            cursor = conn.cursor()
            batch_wall_start = time.monotonic()
            try:
                for i, batch_tsv in enumerate(tsv_paths, 1):
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

                    # Calculate ETA based on wall time and batches completed
                    wall_elapsed = time.monotonic() - batch_wall_start
                    batches_remaining = total_batches - i
                    if i > 0 and batches_remaining > 0:
                        avg_per_batch = wall_elapsed / i
                        eta_seconds = avg_per_batch * batches_remaining
                        eta_min = int(eta_seconds) // 60
                        eta_sec = int(eta_seconds) % 60
                        eta_str = f" (ETA: ~{eta_min}m {eta_sec:02d}s remaining)"
                    else:
                        eta_str = ""

                    self.logger.info(
                        "Batch %d/%d: %d loaded, %d upserted in %.1fs%s",
                        i, total_batches, loaded, upserted, elapsed, eta_str,
                    )

                    # Free disk space immediately
                    try:
                        os.unlink(batch_tsv)
                    except OSError:
                        pass

            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
                conn.close()

        finally:
            if tsv_dir and os.path.exists(tsv_dir):
                shutil.rmtree(tsv_dir, ignore_errors=True)

        return stats

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
