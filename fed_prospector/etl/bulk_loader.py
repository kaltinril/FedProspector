"""Bulk loader using MySQL LOAD DATA INFILE for fast entity data loading.

Reads parsed entity data (from the DAT parser) and writes temp TSV files,
then uses LOAD DATA INFILE to load them into MySQL at maximum speed.
Designed for initial full loads of the SAM.gov monthly entity extract.
"""

import logging
import os
import shutil
import tempfile
import time

from db.connection import get_connection
from etl.load_manager import LoadManager
from utils.hashing import compute_record_hash

logger = logging.getLogger("fed_prospector.etl.bulk_loader")

# Fields used for entity record hash (must match entity_loader.py)
_ENTITY_HASH_FIELDS = [
    "uei_sam", "uei_duns", "cage_code", "dodaac",
    "registration_status", "purpose_of_registration",
    "initial_registration_date", "registration_expiration_date",
    "last_update_date", "activation_date",
    "legal_business_name", "dba_name",
    "entity_division", "entity_division_number",
    "dnb_open_data_flag", "entity_start_date",
    "fiscal_year_end_close", "entity_url",
    "entity_structure_code", "entity_type_code",
    "profit_structure_code", "organization_structure_code",
    "state_of_incorporation", "country_of_incorporation",
    "primary_naics",
    "credit_card_usage", "correspondence_flag",
    "debt_subject_to_offset", "exclusion_status_flag",
    "no_public_display_flag", "evs_source",
]

# ---------------------------------------------------------------------------
# Entity TSV column order (matches entity table, minus auto-managed timestamps)
# ---------------------------------------------------------------------------
_ENTITY_COLUMNS = [
    "uei_sam", "uei_duns", "cage_code", "dodaac",
    "registration_status", "purpose_of_registration",
    "initial_registration_date", "registration_expiration_date",
    "last_update_date", "activation_date",
    "legal_business_name", "dba_name",
    "entity_division", "entity_division_number",
    "dnb_open_data_flag", "entity_start_date",
    "fiscal_year_end_close", "entity_url",
    "entity_structure_code", "entity_type_code",
    "profit_structure_code", "organization_structure_code",
    "state_of_incorporation", "country_of_incorporation",
    "primary_naics",
    "credit_card_usage", "correspondence_flag",
    "debt_subject_to_offset", "exclusion_status_flag",
    "no_public_display_flag", "evs_source",
    "record_hash", "last_load_id",
]

# ---------------------------------------------------------------------------
# Child table column orders (skip auto-increment `id` column)
# ---------------------------------------------------------------------------
_CHILD_COLUMNS = {
    "entity_address": [
        "uei_sam", "address_type", "address_line_1", "address_line_2",
        "city", "state_or_province", "zip_code", "zip_code_plus4",
        "country_code", "congressional_district",
    ],
    "entity_naics": [
        "uei_sam", "naics_code", "is_primary",
        "sba_small_business", "naics_exception",
    ],
    "entity_psc": [
        "uei_sam", "psc_code",
    ],
    "entity_business_type": [
        "uei_sam", "business_type_code",
    ],
    "entity_sba_certification": [
        "uei_sam", "sba_type_code", "sba_type_desc",
        "certification_entry_date", "certification_exit_date",
    ],
    "entity_poc": [
        "uei_sam", "poc_type", "first_name", "middle_initial",
        "last_name", "title", "address_line_1", "address_line_2",
        "city", "state_or_province", "zip_code", "zip_code_plus4",
        "country_code",
    ],
    "entity_disaster_response": [
        "uei_sam", "state_code", "state_name",
        "county_code", "county_name", "msa_code", "msa_name",
    ],
}

# Order for truncating child tables (any order is fine with FK checks off)
_CHILD_TABLE_NAMES = [
    "entity_disaster_response",
    "entity_poc",
    "entity_sba_certification",
    "entity_business_type",
    "entity_psc",
    "entity_naics",
    "entity_address",
]


def _escape_tsv_value(value):
    """Escape a value for MySQL LOAD DATA INFILE TSV format.

    - None becomes the literal string ``\\N`` (MySQL NULL).
    - Backslashes are doubled.
    - Tab characters are escaped to ``\\t``.
    - Newline characters are escaped to ``\\n``.
    - Carriage returns are escaped to ``\\r``.

    Returns:
        Escaped string suitable for writing into a TSV file.
    """
    if value is None:
        return "\\N"
    s = str(value)
    # Backslash must be escaped first to avoid double-escaping
    s = s.replace("\\", "\\\\")
    s = s.replace("\t", "\\t")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return s


class BulkLoader:
    """Fast bulk loader for SAM.gov entity data using LOAD DATA INFILE."""

    PROGRESS_INTERVAL = 50_000

    def __init__(self, load_manager=None):
        self.load_manager = load_manager or LoadManager()
        self.logger = logger

    # =================================================================
    # Public entry point
    # =================================================================

    def bulk_load_entities(self, entity_iterator, source_file="", load_type="FULL"):
        """Load entities from an iterator using temp TSV files + LOAD DATA INFILE.

        Args:
            entity_iterator: Iterator yielding dicts from dat_parser.parse_dat_file().
                Each dict has keys: "entity", "addresses", "naics", "pscs",
                "business_types", "sba_certifications", "pocs", "disaster_response"
            source_file: Source file path for logging.
            load_type: "FULL" or "INCREMENTAL".

        Returns:
            dict with load statistics.
        """
        load_id = self.load_manager.start_load(
            source_system="SAM_ENTITY",
            load_type=load_type,
            source_file=str(source_file),
            parameters={"loader": "bulk", "method": "LOAD_DATA_INFILE"},
        )
        self.logger.info(
            "Starting %s bulk entity load from %s (load_id=%d)",
            load_type, source_file, load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
            "child_counts": {
                "entity_address": 0,
                "entity_naics": 0,
                "entity_psc": 0,
                "entity_business_type": 0,
                "entity_sba_certification": 0,
                "entity_poc": 0,
                "entity_disaster_response": 0,
            },
        }

        tmp_dir = None
        try:
            # ----------------------------------------------------------
            # Phase 1: Write temp TSV files
            # ----------------------------------------------------------
            tmp_dir = tempfile.mkdtemp(prefix="bulk_entity_")
            self.logger.info("Temp directory: %s", tmp_dir)

            tsv_paths = self._write_tsv_files(
                entity_iterator, tmp_dir, load_id, stats,
            )

            self.logger.info(
                "TSV write complete: %d entities, %s child rows",
                stats["records_read"],
                {k: v for k, v in stats["child_counts"].items() if v > 0},
            )

            # ----------------------------------------------------------
            # Phase 2: LOAD DATA INFILE into MySQL
            # ----------------------------------------------------------
            self._load_into_mysql(tsv_paths, load_type)

            # For a full initial load, inserted == read
            stats["records_inserted"] = stats["records_read"]

            self.load_manager.complete_load(
                load_id,
                records_read=stats["records_read"],
                records_inserted=stats["records_inserted"],
                records_updated=stats["records_updated"],
                records_unchanged=stats["records_unchanged"],
                records_errored=stats["records_errored"],
            )
            self.logger.info("Bulk load %d complete: %s", load_id, {
                k: v for k, v in stats.items() if k != "child_counts"
            })
            return stats

        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            self.logger.exception("Bulk load %d failed", load_id)
            raise
        finally:
            # Clean up temp files
            if tmp_dir and os.path.isdir(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir)
                    self.logger.debug("Cleaned up temp directory: %s", tmp_dir)
                except OSError:
                    self.logger.warning(
                        "Could not remove temp directory: %s", tmp_dir,
                        exc_info=True,
                    )

    # =================================================================
    # Phase 1: TSV file writing
    # =================================================================

    def _write_tsv_files(self, entity_iterator, tmp_dir, load_id, stats):
        """Write entity and child data to tab-separated temp files.

        Args:
            entity_iterator: Iterator yielding parsed entity dicts.
            tmp_dir: Path to temp directory for TSV files.
            load_id: Current load ID for the last_load_id column.
            stats: Mutable stats dict to update counts.

        Returns:
            dict mapping table_name -> absolute file path of the TSV file.
        """
        tsv_paths = {}
        file_handles = {}

        try:
            # Open file handles for entity and all child tables
            entity_path = os.path.join(tmp_dir, "entity.tsv")
            file_handles["entity"] = open(entity_path, "w", encoding="utf-8", newline="")
            tsv_paths["entity"] = entity_path

            for table_name in _CHILD_TABLE_NAMES:
                path = os.path.join(tmp_dir, f"{table_name}.tsv")
                file_handles[table_name] = open(path, "w", encoding="utf-8", newline="")
                tsv_paths[table_name] = path

            # Iterate over entities and write TSV rows
            for record in entity_iterator:
                stats["records_read"] += 1

                entity_data = record["entity"]

                # Fields not in DAT file: write as None
                entity_data.setdefault("uei_duns", None)
                entity_data.setdefault("entity_type_code", None)
                entity_data.setdefault("profit_structure_code", None)
                entity_data.setdefault("organization_structure_code", None)

                # Compute record hash
                record_hash = compute_record_hash(entity_data, _ENTITY_HASH_FIELDS)
                entity_data["record_hash"] = record_hash
                entity_data["last_load_id"] = load_id

                # Write entity row
                self._write_tsv_row(
                    file_handles["entity"], entity_data, _ENTITY_COLUMNS,
                )

                # Write child table rows
                self._write_child_rows(
                    file_handles, record, "entity_address", "addresses",
                    entity_data["uei_sam"], stats,
                )
                self._write_child_rows(
                    file_handles, record, "entity_naics", "naics",
                    entity_data["uei_sam"], stats,
                )
                self._write_child_rows(
                    file_handles, record, "entity_psc", "pscs",
                    entity_data["uei_sam"], stats,
                )
                self._write_child_rows(
                    file_handles, record, "entity_business_type", "business_types",
                    entity_data["uei_sam"], stats,
                )
                self._write_child_rows(
                    file_handles, record, "entity_sba_certification",
                    "sba_certifications", entity_data["uei_sam"], stats,
                )
                self._write_child_rows(
                    file_handles, record, "entity_poc", "pocs",
                    entity_data["uei_sam"], stats,
                )
                self._write_child_rows(
                    file_handles, record, "entity_disaster_response",
                    "disaster_response", entity_data["uei_sam"], stats,
                )

                # Progress logging
                if stats["records_read"] % self.PROGRESS_INTERVAL == 0:
                    self.logger.info(
                        "TSV write progress: %d entities processed",
                        stats["records_read"],
                    )

        finally:
            for fh in file_handles.values():
                fh.close()

        return tsv_paths

    def _write_child_rows(self, file_handles, record, table_name, record_key,
                          uei_sam, stats):
        """Write child table rows from the parsed record to the TSV file.

        Args:
            file_handles: Dict of table_name -> open file handle.
            record: Full parsed entity record dict from the DAT parser.
            table_name: Target child table name.
            record_key: Key in the record dict holding the child row list.
            uei_sam: Parent UEI to inject into each child row.
            stats: Mutable stats dict.
        """
        rows = record.get(record_key) or []
        columns = _CHILD_COLUMNS[table_name]
        fh = file_handles[table_name]

        for row in rows:
            row["uei_sam"] = uei_sam
            self._write_tsv_row(fh, row, columns)
            stats["child_counts"][table_name] += 1

    @staticmethod
    def _write_tsv_row(fh, data, columns):
        """Write a single TSV row to an open file handle.

        Args:
            fh: Open file handle for writing.
            data: Dict with field values.
            columns: Ordered list of column names to write.
        """
        values = [_escape_tsv_value(data.get(col)) for col in columns]
        fh.write("\t".join(values))
        fh.write("\n")

    # =================================================================
    # Phase 2: LOAD DATA INFILE
    # =================================================================

    def _load_into_mysql(self, tsv_paths, load_type):
        """Execute LOAD DATA INFILE for each TSV file.

        Args:
            tsv_paths: Dict of table_name -> absolute TSV file path.
            load_type: "FULL" or "INCREMENTAL".
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            t_start = time.monotonic()

            if load_type == "FULL":
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                # Truncate child tables first, then entity
                for table_name in _CHILD_TABLE_NAMES:
                    cursor.execute(f"TRUNCATE TABLE {table_name}")
                    self.logger.debug("Truncated %s", table_name)
                cursor.execute("TRUNCATE TABLE entity")
                self.logger.debug("Truncated entity")

            # Load entity table first (parent)
            self._execute_load_data(
                cursor, tsv_paths["entity"], "entity", _ENTITY_COLUMNS,
            )

            # Load child tables
            for table_name in _CHILD_TABLE_NAMES:
                if table_name in tsv_paths:
                    self._execute_load_data(
                        cursor, tsv_paths[table_name], table_name,
                        _CHILD_COLUMNS[table_name],
                    )

            conn.commit()

            elapsed = time.monotonic() - t_start
            self.logger.info(
                "LOAD DATA INFILE complete in %.1f seconds", elapsed,
            )

        except Exception:
            conn.rollback()
            raise
        finally:
            # Re-enable FK checks in finally so they are restored even if the
            # load crashes. FOREIGN_KEY_CHECKS is a session variable — if the
            # connection is recycled by the pool while still disabled, the next
            # caller would silently have FK checks off.
            if load_type == "FULL":
                try:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                    # No commit needed — SET is a session variable, not transactional
                except Exception as e:
                    self.logger.error("Failed to re-enable FK checks: %s", e)
            cursor.close()
            conn.close()

    def _execute_load_data(self, cursor, file_path, table_name, columns):
        """Execute a single LOAD DATA INFILE statement.

        Args:
            cursor: Active database cursor.
            file_path: Absolute path to the TSV file.
            table_name: Target MySQL table name.
            columns: Ordered list of column names matching the TSV columns.
        """
        # MySQL requires forward slashes in file paths, even on Windows
        mysql_path = file_path.replace("\\", "/")

        col_list = ", ".join(columns)

        # Entity table gets timestamp SET clauses; child tables do not
        if table_name == "entity":
            set_clause = "SET first_loaded_at = NOW(), last_loaded_at = NOW()"
        else:
            set_clause = ""

        # Use IGNORE for child tables to skip duplicate key violations
        # (e.g. entity with same NAICS code listed twice with different flags)
        ignore = "IGNORE " if table_name != "entity" else ""

        sql = (
            f"LOAD DATA INFILE '{mysql_path}' "
            f"{ignore}"
            f"INTO TABLE {table_name} "
            f"FIELDS TERMINATED BY '\\t' "
            f"LINES TERMINATED BY '\\n' "
            f"({col_list})"
        )
        if set_clause:
            sql += f" {set_clause}"

        self.logger.debug("Executing: %s", sql[:200])
        cursor.execute(sql)

        rows_loaded = cursor.rowcount
        self.logger.info(
            "Loaded %d rows into %s", rows_loaded, table_name,
        )
