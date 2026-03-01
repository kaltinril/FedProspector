"""System health check and data freshness monitoring.

Provides comprehensive health status including:
- Data freshness (staleness detection)
- API usage tracking
- API key expiration warnings
- Table statistics
- Recent error summary
"""

import logging
from datetime import datetime, timedelta, date

from db.connection import get_connection
from config import settings


logger = logging.getLogger("fed_prospector.health")


# Staleness thresholds (hours) - matches JOBS definitions
STALENESS_THRESHOLDS = {
    "SAM_OPPORTUNITY_KEY2": ("Opportunities", 6),
    "SAM_ENTITY": ("Entity Data", 48),
    "SAM_FEDHIER": ("Federal Hierarchy", 336),
    "SAM_AWARDS": ("Contract Awards", 336),
    "GSA_CALC": ("CALC+ Labor Rates", 1080),
    "USASPENDING": ("USASpending", 1080),
    "SAM_EXCLUSIONS": ("Exclusions", 336),
    "SAM_SUBAWARD": ("Subaward Data", 336),
}


class HealthCheck:
    """Perform system health checks and return structured results."""

    def check_all(self):
        """Run all health checks. Returns dict with sections."""
        return {
            "data_freshness": self.check_data_freshness(),
            "table_stats": self.get_table_stats(),
            "api_usage": self.get_api_usage_today(),
            "api_key_status": self.check_api_keys(),
            "recent_errors": self.get_recent_errors(),
            "alerts": self.get_alerts(),
        }

    def check_data_freshness(self):
        """Check each source's last successful load against threshold.

        Returns list of dicts with: source, label, last_load, hours_ago,
        threshold_hours, status ('OK', 'WARNING', 'STALE', 'NEVER').
        """
        results = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            for source_system, (label, threshold_hours) in STALENESS_THRESHOLDS.items():
                cursor.execute(
                    "SELECT started_at "
                    "FROM etl_load_log "
                    "WHERE source_system = %s AND status = 'SUCCESS' "
                    "ORDER BY started_at DESC LIMIT 1",
                    (source_system,),
                )
                row = cursor.fetchone()

                if row and row["started_at"]:
                    last_load = row["started_at"]
                    delta = datetime.now() - last_load
                    hours_ago = delta.total_seconds() / 3600

                    # WARNING at 80% of threshold, STALE at 100%
                    if hours_ago > threshold_hours:
                        status = "STALE"
                    elif hours_ago > threshold_hours * 0.8:
                        status = "WARNING"
                    else:
                        status = "OK"
                else:
                    last_load = None
                    hours_ago = None
                    status = "NEVER"

                results.append({
                    "source": source_system,
                    "label": label,
                    "last_load": last_load,
                    "hours_ago": hours_ago,
                    "threshold_hours": threshold_hours,
                    "status": status,
                })

            return results
        finally:
            cursor.close()
            conn.close()

    def get_table_stats(self):
        """Get row counts for key tables.

        Returns list of dicts with: table_name, row_count, category.
        """
        results = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT TABLE_NAME, TABLE_ROWS "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME",
                (settings.DB_NAME,),
            )
            for row in cursor.fetchall():
                name = row["TABLE_NAME"]
                rows = row["TABLE_ROWS"] or 0

                if name.startswith("ref_"):
                    category = "Reference"
                elif name.startswith("etl_"):
                    category = "ETL"
                elif name.startswith("stg_"):
                    category = "Staging"
                elif name in ("entity", "opportunity", "fpds_contract",
                              "federal_organization", "gsa_labor_rate",
                              "usaspending_award", "usaspending_transaction",
                              "sam_subaward"):
                    category = "Data"
                elif name in ("prospect", "prospect_note", "prospect_team_member",
                              "saved_search", "app_user"):
                    category = "Prospecting"
                else:
                    category = "Other"

                results.append({
                    "table_name": name,
                    "row_count": rows,
                    "category": category,
                })

            return results
        finally:
            cursor.close()
            conn.close()

    def get_api_usage_today(self):
        """Get today's API usage per source.

        Returns list of dicts with: source, used, limit, remaining, last_call.
        """
        results = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT source_system, requests_made, max_requests, last_request_at "
                "FROM etl_rate_limit "
                "WHERE request_date = CURDATE()"
            )
            for row in cursor.fetchall():
                used = row["requests_made"] or 0
                limit = row["max_requests"] or 0
                remaining = max(0, limit - used)
                results.append({
                    "source": row["source_system"],
                    "used": used,
                    "limit": limit,
                    "remaining": remaining,
                    "last_call": row["last_request_at"],
                })

            # If no rows, show known API sources with 0 usage
            if not results:
                known_sources = [
                    ("SAM_OPPORTUNITY_KEY1", settings.SAM_DAILY_LIMIT),
                    ("SAM_OPPORTUNITY_KEY2", settings.SAM_DAILY_LIMIT_2),
                ]
                for source, limit in known_sources:
                    results.append({
                        "source": source,
                        "used": 0,
                        "limit": limit,
                        "remaining": limit,
                        "last_call": None,
                    })

            return results
        finally:
            cursor.close()
            conn.close()

    def check_api_keys(self):
        """Check API key configuration and expiration.

        Returns list of dicts with: key_name, configured (bool),
        daily_limit, status.

        SAM.gov keys expire every 90 days. Check .env for SAM_API_KEY_CREATED
        date (user should set this when they renew their key).
        """
        results = []

        # Check SAM_API_KEY
        key1_configured = bool(
            settings.SAM_API_KEY and settings.SAM_API_KEY != "your_api_key_here"
        )
        results.append({
            "key_name": "SAM API Key 1",
            "configured": key1_configured,
            "daily_limit": settings.SAM_DAILY_LIMIT,
        })

        # Check SAM_API_KEY_2
        key2_configured = bool(settings.SAM_API_KEY_2)
        results.append({
            "key_name": "SAM API Key 2",
            "configured": key2_configured,
            "daily_limit": settings.SAM_DAILY_LIMIT_2,
        })

        return results

    def get_recent_errors(self, days=7):
        """Get summary of recent load errors.

        Returns list of dicts with: source_system, load_type, started_at,
        error_message (from failed etl_load_log entries).
        """
        results = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cursor.execute(
                "SELECT source_system, load_type, started_at, error_message "
                "FROM etl_load_log "
                "WHERE status = 'FAILED' AND started_at >= %s "
                "ORDER BY started_at DESC "
                "LIMIT 20",
                (cutoff,),
            )
            results = cursor.fetchall()
            return results
        finally:
            cursor.close()
            conn.close()

    def get_alerts(self):
        """Generate alert messages based on all checks.

        Returns list of dicts with: level ('OK', 'WARN', 'ERROR'), message.
        """
        alerts = []

        # Check data freshness
        freshness = self.check_data_freshness()
        for item in freshness:
            if item["status"] == "STALE":
                alerts.append({
                    "level": "ERROR",
                    "message": (
                        f"{item['label']} data is stale "
                        f"({item['hours_ago']:.0f}h since last load, "
                        f"threshold: {item['threshold_hours']}h)"
                    ),
                })
            elif item["status"] == "NEVER":
                alerts.append({
                    "level": "WARN",
                    "message": f"{item['label']} has never been loaded",
                })

        # Check API key configuration
        api_keys = self.check_api_keys()
        for key in api_keys:
            if not key["configured"]:
                alerts.append({
                    "level": "WARN",
                    "message": f"{key['key_name']} is not configured",
                })

        # Check recent failures
        errors = self.get_recent_errors(days=1)
        if errors:
            alerts.append({
                "level": "ERROR",
                "message": f"{len(errors)} load failure(s) in the last 24 hours",
            })

        # Check rate limit exhaustion
        api_usage = self.get_api_usage_today()
        for usage in api_usage:
            if usage["limit"] > 0 and usage["remaining"] == 0:
                alerts.append({
                    "level": "WARN",
                    "message": (
                        f"API rate limit exhausted for {usage['source']} "
                        f"({usage['used']}/{usage['limit']} calls used)"
                    ),
                })
            elif usage["limit"] > 0 and usage["remaining"] <= usage["limit"] * 0.1:
                alerts.append({
                    "level": "WARN",
                    "message": (
                        f"API rate limit nearly exhausted for {usage['source']} "
                        f"({usage['used']}/{usage['limit']} calls used, "
                        f"{usage['remaining']} remaining)"
                    ),
                })

        if not alerts:
            alerts.append({
                "level": "OK",
                "message": "All systems healthy",
            })

        return alerts
