"""On-demand data loading processor for Phase 43.

Polls the data_load_request table for PENDING requests and processes them
by fetching data from external APIs (USASpending, SAM.gov) and loading
into the local database.

Request types:
    USASPENDING_AWARD   - Fetch award + transactions from USASpending.gov
    FPDS_AWARD          - Fetch FPDS contract data from SAM.gov Awards API
    ATTACHMENT_ANALYSIS - Run Claude AI analysis on attachment documents
"""

import json
import logging
from datetime import datetime

from db.connection import get_connection
from etl.load_manager import LoadManager
from etl.usaspending_loader import USASpendingLoader
from etl.awards_loader import AwardsLoader
from api_clients.usaspending_client import USASpendingClient
from api_clients.sam_awards_client import SAMAwardsClient

logger = logging.getLogger("fed_prospector.etl.demand_loader")


class DemandLoader:
    """Processes on-demand data load requests from the data_load_request table.

    The C# API inserts rows with status='PENDING'. This class polls for
    those rows and processes them using the existing ETL loaders and
    API clients.
    """

    def __init__(self):
        self.usa_client = USASpendingClient()
        self.sam_client = SAMAwardsClient(api_key_number=2)
        self.usa_loader = USASpendingLoader()
        self.awards_loader = AwardsLoader()
        self.load_manager = LoadManager()

    def process_pending_requests(self) -> int:
        """Process up to 10 pending requests. Returns count processed."""
        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM data_load_request WHERE status = 'PENDING' "
                "ORDER BY requested_at LIMIT 10"
            )
            requests = cursor.fetchall()
            cursor.close()

            processed = 0
            for req in requests:
                try:
                    self._process_request(req)
                    processed += 1
                except Exception as e:
                    self._fail_request(req["request_id"], str(e))
                    logger.error("Request %d failed: %s", req["request_id"], e)

            return processed
        finally:
            conn.close()

    def _process_request(self, req):
        """Route request to appropriate handler."""
        request_type = req["request_type"]
        if request_type == "USASPENDING_AWARD":
            self._process_usaspending(req)
        elif request_type == "FPDS_AWARD":
            self._process_fpds(req)
        elif request_type == "ATTACHMENT_ANALYSIS":
            self._process_attachment_analysis(req)
        else:
            raise ValueError(f"Unknown request_type: {request_type}")

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _set_status(self, request_id, status, **kwargs):
        """Update request status with optional extra fields."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sets = ["status = %s"]
            params = [status]

            if "started_at" in kwargs:
                sets.append("started_at = %s")
                params.append(kwargs["started_at"])
            if "completed_at" in kwargs:
                sets.append("completed_at = %s")
                params.append(kwargs["completed_at"])
            if "load_id" in kwargs:
                sets.append("load_id = %s")
                params.append(kwargs["load_id"])
            if "error_message" in kwargs:
                sets.append("error_message = %s")
                params.append(str(kwargs["error_message"])[:5000])
            if "result_summary" in kwargs:
                sets.append("result_summary = %s")
                params.append(json.dumps(kwargs["result_summary"]))

            params.append(request_id)
            sql = f"UPDATE data_load_request SET {', '.join(sets)} WHERE request_id = %s"
            cursor.execute(sql, params)
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def _fail_request(self, request_id, error_message):
        """Mark request as FAILED."""
        self._set_status(
            request_id, "FAILED",
            completed_at=datetime.now(),
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # USASpending award processing
    # ------------------------------------------------------------------

    def _process_usaspending(self, req):
        """Fetch award from USASpending.gov and load into DB.

        Follows the same pattern as cli/spending.py burn-rate --load-if-missing:
        1. Search USASpending by keyword (PIID)
        2. Load matching awards via USASpendingLoader
        3. Load transactions for the top award
        4. Auto-queue an FPDS_AWARD request for the same PIID
        """
        request_id = req["request_id"]
        piid = req["lookup_key"]

        self._set_status(request_id, "PROCESSING", started_at=datetime.now())

        # Search USASpending by keyword (PIID)
        logger.info("Request %d: searching USASpending for PIID '%s'", request_id, piid)
        response = self.usa_client.search_awards(keyword=piid, limit=5)
        awards = response.get("results", [])

        if not awards:
            raise ValueError(f"No award found on USASpending for PIID '{piid}'")

        # Load awards into usaspending_award table
        load_id = self.load_manager.start_load(
            "USASPENDING_AWARD", "INCREMENTAL",
            parameters={"keyword": piid, "demand_request_id": request_id},
        )
        try:
            award_stats = self.usa_loader.load_awards(awards, load_id)
            self.load_manager.complete_load(
                load_id,
                records_read=award_stats["records_read"],
                records_inserted=award_stats["records_inserted"],
                records_updated=award_stats.get("records_updated", 0),
            )
        except Exception as e:
            self.load_manager.fail_load(load_id, str(e))
            raise

        # Get the top award's unique ID for transaction loading
        top = awards[0]
        award_id = (
            top.get("generated_unique_award_id")
            or top.get("generated_internal_id")
        )

        # Load transactions
        txn_stats = {"records_read": 0, "records_inserted": 0}
        if award_id:
            txn_load_id = self.load_manager.start_load(
                "USASPENDING_TXN", "INCREMENTAL",
                parameters={"award_id": award_id, "demand_request_id": request_id},
            )
            try:
                transactions = self.usa_client.get_all_transactions(award_id)
                txn_stats = self.usa_loader.load_transactions(award_id, transactions, txn_load_id)
                self.load_manager.complete_load(
                    txn_load_id,
                    records_read=txn_stats["records_read"],
                    records_inserted=txn_stats["records_inserted"],
                )
            except Exception as e:
                self.load_manager.fail_load(txn_load_id, str(e))
                logger.warning("Transaction load failed for %s: %s", award_id, e)

        # Mark request as completed
        summary = {
            "awards_loaded": award_stats["records_inserted"] + award_stats.get("records_updated", 0),
            "transactions_loaded": txn_stats["records_inserted"],
            "top_award_id": award_id,
            "top_recipient": top.get("Recipient Name"),
            "top_amount": top.get("Award Amount"),
        }
        self._set_status(
            request_id, "COMPLETED",
            completed_at=datetime.now(),
            load_id=load_id,
            result_summary=summary,
        )

        logger.info(
            "Request %d completed: %d awards, %d transactions for PIID '%s'",
            request_id, summary["awards_loaded"], summary["transactions_loaded"], piid,
        )

        # Auto-queue FPDS_AWARD request for the same PIID
        self._queue_fpds_request(piid, req.get("requested_by"))

    # ------------------------------------------------------------------
    # FPDS award processing
    # ------------------------------------------------------------------

    def _process_fpds(self, req):
        """Fetch FPDS award from SAM.gov and load into DB.

        Checks SAM.gov rate budget before making API calls. If over budget,
        leaves the request as PENDING for the next polling cycle.
        """
        request_id = req["request_id"]
        piid = req["lookup_key"]

        # Log remaining requests for visibility but don't block — let the
        # API itself return 429 if the limit is actually reached.
        remaining = self.sam_client._get_remaining_requests()
        if remaining <= 0:
            logger.info(
                "Request %d: SAM.gov rate counter exhausted (may reset soon), "
                "attempting API call for '%s' anyway",
                request_id, piid,
            )

        self._set_status(request_id, "PROCESSING", started_at=datetime.now())

        # Search SAM.gov by PIID
        logger.info("Request %d: searching SAM.gov Awards for PIID '%s'", request_id, piid)
        result = self.sam_client.search_awards(piid=piid, limit=100)
        awards_data = result.get("data") or result.get("awardSummary") or []

        if not awards_data:
            # Not necessarily an error -- the award may not be in FPDS yet
            summary = {"awards_loaded": 0, "message": f"No FPDS data found for PIID '{piid}'"}
            self._set_status(
                request_id, "COMPLETED",
                completed_at=datetime.now(),
                result_summary=summary,
            )
            logger.info("Request %d: no FPDS data found for PIID '%s'", request_id, piid)
            return

        # Load awards into fpds_contract table
        load_id = self.load_manager.start_load(
            "SAM_AWARDS", "INCREMENTAL",
            parameters={"piid": piid, "demand_request_id": request_id},
        )
        try:
            stats = self.awards_loader.load_awards(awards_data, load_id)
            self.load_manager.complete_load(
                load_id,
                records_read=stats["records_read"],
                records_inserted=stats["records_inserted"],
                records_updated=stats.get("records_updated", 0),
            )
        except Exception as e:
            self.load_manager.fail_load(load_id, str(e))
            raise

        summary = {
            "awards_loaded": stats["records_inserted"] + stats.get("records_updated", 0),
            "records_read": stats["records_read"],
        }
        self._set_status(
            request_id, "COMPLETED",
            completed_at=datetime.now(),
            load_id=load_id,
            result_summary=summary,
        )

        logger.info(
            "Request %d completed: %d FPDS records for PIID '%s'",
            request_id, summary["awards_loaded"], piid,
        )

    # ------------------------------------------------------------------
    # Attachment AI analysis
    # ------------------------------------------------------------------

    def _process_attachment_analysis(self, req):
        """Run AI analysis on attachments for a specific opportunity.

        Triggered by the UI "Enhance with AI" button via
        POST /opportunities/{noticeId}/analyze.
        """
        request_id = req["request_id"]
        notice_id = req["lookup_key"]

        self._set_status(request_id, "PROCESSING", started_at=datetime.now())

        logger.info("Request %d: running AI analysis for notice '%s'", request_id, notice_id)

        from etl.attachment_ai_analyzer import AttachmentAIAnalyzer

        analyzer = AttachmentAIAnalyzer(model="haiku")
        stats = analyzer.analyze_notice(notice_id)

        summary = {
            "processed": stats["processed"],
            "analyzed": stats["analyzed"],
            "skipped": stats["skipped"],
            "failed": stats["failed"],
        }

        self._set_status(
            request_id, "COMPLETED",
            completed_at=datetime.now(),
            result_summary=summary,
        )

        logger.info(
            "Request %d completed: analyzed %d documents for notice '%s'",
            request_id, summary["analyzed"], notice_id,
        )

    # ------------------------------------------------------------------
    # Auto-queue helper
    # ------------------------------------------------------------------

    def _queue_fpds_request(self, piid, requested_by):
        """Insert a new FPDS_AWARD request for the same PIID.

        Skips if an identical pending/processing request already exists.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Check for existing pending/processing request
            cursor.execute(
                "SELECT request_id FROM data_load_request "
                "WHERE request_type = 'FPDS_AWARD' AND lookup_key = %s "
                "AND status IN ('PENDING', 'PROCESSING') LIMIT 1",
                (piid,),
            )
            if cursor.fetchone():
                logger.debug("FPDS_AWARD request already queued for PIID '%s'", piid)
                return

            cursor.execute(
                "INSERT INTO data_load_request "
                "(request_type, lookup_key, lookup_key_type, status, requested_by) "
                "VALUES ('FPDS_AWARD', %s, 'PIID', 'PENDING', %s)",
                (piid, requested_by),
            )
            conn.commit()
            logger.info("Auto-queued FPDS_AWARD request for PIID '%s'", piid)
        finally:
            cursor.close()
            conn.close()
