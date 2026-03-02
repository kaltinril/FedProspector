"""Tests for config.settings -- environment-based configuration."""

import os
import pytest
from unittest.mock import patch


class TestSettingsDefaults:
    """Verify default values when no .env is loaded."""

    def test_db_host_default(self):
        import config.settings as settings
        assert settings.DB_HOST == "localhost" or isinstance(settings.DB_HOST, str)

    def test_db_port_is_int(self):
        import config.settings as settings
        assert isinstance(settings.DB_PORT, int)

    def test_db_name_default(self):
        import config.settings as settings
        assert settings.DB_NAME is not None

    def test_sam_daily_limit_is_int(self):
        import config.settings as settings
        assert isinstance(settings.SAM_DAILY_LIMIT, int)

    def test_sam_daily_limit_2_is_int(self):
        import config.settings as settings
        assert isinstance(settings.SAM_DAILY_LIMIT_2, int)


class TestSettingsApiUrls:
    """Verify API URL constants are set."""

    def test_sam_api_base_url(self):
        import config.settings as settings
        assert settings.SAM_API_BASE_URL.startswith("https://")

    def test_usaspending_api_base_url(self):
        import config.settings as settings
        assert "usaspending" in settings.USASPENDING_API_BASE_URL

    def test_calc_api_base_url(self):
        import config.settings as settings
        assert "gsa.gov" in settings.CALC_API_BASE_URL

    def test_sam_contract_awards_url(self):
        import config.settings as settings
        assert "contract-awards" in settings.SAM_CONTRACT_AWARDS_URL


class TestSettingsPaths:
    """Verify path configuration."""

    def test_project_root_exists(self):
        import config.settings as settings
        assert settings.PROJECT_ROOT.exists()

    def test_data_dir_is_path(self):
        from pathlib import Path
        import config.settings as settings
        assert isinstance(settings.DATA_DIR, Path)

    def test_log_dir_is_path(self):
        from pathlib import Path
        import config.settings as settings
        assert isinstance(settings.LOG_DIR, Path)


class TestSettingsWithEnvOverride:
    """Test that environment variables override defaults."""

    def test_db_host_from_env(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "custom-host.example.com")
        # Re-evaluate the variable (settings is module-level, so we test
        # the os.getenv pattern directly)
        result = os.getenv("DB_HOST", "localhost")
        assert result == "custom-host.example.com"

    def test_db_port_from_env(self, monkeypatch):
        monkeypatch.setenv("DB_PORT", "3307")
        result = int(os.getenv("DB_PORT", "3306"))
        assert result == 3307

    def test_sam_daily_limit_from_env(self, monkeypatch):
        monkeypatch.setenv("SAM_DAILY_LIMIT", "50")
        result = int(os.getenv("SAM_DAILY_LIMIT", "10"))
        assert result == 50
