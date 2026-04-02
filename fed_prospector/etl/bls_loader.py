"""Load BLS Employment Cost Index and CPI data into bls_cost_index table.

Fetches ECI and CPI time series from the BLS public API and upserts
into the bls_cost_index table for rate escalation benchmarking.
"""

import logging
from datetime import datetime

from db.connection import get_connection
from etl.load_manager import LoadManager


logger = logging.getLogger("fed_prospector.etl.bls_loader")


class BLSLoader:
    """Load BLS cost index data into bls_cost_index table."""

    def __init__(self, load_manager=None):
        self.load_manager = load_manager or LoadManager()
        self.logger = logger

    def load(self, client, full=False):
        """Fetch BLS series data and upsert into bls_cost_index.

        Args:
            client: BLSClient instance.
            full: If True, fetch last 20 years. Otherwise fetch last 2 years.

        Returns:
            dict with load statistics.
        """
        from api_clients.bls_client import ALL_SERIES, SERIES_NAMES

        current_year = datetime.now().year

        # Determine year range
        if full:
            start_year = current_year - 20
            load_type = "FULL"
        else:
            # Check for prior loads to determine incremental vs full
            last_load = self.load_manager.get_last_load("BLS")
            if last_load is None:
                start_year = current_year - 20
                load_type = "FULL"
                self.logger.info("No prior BLS load found, performing full load")
            else:
                start_year = current_year - 2
                load_type = "INCREMENTAL"

        end_year = current_year

        load_id = self.load_manager.start_load(
            source_system="BLS",
            load_type=load_type,
            parameters={
                "start_year": start_year,
                "end_year": end_year,
                "series_count": len(ALL_SERIES),
            },
        )
        self.logger.info(
            "Starting BLS load (load_id=%d, type=%s, years=%d-%d)",
            load_id, load_type, start_year, end_year,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_errored": 0,
        }

        try:
            # BLS API allows max 20-year spans per request
            # and max 50 series per request. We have 4 series
            # so a single request per 20-year window suffices.
            chunk_size = 20
            for chunk_start in range(start_year, end_year + 1, chunk_size):
                chunk_end = min(chunk_start + chunk_size - 1, end_year)
                data = client.fetch_series(ALL_SERIES, chunk_start, chunk_end)

                results = data.get("Results", {})
                for series_data in results.get("series", []):
                    series_id = series_data.get("seriesID", "")
                    series_name = SERIES_NAMES.get(series_id, "")
                    observations = series_data.get("data", [])

                    self.logger.info(
                        "Processing series %s: %d observations",
                        series_id, len(observations),
                    )

                    batch = []
                    for obs in observations:
                        stats["records_read"] += 1
                        try:
                            row = {
                                "series_id": series_id,
                                "series_name": series_name,
                                "year": int(obs["year"]),
                                "period": obs["period"],
                                "value": float(obs["value"]),
                                "footnotes": self._parse_footnotes(obs.get("footnotes", [])),
                                "last_load_id": load_id,
                            }
                            batch.append(row)
                        except (ValueError, KeyError) as exc:
                            stats["records_errored"] += 1
                            self.logger.warning(
                                "Error parsing BLS observation: %s — %s", obs, exc,
                            )

                    if batch:
                        inserted, updated = self._upsert_batch(batch)
                        stats["records_inserted"] += inserted
                        stats["records_updated"] += updated

            self.load_manager.complete_load(
                load_id,
                records_read=stats["records_read"],
                records_inserted=stats["records_inserted"],
                records_updated=stats["records_updated"],
                records_errored=stats["records_errored"],
            )
            self.logger.info("BLS load complete (load_id=%d): %s", load_id, stats)
            return stats

        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            self.logger.exception("BLS load failed (load_id=%d)", load_id)
            raise

    def _upsert_batch(self, batch):
        """INSERT ... ON DUPLICATE KEY UPDATE for bls_cost_index rows.

        Args:
            batch: List of row dicts.

        Returns:
            Tuple of (inserted_count, updated_count).
        """
        if not batch:
            return 0, 0

        sql = (
            "INSERT INTO bls_cost_index "
            "(series_id, series_name, year, period, value, footnotes, last_load_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) AS new_row "
            "ON DUPLICATE KEY UPDATE "
            "series_name = new_row.series_name, "
            "value = new_row.value, "
            "footnotes = new_row.footnotes, "
            "last_load_id = new_row.last_load_id"
        )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            rows = []
            for row in batch:
                rows.append((
                    row["series_id"],
                    row["series_name"],
                    row["year"],
                    row["period"],
                    row["value"],
                    row["footnotes"],
                    row["last_load_id"],
                ))
            cursor.executemany(sql, rows)
            conn.commit()

            # MySQL: rowcount for ON DUPLICATE KEY UPDATE reports
            # 1 per insert, 2 per update, 0 for no change
            # So: affected = inserts*1 + updates*2
            #     inserts + updates = len(batch)
            # Solving: updates = affected - len(batch), inserts = len(batch) - updates
            affected = cursor.rowcount
            updated = max(0, affected - len(batch))
            inserted = len(batch) - updated
            return inserted, updated
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _parse_footnotes(footnotes_list):
        """Parse BLS footnotes array into a string.

        Args:
            footnotes_list: List of footnote dicts from BLS API.

        Returns:
            str or None.
        """
        if not footnotes_list:
            return None
        texts = []
        for fn in footnotes_list:
            text = fn.get("text", "")
            if text:
                texts.append(text)
        return "; ".join(texts)[:200] if texts else None
