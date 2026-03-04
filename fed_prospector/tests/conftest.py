"""Shared pytest fixtures for fed_prospector tests.

Provides mock database connections, API keys, and sample response data
so that unit tests never touch a real database or make live API calls.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure fed_prospector package is importable
# ---------------------------------------------------------------------------
FED_PROSPECTOR_DIR = Path(__file__).resolve().parent.parent
if str(FED_PROSPECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(FED_PROSPECTOR_DIR))


# ---------------------------------------------------------------------------
# Fixtures directory for sample JSON responses
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the absolute path to the fixtures directory."""
    return FIXTURES_DIR


def load_fixture(name):
    """Load a JSON fixture file by name (without extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Mock settings module so nothing reads real .env
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Provide deterministic settings values for all tests.

    This avoids reading .env or connecting to a real database.
    """
    import config.settings as settings_module

    monkeypatch.setattr(settings_module, "SAM_API_KEY", "test-api-key-1")
    monkeypatch.setattr(settings_module, "SAM_API_KEY_2", "test-api-key-2")
    monkeypatch.setattr(settings_module, "SAM_API_BASE_URL", "https://api.sam.gov")
    monkeypatch.setattr(settings_module, "SAM_DAILY_LIMIT", 10)
    monkeypatch.setattr(settings_module, "SAM_DAILY_LIMIT_2", 1000)
    monkeypatch.setattr(settings_module, "USASPENDING_API_BASE_URL", "https://api.usaspending.gov")
    monkeypatch.setattr(settings_module, "CALC_API_BASE_URL", "https://api.gsa.gov/acquisition/calc/v3/api")


# ---------------------------------------------------------------------------
# Mock database connection (used by BaseAPIClient rate limiting)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_db_connection():
    """Patch get_connection at every import site so no real DB calls happen.

    Modules that do ``from db.connection import get_connection`` create a local
    binding that is *not* affected by patching ``db.connection.get_connection``.
    We therefore patch each local binding explicitly.

    The mock cursor returns no rows by default (rate limit not reached).
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None  # 0 requests made today
    mock_cursor.fetchall.return_value = []  # no DB rules loaded
    mock_conn.cursor.return_value = mock_cursor

    mock_get_conn = MagicMock(return_value=mock_conn)

    with patch("db.connection.get_connection", mock_get_conn), \
         patch("api_clients.base_client.get_connection", mock_get_conn), \
         patch("etl.data_cleaner.get_connection", mock_get_conn), \
         patch("etl.staging_mixin.get_connection", mock_get_conn), \
         patch("etl.etl_utils.get_connection", mock_get_conn), \
         patch("etl.calc_loader.get_connection", mock_get_conn), \
         patch("etl.fedhier_loader.get_connection", mock_get_conn), \
         patch("etl.exclusions_loader.get_connection", mock_get_conn), \
         patch("etl.subaward_loader.get_connection", mock_get_conn), \
         patch("etl.load_manager.get_connection", mock_get_conn), \
         patch("etl.db_maintenance.get_connection", mock_get_conn):
        yield mock_get_conn


# ---------------------------------------------------------------------------
# Mock HTTP session for BaseAPIClient
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_session():
    """Return a MagicMock that replaces requests.Session."""
    return MagicMock()


def make_mock_response(status_code=200, json_data=None, content=b"", text=""):
    """Create a mock requests.Response with the given attributes."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.content = content
    response.text = text or json.dumps(json_data or {})
    return response


# ---------------------------------------------------------------------------
# Convenience fixtures for loader tests
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_change_detector():
    """Return a MagicMock configured as a ChangeDetector."""
    cd = MagicMock()
    cd.get_existing_hashes.return_value = {}
    cd.compute_hash.return_value = "abc123hash"
    cd.compute_field_diff.return_value = []
    return cd


@pytest.fixture
def mock_load_manager():
    """Return a MagicMock configured as a LoadManager."""
    lm = MagicMock()
    lm.start_load.return_value = 1
    return lm
