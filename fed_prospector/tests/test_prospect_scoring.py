"""Tests for ProspectManager scoring and status flow logic."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from etl.prospect_manager import ProspectManager


# ===================================================================
# Score calculation tests (mock all DB)
# ===================================================================

class TestCalculateScoreSetAside:
    """Test set-aside favorability scoring (criterion 1, 0-10 pts)."""

    @pytest.mark.parametrize("code,expected_score", [
        ("WOSB", 10),
        ("EDWOSB", 10),
        ("WOSBSS", 10),
        ("EDWOSBSS", 10),
        ("8A", 8),
        ("8AN", 8),
        ("SBA", 5),
        ("SBP", 5),
        ("HZC", 5),
        ("SDVOSBC", 5),
        ("", 0),
        (None, 0),
    ])
    def test_set_aside_scores(self, code, expected_score):
        """Verify set-aside codes map to correct scores."""
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            # Prospect + opportunity row
            deadline = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": code,
                    "naics_code": None,
                    "response_deadline": deadline,
                    "award_amount": None,
                },
                {"cnt": 0},  # NAICS match query
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["breakdown"]["set_aside"]["score"] == expected_score


class TestCalculateScoreTimeRemaining:
    """Test time remaining scoring (criterion 2, 0-10 pts)."""

    @pytest.mark.parametrize("days_ahead,expected_score", [
        (45, 10),    # > 30 days
        (25, 7),     # 15-30 days
        (10, 4),     # 7-14 days
        (3, 1),      # < 7 days
        (-5, 0),     # past deadline
    ])
    def test_time_remaining_scores(self, days_ahead, expected_score):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            deadline = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": None,
                    "naics_code": None,
                    "response_deadline": deadline,
                    "award_amount": None,
                },
                {"cnt": 0},
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["breakdown"]["time_remaining"]["score"] == expected_score

    def test_no_deadline_gets_neutral_score(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": None,
                    "naics_code": None,
                    "response_deadline": None,
                    "award_amount": None,
                },
                {"cnt": 0},
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["breakdown"]["time_remaining"]["score"] == 5


class TestCalculateScoreNaicsMatch:
    """Test NAICS match scoring (criterion 3, 0 or 10 pts)."""

    def test_naics_match_found(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            deadline = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": None,
                    "naics_code": "541511",
                    "response_deadline": deadline,
                    "award_amount": None,
                },
                {"cnt": 3},  # NAICS match found
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["breakdown"]["naics_match"]["score"] == 10

    def test_naics_no_match(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            deadline = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": None,
                    "naics_code": "999999",
                    "response_deadline": deadline,
                    "award_amount": None,
                },
                {"cnt": 0},
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["breakdown"]["naics_match"]["score"] == 0


class TestCalculateScoreAwardValue:
    """Test award value scoring (criterion 4, 0-10 pts)."""

    @pytest.mark.parametrize("amount,expected_score", [
        (1_500_000, 10),
        (1_000_000, 10),
        (750_000, 8),
        (500_000, 8),
        (250_000, 6),
        (100_000, 6),
        (75_000, 4),
        (50_000, 4),
        (25_000, 2),
        (None, 3),  # unknown gets neutral-low
    ])
    def test_award_value_scores(self, amount, expected_score):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            deadline = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": None,
                    "naics_code": None,
                    "response_deadline": deadline,
                    "award_amount": amount,
                },
                {"cnt": 0},
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["breakdown"]["award_value"]["score"] == expected_score


class TestCalculateScoreTotal:
    """Test total score computation and percentage."""

    def test_max_score_is_40(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            deadline = (datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
            mock_cursor.fetchone.side_effect = [
                {
                    "prospect_id": 1,
                    "notice_id": "N1",
                    "estimated_value": None,
                    "set_aside_code": "WOSB",
                    "naics_code": "541511",
                    "response_deadline": deadline,
                    "award_amount": 2_000_000,
                },
                {"cnt": 5},  # NAICS match
            ]
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            result = pm.calculate_score(1)

        assert result["max_score"] == 40
        assert result["total_score"] == 40
        assert result["percentage"] == 100.0

    def test_prospect_not_found_raises(self):
        with patch("etl.prospect_manager.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None
            mock_gc.return_value = mock_conn

            pm = ProspectManager()
            with pytest.raises(ValueError, match="not found"):
                pm.calculate_score(999)
