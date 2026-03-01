"""Environment-based configuration. Never hardcode secrets."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "fed_contracts")
DB_USER = os.getenv("DB_USER", "fed_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# SAM.gov API
SAM_API_KEY = os.getenv("SAM_API_KEY", "")
SAM_API_KEY_2 = os.getenv("SAM_API_KEY_2", "")
SAM_API_BASE_URL = "https://api.sam.gov"
SAM_DAILY_LIMIT = int(os.getenv("SAM_DAILY_LIMIT", "10"))
SAM_DAILY_LIMIT_2 = int(os.getenv("SAM_DAILY_LIMIT_2", "1000"))

# SAM.gov Federal Hierarchy API
SAM_FED_HIERARCHY_URL = "https://api.sam.gov/prod/federalorganizations/v1/orgs"

# SAM.gov Exclusions API
SAM_EXCLUSIONS_URL = "https://api.sam.gov/entity-information/v4/exclusions"

# GSA CALC API (no auth needed)
CALC_API_BASE_URL = "https://api.gsa.gov/acquisition/calc/v3/api"

# USASpending API (no auth needed)
USASPENDING_API_BASE_URL = "https://api.usaspending.gov"

# SAM.gov Contract Awards API (replacement for FPDS)
SAM_CONTRACT_AWARDS_URL = "https://api.sam.gov/contract-awards/v1/search"

# SAM.gov Subaward Reporting API
SAM_SUBAWARD_URL = "https://api.sam.gov/prod/contract/v1/subcontracts/search"

# FPDS ATOM Feed - DEPRECATED: ezSearch decommissioned Feb 24, 2026;
# ATOM feed sunsetting later FY2026. Use SAM_CONTRACT_AWARDS_URL instead.
FPDS_ATOM_BASE_URL = "https://www.fpds.gov/dbsight/FEEDS/ATOM"

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DOWNLOAD_DIR = DATA_DIR / "downloads"
LOG_DIR = DATA_DIR / "logs"

# Reference data paths (relative to project root's parent = pbdc/)
PBDC_ROOT = PROJECT_ROOT.parent
WORKDIR = PBDC_ROOT / "workdir" / "converted"
REF_DATA_DIR = WORKDIR / "local database" / "data_to_import"
OLD_RESOURCES = PBDC_ROOT / "OLD_RESOURCES"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
