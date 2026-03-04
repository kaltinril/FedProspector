"""Orchestrates load operations and creates etl_load_log entries."""

import logging
from datetime import datetime

from db.connection import get_connection


class LoadManager:
    def __init__(self):
        self.logger = logging.getLogger("fed_prospector.etl.load_manager")

    def start_load(self, source_system, load_type, source_file=None, parameters=None):
        """Create a new etl_load_log entry with status RUNNING.

        Args:
            source_system: e.g. 'SAM_ENTITY', 'SAM_OPPORTUNITY', 'REFERENCE'
            load_type: 'FULL', 'INCREMENTAL', 'DAILY'
            source_file: Optional path to source file
            parameters: Optional JSON-serializable dict of parameters

        Returns:
            load_id (int)
        """
        import json
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO etl_load_log "
                "(source_system, load_type, status, started_at, source_file, parameters) "
                "VALUES (%s, %s, 'RUNNING', %s, %s, %s)",
                (
                    source_system,
                    load_type,
                    datetime.now(),
                    source_file,
                    json.dumps(parameters) if parameters else None,
                ),
            )
            conn.commit()
            load_id = cursor.lastrowid
            self.logger.info(
                "Started load %d: %s %s", load_id, source_system, load_type
            )
            return load_id
        finally:
            cursor.close()
            conn.close()

    def complete_load(self, load_id, records_read=0, records_inserted=0,
                      records_updated=0, records_unchanged=0, records_errored=0):
        """Mark a load as SUCCESS and record final counts."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE etl_load_log SET "
                "status = 'SUCCESS', completed_at = %s, "
                "records_read = %s, records_inserted = %s, "
                "records_updated = %s, records_unchanged = %s, records_errored = %s "
                "WHERE load_id = %s",
                (
                    datetime.now(),
                    records_read, records_inserted,
                    records_updated, records_unchanged, records_errored,
                    load_id,
                ),
            )
            conn.commit()
            self.logger.info(
                "Completed load %d: read=%d inserted=%d updated=%d unchanged=%d errors=%d",
                load_id, records_read, records_inserted,
                records_updated, records_unchanged, records_errored,
            )
        finally:
            cursor.close()
            conn.close()

    def save_load_progress(self, load_id, parameters,
                           records_read=0, records_inserted=0,
                           records_updated=0, records_unchanged=0,
                           records_errored=0):
        """Save incremental progress: update counts, parameters, and mark SUCCESS.

        Called after each page of a paginated load so that progress survives
        a killed process. The next run can read pages_fetched from parameters
        to resume.
        """
        import json
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE etl_load_log SET "
                "status = 'SUCCESS', completed_at = %s, "
                "records_read = %s, records_inserted = %s, "
                "records_updated = %s, records_unchanged = %s, records_errored = %s, "
                "parameters = %s "
                "WHERE load_id = %s",
                (
                    datetime.now(),
                    records_read, records_inserted,
                    records_updated, records_unchanged, records_errored,
                    json.dumps(parameters),
                    load_id,
                ),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def fail_load(self, load_id, error_message):
        """Mark a load as FAILED with an error message."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE etl_load_log SET "
                "status = 'FAILED', completed_at = %s, error_message = %s "
                "WHERE load_id = %s",
                (datetime.now(), str(error_message)[:5000], load_id),
            )
            conn.commit()
            self.logger.error("Load %d FAILED: %s", load_id, error_message)
        finally:
            cursor.close()
            conn.close()

    def log_record_error(self, load_id, record_identifier, error_type, error_message, raw_data=None):
        """Log an individual record-level error during a load."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO etl_load_error "
                "(load_id, record_identifier, error_type, error_message, raw_data) "
                "VALUES (%s, %s, %s, %s, %s)",
                (load_id, record_identifier, error_type, str(error_message)[:5000],
                 str(raw_data)[:10000] if raw_data else None),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def get_last_load(self, source_system, status="SUCCESS"):
        """Get the most recent successful load for a source system.

        Returns:
            dict with load info, or None if no loads found
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT * FROM etl_load_log "
                "WHERE source_system = %s AND status = %s "
                "ORDER BY started_at DESC LIMIT 1",
                (source_system, status),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
