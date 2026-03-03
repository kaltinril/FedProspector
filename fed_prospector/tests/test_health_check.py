"""Tests for etl.health_check -- freshness, thresholds, alerts."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from etl.health_check import HealthCheck, STALENESS_THRESHOLDS


# ===================================================================
# Staleness threshold constants
# ===================================================================

class TestStalenessThresholds:

    def test_all_sources_have_label_and_hours(self):
        for source, (label, hours) in STALENESS_THRESHOLDS.items():
            assert isinstance(label, str) and len(label) > 0
            assert isinstance(hours, int) and hours > 0

    def test_known_sources_present(self):
        expected = {
            "SAM_OPPORTUNITY", "SAM_ENTITY", "SAM_FEDHIER",
            "SAM_AWARDS", "GSA_CALC", "USASPENDING",
            "SAM_EXCLUSIONS", "SAM_SUBAWARD",
        }
        assert expected == set(STALENESS_THRESHOLDS.keys())

    def test_opportunity_threshold_is_6_hours(self):
        _, hours = STALENESS_THRESHOLDS["SAM_OPPORTUNITY"]
        assert hours == 6

    def test_entity_threshold_is_48_hours(self):
        _, hours = STALENESS_THRESHOLDS["SAM_ENTITY"]
        assert hours == 48


# ===================================================================
# check_data_freshness tests
# ===================================================================

class TestCheckDataFreshness:

    def test_ok_status_when_fresh(self):
        """Data loaded 1 hour ago with 6-hour threshold should be OK."""
        with patch("etl.health_check.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            # All sources return "loaded 1 hour ago"
            one_hour_ago = datetime.now() - timedelta(hours=1)
            mock_cursor.fetchone.return_value = {"started_at": one_hour_ago}

            hc = HealthCheck()
            results = hc.check_data_freshness()

        for r in results:
            assert r["status"] == "OK"
            assert r["hours_ago"] is not None
            assert r["hours_ago"] < 2  # roughly 1 hour

    def test_stale_status_when_old(self):
        """Data loaded 100 hours ago with 6-hour threshold should be STALE."""
        with patch("etl.health_check.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            hundred_hours_ago = datetime.now() - timedelta(hours=100)
            mock_cursor.fetchone.return_value = {"started_at": hundred_hours_ago}

            hc = HealthCheck()
            results = hc.check_data_freshness()

        # At least the 6-hour threshold source should be STALE
        opportunity_result = [r for r in results if r["source"] == "SAM_OPPORTUNITY"][0]
        assert opportunity_result["status"] == "STALE"

    def test_warning_status_near_threshold(self):
        """Data at 85% of threshold should be WARNING."""
        with patch("etl.health_check.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            # 5.2 hours ago for 6-hour threshold = 86.7% -> WARNING
            hours_ago = 5.2
            some_time_ago = datetime.now() - timedelta(hours=hours_ago)
            mock_cursor.fetchone.return_value = {"started_at": some_time_ago}

            hc = HealthCheck()
            results = hc.check_data_freshness()

        opp_result = [r for r in results if r["source"] == "SAM_OPPORTUNITY"][0]
        assert opp_result["status"] == "WARNING"

    def test_never_status_when_no_loads(self):
        """No load history should return NEVER status."""
        with patch("etl.health_check.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_gc.return_value = mock_conn

            mock_cursor.fetchone.return_value = None

            hc = HealthCheck()
            results = hc.check_data_freshness()

        for r in results:
            assert r["status"] == "NEVER"
            assert r["last_load"] is None
            assert r["hours_ago"] is None


# ===================================================================
# check_api_keys tests
# ===================================================================

class TestCheckApiKeys:

    def test_configured_keys(self):
        hc = HealthCheck()
        results = hc.check_api_keys()

        assert len(results) == 2
        assert results[0]["key_name"] == "SAM API Key 1"
        assert results[1]["key_name"] == "SAM API Key 2"

    def test_key1_configured_when_set(self):
        """mock_settings sets SAM_API_KEY to 'test-api-key-1'."""
        hc = HealthCheck()
        results = hc.check_api_keys()
        assert results[0]["configured"] is True

    def test_daily_limits_reported(self):
        hc = HealthCheck()
        results = hc.check_api_keys()
        assert results[0]["daily_limit"] == 10
        assert results[1]["daily_limit"] == 1000


# ===================================================================
# get_alerts tests
# ===================================================================

class TestGetAlerts:

    @patch.object(HealthCheck, "check_data_freshness")
    @patch.object(HealthCheck, "check_api_keys")
    @patch.object(HealthCheck, "get_recent_errors")
    @patch.object(HealthCheck, "get_api_usage_today")
    def test_all_healthy_returns_ok(self, mock_usage, mock_errors, mock_keys, mock_freshness):
        mock_freshness.return_value = [
            {"source": "SAM_OPPORTUNITY", "label": "Opportunities",
             "status": "OK", "hours_ago": 1, "threshold_hours": 6},
        ]
        mock_keys.return_value = [
            {"key_name": "Key 1", "configured": True, "daily_limit": 10},
        ]
        mock_errors.return_value = []
        mock_usage.return_value = [
            {"source": "SAM", "used": 5, "limit": 10, "remaining": 5, "last_call": None},
        ]

        hc = HealthCheck()
        alerts = hc.get_alerts()

        assert len(alerts) == 1
        assert alerts[0]["level"] == "OK"

    @patch.object(HealthCheck, "check_data_freshness")
    @patch.object(HealthCheck, "check_api_keys")
    @patch.object(HealthCheck, "get_recent_errors")
    @patch.object(HealthCheck, "get_api_usage_today")
    def test_stale_data_generates_error_alert(self, mock_usage, mock_errors, mock_keys, mock_freshness):
        mock_freshness.return_value = [
            {"source": "SAM_OPPORTUNITY", "label": "Opportunities",
             "status": "STALE", "hours_ago": 100, "threshold_hours": 6},
        ]
        mock_keys.return_value = []
        mock_errors.return_value = []
        mock_usage.return_value = []

        hc = HealthCheck()
        alerts = hc.get_alerts()

        error_alerts = [a for a in alerts if a["level"] == "ERROR"]
        assert len(error_alerts) >= 1
        assert "stale" in error_alerts[0]["message"].lower()

    @patch.object(HealthCheck, "check_data_freshness")
    @patch.object(HealthCheck, "check_api_keys")
    @patch.object(HealthCheck, "get_recent_errors")
    @patch.object(HealthCheck, "get_api_usage_today")
    def test_never_loaded_generates_warn_alert(self, mock_usage, mock_errors, mock_keys, mock_freshness):
        mock_freshness.return_value = [
            {"source": "SAM_ENTITY", "label": "Entity Data",
             "status": "NEVER", "hours_ago": None, "threshold_hours": 48},
        ]
        mock_keys.return_value = []
        mock_errors.return_value = []
        mock_usage.return_value = []

        hc = HealthCheck()
        alerts = hc.get_alerts()

        warn_alerts = [a for a in alerts if a["level"] == "WARN"]
        assert len(warn_alerts) >= 1
        assert "never been loaded" in warn_alerts[0]["message"].lower()

    @patch.object(HealthCheck, "check_data_freshness")
    @patch.object(HealthCheck, "check_api_keys")
    @patch.object(HealthCheck, "get_recent_errors")
    @patch.object(HealthCheck, "get_api_usage_today")
    def test_unconfigured_key_generates_warn(self, mock_usage, mock_errors, mock_keys, mock_freshness):
        mock_freshness.return_value = []
        mock_keys.return_value = [
            {"key_name": "SAM API Key 1", "configured": False, "daily_limit": 10},
        ]
        mock_errors.return_value = []
        mock_usage.return_value = []

        hc = HealthCheck()
        alerts = hc.get_alerts()

        warn_alerts = [a for a in alerts if a["level"] == "WARN"]
        assert len(warn_alerts) >= 1
        assert "not configured" in warn_alerts[0]["message"].lower()

    @patch.object(HealthCheck, "check_data_freshness")
    @patch.object(HealthCheck, "check_api_keys")
    @patch.object(HealthCheck, "get_recent_errors")
    @patch.object(HealthCheck, "get_api_usage_today")
    def test_rate_limit_exhausted_generates_warn(self, mock_usage, mock_errors, mock_keys, mock_freshness):
        mock_freshness.return_value = []
        mock_keys.return_value = []
        mock_errors.return_value = []
        mock_usage.return_value = [
            {"source": "SAM", "used": 10, "limit": 10, "remaining": 0, "last_call": None},
        ]

        hc = HealthCheck()
        alerts = hc.get_alerts()

        warn_alerts = [a for a in alerts if a["level"] == "WARN"]
        assert len(warn_alerts) >= 1
        assert "exhausted" in warn_alerts[0]["message"].lower()

    @patch.object(HealthCheck, "check_data_freshness")
    @patch.object(HealthCheck, "check_api_keys")
    @patch.object(HealthCheck, "get_recent_errors")
    @patch.object(HealthCheck, "get_api_usage_today")
    def test_recent_failures_generate_error(self, mock_usage, mock_errors, mock_keys, mock_freshness):
        mock_freshness.return_value = []
        mock_keys.return_value = []
        mock_errors.return_value = [
            {"source_system": "SAM_ENTITY", "error_message": "Timeout"},
        ]
        mock_usage.return_value = []

        hc = HealthCheck()
        alerts = hc.get_alerts()

        error_alerts = [a for a in alerts if a["level"] == "ERROR"]
        assert len(error_alerts) >= 1
        assert "failure" in error_alerts[0]["message"].lower()


# ===================================================================
# check_all tests
# ===================================================================

class TestCheckAll:

    @patch.object(HealthCheck, "check_data_freshness", return_value=[])
    @patch.object(HealthCheck, "get_table_stats", return_value=[])
    @patch.object(HealthCheck, "get_api_usage_today", return_value=[])
    @patch.object(HealthCheck, "check_api_keys", return_value=[])
    @patch.object(HealthCheck, "get_recent_errors", return_value=[])
    @patch.object(HealthCheck, "get_alerts", return_value=[{"level": "OK", "message": "All good"}])
    def test_check_all_returns_all_sections(self, *mocks):
        hc = HealthCheck()
        result = hc.check_all()

        expected_keys = {
            "data_freshness", "table_stats", "api_usage",
            "api_key_status", "recent_errors", "alerts",
        }
        assert set(result.keys()) == expected_keys
