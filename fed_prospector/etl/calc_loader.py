"""Load GSA CALC+ labor rate data into gsa_labor_rate table.

Supports two loading paths:
1. API pagination: fetch rates via CalcPlusClient.get_all_rates() and batch-insert
2. CSV file: load a pre-downloaded CSV via LOAD DATA INFILE

Both paths use the same normalize/upsert logic. The full_refresh() method
truncates and reloads via the API (multi-query de-duplication to work around
the Elasticsearch 10K window limit). Simpler and faster than change
detection for this fully-refreshed dataset.
"""

import csv
import logging
import os
import tempfile
import time
from pathlib import Path

from db.connection import get_connection
from etl.etl_utils import escape_tsv_value, parse_date, parse_decimal
from etl.load_manager import LoadManager


logger = logging.getLogger("fed_prospector.etl.calc_loader")

# ---------------------------------------------------------------------------
# Column order for gsa_labor_rate (matches tables/04_federal.sql)
# Excludes: id (auto-increment), first_loaded_at (default)
# ---------------------------------------------------------------------------
_RATE_COLUMNS = [
    "labor_category", "education_level", "min_years_experience",
    "current_price", "next_year_price", "second_year_price",
    "schedule", "contractor_name", "sin", "business_size",
    "security_clearance", "worksite",
    "contract_start", "contract_end",
    "idv_piid", "category", "subcategory",
    "last_load_id",
]

# Mapping from API response field names to DB column names
_API_FIELD_MAP = {
    "labor_category": "labor_category",
    "education_level": "education_level",
    "min_years_experience": "min_years_experience",
    "current_price": "current_price",
    "next_year_price": "next_year_price",
    "second_year_price": "second_year_price",
    "schedule": "schedule",
    "vendor_name": "contractor_name",
    "sin": "sin",
    "business_size": "business_size",
    "security_clearance": "security_clearance",
    "worksite": "worksite",
    "contract_start": "contract_start",
    "contract_end": "contract_end",
    "idv_piid": "idv_piid",
    "category": "category",
    "subcategory": "subcategory",
}


class CalcLoader:
    """Load GSA CALC+ labor rate data into gsa_labor_rate table."""

    BATCH_SIZE = 1000  # Larger batch since records are simple

    def __init__(self, load_manager=None):
        self.load_manager = load_manager or LoadManager()
        self.logger = logger

    # =================================================================
    # Public entry points
    # =================================================================

    def load_from_api(self, rates_data, load_id):
        """Load list of rate dicts from API pagination.

        Uses INSERT with batch execution for efficient loading.
        No change detection -- rates are reloaded in full each time.

        Args:
            rates_data: Iterable of raw rate dicts from the CALC+ API.
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_errored
        """
        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_errored": 0,
        }

        conn = get_connection()
        cursor = conn.cursor()
        try:
            batch = []
            for raw in rates_data:
                stats["records_read"] += 1
                try:
                    normalized = self._normalize_rate(raw)
                    normalized["last_load_id"] = load_id
                    batch.append(normalized)
                except Exception as exc:
                    stats["records_errored"] += 1
                    self.logger.warning(
                        "Error normalizing rate record #%d: %s",
                        stats["records_read"], exc,
                    )
                    continue

                if len(batch) >= self.BATCH_SIZE:
                    inserted = self._insert_batch(cursor, batch)
                    stats["records_inserted"] += inserted
                    conn.commit()
                    batch = []

                    if stats["records_read"] % 5000 == 0:
                        self.logger.info(
                            "Progress: read=%d inserted=%d errors=%d",
                            stats["records_read"],
                            stats["records_inserted"],
                            stats["records_errored"],
                        )

            # Final partial batch
            if batch:
                inserted = self._insert_batch(cursor, batch)
                stats["records_inserted"] += inserted
                conn.commit()

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

        self.logger.info(
            "API load complete (load_id=%d): read=%d inserted=%d errors=%d",
            load_id, stats["records_read"],
            stats["records_inserted"], stats["records_errored"],
        )
        return stats

    def load_from_csv(self, csv_path, load_id):
        """Load from downloaded CSV file.

        Converts CSV to TSV and uses LOAD DATA INFILE for speed.
        Falls back to batch INSERT if LOAD DATA INFILE fails (e.g.,
        missing FILE privilege).

        Args:
            csv_path: Path to the CSV file (string or Path).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_errored
        """
        csv_path = Path(csv_path)
        self.logger.info("Loading CALC+ rates from CSV: %s", csv_path)

        # Try LOAD DATA INFILE first (fastest)
        try:
            return self._load_csv_via_infile(csv_path, load_id)
        except Exception as exc:
            self.logger.warning(
                "LOAD DATA INFILE failed (%s), falling back to batch INSERT",
                exc,
            )

        # Fallback: read CSV and insert via API path
        return self._load_csv_via_insert(csv_path, load_id)

    def full_refresh(self, client, load_manager=None, progress_callback=None):
        """Complete reload: truncate + fetch all rates via API + batch-insert.

        The CALC+ v3 API is Elasticsearch-backed with a 10K result window.
        CalcPlusClient.get_all_rates() works around this by issuing
        multiple queries with different sort orderings and de-duplicating
        by ES ``_id``.  Typically retrieves 100K-140K unique rates.

        Args:
            client: CalcPlusClient instance.
            load_manager: Optional LoadManager override.
            progress_callback: Optional callable(seen_count, label) for
                progress reporting.

        Returns:
            dict with load statistics.
        """
        lm = load_manager or self.load_manager

        load_id = lm.start_load(
            source_system="GSA_CALC",
            load_type="FULL",
            parameters={"method": "api_multi_sort"},
        )
        self.logger.info("Starting CALC+ full refresh (load_id=%d)", load_id)

        try:
            # Truncate and reload from API
            self._truncate_table()

            stats = self.load_from_api(
                client.get_all_rates(progress_callback=progress_callback),
                load_id,
            )

            lm.complete_load(
                load_id,
                records_read=stats["records_read"],
                records_inserted=stats["records_inserted"],
                records_errored=stats["records_errored"],
            )
            self.logger.info(
                "CALC+ full refresh complete (load_id=%d): %s",
                load_id, stats,
            )
            return stats

        except Exception as exc:
            lm.fail_load(load_id, str(exc))
            self.logger.exception("CALC+ full refresh failed (load_id=%d)", load_id)
            raise

    # =================================================================
    # Normalization
    # =================================================================

    def _normalize_rate(self, raw):
        """Map API response fields to DB columns.

        Args:
            raw: dict from CALC+ API response (single rate record).

        Returns:
            dict with keys matching gsa_labor_rate columns.
        """
        normalized = {}
        for api_field, db_col in _API_FIELD_MAP.items():
            normalized[db_col] = raw.get(api_field)

        # Parse numeric fields
        normalized["min_years_experience"] = self._parse_int(
            normalized.get("min_years_experience")
        )
        normalized["current_price"] = parse_decimal(
            normalized.get("current_price")
        )
        normalized["next_year_price"] = parse_decimal(
            normalized.get("next_year_price")
        )
        normalized["second_year_price"] = parse_decimal(
            normalized.get("second_year_price")
        )

        # Parse date fields
        normalized["contract_start"] = parse_date(
            normalized.get("contract_start")
        )
        normalized["contract_end"] = parse_date(
            normalized.get("contract_end")
        )

        # Coerce all string fields to str (API can return booleans for
        # fields like security_clearance: false/true).
        for field in ("labor_category", "education_level", "schedule",
                       "contractor_name", "sin", "business_size",
                       "security_clearance", "worksite",
                       "idv_piid", "category", "subcategory"):
            val = normalized.get(field)
            if val is not None and not isinstance(val, str):
                normalized[field] = str(val)

        # Truncate strings to fit column sizes
        if normalized.get("labor_category"):
            normalized["labor_category"] = normalized["labor_category"][:200]
        if normalized.get("education_level"):
            normalized["education_level"] = normalized["education_level"][:50]
        if normalized.get("schedule"):
            normalized["schedule"] = normalized["schedule"][:200]
        if normalized.get("contractor_name"):
            normalized["contractor_name"] = normalized["contractor_name"][:200]
        if normalized.get("sin"):
            # SIN values can be multi-line comma-separated lists (e.g.
            # "541611,541930,\n611430") -- collapse to single line.
            sin_val = normalized["sin"].replace("\n", ",").replace("\r", "")
            sin_val = ",".join(s.strip() for s in sin_val.split(",") if s.strip())
            normalized["sin"] = sin_val[:500]
        if normalized.get("business_size"):
            normalized["business_size"] = normalized["business_size"][:10]
        if normalized.get("security_clearance"):
            normalized["security_clearance"] = normalized["security_clearance"][:50]
        if normalized.get("worksite"):
            normalized["worksite"] = normalized["worksite"][:100]
        if normalized.get("idv_piid"):
            normalized["idv_piid"] = normalized["idv_piid"][:50]
        if normalized.get("category"):
            normalized["category"] = normalized["category"][:200]
        if normalized.get("subcategory"):
            normalized["subcategory"] = normalized["subcategory"][:500]

        return normalized

    # =================================================================
    # Database operations
    # =================================================================

    def _insert_batch(self, cursor, batch):
        """Batch INSERT into gsa_labor_rate.

        Args:
            cursor: Active DB cursor.
            batch: List of normalized rate dicts.

        Returns:
            int: Number of rows inserted.
        """
        if not batch:
            return 0

        placeholders = ", ".join(["%s"] * len(_RATE_COLUMNS))
        col_list = ", ".join(_RATE_COLUMNS)

        sql = (
            f"INSERT INTO gsa_labor_rate ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW())"
        )

        rows = []
        for rate in batch:
            values = tuple(rate.get(col) for col in _RATE_COLUMNS)
            rows.append(values)

        cursor.executemany(sql, rows)
        return len(rows)

    def _truncate_table(self):
        """TRUNCATE the gsa_labor_rate table for a full refresh."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE gsa_labor_rate")
            conn.commit()
            self.logger.info("Truncated gsa_labor_rate table")
        finally:
            cursor.close()
            conn.close()

    # =================================================================
    # CSV loading helpers
    # =================================================================

    def _load_csv_via_infile(self, csv_path, load_id):
        """Convert CSV to TSV and load via LOAD DATA INFILE.

        Args:
            csv_path: Path to the CSV file.
            load_id: Current load ID.

        Returns:
            dict with load stats.
        """
        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_errored": 0,
        }

        # Convert CSV -> TSV with normalized values
        tsv_path = None
        try:
            tsv_fd, tsv_path = tempfile.mkstemp(suffix=".tsv", prefix="calc_rates_")
            os.close(tsv_fd)

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                with open(tsv_path, "w", encoding="utf-8", newline="") as tsv_file:
                    for row in reader:
                        stats["records_read"] += 1
                        try:
                            normalized = self._normalize_rate(row)
                            normalized["last_load_id"] = load_id
                            values = [
                                escape_tsv_value(normalized.get(col))
                                for col in _RATE_COLUMNS
                            ]
                            tsv_file.write("\t".join(values) + "\n")
                        except Exception as exc:
                            stats["records_errored"] += 1
                            self.logger.warning(
                                "Error normalizing CSV row #%d: %s",
                                stats["records_read"], exc,
                            )

            # Execute LOAD DATA INFILE
            mysql_path = tsv_path.replace("\\", "/")
            col_list = ", ".join(_RATE_COLUMNS)

            sql = (
                f"LOAD DATA INFILE '{mysql_path}' "
                f"INTO TABLE gsa_labor_rate "
                f"FIELDS TERMINATED BY '\\t' "
                f"LINES TERMINATED BY '\\n' "
                f"({col_list}) "
                f"SET first_loaded_at = NOW(), last_loaded_at = NOW()"
            )

            conn = get_connection()
            cursor = conn.cursor()
            try:
                t_start = time.monotonic()
                cursor.execute(sql)
                conn.commit()
                elapsed = time.monotonic() - t_start

                stats["records_inserted"] = cursor.rowcount
                self.logger.info(
                    "LOAD DATA INFILE complete: %d rows in %.1f seconds",
                    stats["records_inserted"], elapsed,
                )
            finally:
                cursor.close()
                conn.close()

        finally:
            if tsv_path and os.path.exists(tsv_path):
                try:
                    os.unlink(tsv_path)
                except OSError:
                    pass

        return stats

    def _load_csv_via_insert(self, csv_path, load_id):
        """Fallback: read CSV and batch-insert rows.

        Args:
            csv_path: Path to the CSV file.
            load_id: Current load ID.

        Returns:
            dict with load stats.
        """
        self.logger.info("Loading CSV via batch INSERT (fallback)")

        def csv_rate_generator():
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row

        return self.load_from_api(csv_rate_generator(), load_id)

    # =================================================================
    # Parsing helpers
    # =================================================================

    @staticmethod
    def _parse_int(value):
        """Parse a value to int, or None."""
        if value is None:
            return None
        s = str(value).strip()
        if not s or s.lower() in ("none", "null", "n/a", ""):
            return None
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None
